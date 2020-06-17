from PyQt5 import QtWidgets
from PyQt5 import QtCore
from PyQt5 import QtGui
from popplerqt5 import Poppler

from utils import debug

class CustomScrollArea(QtWidgets.QScrollArea):
    # rendered = QtCore.pyqtSignal(int, QtGui.QImage)
    # textFound = QtCore.pyqtSignal(int, list)

    resizeRequested = QtCore.pyqtSignal(int, int)

    def __init__(self, parent):
        super(CustomScrollArea, self).__init__(parent)
        
        # emit the resize event slowly
        self.resize_event_queue = []
        self.resize_timer = QtCore.QTimer(self)
        self.resize_timer.timeout.connect(self.resizeTrigger)
        self.resize_timer.start(200)

    def resizeTrigger(self):
        if len(self.resize_event_queue) > 0:
            self.resizeRequested.emit(self.width(), self.height())
            self.resize_event_queue = []

    def resizeEvent(self, ev):
        # debug("resizeEvent in DocScrollArea")
        # print(self.width(), self.height())
        self.resize_event_queue.append(1) # save first
        QtWidgets.QScrollArea.resizeEvent(self, ev) # call parent's event handler
        
