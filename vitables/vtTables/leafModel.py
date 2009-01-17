#!/usr/bin/env python
# -*- coding: utf-8 -*-


########################################################################
#
#       Copyright (C) 2008 Vicent Mas. All rights reserved
#
#       This program is free software: you can redistribute it and/or modify
#       it under the terms of the GNU General Public License as published by
#       the Free Software Foundation, either version 3 of the License, or
#       (at your option) any later version.
#
#       This program is distributed in the hope that it will be useful,
#       but WITHOUT ANY WARRANTY; without even the implied warranty of
#       MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#       GNU General Public License for more details.
#
#       You should have received a copy of the GNU General Public License
#       along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
#       Author:  Vicent Mas - vmas@vitables.org
#
#       $Source$
#       $Id: leafModel.py 1083 2008-11-04 16:41:02Z vmas $
#
########################################################################

"""
Here is defined the LeafModel class.

Classes:

* LeafModel(QAbstractItemModel)

Methods:


Functions:

Misc variables:

* __docformat__

"""

__docformat__ = 'restructuredtext'

import tempfile
import os
import sets
import exceptions
import time

import tables

from PyQt4.QtCore import *
from PyQt4.QtGui import *

import vitables.utils

class LeafModel(QAbstractTableModel):
    """
    The model for real data contained in leaves.

    The data is read from data sources (i.e., HDF5/PyTables nodes) by
    the model.
    """

    def __init__(self, rbuffer, parent=None):
        """Create the model.

        :Parameters:

            - `rbuffer`: a buffer used for optimizing read access to data
            - `parent`: the parent of the model
        """

        QAbstractTableModel.__init__(self, parent)

        # The model data source (a PyTables/HDF5 leaf) and its access buffer
        self.data_source = rbuffer.data_source
        self.rbuffer = rbuffer

        # The number of digits of the last row
        self.last_row_width = len(unicode(self.rbuffer.leaf_numrows))

        #
        # The table dimensions
        #

        # The dataset number of rows is potentially huge but tables are
        # kept small: just the data returned by a read operation of the
        # buffer are displayed
        self.numrows = self.rbuffer.leafNumberOfRows()
        if self.numrows > self.rbuffer.chunk_size:
            self.numrows = self.rbuffer.chunk_size

        # The dataset number of columns doesn't use to be large so, we don't
        # need set a maximum as we did with rows. The whole set of columns
        # are displayed
        if isinstance(self.data_source, tables.Table):
            # Leaf is a PyTables table
            self.numcols = len(self.data_source.colnames)
        else:
            # Leaf is some kind of PyTables array
            shape = self.data_source.shape
            if len(shape) > 1:
                # The leaf will be displayed as a bidimensional matrix
                self.numcols = shape[1]
            else:
                # The leaf will be displayed as a column vector
                self.numcols = 1

        #
        # Choose a format for cells. The support for dates includes the
        # scikits.timeseries module
        #

        self.formatContent = vitables.utils.formatArrayContent
        self.time_cols = []
        if self.data_source._v_attrs.CLASS == 'TimeSeriesTable':
            # Leaf is a TimeSeriesTable table
            self.time_cols.append(self.data_source.coldescrs['_dates']._v_pos)
        elif isinstance(self.data_source, tables.Table):
            # Leaf is a regular Table
            for cpathname in self.data_source.colpathnames:
                if self.data_source.coltypes[cpathname] in ['time32', 'time64']:
                    position = self.data_source.coldescrs[cpathname]._v_pos
                    self.time_cols.append(position)
        else:
            # Leaf is some kind of PyTables array
            atom_type = self.data_source.atom.type
            if atom_type in ['time32', 'time64']:
                self.formatContent = vitables.utils.formatTimeContent
            if atom_type == 'object':
                self.formatContent = vitables.utils.formatObjectContent
            elif atom_type in ('vlstring', 'vlunicode'):
                self.formatContent = vitables.utils.formatStringContent

        # Populate the model with the first chunk of data
        self.loadData(self.rbuffer.start, self.rbuffer.chunk_size)

    def __tr(self, source, comment=None):
        """Translate method."""
        return unicode(qApp.translate('LeafModel', source, 
                                            comment).toUtf8(), 'utf_8')

    def headerData(self, section, orientation, role):
        """Returns the data for the given role and section in the header
        with the specified orientation.
        """

        # The section alignment
        if role == Qt.TextAlignmentRole:
            if orientation == Qt.Horizontal:
                return QVariant(\
                    int(Qt.AlignLeft|Qt.AlignVCenter))
            return QVariant(\
                int(Qt.AlignRight|Qt.AlignVCenter))
        if role != Qt.DisplayRole:
            return QVariant()
        # The section label for horizontal header
        if orientation == Qt.Horizontal:
            # For tables horizontal labels are column names, for arrays
            # the section numbers are used as horizontal labels
            if hasattr(self.data_source, 'description'):
                return QVariant(self.data_source.colnames[section])
            return QVariant(unicode(section + 1))
        # The section label for vertical header
        return QVariant(unicode(self.rbuffer.start + section + 1))

    def data(self, index, role=Qt.DisplayRole):
        """Returns the data stored under the given role for the item
        referred to by the index.

        :Parameters:

        - `index`: the index of a data item
        - `role`: the role being returned
        """

        if not index.isValid() or \
            not (0 <= index.row() < self.numrows):
            return QVariant()
        cell = self.rbuffer.getCell(self.rbuffer.start + index.row(), index.column())
        if role == Qt.DisplayRole:
            if index.column() in self.time_cols:
                return QVariant(time.ctime(cell))
            return QVariant(self.formatContent(cell))
        elif role == Qt.TextAlignmentRole:
            return QVariant(int(Qt.AlignLeft|Qt.AlignTop))
        else:
            return QVariant()

    def columnCount(self, index=QModelIndex()):
        """The number of columns of the table.

        :Parameter index: the index of the node being inspected.
        """
        return self.numcols

    def rowCount(self, index=QModelIndex()):
        """The number of rows of the table.

        :Parameter index: the index of the node being inspected.
        """
        return self.numrows

    def loadData(self, start, chunk_size):
        """Load the model with fresh data from the buffer.

        :Parameters:

            - `start`: the row where the buffer starts
            - `chunk_size`: the size of the buffer
        """

        self.rbuffer.readBuffer(start, chunk_size)
        self.emit(SIGNAL("headerDataChanged(int, int, int)"), 
                    Qt.Vertical, 0, self.numrows - 1)

