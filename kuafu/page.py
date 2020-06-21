 
from PyQt5 import QtCore
from PyQt5 import QtGui
from PyQt5 import QtWidgets

from popplerqt5 import Poppler
from pdfworker import PdfRender

from utils import debug
import math

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

        # pixmaps
        self.patch_basesize = 1000
        self.patch_rects = []
        
        # for smoothing transitions
        self.cached_pixmaps = {}
        self.current_items = {}

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
        self.maskItem.setZValue(3)
        # 0: self, 1: transient, 2: current, 3: mask

    def setSize(self, width, height):
        self.patch_rects = self.compute_patch_rects(width, height)

        # may be called many times before the first addPixmap()
        ratio_thistime = width / self.rect().width()

        self.setRect(0, 0, width, height)
        self.maskItem.setRect(0, 0, 0, 0)

        # remove all transient items
        for pixmap in self.cached_pixmaps:
            item = self.cached_pixmaps[pixmap]['associated_item']
            if item:
                item.setParentItem(None)
                self.cached_pixmaps[pixmap]['associated_item'] = None

        # remove all current items (move their pixmaps to cache)
        for item in self.current_items:
            item.setParentItem(None)
            # 
            pixmap = self.current_items[item]['pixmap']
            self.cached_pixmaps[pixmap] = {
                "dx": self.current_items[item]['dx'],
                "dy": self.current_items[item]['dy'],
                "ratio": self.current_items[item]['ratio'],
                "associated_item": None
            }
        self.current_items = {}

        # update the ratio in cached pixmaps
        for pixmap in self.cached_pixmaps:
            self.cached_pixmaps[pixmap]['ratio'] *= ratio_thistime

    def updateTransientItems(self, visibleRect):
        for pixmap in self.cached_pixmaps:
            raw_dx = self.cached_pixmaps[pixmap]['dx']
            raw_dy = self.cached_pixmaps[pixmap]['dy']
            ratio = self.cached_pixmaps[pixmap]['ratio']
            associated_item = self.cached_pixmaps[pixmap]['associated_item']
            # 
            x = raw_dx * ratio
            y = raw_dy * ratio
            w = pixmap.width() * ratio
            h = pixmap.height() * ratio
            vrect = QtCore.QRectF(x, y, w, h) # virtual rect
            irect = visibleRect.intersected(vrect) # intersected rect
            # 
            if irect.isEmpty(): # remove associated transient item if unvisible
                if associated_item:
                    associated_item.setParentItem(None)
                    self.cached_pixmaps[pixmap]['associated_item'] = None
            else:
                # check if already visible in current items
                total_overlap_size = 0
                for it in self.current_items:
                    rect = QtCore.QRectF(
                        it.offset().x(), it.offset().y(), 
                        it.boundingRect().width(), it.boundingRect().height()
                    )
                    cirect = rect.intersected(irect)
                    total_overlap_size += cirect.width() * cirect.height()
                if total_overlap_size / (irect.width()*irect.height()) > 0.90:
                    continue
                    
                # crop the visible part
                crop_x = math.floor((irect.x() - vrect.x()) / ratio)
                crop_y = math.floor((irect.y() - vrect.y()) / ratio)
                crop_w = math.ceil(irect.width() / ratio)
                crop_h = math.ceil(irect.height() / ratio)
                cropped_pixmap = pixmap.copy(crop_x, crop_y, crop_w, crop_h)

                # resize to current scale
                resized_pixmap = cropped_pixmap.scaled(math.ceil(irect.width()), math.ceil(irect.height()))

                # debug, draw some mask
                # if True:
                if False:
                    painter = QtGui.QPainter()
                    painter.begin(resized_pixmap)
                    painter.fillRect(resized_pixmap.rect(), QtGui.QColor(255, 0, 0, 100))
                    painter.end()
                    debug("Add transient item: <%d x %d>" % (resized_pixmap.width(), resized_pixmap.height()))

                if associated_item:
                    associated_item.setPixmap(resized_pixmap)
                    associated_item.setOffset(irect.x(), irect.y())
                else:
                    # add to scene
                    item = QtWidgets.QGraphicsPixmapItem(resized_pixmap, parent=self)
                    item.setOffset(irect.x(), irect.y())
                    item.setZValue(1)
                    self.cached_pixmaps[pixmap]['associated_item'] = item

    def get_roi_patches(self, roi_rect):
        patch_positions = []
        patches = []
        for i in range(len(self.patch_rects)):
            pRect = self.patch_rects[i]
            interRect = roi_rect.intersected(pRect)
            if not interRect.isEmpty():
                patches.append(pRect)
                patch_positions.append(i)
        return patch_positions, patches
            
    def compute_patch_rects(self, width, height):
        rects = []

        if width >= self.patch_basesize:
            horiCnt = int(math.pow(2, int(math.log2(width / self.patch_basesize) + 0.5)))
        else:
            horiCnt = 1
        if height >= self.patch_basesize:
            vertCnt = int(math.pow(2, int(math.log2(height / self.patch_basesize) + 0.5)))
        else:
            vertCnt = 1

        horiStep = int(width / horiCnt)
        vertStep = int(height / vertCnt)
        for i in range(horiCnt):
            for j in range(vertCnt):
                x = i*horiStep
                y = j*vertStep
                w = horiStep
                h = vertStep
                # 
                if x + w > width:
                    w = width - x
                if y + h > height:
                    h = height - y
                rects.append(QtCore.QRectF(x, y, w, h))
        return rects

    def setPosition(self, x, y):
        self.setPos(x, y)

    def addPixmap(self, pixmap, dx, dy):
        item = QtWidgets.QGraphicsPixmapItem(pixmap, parent=self)
        item.setOffset(dx, dy)
        item.setZValue(2)

        self.current_items[item] = {
            "pixmap": pixmap,
            "dx": dx,
            "dy": dy,
            "ratio": 1.0,
        }

        # remove cached pixmaps which are fully covered
        pixmapsToRemove = []
        for pm in self.cached_pixmaps:
            raw_dx = self.cached_pixmaps[pm]['dx']
            raw_dy = self.cached_pixmaps[pm]['dy']
            ratio = self.cached_pixmaps[pm]['ratio']
            # 
            x = raw_dx * ratio
            y = raw_dy * ratio
            w = pm.width() * ratio
            h = pm.height() * ratio
            current_rect = QtCore.QRectF(x, y, w, h)
            # 
            total_overlap_size = 0
            for it in self.current_items:
                rect = QtCore.QRectF(
                    it.offset().x(), it.offset().y(), 
                    it.boundingRect().width(), it.boundingRect().height()
                )
                irect = rect.intersected(current_rect)
                total_overlap_size += irect.width() * irect.height()
            #
            # debug(w*h, total_overlap_size)

            fully_coverd = False
            if total_overlap_size / (w*h) > 0.90:
                fully_coverd = True
            # 
            if fully_coverd:
                pixmapsToRemove.append(pm)
                debug("Remove cached pixmap: <%d x %d> ratio: %.2f" % (w, h, ratio))
        # 
        for pm in pixmapsToRemove:
            self.removeCachedPixmap(pm)

        # debug
        currentItemsCnt = len(self.current_items)
        cachedPixmapsCnt = len(self.cached_pixmaps)
        debug("Current items: ", currentItemsCnt, " Cached pixmaps: ", cachedPixmapsCnt)
        
    def removeCachedPixmap(self, pixmap):
        if pixmap in self.cached_pixmaps:
            associated_item = self.cached_pixmaps[pixmap]['associated_item']
            if associated_item:
                associated_item.setParentItem(None)
            self.cached_pixmaps.pop(pixmap)

    def clear(self):
        #TODO
        pass
        #self.cachedPixmap = None
        #self.cachedOffset = [0, 0]
        #self.cachedRatio = 1.0
        #self.pixmapItem.setPixmap(QtGui.QPixmap())
        #self.pixmapItem.setOffset(0, 0)

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