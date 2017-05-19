# -*- coding: utf-8 -*-
"""
/***************************************************************************
 EditData
                                 A QGIS plugin
 plugin to edit CLEERIO data
                              -------------------
        begin                : 2017-03-23
        git sha              : $Format:%H$
        copyright            : (C) 2017 by betka
        email                : alzbeta.gardonova@cleerio.com
 ***************************************************************************/

/***************************************************************************
 *                                                                         *
 *   This program is free software; you can redistribute it and/or modify  *
 *   it under the terms of the GNU General Public License as published by  *
 *   the Free Software Foundation; either version 2 of the License, or     *
 *   (at your option) any later version.                                   *
 *                                                                         *
 ***************************************************************************/
"""
from PyQt4.QtCore import *
from PyQt4.QtCore import pyqtSlot
from qgis.core import *
from PyQt4.QtCore import QSettings, QTranslator, qVersion, QCoreApplication
from PyQt4.QtGui import QAction, QIcon,QMessageBox
# Initialize Qt resources from file resources.py
import resources
# Import the code for the dialog
from edit_data_dialog import EditDataDialog
import os.path
import ConfigParser
import sqlite3
import requests
import json
import re
import collections


class EditData:
    """QGIS Plugin Implementation."""

    def __init__(self, iface):
        """Constructor.

        :param iface: An interface instance that will be passed to this class
            which provides the hook by which you can manipulate the QGIS
            application at run time.
        :type iface: QgsInterface
        """
	self.conf = {}
	self.layer = None
        #filled with values: id of row in layer, layer_object, layer_object_name, user_name, read, add, edit, delete
	self.layer_def = None

        # Save reference to the QGIS interface
        self.iface = iface
        # initialize plugin directory
        self.plugin_dir = os.path.dirname(__file__)
        # initialize locale
        locale = QSettings().value('locale/userLocale')[0:2]
        locale_path = os.path.join(
            self.plugin_dir,
            'i18n',
            'EditData_{}.qm'.format(locale))

        if os.path.exists(locale_path):
            self.translator = QTranslator()
            self.translator.load(locale_path)

            if qVersion() > '4.3.3':
                QCoreApplication.installTranslator(self.translator)


        # Declare instance attributes
        self.actions = []
        self.menu = self.tr(u'&EditData')
        # TODO: We are going to let the user set this up in a future iteration
        self.toolbar = self.iface.addToolBar(u'EditData')
        self.toolbar.setObjectName(u'EditData')

    # noinspection PyMethodMayBeStatic
    def tr(self, message):
        """Get the translation for a string using Qt translation API.

        We implement this ourselves since we do not inherit QObject.

        :param message: String for translation.
        :type message: str, QString

        :returns: Translated version of message.
        :rtype: QString
        """
        # noinspection PyTypeChecker,PyArgumentList,PyCallByClass
        return QCoreApplication.translate('EditData', message)


    def add_action(
        self,
        icon_path,
        text,
        callback,
        enabled_flag=True,
        add_to_menu=True,
        add_to_toolbar=True,
        status_tip=None,
        whats_this=None,
        parent=None):
        """Add a toolbar icon to the toolbar.

        :param icon_path: Path to the icon for this action. Can be a resource
            path (e.g. ':/plugins/foo/bar.png') or a normal file system path.
        :type icon_path: str

        :param text: Text that should be shown in menu items for this action.
        :type text: str

        :param callback: Function to be called when the action is triggered.
        :type callback: function

        :param enabled_flag: A flag indicating if the action should be enabled
            by default. Defaults to True.
        :type enabled_flag: bool

        :param add_to_menu: Flag indicating whether the action should also
            be added to the menu. Defaults to True.
        :type add_to_menu: bool

        :param add_to_toolbar: Flag indicating whether the action should also
            be added to the toolbar. Defaults to True.
        :type add_to_toolbar: bool

        :param status_tip: Optional text to show in a popup when mouse pointer
            hovers over the action.
        :type status_tip: str

        :param parent: Parent widget for the new action. Defaults None.
        :type parent: QWidget

        :param whats_this: Optional text to show in the status bar when the
            mouse pointer hovers over the action.

        :returns: The action that was created. Note that the action is also
            added to self.actions list.
        :rtype: QAction
        """

        # Create the dialog (after translation) and keep reference
        self.dlg = EditDataDialog()

	# When layer was selected and button to start edit was clicked
      	self.dlg.start_editting.clicked.connect(lambda: self.prepare_editing())

        icon = QIcon(icon_path)
        action = QAction(icon, text, parent)
        action.triggered.connect(callback)
        action.setEnabled(enabled_flag)

        if status_tip is not None:
            action.setStatusTip(status_tip)

        if whats_this is not None:
            action.setWhatsThis(whats_this)

        if add_to_toolbar:
            self.toolbar.addAction(action)

        if add_to_menu:
            self.iface.addPluginToMenu(
                self.menu,
                action)

        self.actions.append(action)

        return action

    def initGui(self):
        """Create the menu entries and toolbar icons inside the QGIS GUI."""

        icon_path = ':/plugins/EditData/icon.png'
        self.add_action(
            icon_path,
            text=self.tr(u'Edit data'),
            callback=self.run,
            parent=self.iface.mainWindow())


    def unload(self):
        """Removes the plugin menu item and icon from QGIS GUI."""
        for action in self.actions:
            self.iface.removePluginMenu(
                self.tr(u'&EditData'),
                action)
            self.iface.removeToolBarIcon(action)
        # remove the toolbar
        del self.toolbar


    def run(self):
        """Run method that performs all the real work"""
        
        self.dlg.show()
	self.set_layers()

        # Run the dialog event loop
        result = self.dlg.exec_()

        # See if OK was pressed
        if result:
            self.upload_changes()
            self.layer.commitChanges()
	    pass

    def set_layers(self):
	"""iterate layers from TOC and populate combobox
        """
	layers = []
        for layer in self.iface.mapCanvas().layers():
	    layers.append(layer.name())
                     
        self.dlg.layer.clear()
	self.dlg.layer.addItems(layers)  

    def prepare_editing(self):
	"""set layer to edit mode and run chcecking functions
           checking:public user - cannot edit, read only - cannot make changes
	   when all is OK clean meta tables and,get config and start edit
	"""
	
    	self.layer = QgsMapLayerRegistry.instance().mapLayersByName(self.dlg.layer.currentText())[0]
        self.iface.setActiveLayer(self.layer)
        self.check_layer()

        if self.layer_def != None:	    
            rights = {} 
            rights['read'] = self.layer_def[4]
            rights['add'] = self.layer_def[5]
            rights['edit'] = self.layer_def[6]
	    rights['delete'] = self.layer_def[7]
            
            able = []
            disable = []
            for key,val in rights.items():
                if val == 1:  
		    able.append(key)
		else:
		    disable.append(key)
	 
            text = ''
            if self.layer_def[3] == '':
		text = 'data jsi stáhnul bez zadaného uživatele, nemáš právo editovat'.decode('utf-8')
	    else:
                if len(able) ==1 and 'read' in able:
                    text = ('data jsi stáhnul jako uživatel:{} a můžeš jen číst'.format(self.layer_def[3])).decode('utf-8')
	        else:
		    self.clean_revisions()
		    self.layer.startEditing()
  		    self.getConfig()
                    self.layer.beforeCommitChanges.connect(lambda: self.check_changes())

                    text = ('začni editovat, můžeš: ' + ', '.join(right for right in able)).decode('utf-8')
   
	    msgBox = QMessageBox()
	    msgBox.setText(text)
	    msgBox.setIcon(QMessageBox.Question)
	    msgBox.exec_()
 
    def getConfig(self):
	"""
	   read definition for sending changes from file (stored during download)
	   store gp_id, user, domain, password to self.conf()
	"""
	cfg_file = os.path.join(QgsApplication.qgisSettingsDirPath(),'cleerio.config')
 	config = ConfigParser.RawConfigParser()
      	config.read(cfg_file)  
        gp_id = os.path.splitext((os.path.basename(self.layer.source().split('|')[0]
)))[0]
	self.conf['gp_id'] = gp_id
        self.conf['user'] = config.get(gp_id, 'user')
	self.conf['domain'] = config.get(gp_id, 'domain')
	self.conf['password'] = config.get(gp_id, 'password')
	 
    def clean_revisions(self):
        """
	   delete all revisions and changes
           TODO: make them only invalid, not delete them
	"""
	source = self.layer.source()
	con = sqlite3.connect(source.split('|')[0])
    	cursor = con.cursor()
    	del_rev = "DELETE FROM meta_revisions"
        del_changes = "DELETE FROM meta_changes"
    	cursor.execute(del_rev)
        cursor.execute(del_changes)
	con.commit()	  
     
    def check_layer(self):
	"""check layer if it is sqlitedb, has defined structure,
           if is ok, all layer definition is stored 
	"""
         
        if self.layer.storageType() =='SQLite':
	    source = self.layer.source()
            con = sqlite3.connect(source.split('|')[0])
 	    cursor = con.cursor()

            sql = """SELECT * FROM meta_user WHERE layer_object_name = '{}'
		     ORDER BY id desc LIMIT 1
                  """.format(self.layer.name().encode('utf-8'))
            try:
                cursor.execute(sql)
                ### store layer definition
	        self.layer_def = cursor.fetchone()
                
	    except Exception as e:
		text_msg = """Nejedná se o vrsvtu z MA Cleerio/je špatně stažená""".decode("utf-8")
                msgBox = QMessageBox()
                msgBox.setText(text_msg)
                msgBox.setIcon(QMessageBox.Question)
                msgBox.exec_()

        else:
	    text_msg = """Nejedná se o vrsvtu z MA Cleerio, vyberte vrstvu \n
                          staženou pomocí pluginu X""".decode("utf-8")
            msgBox = QMessageBox()
            msgBox.setText(text_msg)
            msgBox.setIcon(QMessageBox.Question)
            msgBox.exec_()

    def check_changes(self):
	"""
	   store ids of changed features into meta_tables
	""" 
	changed_att = self.layer.editBuffer().changedAttributeValues()
        added_f = self.layer.editBuffer().addedFeatures()
	deleted = self.layer.editBuffer().deletedFeatureIds()
	changed_geom = self.layer.editBuffer().changedGeometries()
	
	#changed consist of changed attributes and also geometries
        changed = changed_att.keys()
        changed.extend(changed_geom.keys())
        
        changes = {}
        if len(changed) > 0:
	    changes['update-object'] = changed
        if len(added_f.keys()) > 0:
	    changes['insert-object'] = added_f.keys()
	if len(deleted) > 0:
	    changes['delete-object'] = deleted 

	self.write_changes_info(changes)

    def write_changes_info(self, changes):
	"""
	   create new revision and write all changes definition into meta tables
	"""
        source = self.layer.source()
        con = sqlite3.connect(source.split('|')[0])
 	cursor = con.cursor()
    
        new_revision_insert = """INSERT INTO meta_revisions 
			(layer_object, revision_date, status,fid_max) 
 			 VALUES('{}', datetime('now'),'new',(SELECT max(OGC_FID) from  {}))
                        """.format(self.layer_def[1],re.sub('layername=','',source.split('|')[1]))
        
        cursor.execute(new_revision_insert)
        con.commit() 
        new_rev_id = ("SELECT max(id) FROM meta_revisions")
        cursor.execute(new_rev_id)
        rev_id = cursor.fetchone()[0]

        for key,val in changes.items():
            for feature in val:
	        insert = """INSERT INTO meta_changes (rev_id, feature_id, operation)
                        VALUES({},{},'{}')""".format(rev_id, feature, key)
		cursor.execute(insert)
                con.commit()

    def upload_changes(self):
	"""
	   try to upload changes after changes wehe saved
           make session as login
	"""
	global SESSION

        source = self.layer.source()
        con = sqlite3.connect(source.split('|')[0])
    	cursor = con.cursor()

        SESSION = requests.session() 
        self.try_user_login()
	
	self.prepare_changed(cursor, 'update-object')
	self.prepare_added(cursor)        
	self.prepare_changed(cursor, 'delete-object')       

        self.layer.beforeCommitChanges.disconnect()	

    def try_user_login(self):
        """
	   login into session by stored user
	"""
        login = 'https://api.cleerio.' + self.conf['domain'] + '/gp2/sign-in/' + self.conf['gp_id']
        login_data = {"username": self.conf['user'],"password": self.conf['password']}

        log_in = SESSION.post(login, data=json.dumps(login_data))
        response = byteify(json.loads(log_in.text, encoding="utf-8"))
	    
        try:
       	    login_status = response['result']
    	except Exception as e:
            exc = Exception
            return exc

    def prepare_changed(self, cursor, edit_type): 
	
	      	  
        sql = """SELECT feature_id FROM meta_changes changes join meta_revisions rev on changes.rev_id =rev.id  WHERE operation = '{}' and layer_object = '{}'""".format(edit_type, self.layer_def[1])
	    
	cursor.execute(sql)
	chan = cursor.fetchall()

        to_change = [long(i[0]) for i in chan]
	print (sql,chan)
 	request = QgsFeatureRequest()
   	request.setFilterFids(to_change)
	        
        if len(to_change)>0:
	    features = self.layer.getFeatures(request)
	    if edit_type == 'delete-object':
		source = self.layer.source()
        	origin_tab = (source.split('|')[1]).replace("_revid","").replace("layername=","")
		vals = ','.join(str(val) for val in to_change)
                
	 	sql2 = """SELECT id from {} where OGC_FID in({})""".format(origin_tab, vals)    
		cursor.execute(sql2)
	        chan = cursor.fetchall()
                feature_ids = []
                for i in chan:
 		    feature_ids.append(i[0])
		self.send_changes(feature_ids, edit_type, cursor)
	    elif edit_type == 'update-object':
		self.send_changes(features, edit_type, cursor)


    def prepare_added(self, cursor):   
	added = """SELECT min(fid_max) FROM meta_revisions WHERE layer_object = '{}'""".format(self.layer_def[1])
        cursor.execute(added)
	max_fid = cursor.fetchone()[0]        

	exp = QgsExpression('OGC_FID > {}'.format(max_fid))
        added_fids = []
	for f in self.layer.getFeatures():
            val = exp.evaluate(f)
 	    if val == 1:
		added_fids.append(f.id())  
        if len(added_fids) > 0:
 	    request = QgsFeatureRequest()
   	    request.setFilterFids(added_fids)
	    features = self.layer.getFeatures(request)

	    self.send_changes(features,'insert-object', cursor)
           	

    def send_changes(self, features, edit_type, cursor):
	"""detect type of change and prepare parameters for POST
        """

	def all_features_def():
	    """prepare part of parameters which are the same for all features
	    """
	    params['feature'] = {}
	    params['feature']['type'] = "Feature"
            params['feature']['geometry'] = {}
           
            if self.layer.geometryType() in (0,1,2):
                params['feature']['geometry']['type'] = geometries[self.layer.geometryType()]
                params['feature']['geometry']['crs'] = {}
                params['feature']['geometry']['crs']['properties'] = {}
                params['feature']['geometry']['crs']['type'] = "name"
                params['feature']['geometry']['crs']['properties']['name'] = str(self.layer.crs().authid())
                params['feature']['properties'] = {}
	    elif self.layer.geometryType() == 4:
		params['feature']['geometry'] = null
            params['feature']['properties'] = {}  
 	    params['feature']['properties']['object_type_id'] = int(self.layer_def[1].split('_')[1])
            params['feature']['properties']['layers'] = [int(self.layer_def[1].split('_')[0])]
	    params['feature']['properties']['state_'] = "unfiltered"
            params['feature']['properties']['label'] = ""
     

        def define_geometry():
            """redefine geometry to needed form as parameter
	    """
	    geometry_def = []
            vert = None
	    if params['feature']['geometry']['type'] =='Point':
                vert = feature.geometry().asPoint()
                geometry_def.append(vert.x())
                geometry_def.append(vert.y())
            elif params['feature']['geometry']['type'] =='LineString':
	        vert = feature.geometry().asPolyline()
	        for i in vert:
	            geometry_def.append([i.x(),i.y()])
	    elif params['feature']['geometry']['type'] =='MultiPolygon':
	        vert = feature.geometry().asMultiPolygon()
	        for part in vert:
                    geom_part = []
                    for subpart in part:
                        if len(subpart) != 0:
		            for i in subpart:
		       	        geom_part.append([i.x(),i.y()])
		                geometry_def.append(geom_part)
            params['feature']['geometry']['coordinates'] = geometry_def


	def iterate_fields():
	    """single definition of property num and value into parameter
	       differ in case od change type in "id" definition (when add then is temporal)
	    """
            value = None
            if properties[f]["type"] in ('relation','relations','multirelation','multirelations','image','iframe','link','document'):
	        value = []
            elif feature[f] == NULL:
	        value = ""
	    elif properties[f]["type"] in ('id_list','id_alist','id_elist'):
                value = (prop_def[properties[f]["name"]][feature[f]]).encode("utf-8")
            else:
                if type(feature[f]) in (int,float):
  	            value = feature[f]
		else:
	            value = str(feature[f].encode("utf-8")) 
            params['feature']['properties'][str(properties[f]["id"])] =  value 
   	    if edit_type == 'insert-object':
	        params['feature']['properties']['id'] = 'temporal_id'
	    elif edit_type == 'update-object':
 	        params['feature']['properties']['id'] = feature['id']
       


      	geometries = {0:"Point",1:"LineString",2:"MultiPolygon",4:"Nongeometry"}
    	url = 'https://api.cleerio.' + self.conf['domain'] + '/gp2/' + edit_type + '/' + self.conf['gp_id']
        params = {}
	
	if edit_type == 'delete-object':
            params['layer_id'] = int(self.layer_def[1].split('_')[0])
            for feature in features:
                params['object_id'] = str(feature)
                print(url,params)	
                ans = SESSION.post(url, json.dumps(params))

                res = byteify(json.loads(ans.text,encoding="utf-8"))
		errors = [] 
	        if 'status' in res.keys():
	            if res["status"] == 'error':
	                errors.append(int(feature.id()))
                print ('tohle neslo ulozit: ',errors)
		
        elif edit_type in ('update-object, insert-object'):
            sql ="""select prop_name, all_values from meta_attributes where layer_object = "{}" and prop_type in ('id_list', 'id_alist', 'id_elist') """.format(self.layer_def[1])
	    cursor.execute(sql)
  	    res = cursor.fetchall()
            prop_def = {}
            for each in res:
                vals = json.loads(each[1].replace("'",'"'))
                transl = {}
                for key,val in vals.items():
		    transl[val] = key
                prop_def[each[0]] = transl   
            
            all_features_def()           
    	    properties = self.get_property_def(cursor)
        
            field_names = [str(i.name()) for i in self.layer.pendingFields()]
    	    field_names.remove('OGC_FID')
	    field_names.remove('id')

            errors = []
    	    for feature in features:                
                params['feature']['id'] = int(feature.id())
		if self.layer.geometryType() in (0,1,2):
		    define_geometry()  
       
                for f in field_names:
                    iterate_fields() 	
                
	        ans = SESSION.post(url, json.dumps(params))
                print(ans,url, params)
                res = byteify(json.loads(ans.text,encoding="utf-8"))
            
	        if 'status' in res.keys():
	            if res["status"] == 'error':
	                errors.append(int(feature.id()))
                print ('tohle neslo ulozit: ',errors)
        
	    
        
    def get_property_def(self, cursor):
	sql = """select  prop_id, prop_name, prop_type from meta_attributes where layer_object = '{}'""".format(self.layer_def[1])         
	cursor.execute(sql)
	res = cursor.fetchall()
        properties = {}
	for i in res:
  	    properties[i[1]]={}
	    properties[i[1]]["id"]=i[0]
            properties[i[1]]["name"] = i[1]
	    properties[i[1]]["type"] = str(i[2])
	return properties
        
def byteify(input):

    if isinstance(input, dict):
        return {byteify(key): byteify(value)
                for key, value in input.iteritems()}
    elif isinstance(input, list):
        return [byteify(element) for element in input]
    elif isinstance(input, unicode):
        return input.encode('utf-8')
    else:
        return input	       

