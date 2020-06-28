 
from PyQt5 import QtCore
from PyQt5 import QtGui
from PyQt5 import QtWidgets

from utils import debug

class PageNoLineEdit(QtWidgets.QLineEdit):

    def __init__(self, parent):
        super(PageNoLineEdit, self).__init__(parent)
        self.parent = parent

        self.setAlignment(QtCore.Qt.AlignCenter)
        self.setMaxLength(5)

        validator = QtGui.QIntValidator(1, 9999, self)
        self.setValidator(validator)

    def mousePressEvent(self, event):
        self.selectAll()

        # print('forwarding to the main window')
        self.parent.mousePressEvent(event)

class FindLineEdit(QtWidgets.QLineEdit):

    def __init__(self, parent):
        super(FindLineEdit, self).__init__(parent)
        self.parent = parent

        self.setAlignment(QtCore.Qt.AlignCenter)
        self.setFixedWidth(50)
        self.setMaxLength(4)

        validator = QtGui.QIntValidator(1, 9999, self)
        self.setValidator(validator)

    def mousePressEvent(self, event):
        self.selectAll()

        # print('forwarding to the main window')
        self.parent.mousePressEvent(event)