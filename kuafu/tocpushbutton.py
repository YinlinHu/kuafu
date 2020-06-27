
from PyQt5 import QtCore
from PyQt5 import QtGui
from PyQt5 import QtWidgets

import numpy as np
from utils import debug

class viewEventFilter(QtCore.QObject):
    def eventFilter(self, widget, event):
        # FocusOut event
        if event.type() == QtCore.QEvent.FocusOut:
            # do custom stuff
            # print('focus out')
            widget.hide()
            # return False so that the widget will also handle the event
            # otherwise it won't focus out
            return False
        else:
            # we don't care about other events
            return False

class TocPushButton(QtWidgets.QPushButton):
    def __init__(self, parent):
        super(TocPushButton, self).__init__(parent)
        self.setFlat(True)
        self.setStyleSheet("Text-align:left")
        self.clicked.connect(self.onClicked)
        self.view = None

    def setView(self, view):
        self.view = view
        self.view_event_filter = viewEventFilter()
        self.view.installEventFilter(self.view_event_filter)

    def resizeEvent(self, ev):
        rect = self.geometry()
        self.view.setGeometry(QtCore.QRect(0, rect.height(), rect.width(), 400))
        super(TocPushButton, self).resizeEvent(ev)

    def onClicked(self):
        # debug("onClicked in TocButton")
        if self.view:
            if self.view.isVisible():
                self.view.hide()
            else:
                self.view.show()
                self.view.setFocus()