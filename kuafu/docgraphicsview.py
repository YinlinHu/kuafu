from PyQt5 import QtWidgets
from PyQt5 import QtCore
from PyQt5 import QtGui
from PyQt5 import QtOpenGL

# import fitz #PyMuPDF
from popplerqt5 import Poppler

from pdfworker import PdfRender
from multiprocessing import Queue
from page import PageGraphicsItem

from utils import debug

import math
import time
import numpy as np

class DocGraphicsView(QtWidgets.QGraphicsView):
    pagePositionChanged = QtCore.pyqtSignal(int, int)

    def __init__(self, parent, render_num=4):
        super(DocGraphicsView, self).__init__(parent)

        # self.setViewport(QtOpenGL.QGLWidget()) # opengl

        self.scene = QtWidgets.QGraphicsScene(self)
        self.scene.setBackgroundBrush(QtGui.QBrush(QtCore.Qt.gray)) # set gray background

        self.current_cursor_x = 0
        self.current_cursor_y = 0
        self.mouse_pressed = False

        self.setScene(self.scene)
        
        self.page_items = [] # instances of PageGraphicsItem

        self.current_filename = None

        self.page_counts = 0
        self.pages_size_inch = [] # (width, height) in inch, invarient
        self.current_pages_size_pix = [] # varient depends on the view

        self.current_page = 0
        self.current_visible_regions = {}
        self.view_column_count = 1
        self.leading_empty_pages = 0

        self.render_num = render_num
        self.render_list = []
        self.rendered_info = {}
        self.current_rendering_dpi = []

        for i in range(self.render_num):
            tmpRender = PdfRender(Queue(), Queue())
            tmpRender.start()
            self.render_list.append(tmpRender)

        self.fitwidth_flag = True
        self.screen_dpi = 0

        self.horispacing = 3
        self.vertspacing = 3

        # there are cases unwanted, making GUI slower
        # self.horizontalScrollBar().valueChanged.connect(self.onViewportChanged)
        # self.verticalScrollBar().valueChanged.connect(self.onViewportChanged)

        self.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAsNeeded)
        self.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOn)

        # self.setRenderHint(QtGui.QPainter.Antialiasing)
        self.setViewportUpdateMode(QtWidgets.QGraphicsView.FullViewportUpdate)
        # self.setViewportUpdateMode(QtWidgets.QGraphicsView.SmartViewportUpdate)
        # self.setViewportUpdateMode(QtWidgets.QGraphicsView.MinimalViewportUpdate)
        self.setDragMode(QtWidgets.QGraphicsView.ScrollHandDrag)
        # self.setTransformationAnchor(QtWidgets.QGraphicsView.AnchorUnderMouse)

        self.setMouseTracking(True)

        self.setTransform(QtGui.QTransform()) # set identity matrix for transformation

        # read the queue periodically
        self.queue_timer = QtCore.QTimer(self)
        self.queue_timer.timeout.connect(self.retrieveQueueResults)
        self.queue_timer.start(50)

    def clear(self):
        self.scene.clear()
        self.page_items = []
        self.pages_size_inch = [] # (width, height) in inch, invarient
        self.current_pages_size_pix = [] # varient depends on the view
        self.current_visible_regions = {}
        self.current_rendering_dpi = []
        self.rendered_info = {}

    def setDocument(self, filename, screen_dpi):
        self.clear()

        self.current_filename = filename
        self.screen_dpi = screen_dpi

        # reSET for all render processes
        for rd in self.render_list:
            rd.commandQ.put(['SET', [self.current_filename]])

        # query page size using the first worker
        self.render_list[0].commandQ.put(['PAGESIZES', [None]])

    def onPageSizesReceived(self, pages_size_inch):
        debug("%d Page Sizes Received" % len(pages_size_inch))
        time_0 = time.time()

        self.page_counts = len(pages_size_inch)
        self.pages_size_inch = pages_size_inch

        for i in range(self.page_counts):
            pageItem = PageGraphicsItem()
            self.scene.addItem(pageItem)
            self.page_items.append(pageItem)

        self.fitwidth_flag = True
        time_a = time.time()
        debug('A', time_a - time_0)

        self.computePagesDPI(self.viewport())
        time_b = time.time()
        debug('B', time_b - time_a)

        self.__rearrangePages()
        time_c = time.time()
        debug('C', time_c - time_b)

        self.renderCurrentVisiblePages()
        time_d = time.time()
        debug('D', time_d - time_c)

        self.pagePositionChanged.emit(self.current_page, self.page_counts)

    def onViewportChanged(self):
        self.renderCurrentVisiblePages()
        self.pagePositionChanged.emit(self.current_page, self.page_counts)

    def computePagesDPI(self, viewport):
        if self.fitwidth_flag:
            viewWidth = viewport.width()
            viewHeight = viewport.height()
            
            # all pages will have the same width, but may different height
            self.current_rendering_dpi = []
            self.current_pages_size_pix =[]

            viewWidth -= (self.horispacing * (self.view_column_count + 1))
            viewWidth /= self.view_column_count
            
            for i in range(self.page_counts):
                dpi = viewWidth / self.pages_size_inch[i][0]
                height = self.pages_size_inch[i][1] * dpi
                self.current_rendering_dpi.append(dpi)
                self.current_pages_size_pix.append([int(viewWidth), int(height)])
        else:
            pass

    def getVisibleRegions(self):
        visRect = self.viewport().rect() # visible area (without scrollbars)
        if visRect.isEmpty():
            self.current_visible_regions = {}
            return

        visRect = self.mapToScene(visRect).boundingRect() # change to scene coordinates
        # 
        regions = {}
        for pg_no in range(self.page_counts):
            pos = self.page_items[pg_no].scenePos()
            rect = self.page_items[pg_no].boundingRect()
            pageRect = QtCore.QRectF(pos.x(), pos.y(), rect.width(), rect.height())
            intsec = visRect.intersected(pageRect)
            # change to item coordinate
            intsec = QtCore.QRectF(
                intsec.x() - pos.x(), intsec.y() - pos.y(), 
                intsec.width(), intsec.height()
                )
            if intsec.isEmpty():
                continue
            regions[pg_no] = intsec

        self.current_visible_regions = regions

    def renderRequest(self, page_no, dpi, roi, render_idx, visible_regions):
        self.render_list[render_idx].commandQ.put(['RENDER', [page_no, dpi, roi, visible_regions]])

    def renderCurrentVisiblePages(self):
        self.getVisibleRegions()
        if len(self.current_visible_regions) == 0:
            return

        # debug("Visible Regions: ", self.current_visible_regions)

        # update the cached images for visible pages first (for smoothing transitions)
        for page_no in self.current_visible_regions:
            self.page_items[page_no].updateTransientItems(self.current_visible_regions[page_no])

        # first key as current page
        self.current_page = next(iter(self.current_visible_regions))

        for page_no in self.current_visible_regions:
            history_dpi = 0
            history_roi_list = []
            if page_no in self.rendered_info:
                history_dpi, history_roi_list = self.rendered_info[page_no]
                
            # split roi to small patches
            roi_raw = self.current_visible_regions[page_no]
            patch_positions, patches = self.page_items[page_no].get_roi_patches(roi_raw)
            patch_col_num = self.page_items[page_no].patch_col_num

            dpi = self.current_rendering_dpi[page_no]
            for i in range(len(patches)):
                pRow, pCol = patch_positions[i]
                pIdx = pRow * patch_col_num + pCol
                roi = patches[i]

                # already cached, no need to render
                if dpi == history_dpi and roi in history_roi_list:
                    continue

                # assign render index according to the page number and the patch position
                prefixNum = page_no % self.render_num
                render_idx = (prefixNum + pIdx) % self.render_num

                self.renderRequest(page_no, dpi, roi, render_idx, self.current_visible_regions)

                debug("<- Render %d Requested : <page:%d> <dpi:%.2f> <roi_raw: %.1f %.1f %.1f %.1f> <roi: %.1f %.1f %.1f %.1f>" % (
                    render_idx, page_no, dpi, 
                    roi_raw.left(), roi_raw.top(), roi_raw.width(), roi_raw.height(), 
                    roi.left(), roi.top(), roi.width(), roi.height()
                    ))

    def handleSingleRenderedImage(self, render_idx, filename, page_no, dpi, roi, img_byte_array):
        debug("-> Rendering %d Completed : <page:%d> <dpi:%.2f> <roi: %.1f %.1f %.1f %.1f>" % (
            render_idx, page_no, dpi, roi.left(), roi.top(), roi.width(), roi.height()
        ))

        # the doc has changed, too late
        if filename != self.current_filename:
            debug("file name changed: %s -> %s. skipping" % (filename, self.current_filename))
            return

        # if page_no not in self.current_visible_regions:
        #     debug("become unvisible: %d. skipping" % page_no)
        #     return
        
        if page_no in self.rendered_info \
           and self.rendered_info[page_no][0] == dpi \
           and roi in self.rendered_info[page_no][1]:
            debug("duplicated rendering. skipping")
            return

        if len(self.current_rendering_dpi) == 0:
            return
        # too late, the current rendering dpi is already changed
        if dpi != self.current_rendering_dpi[page_no]:
            debug("unmatched DPI: %.2f -> %.2f. skipping" % (dpi, self.current_rendering_dpi[page_no]))
            return
            
        # QByteArray to QImage
        img_buffer = QtCore.QBuffer(img_byte_array)
        img_buffer.open(QtCore.QIODevice.ReadOnly)
        image = QtGui.QImageReader(img_buffer).read()

        # crop to container's size
        # containerSize = self.page_items[page_no].rect()
        # debug("dim: (%d x %d) -> [%d x %d]" % (image.width(), image.height(), containerSize.width(), containerSize.height()))
        # roi = QtCore.QRect(1,1,containerSize.width()-2, containerSize.height()-2)
        # image = image.copy(roi)

        self.page_items[page_no].addPixmap(QtGui.QPixmap.fromImage(image), roi.x(), roi.y())
        
        if page_no in self.rendered_info:
            dpi0, roi_list = self.rendered_info[page_no]
            assert(dpi == dpi0)
            roi_list.append(roi)
        else:
            self.rendered_info[page_no] = [dpi, [roi]]

        # # Request to render next page
        # if self.current_page <= page_no < (self.current_page + self.max_preload - 2):
        #     if (page_no+2 not in self.rendered_pages) and (page_no+2 <= self.pages_count):
        #       self.renderRequested.emit(page_no+2, self.pages[page_no+1].dpi)
        # Replace old rendered pages with blank image

        #if len(self.rendered_info) > 10:
            #self.getVisibleRegions() # update visible regions again
            #firstKey = next(iter(self.rendered_info))
            #if self.current_visible_regions is None or firstKey not in self.current_visible_regions:
                #self.rendered_info.pop(firstKey)
                #debug("Clear Page :", firstKey)
                #self.page_items[firstKey].clear()

        # debug("Rendered Images: ", self.rendered_pages)

    def retrieveQueueResults(self):
        for rd_idx in range(self.render_num):
            rd = self.render_list[rd_idx]
            resultsQ = rd.resultsQ
            # collect all results
            size = resultsQ.qsize()
            for i in range(size):
                item = resultsQ.get() # will be blocked until when some data are avaliable
                if item[0] == 'PAGESIZES_RES':
                    _, filename, pages_size_inch = item
                    if filename != self.current_filename: # the doc has changed, too late
                        continue
                    self.onPageSizesReceived(pages_size_inch)
                elif item[0] == 'RENDER_RES':
                    _, filename, page_no, dpi, roi, img_byte_array = item
                    self.handleSingleRenderedImage(rd_idx, filename, page_no, dpi, roi, img_byte_array)

    def __rearrangePages(self):
        if len(self.current_pages_size_pix) == 0:
            return

        pages_width_pix = np.array(self.current_pages_size_pix)[:, 0]
        pages_height_pix = np.array(self.current_pages_size_pix)[:, 1]

        rowNum = math.ceil((self.page_counts + self.leading_empty_pages) / self.view_column_count)
        pages_width_pix = np.concatenate((np.zeros((self.leading_empty_pages)), pages_width_pix))
        pages_height_pix = np.concatenate((np.zeros((self.leading_empty_pages)), pages_height_pix))

        pad_num = (self.page_counts + self.leading_empty_pages) % self.view_column_count
        if pad_num > 0:
            pad_num = self.view_column_count - pad_num
            pages_width_pix = np.concatenate((pages_width_pix, np.zeros((pad_num))))
            pages_height_pix = np.concatenate((pages_height_pix, np.zeros((pad_num))))

        pages_width_pix = pages_width_pix.reshape((rowNum, self.view_column_count))
        pages_height_pix = pages_height_pix.reshape((rowNum, self.view_column_count))
        rowHeights = pages_height_pix.max(axis=1)
        colWidths = pages_width_pix.max(axis=0)

        rowCumHeights = np.cumsum(rowHeights)
        colCumWidths = np.cumsum(colWidths)

        for i in range(self.page_counts):
            row = int((i + self.leading_empty_pages) / self.view_column_count)
            col = int((i + self.leading_empty_pages) % self.view_column_count)

            if col == 0:
                startx = 0
            else:
                startx = colCumWidths[col - 1]

            if row == 0:
                starty = 0
            else:
                starty = rowCumHeights[row - 1]

            # add spacing 
            startx += (self.horispacing * (col + 1))
            starty += (self.vertspacing * (row + 1))

            # center it
            startx += (colWidths[col] - pages_width_pix[row][col]) / 2
            starty += (rowHeights[row] - pages_height_pix[row][col]) / 2

            self.page_items[i].setSize(pages_width_pix[row][col], pages_height_pix[row][col])
            self.page_items[i].setPosition(startx, starty)

        sceneWidthFix = colWidths.sum() + (self.view_column_count + 1) * self.horispacing
        sceneHeightFix = rowHeights.sum() + (rowNum + 1) * self.vertspacing
        self.scene.setSceneRect(0, 0, sceneWidthFix, sceneHeightFix)
        
        # after rearrangement, the cached rendering information is useless
        # that means, everything should be re-rendered
        self.rendered_info = {}

    def __resizePages(self, ratio):

        # make sure the page size will not be too large or too small
        firstPageDpi = self.current_rendering_dpi[0] * ratio
        if firstPageDpi < 5 or firstPageDpi > 1200:
            return

        time_0 = time.time()

        # save previous cursor position
        viewRect = self.viewport()
        cursor_in_scene = self.mapToScene(self.current_cursor_x, self.current_cursor_y)
        scene_cx = cursor_in_scene.x() * ratio - (self.current_cursor_x - viewRect.width() / 2)
        scene_cy = cursor_in_scene.y() * ratio - (self.current_cursor_y - viewRect.height() / 2)

        for i in range(self.page_counts):
            self.current_pages_size_pix[i][0] *= ratio
            self.current_pages_size_pix[i][1] *= ratio
            self.current_rendering_dpi[i] *= ratio

        time_a = time.time()
        debug("A ", time_a - time_0)

        self.__rearrangePages()
        time_b = time.time()
        debug("B ", time_b - time_a)

        # set viewport
        self.centerOn(scene_cx, scene_cy)

        self.renderCurrentVisiblePages()
        time_c = time.time()
        debug("C ", time_c - time_b)

    def setColumnNumber(self, colNum):
        if self.page_counts > 0:
            self.view_column_count = min(self.page_counts, colNum)
            self.computePagesDPI(self.viewport())
            self.__rearrangePages()
            self.renderCurrentVisiblePages()
            return True
        else:
            return False

    def setPrecedingEmptyPage(self, emptyPages):
        if self.view_column_count > 1:
            self.leading_empty_pages = emptyPages
            self.computePagesDPI(self.viewport())
            self.__rearrangePages()
            self.renderCurrentVisiblePages()
            return True
        else:
            return False

    def zoomIn(self):
        self.__resizePages(1.5)
        self.fitwidth_flag = False

    def zoomOut(self):
        self.__resizePages(0.5)
        self.fitwidth_flag = False

    def zoomFitWidth(self):
        self.fitwidth_flag = True
        self.computePagesDPI(self.viewport())
        self.__rearrangePages()
        self.renderCurrentVisiblePages()
    # def showEvent(self, ev):
    #     debug('showEvent in DocGraphicsView')
    #     ev.ignore()

    def closeEvent(self, ev):
        debug('closeEvent in DocGraphicsView')
        self.destroyRenders()
        debug('All renders are destroyed')

    def destroyRenders(self):
        for rd in self.render_list:
            rd.commandQ.put(['STOP', []])
        for rd in self.render_list:
            # rd.wait()
            rd.join()
        self.render_list = []
        self.render_num = 0

    def resizeEvent(self, ev):
        # debug('resizeEvent in DocGraphicsView')
        # 
        # self.computePagesDPI(self.viewport())
        # self.__rearrangePages()
        # self.renderCurrentVisiblePages()

        # call the parent's handler, it will do some alignments
        super().resizeEvent(ev)

    def wheelEvent(self, ev):
        # debug("wheelEvent in DocGraphicsView")
        modifiers = QtWidgets.QApplication.keyboardModifiers()
        if modifiers == QtCore.Qt.ControlModifier:
            delta = ev.angleDelta()
            if delta.y() > 0:
                self.__resizePages(1.2)
            else:
                self.__resizePages(0.8)
            self.fitwidth_flag = False
            ev.accept() # accept an event in order to stop it from propagating further
        else:
            super().wheelEvent(ev) # call parent's handler, making the view scrolled (touch included)
            self.onViewportChanged()

    def mousePressEvent(self, ev):
        # debug('mousePressEvent in DocGraphicsView')
        self.mouse_pressed = True
        super().mousePressEvent(ev)

    def mouseReleaseEvent(self, ev):
        # debug('mouseReleaseEvent in DocGraphicsView')
        self.mouse_pressed = False
        super().mouseReleaseEvent(ev)

    def mouseDoubleClickEvent(self, ev):
        # debug('mouseDoubleClickEvent in DocGraphicsView')
        super().mouseDoubleClickEvent(ev)

    def mouseMoveEvent(self, ev):
        # debug('mouseMoveEvent in DocGraphicsView')
        if self.mouse_pressed:
            self.onViewportChanged() # detect drag
        self.current_cursor_x = ev.x()
        self.current_cursor_y = ev.y()
        # debug(self.current_cursor_x, self.current_cursor_y)
        super().mouseMoveEvent(ev)
