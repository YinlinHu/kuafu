from PyQt5 import QtWidgets
from PyQt5 import QtCore
from PyQt5 import QtGui

from basedocgraphicsview import BaseDocGraphicsView
from utils import debug

class ThumbGraphicsView(BaseDocGraphicsView):
    pageRelocationRequest = QtCore.pyqtSignal(int, float, float)

    def __init__(self, parent, render_num=4):
        super(ThumbGraphicsView, self).__init__(parent, render_num)

        self.scene.setBackgroundBrush(QtGui.QBrush(QtCore.Qt.white)) # set background

        self.setDragMode(QtWidgets.QGraphicsView.NoDrag) # disable the default dragger

        self.isMousePressed = False
        self.isMouseOver = False

    def highlightVisibleMasks(self, filename, visible_regions):
        # the items in visible_regions are in normalized coordinates
        # 
        if filename != self.current_filename:
            return
        if not self.load_finished_flag:
            return
        # 
        # remove current highlighted first
        for pg_no in self.current_highlighted_pages:
            self.page_items[pg_no].setMask(0, 0, 0, 0)
        self.current_highlighted_pages = []
        # remove border of the page that is marked as the current
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
        if not self.load_finished_flag:
            return
        self.isMousePressed = True
        self.setCursor(QtCore.Qt.ClosedHandCursor)
        page_no, x_ratio, y_ratio = self.getPageByPos(ev.pos().x(), ev.pos().y())
        self.pageRelocationRequest.emit(page_no, x_ratio, y_ratio)
        return super().mousePressEvent(ev)

    def mouseReleaseEvent(self, ev):
        # debug('mouseReleaseEvent in ThumbGraphicsView')
        if not self.load_finished_flag:
            return
        self.isMousePressed = False
        self.setCursor(QtCore.Qt.ArrowCursor)
        return super().mouseReleaseEvent(ev)

    def mouseMoveEvent(self, ev):
        # debug('mouseMoveEvent in ThumbGraphicsView')
        if not self.load_finished_flag:
            return
        if self.isMousePressed:
            page_no, x_ratio, y_ratio = self.getPageByPos(ev.pos().x(), ev.pos().y())
            self.pageRelocationRequest.emit(page_no, x_ratio, y_ratio)
        return super().mouseMoveEvent(ev)

    def enterEvent(self, ev):
        # debug('enterEvent in ThumbGraphicsView')
        self.isMouseOver = True
        return super().enterEvent(ev)
    
    def leaveEvent(self, ev):
        # debug('leaveEvent in ThumbGraphicsView')
        self.isMouseOver = False
        return super().leaveEvent(ev)
