# -*- coding: utf-8 -*-

from PyQt5 import QtCore
from PyQt5 import QtGui
from PyQt5 import QtWidgets

import numpy as np
from utils import debug

from tocpushbutton import TocPushButton

class TocManager(QtCore.QObject):
    tocIndexChanged = QtCore.pyqtSignal(int)
    def __init__(self, tocButton):
        parent = tocButton.parentWidget()
        super(TocManager, self).__init__(tocButton)

        self.view = QtWidgets.QTreeView(parent)
        self.model = QtGui.QStandardItemModel(parent)
        self.view.setModel(self.model)
        self.view.clicked.connect(self.OnViewClicked)
        self.view.hide()

        self.tocButton = tocButton
        self.tocButton.setView(self.view)

        self.toc = None

    def setToc(self, toc):
        # remove all model items first
        self.model.removeRows(0, self.model.rowCount())

        # clear title
        self.tocButton.clearTitleText()

        self.toc = toc
        self.toc_item_parents = None
        self.toc_item_pages = None
        self.toc_model_items = None
        self.current_page_idx = -1

        # extract parent informaton for each node from toc (in format of PyMuPDF)
        tocItemCnt = len(toc)
        self.toc_item_parents = [-1] * tocItemCnt # each item has one parent
        self.toc_item_pages = []
        parent_queue = []
        for i in range(tocItemCnt):
            lvl, title, page, extra = toc[i]
            self.toc_item_pages.append(page - 1) # make page start from 0
            if i == 0:
                assert(lvl == 1)
                parent_queue.append(-1)
                continue
            # 
            lvl_prev = toc[i-1][0]
            if lvl > lvl_prev:
                assert(lvl == lvl_prev + 1)
                parent_queue.append(i-1)
            else:
                for j in range(lvl_prev - lvl):
                    parent_queue.pop(-1)
            self.toc_item_parents[i] = parent_queue[-1] # the latest one
        self.toc_item_parents = np.array(self.toc_item_parents)
        self.toc_item_pages = np.array(self.toc_item_pages)

        # construct tree structure
        rooItem = self.model.invisibleRootItem()
        self.toc_model_items = [None] * tocItemCnt
        for i in range(tocItemCnt):
            lvl, title, page, extra = toc[i] # page start from 1
            item = QtGui.QStandardItem(title)
            item.setData(page - 1, QtCore.Qt.UserRole + 1)
            # 
            pageItem = item.clone()
            if page >= 1:
                pageItem.setText(str(page))
            else:
                pageItem.setText("")
            pageItem.setTextAlignment(QtCore.Qt.AlignRight)
            pid = self.toc_item_parents[i]
            if pid == -1:
                rooItem.appendRow([item, pageItem])
            else:
                self.toc_model_items[pid].appendRow([item, pageItem])
            self.toc_model_items[i] = item

        # 
        if tocItemCnt > 0:
            self.view.setAlternatingRowColors(True)
            self.view.setHeaderHidden(True)
            self.view.header().setSectionResizeMode(0, QtWidgets.QHeaderView.Stretch)
            self.view.header().setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeToContents)
            self.view.header().setStretchLastSection(False)

    def OnViewClicked(self, mIndex):
        page_no = self.view.model().data(mIndex, QtCore.Qt.UserRole+1)
        if page_no >= 0:
            self.tocIndexChanged.emit(page_no)
            self.view.hide()

    def update(self, current_page_idx):
        if not self.toc:
            return

        if current_page_idx == self.current_page_idx:
            return

        self.current_page_idx = current_page_idx

        # get the first one larger than current_page_idx
        current_toc_idx = np.argmax(self.toc_item_pages > self.current_page_idx)
        if self.toc_item_pages[current_toc_idx] > self.current_page_idx: # found successfully
            if current_toc_idx > 0:
                current_toc_idx -= 1 # get the previous one
        else: # can not find
            current_toc_idx = len(self.toc) - 1 # get the very last one
            
        # 
        scrollTargetModelIndex = self.model.indexFromItem(self.toc_model_items[current_toc_idx])

        # 
        title_list = []
        valid_tocs = []
        while current_toc_idx >= 0:
            lvl, title, page, extra = self.toc[current_toc_idx]
            title_list.append(title)
            valid_tocs.append(current_toc_idx)
            current_toc_idx = self.toc_item_parents[current_toc_idx]
        title_list.reverse()
        self.tocButton.setTitleText(title_list)

        self.view.clearSelection()
        self.view.expand(scrollTargetModelIndex)
        self.view.scrollTo(scrollTargetModelIndex, QtWidgets.QAbstractItemView.ScrollHint.PositionAtCenter)
        self.view.selectionModel().setCurrentIndex(scrollTargetModelIndex, QtCore.QItemSelectionModel.Select)