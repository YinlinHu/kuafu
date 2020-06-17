from PyQt5 import QtWidgets
from PyQt5 import QtCore
from PyQt5 import QtGui
from popplerqt5 import Poppler

from utils import debug

class StyledItemDelegate(QtWidgets.QStyledItemDelegate):
    """
    style definition for items in tableview
    """
    def initStyleOption(self, option, index):
        super(StyledItemDelegate, self).initStyleOption(option, index)
        # option.decorationPosition = QtWidgets.QStyleOptionViewItem.Top
        # option.displayAlignment = QtCore.Qt.AlignHCenter | QtCore.Qt.AlignTop

class AnnotTableView(QtWidgets.QTableView):
    # rendered = QtCore.pyqtSignal(int, QtGui.QImage)
    # textFound = QtCore.pyqtSignal(int, list)

    resizeRequested = QtCore.pyqtSignal(int, int)

    def __init__(self, parent):
        super(AnnotTableView, self).__init__(parent)
        # self.horizontalHeader().setStretchLastSection(True)
        self.horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.Stretch)
        # self.verticalHeader().setSectionResizeMode(QtWidgets.QHeaderView.ResizeToContents)

        # header.setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeToContents)
        # header.setSectionResizeMode(2, QtWidgets.QHeaderView.ResizeToContents)

        self.horizontalHeader().hide()
        self.verticalHeader().hide()
        
        self.setItemDelegate(StyledItemDelegate(self)) # customed style

        self.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers) # make items readonly

        # self.horizontalHeader().setSizeAdjustPolicy(QtWidgets.Q)
        
    # def viewOptions(self):
    #     # https://stackoverflow.com/questions/56438540/align-pixmap-in-columns-center-with-qtreeview-and-qabstractitemmodel
    #     # align the icons of all items centerally
    #     option = super().viewOptions()
    #     option.decorationAlignment = (QtCore.Qt.AlignHCenter | QtCore.Qt.AlignCenter)
    #     option.decorationPosition = QtWidgets.QStyleOptionViewItem.Top
    #     return option

    def resizeEvent(self, ev):
        debug("resizeEvent in AnnotTableView")
        print(self.width(), self.height())
        QtWidgets.QTableView.resizeEvent(self, ev) # call parent's event handler
        self.resizeRequested.emit(self.width(), self.height())
