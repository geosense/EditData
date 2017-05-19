# -*- coding: utf-8 -*-
"""
/***************************************************************************
 EditData
                                 A QGIS plugin
 plugin to edit CLEERIO data
                             -------------------
        begin                : 2017-03-23
        copyright            : (C) 2017 by betka
        email                : alzbeta.gardonova@cleerio.com
        git sha              : $Format:%H$
 ***************************************************************************/

/***************************************************************************
 *                                                                         *
 *   This program is free software; you can redistribute it and/or modify  *
 *   it under the terms of the GNU General Public License as published by  *
 *   the Free Software Foundation; either version 2 of the License, or     *
 *   (at your option) any later version.                                   *
 *                                                                         *
 ***************************************************************************/
 This script initializes the plugin, making it known to QGIS.
"""


# noinspection PyPep8Naming
def classFactory(iface):  # pylint: disable=invalid-name
    """Load EditData class from file EditData.

    :param iface: A QGIS interface instance.
    :type iface: QgsInterface
    """
    #
    from .edit_data import EditData
    return EditData(iface)
