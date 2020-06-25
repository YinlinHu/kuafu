from PyQt5 import QtWidgets
from PyQt5 import QtCore
from PyQt5 import QtGui

from basedocgraphicsview import BaseDocGraphicsView

class DocGraphicsView(BaseDocGraphicsView):
    def __init__(self, parent, render_num=4):
        super(DocGraphicsView, self).__init__(parent)

        self.scene.setBackgroundBrush(QtGui.QBrush(QtCore.Qt.white)) # set background

    def wheelEvent(self, ev):
        # debug("wheelEvent in BaseDocGraphicsView")
        modifiers = QtWidgets.QApplication.keyboardModifiers()
        if modifiers == QtCore.Qt.ControlModifier:
            delta = ev.angleDelta()
            if delta.y() > 0:
                self.zoomIn()
            else:
                self.zoomOut()
            ev.accept() # accept an event in order to stop it from propagating further
        else:
            return super().wheelEvent(ev) # call parent's handler, making the view scrolled (touch included)

    def mouseDoubleClickEvent(self, ev):
        # debug('mouseDoubleClickEvent in BaseDocGraphicsView')
        if self.current_zoom_index == 6 and self.fitwidth_flag == False:
            self.zoomFitWidth()
        else:
            # Zoom to 100%
            self.current_zoom_index = 6 # magic number, TODO
            assert(self.zoom_levels[self.current_zoom_index] == 1.0)
            self.fitwidth_flag = False
            self.redrawPages()
            self.zoomRatioChanged.emit(self.zoom_levels[self.current_zoom_index])
        return super().mouseDoubleClickEvent(ev)

