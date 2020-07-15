from PyQt5 import QtWidgets
from PyQt5 import QtCore
from PyQt5 import QtGui

from basedocgraphicsview import BaseDocGraphicsView
from page import PageGraphicsItem
from utils import debug

class DocGraphicsView(BaseDocGraphicsView):
    def __init__(self, parent, render_num=2):
        super(DocGraphicsView, self).__init__(parent, render_num)

        self.scene.setBackgroundBrush(QtGui.QBrush(QtCore.Qt.white)) # set background
        self.textSelectionMode = False

    def textUnder(self, view_x, view_y):
        hasText = False
        # find the associated page first
        scene_pos = self.mapToScene(view_x, view_y)
        item = self.itemAt(view_x, view_y)
        if item:
            item = item.parentItem() if item.parentItem() else item
            assert(isinstance(item, PageGraphicsItem))
            page_no = self.page_items.index(item)
            #
            _, x, y, w, h = self.current_pages_rect[page_no]
            scalingRatio = self.current_rendering_dpi[page_no] / 72.0
            hasText = item.textUnder((scene_pos.x() - x) / scalingRatio, (scene_pos.y() - y) / scalingRatio)
        return hasText

    def linkUnder(self, view_x, view_y):
        dest = None
        # find the associated page first
        scene_pos = self.mapToScene(view_x, view_y)
        item = self.itemAt(view_x, view_y)
        if item:
            item = item.parentItem() if item.parentItem() else item
            assert(isinstance(item, PageGraphicsItem))
            page_no = self.page_items.index(item)
            #
            _, x, y, w, h = self.current_pages_rect[page_no]
            scalingRatio = self.current_rendering_dpi[page_no] / 72.0
            dest = item.linkUnder((scene_pos.x() - x) / scalingRatio, (scene_pos.y() - y) / scalingRatio)
        return dest

    def wheelEvent(self, ev):
        # debug("wheelEvent in BaseDocGraphicsView")
        self.setFocus()
        # 
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
        if self.textUnder(ev.x(), ev.y()):
            pass
        else:
            # adaptive zooming
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

    def mousePressEvent(self, ev):
        dest = self.linkUnder(ev.x(), ev.y())
        if dest:
            # print(dest)
            self.saveCurrentView()
            self.gotoPage(dest)
        elif self.textUnder(ev.x(), ev.y()):
            self.textSelectionMode = True
        return super(DocGraphicsView, self).mousePressEvent(ev)

    def mouseReleaseEvent(self, ev):
        if self.textSelectionMode:
            self.textSelectionMode = False
        else:
            self.setCursor(QtCore.Qt.ArrowCursor)
        return super(DocGraphicsView, self).mouseReleaseEvent(ev)

    def mouseMoveEvent(self, ev):
        # 
        if self.isMousePressed and not self.textSelectionMode: # drag mode
            self.setCursor(QtCore.Qt.ClosedHandCursor)
            self.horizontalScrollBar().setValue(self.hScrollPosWhenClicked + self.clickedPos.x() - ev.globalX())
            self.verticalScrollBar().setValue(self.vScrollPosWhenClicked + self.clickedPos.y() - ev.globalY())
        else:
            link = self.linkUnder(ev.x(), ev.y())
            text = self.textUnder(ev.x(), ev.y())
            if self.textSelectionMode:
                self.setCursor(QtCore.Qt.IBeamCursor)
            else:
                if link:
                    self.setCursor(QtCore.Qt.PointingHandCursor)
                else:
                    if text:
                        self.setCursor(QtCore.Qt.IBeamCursor)
                    else:
                        self.setCursor(QtCore.Qt.ArrowCursor)
        # 
        return super(DocGraphicsView, self).mouseMoveEvent(ev)
