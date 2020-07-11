from PyQt5 import QtWidgets
from PyQt5 import QtCore
from PyQt5 import QtGui

from basedocgraphicsview import BaseDocGraphicsView
from utils import debug

class ThumbGraphicsView(BaseDocGraphicsView):
    pageRelocationRequest = QtCore.pyqtSignal(int, float, float)
    zoomRequest = QtCore.pyqtSignal(bool, int, float, float)

    def __init__(self, parent, render_num=2):
        super(ThumbGraphicsView, self).__init__(parent, render_num)

        self.scene.setBackgroundBrush(QtGui.QBrush(QtCore.Qt.white)) # set background

    def initializePage(self, page_no):
        super(ThumbGraphicsView, self).initializePage(page_no) # call parent's implementation
        # add some more
        tipStr = ("Page %d" % (page_no+1))
        self.page_items[page_no].setToolTip(tipStr)

    def highlightVisibleMasks(self, filename, visible_regions):
        # the items in visible_regions are in normalized coordinates
        # 
        if filename != self.current_filename:
            return
        if self.page_counts == 0:
            return
        # 
        # remove current highlighted first
        for pg_no in self.current_highlighted_pages:
            if self.page_items[pg_no]:
                self.page_items[pg_no].setMask(0, 0, 0, 0)
        self.current_highlighted_pages = []
        # remove border of the page that is marked as the current
        if self.page_items[self.pageMarkedAsCurrent]:
            self.page_items[self.pageMarkedAsCurrent].setBorderHighlight(False)

        currentPageIdx = next(iter(visible_regions)) # first key as the current
        for pg_no in visible_regions:
            vRect = visible_regions[pg_no]
            self.initializePage(pg_no)
            if pg_no == currentPageIdx:
                self.page_items[pg_no].setBorderHighlight(True)
                self.pageMarkedAsCurrent = pg_no
            self.page_items[pg_no].setMask(vRect[0], vRect[1], vRect[2], vRect[3])
            if not self.isMouseOver:
                # self.centerOn(self.page_items[pg_no])
                self.ensureVisible(self.page_items[pg_no])
            # 
            self.current_highlighted_pages.append(pg_no)

    def mousePressEvent(self, ev):
        # debug('mousePressEvent in ThumbGraphicsView')
        if self.page_counts == 0:
            return
        self.setCursor(QtCore.Qt.ClosedHandCursor)
        page_no, x_ratio, y_ratio, _, _ = self.getPageByPos(ev.pos().x(), ev.pos().y())
        self.pageRelocationRequest.emit(page_no, x_ratio, y_ratio)
        return super().mousePressEvent(ev)

    def mouseReleaseEvent(self, ev):
        # debug('mouseReleaseEvent in ThumbGraphicsView')
        if self.page_counts == 0:
            return
        self.setCursor(QtCore.Qt.ArrowCursor)
        return super().mouseReleaseEvent(ev)

    def mouseMoveEvent(self, ev):
        # debug('mouseMoveEvent in ThumbGraphicsView')
        if self.page_counts == 0:
            return
        if self.isMousePressed:
            page_no, x_ratio, y_ratio, _, _ = self.getPageByPos(ev.pos().x(), ev.pos().y())
            self.pageRelocationRequest.emit(page_no, x_ratio, y_ratio)
        return super().mouseMoveEvent(ev)

    def wheelEvent(self, ev):
        # debug("wheelEvent in ThumbGraphicsView")
        self.setFocus()
        # 
        modifiers = QtWidgets.QApplication.keyboardModifiers()
        if modifiers == QtCore.Qt.ControlModifier:
            page_no, x_ratio, y_ratio, _, _ = self.getPageByPos(ev.pos().x(), ev.pos().y())
            delta = ev.angleDelta()
            if delta.y() > 0:
                self.zoomRequest.emit(True, page_no, x_ratio, y_ratio) # zoom in request
            else:
                self.zoomRequest.emit(False, page_no, x_ratio, y_ratio) # zoom out request
            ev.accept() # accept an event in order to stop it from propagating further
        else:
            return super().wheelEvent(ev) # call parent's handler, making the view scrolled (touch included)

