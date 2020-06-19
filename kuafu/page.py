 
from PyQt5 import QtCore
from PyQt5 import QtGui
from PyQt5 import QtWidgets

from popplerqt5 import Poppler
from pdfworker import PdfRender

from utils import debug

class PageGraphicsItem(QtWidgets.QGraphicsRectItem):
    def __init__(self, parent=None):
        super(PageGraphicsItem, self).__init__(parent)

        self.setRect(0,0,0,0)
        self.setPos(0, 0)

        pen = QtGui.QPen(QtCore.Qt.NoPen) # remove rect border
        # pen = QtGui.QPen(QtCore.Qt.black)
        # pen.setWidth(1)
        self.setPen(pen)
        self.setBrush(QtCore.Qt.white) # fill white color

        self.cachedPixmap = None
        self.cachedOffset = []
        self.cachedRatio = 1.0

        # pixmap
        self.pixmapItem = QtWidgets.QGraphicsPixmapItem(QtGui.QPixmap())
        # self.pixmapItem.setOffset(1, 1) # leave border space
        self.pixmapItem.setParentItem(self)

        # mask
        self.maskItem = QtWidgets.QGraphicsRectItem()
        self.maskItem.setRect(0, 0, 0, 0)

        pen = QtGui.QPen(QtCore.Qt.yellow)
        pen.setWidth(1)
        self.maskItem.setPen(pen)
        self.maskItem.setBrush(QtGui.QBrush(QtGui.QColor(0, 0, 0, 100))) # fill color

        self.maskItem.setParentItem(self)

        # 
        self.setZValue(0)
        self.pixmapItem.setZValue(1)
        self.maskItem.setZValue(2)

    def setSize(self, width, height, transition=True):

        ratio = width / self.rect().width()
        self.cachedRatio *= ratio

        self.setRect(0, 0, width, height)
        self.maskItem.setRect(0, 0, 0, 0)

        if transition:
            if self.cachedPixmap:
                scaledPixmap = self.cachedPixmap.scaled(
                    self.cachedPixmap.width() * self.cachedRatio, 
                    self.cachedPixmap.height() * self.cachedRatio
                    )
                self.pixmapItem.setPixmap(scaledPixmap)
                self.pixmapItem.setOffset(
                    self.cachedOffset[0] * self.cachedRatio, 
                    self.cachedOffset[1] * self.cachedRatio
                    )
        else:
            self.cachedPixmap = None
            self.cachedOffset = [0, 0]
            self.cachedRatio = 1.0
            self.pixmapItem.setPixmap(QtGui.QPixmap())
            self.pixmapItem.setOffset(0, 0)

    def setPosition(self, x, y):
        self.setPos(x, y)

    def setPixmap(self, pixmap, dx, dy):
        self.cachedPixmap = pixmap
        self.cachedOffset = [dx, dy]
        self.cachedRatio = 1.0
        self.pixmapItem.setPixmap(pixmap)
        self.pixmapItem.setOffset(dx, dy)

    def clear(self):
        self.cachedPixmap = None
        self.pixmapItem.setPixmap(QtGui.QPixmap())
        self.pixmapItem.setOffset(0, 0)

class DocumentFrame(QtWidgets.QFrame):
    """ This widget is a container of PageWidgets. PageWidget communicates
        Window through this widget """
    jumpToRequested = QtCore.pyqtSignal(int, float)
    copyTextRequested = QtCore.pyqtSignal(int, QtCore.QPoint, QtCore.QPoint)
    showStatusRequested = QtCore.pyqtSignal(str)
    pagePositionChanged = QtCore.pyqtSignal(int, int)
    # 
    # internal useage

    # parent is scrollAreaWidgetContents
    def __init__(self, parent, scrollArea, doc, screen_dpi, threads = 4):
        super(DocumentFrame, self).__init__(parent)

        self.setFrameShape(QtWidgets.QFrame.StyledPanel)
        self.setFrameShadow(QtWidgets.QFrame.Raised)

        self.scrollArea = scrollArea
        self.vScrollbar = scrollArea.verticalScrollBar()
        self.hScrollbar = scrollArea.horizontalScrollBar()

        self.scrollArea.resizeRequested.connect(self.handleScrollAreaResized)
        self.scrollArea.verticalScrollBar().setValue(0)
        self.scrollArea.verticalScrollBar().valueChanged.connect(self.renderCurrentVisiblePages)

        self.setMouseTracking(True)
        self.clicked = False

        self.copy_text_mode = False

        # 
        self.doc = doc
        self.pages_count = self.doc.numPages()
        #
        self.pre_empty_page_count = 0
        self.view_column_count = 1

        self.layout = QtWidgets.QGridLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0) # left, top, right, bottom
        self.layout.setAlignment(QtCore.Qt.AlignTop | QtCore.Qt.AlignCenter)
        self.layout.setHorizontalSpacing(0)
        self.layout.setVerticalSpacing(0)

        self.setContentsMargins(0, 0, 0, 0)
        
        self.page_widgets = []
        for i in range(self.pages_count):
            for j in range(4):
                page = PageWidget(i, self)
                self.layout.addWidget(page, i, j, QtCore.Qt.AlignCenter)

        self.current_page = 0
        self.current_render_dpi = 0 
        self.zoom_fit_width = True # default on
        self.screen_dpi = screen_dpi

        self.visible_pages = [0]
        self.rendered_pages = {}
 
        # create render threads
        self.num_threads = threads
        self.render_list = []
        for i in range(self.num_threads):
            tmpRender = PdfRender()
            tmpRender.rendered.connect(self.setRenderedImage)
            tmpRender.start()
            self.render_list.append(tmpRender)

        # set document in other threads
        for rd in self.render_list:
            rd.set_document(self.doc)

        # set default style
        self.setStyleSheet("border: 0; background-color: gray")

        self.rearrangePages()

    def rearrangePages(self):
        # https://stackoverflow.com/questions/4528347/clear-all-widgets-in-a-layout-in-pyqt/13103617
        return

        for item in self.page_widgets:
            item.setParent(None)
            item.close()

        self.page_widgets = [] # clear all pages

        for i in range(self.pages_count):
            page = PageWidget(i, self)
            self.page_widgets.append(page)
            gridIdx = i + self.pre_empty_page_count
            row = int (gridIdx / self.view_column_count)
            col = gridIdx % self.view_column_count
            self.layout.addWidget(page, row, col, QtCore.Qt.AlignCenter)

        self.visible_pages = [0]
        self.rendered_pages = {}

        if self.zoom_fit_width:
            self.resizePages(0)
        else:
            self.resizePages(self.current_render_dpi)

    def getVisiblePages(self):
        visible_pages = []
        for pg_no in range(self.pages_count):
            if not self.page_widgets[pg_no].visibleRegion().isEmpty():
                visible_pages.append(pg_no)
        return visible_pages

    def setRenderedImage(self, page_no, dpi, image):
        """ takes a QImage and sets pixmap of the specified page
            when number of rendered pages exceeds a certain number, old page image is
            deleted to save memory """

        debug("> Rendering Completed :", page_no)

        self.page_widgets[page_no].setPageData(page_no, QtGui.QPixmap.fromImage(image), self.doc.page(page_no))
        self.rendered_pages[page_no] = dpi
        # # Request to render next page
        # if self.current_page <= page_no < (self.current_page + self.max_preload - 2):
        #     if (page_no+2 not in self.rendered_pages) and (page_no+2 <= self.pages_count):
        #       self.renderRequested.emit(page_no+2, self.pages[page_no+1].dpi)
        # Replace old rendered pages with blank image

        if len(self.rendered_pages) > 10:
            self.visible_pages = self.getVisiblePages()
            firstKey = next(iter(self.rendered_pages))
            if firstKey not in self.visible_pages:
                self.rendered_pages.pop(firstKey)
                # debug("Clear Page :", firstKey)
                self.page_widgets[firstKey].clear()

        # debug("Rendered Pages :", self.rendered_pages)

    def renderRequest(self, page_no, dpi):
        tgtWorkerIdx = page_no % self.num_threads
        self.render_list[tgtWorkerIdx].set_visible_pages(self.visible_pages)    
        self.render_list[tgtWorkerIdx].render_async(page_no, dpi)

    def renderCurrentVisiblePages(self):
        """ Requests to render current page. if it is already rendered, then request
            to render next unrendered page """

        return

        self.visible_pages = self.getVisiblePages()
        debug("Visible Pages: ", self.visible_pages)

        if len(self.visible_pages) == 0:
            return

        if self.current_page != self.visible_pages[0]:
            self.current_page = self.visible_pages[0]
            self.pagePositionChanged.emit(self.current_page, self.pages_count)

        for page_no in self.visible_pages:
            if page_no < 0 or page_no >= self.pages_count:
                continue
            if page_no in self.rendered_pages and abs(self.rendered_pages[page_no] - self.current_render_dpi) < 1:
                continue
            self.renderRequest(page_no, self.current_render_dpi)
            debug("< Rendering Requested :", page_no)

    def setColumnNumber(self, columnNum):
        debug("setColumnNumber in DocumentFrame")
        self.view_column_count = columnNum
        self.rearrangePages()

    def setPrecedingEmptyPage(self, emptyCount):
        debug("setPrecedingEmptyPage %d in DocumentFrame" % emptyCount)
        self.pre_empty_page_count = emptyCount
        self.rearrangePages()

    def setZoom(self, dpi, keep_fit_with=False):
        """ Gets called when zoom level is changed"""

        if abs(self.current_render_dpi-dpi) > 0.01:
            if dpi != 0 and not keep_fit_with:
                self.zoom_fit_width = False
            self.resizePages(dpi)
            zoomRatio = int(100 * self.current_render_dpi / self.screen_dpi)
            self.showStatus("Zooming to %d%%" % zoomRatio)

    def zoomIn(self):
        dpi = self.current_render_dpi * 1.5
        if dpi > 300:
            return
        self.setZoom(dpi)

    def zoomOut(self):
        dpi = self.current_render_dpi * 0.5
        if dpi < 5:
            return
        self.setZoom(dpi)

    def zoomFitWidth(self):
        self.zoom_fit_width = True
        self.setZoom(0)

    def jumpToCurrentPage(self):
        """ this is used as a slot, to connect with a timer"""
        self.jumpToPage(self.current_page)

    def jumpToPage(self, page_num, top=0.0):
        """ scrolls to a particular page and position """
        if page_num < 0: 
            page_num = 0
        elif page_num >= self.pages_count: 
            page_num = self.pages_count - 1
        if not (0 < top < 1.0) : top = 0
        self.jumped_from = self.current_page
        self.current_page = page_num
        if self.jumped_from != self.current_page:
            self.pagePositionChanged.emit(self.current_page, self.pages_count)
        scrollbar_pos = self.page_widgets[page_num].pos().y()
        scrollbar_pos += top*self.page_widgets[page_num].height()
        self.docScrollArea1.verticalScrollBar().setValue(scrollbar_pos)

    def undoJump(self):
        if self.jumped_from == None: return
        self.jumpToPage(self.jumped_from)

    def goNextPage(self):
        if self.current_page == self.pages_count - 1:
             return
        self.jumpToPage(self.current_page + 1)

    def goPrevPage(self):
        if self.current_page == 0: 
            return
        self.jumpToPage(self.current_page - 1)

    def gotoPage(self, page_no):
        self.jumpToPage(page_no)

    def handleScrollAreaResized(self, width, height):
        debug("ScrollArea Resized Event received in DocumentFrame: %d, %d" % (width, height))
        if self.zoom_fit_width:
            self.setZoom(0, keep_fit_with=True)

    def compute_fixed_width_dpi(self, pageInchWidth):
         # remove the space of scroll bar
        viewPixelWidth = self.scrollArea.width() - self.scrollArea.verticalScrollBar().width() - 4
        viewPixelWidth -= (self.layout.horizontalSpacing() * (self.view_column_count - 1))
        viewPixelWidth /= self.view_column_count
        dpi = viewPixelWidth / pageInchWidth
        return dpi

    def resizePages(self, dpi):
        '''Resize all pages according to zoom level '''

        # get raw width and height of the current page
        pg_width = self.doc.page(self.current_page).pageSizeF().width() / 72.0 # width in inch
        pg_height = self.doc.page(self.current_page).pageSizeF().height() / 72.0

        new_dpi = dpi
        if new_dpi == 0: # if fixed width
            new_dpi = self.compute_fixed_width_dpi(pg_width)

        # adjust page dimentions
        for i in range(self.pages_count):
            self.page_widgets[i].dpi = new_dpi
            self.page_widgets[i].setFixedSize(pg_width * new_dpi, pg_height * new_dpi)

        for page_no in self.rendered_pages:
            self.page_widgets[page_no].updateImage()

        # if self.zoom_level == 0:
        #     # adjust scroll postion
        #     pass

        # scrolbar_pos = self.pages[self.current_page].pos().y()
        # self.scrollArea.verticalScrollBar().setValue(scrolbar_pos)

        self.update() # invoke the paintEvent method using update() explicitly
        self.current_render_dpi = new_dpi

        # the page sizes only take effect after next paint event
        # here use a simple time hacking to wait for its taking effect
        QtCore.QTimer.singleShot(2000, self.renderCurrentVisiblePages)

    def showEvent(self, ev):
        debug('showEvent in DocFrame')
        # self.resizePages(self.current_render_dpi)

    def closeEvent(self, ev):
        """ Save all settings on window close """
        debug('closeEvent in DocFrame')
        for rd in self.render_list:
            rd.stop_async()
        for rd in self.render_list:
            rd.wait()
        return QtWidgets.QFrame.closeEvent(self, ev)

    # def resizeEvent(self, ev):
    #     debug('resizeEvent in DocFrame')

    def wheelEvent(self, ev):
        debug("wheelEvent in DocFrame")
        # modifiers = QtWidgets.QApplication.keyboardModifiers()
        # if modifiers == QtCore.Qt.ControlModifier:
        #     delta = ev.angleDelta()
        #     if delta.y() > 0:
        #         self.zoomIn()
        #     else:
        #         self.zoomOut()
        #     ev.accept() # accept an event in order to stop it from propagating further

    def mousePressEvent(self, ev):
        debug("mousePressEvent in DocFrame")
        self.click_pos = ev.globalPos()
        self.v_scrollbar_pos = self.vScrollbar.value()
        self.h_scrollbar_pos = self.hScrollbar.value()
        self.clicked = True

    def mouseReleaseEvent(self, ev):
        debug("mouseReleaseEvent in DocFrame")
        self.clicked = False
        self.setCursor(QtCore.Qt.OpenHandCursor)

    def mouseDoubleClickEvent(self, ev):
        debug("mouseDoubleClickEvent in DocFrame")
        self.setZoom(self.screen_dpi)
        
    def mouseMoveEvent(self, ev):
        # debug("mouseMoveEvent in DocFrame")
        if not self.clicked : return
        self.setCursor(QtCore.Qt.ClosedHandCursor)
        self.vScrollbar.setValue(self.v_scrollbar_pos + self.click_pos.y() - ev.globalY())
        self.hScrollbar.setValue(self.h_scrollbar_pos + self.click_pos.x() - ev.globalX())

    def jumpTo(self, page_num, top):
        self.jumpToRequested.emit(page_num, top)

    def enableCopyTextMode(self, enable):
        self.copy_text_mode = enable

    def copyText(self, page_num, top_left, bottom_right):
        self.copyTextRequested.emit(page_num, top_left, bottom_right)

    def showStatus(self, msg):
        self.showStatusRequested.emit(msg)


class PageWidget(QtWidgets.QLabel):
    """ This widget shows a rendered page """
    def __init__(self, page_num, frame=None):
        super(PageWidget, self).__init__(frame)

        self.manager = frame
        self.setMouseTracking(True)
        self.setSizePolicy(QtWidgets.QSizePolicy.Fixed, QtWidgets.QSizePolicy.Fixed)
        self.link_areas = []
        self.link_annots = []
        self.annots_listed, self.copy_text_mode = False, False
        self.click_point, self.highlight_area = None, None
        self.page_num = page_num
        self.image = QtGui.QPixmap()
        self.mask = PageMaskWidget(self)

        self.setStyleSheet("border-width: 1px; border-style: solid; border-color: black; background-color: white")
        
        self.setAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignTop)
        self.setText("Loading ...")

        # self.setFixedSize(0, 0)

    def setPageData(self, page_no, pixmap, page):
        self.image = pixmap
        self.updateImage()
        if self.annots_listed : return
        annots = page.annotations()
        for annot in annots:
            if annot.subType() == Poppler.Annotation.ALink:
                x, y = annot.boundary().left()*pixmap.width(), annot.boundary().top()*pixmap.height()
                w, h = annot.boundary().width()*pixmap.width()+1, annot.boundary().height()*pixmap.height()+1
                self.link_areas.append(QtCore.QRectF(x,y, w, h))
                self.link_annots.append(annot)
        self.annots_listed = True

    def clear(self):
        QtWidgets.QLabel.clear(self)
        self.setText("Loading ...")
        self.image = QtGui.QPixmap()

    def mouseMoveEvent(self, ev):
        # Draw rectangle when mouse is clicked and dragged in copy text mode.
        if self.manager.copy_text_mode:
            if self.click_point:
                pm = self.pm.copy()
                painter = QtGui.QPainter()
                painter.begin(pm)
                painter.drawRect(QtCore.QRect(self.click_point, ev.pos()))
                painter.end()
                self.setPixmap(pm)
            return

        # Change cursor if cursor is over link annotation
        for i, area in enumerate(self.link_areas):
            if area.contains(ev.pos()):
                linkDest = self.link_annots[i].linkDestination()
                if not linkDest : continue
                # For jump to page link
                if linkDest.linkType() == Poppler.Link.Goto:
                    p = linkDest.destination().pageNumber()
                    self.manager.showStatus("Jump To Page : %i" % p)
                    self.setCursor(QtCore.Qt.PointingHandCursor)
                # For URL link
                elif linkDest.linkType() == Poppler.Link.Browse:
                    self.manager.showStatus("URL : %s" % linkDest.url())
                    self.setCursor(QtCore.Qt.PointingHandCursor)
                return
        # self.manager.showStatus("")
        self.unsetCursor()
        ev.ignore()         # pass to underlying frame if not over link or copy text mode

    def mousePressEvent(self, ev):
        # In text copy mode
        if self.manager.copy_text_mode:
            self.click_point = ev.pos()
            self.pm = self.pixmap().copy()
            return
        # In normal mode
        for i, area in enumerate(self.link_areas):
            if not area.contains(ev.pos()): continue
            link_dest = self.link_annots[i].linkDestination()
            if not link_dest : continue
            # For jump to page link
            if link_dest.linkType() == Poppler.Link.Goto:
                page_num = link_dest.destination().pageNumber()
                top = 0.0
                if link_dest.destination().isChangeTop():
                    top = link_dest.destination().top()
                self.manager.jumpTo(page_num, top)
            # For URL link
            elif link_dest.linkType() == Poppler.Link.Browse:
                url = link_dest.url()
                if url.startswith("http"):
                    confirm = QMessageBox.question(self, "Open Url in Browser",
                        "Do you want to open browser to open...\n%s" %url, QMessageBox.Yes|QMessageBox.Cancel)
                    if confirm == QMessageBox.Yes:
                        Popen(["x-www-browser", url])
            return
        ev.ignore()

    def mouseReleaseEvent(self, ev):
        if self.manager.copy_text_mode:
            self.manager.copyText(self.page_num, self.click_point, ev.pos())
            self.setPixmap(self.pm)
            self.click_point = None
            self.pm = None
            return
        ev.ignore()

    def updateImage(self):
        """ repaint page widget, and draw highlight areas """
        if self.highlight_area:
            img = self.image.copy()
            painter = QPainter(img)
            zoom = self.dpi / 72.0
            for area in self.highlight_area:
                box = QtCore.QRectF(area.left()*zoom, area.top()*zoom,
                                    area.width()*zoom, area.height()*zoom)
                painter.fillRect(box, QColor(0,255,0, 127))
            painter.end()
            self.setPixmap(img.scaled(self.width(), self.height(), transformMode=QtCore.Qt.SmoothTransformation))
            # self.setPixmap(img)
        else:
            # self.setPixmap(self.image)
            self.setPixmap(self.image.scaled(self.width(), self.height(), transformMode=QtCore.Qt.SmoothTransformation))

class PageMaskWidget(QtWidgets.QLabel):
    """ This widget shows a rendered page """
    def __init__(self, parent):
        super(PageMaskWidget, self).__init__(parent)

        self.setMouseTracking(True)
        self.setSizePolicy(0,0)
        self.setStyleSheet("border-width: 1px; border-style: solid; border-color: yellow; background-color: rgba(0, 0, 0, 100)")
        self.setGeometry(0,0,0,0) # the default is unvisible