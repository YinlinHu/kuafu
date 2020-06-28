
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
        self.parent = parent
        self.clicked.connect(self.onClicked)
        self.view = None
        self.title_list = []

    def setView(self, view):
        self.view = view
        self.view_event_filter = viewEventFilter()
        self.view.installEventFilter(self.view_event_filter)

    def resizeEvent(self, ev):
        self.updateTitleText()
        # 
        rect = self.geometry()
        self.view.setGeometry(QtCore.QRect(0, rect.height(), self.parent.width(), 400))
        super(TocPushButton, self).resizeEvent(ev)

    def onClicked(self):
        # debug("onClicked in TocButton")
        if self.view:
            if self.view.isVisible():
                self.view.hide()
            else:
                self.view.show()
                self.view.setFocus()

    def constructTitleText(self, title_list, cutLength=10000):
        title_str = ""
        for title in title_list:
            title_str += " ⯈ "
            tmpStr = title[:cutLength]
            if len(title) > cutLength:
                tmpStr += " ..."
            title_str += tmpStr
        title_str += " "
        return title_str

    def updateTitleText(self):
        if len(self.title_list) == 0:
            return
        # https://stackoverflow.com/questions/8633433/qt-how-to-get-the-pixel-length-of-a-string-in-a-qlabel
        titleStr = self.constructTitleText(self.title_list)
        textWidth = self.fontMetrics().boundingRect(titleStr).width()
        if textWidth > self.width() - 10:
            titleStr = self.constructTitleText(self.title_list, cutLength=12)
        # 
        textWidth = self.fontMetrics().boundingRect(titleStr).width()
        if textWidth > self.width() - 10:
            self.setStyleSheet("text-align:right")
        else:
            self.setStyleSheet("text-align:left")
        self.setText(titleStr)

    def setTitleText(self, title_list):
        self.title_list = title_list
        self.updateTitleText()

    def clearTitleText(self):
        self.title_list = []
        self.setText(" ⯈ ")
        self.setStyleSheet("text-align:left")