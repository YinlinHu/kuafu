 
from PyQt5 import QtCore
from PyQt5 import QtGui
from PyQt5 import QtWidgets

from utils import debug

class PageNoLineEdit(QtWidgets.QLineEdit):
    gotoPageTrigger = QtCore.pyqtSignal(int)

    def __init__(self, parent):
        super(PageNoLineEdit, self).__init__(parent)
        self.parent = parent

        self.setAlignment(QtCore.Qt.AlignCenter)
        self.setMaxLength(0)
        self.validator = QtGui.QIntValidator(0, 0, self)
        self.setValidator(self.validator)
        # 
        self.page_counts = 0
        # 
        self.returnPressed.connect(self.onReturnPressed)

    def setPageInfo(self, page_no, page_counts):
        self.validator.setRange(1, page_counts)
        maxDigitLen = len(str(page_counts))
        self.setMaxLength(maxDigitLen)
        self.setText("%d" % page_no)
        self.page_counts = page_counts

    def onReturnPressed(self):
        page_no = int(self.text())
        page_no = min(page_no, self.page_counts)
        self.gotoPageTrigger.emit(page_no - 1)

    def mousePressEvent(self, event):
        self.selectAll()
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