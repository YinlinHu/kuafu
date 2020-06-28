from PyQt5 import QtWidgets
from PyQt5 import QtCore
from PyQt5 import QtGui
# from PyQt5 import QtOpenGL

# import fitz #PyMuPDF
from popplerqt5 import Poppler

from pdfworker import PdfRender
from multiprocessing import Queue
from page import PageGraphicsItem

from utils import debug

import math
import time
import numpy as np

class BaseDocGraphicsView(QtWidgets.QGraphicsView):
    loadFinished = QtCore.pyqtSignal()
    tocLoaded = QtCore.pyqtSignal(list)
    viewportChanged = QtCore.pyqtSignal(str, int, dict)
    zoomRatioChanged = QtCore.pyqtSignal(float)
    viewColumnChanged = QtCore.pyqtSignal(int)
    emptyLeadingPageChanged = QtCore.pyqtSignal(int)

    def __init__(self, parent, render_num=1):
        super(BaseDocGraphicsView, self).__init__(parent)

        # self.setViewport(QtOpenGL.QGLWidget()) # opengl

        self.scene = QtWidgets.QGraphicsScene(self)

        self.current_cursor_x = 0
        self.current_cursor_y = 0

        self.setScene(self.scene)

        self.page_items = [] # instances of PageGraphicsItem
        self.load_finished_flag = False

        self.current_filename = None

        self.page_counts = 0
        self.pages_size_inch = [] # (width, height) in inch, invarient
        self.current_pages_size_pix = [] # varient depends on the view
        self.current_pages_rect = [] # one for flag and 4 for scene coordinates
        self.pageMarkedAsCurrent = 0

        self.current_visible_regions = {}
        self.view_column_count = 1
        self.leading_empty_pages = 0

        self.render_num = render_num
        self.render_list = []
        self.rendered_info = {}
        self.current_rendering_dpi = []
        self.current_highlighted_pages = []

        for i in range(self.render_num):
            tmpRender = PdfRender(Queue(), Queue())
            tmpRender.start()
            self.render_list.append(tmpRender)

        self.screen_dpi = 0

        self.zoom_levels = [0.12, 0.25, 0.33, 0.50, 0.66, 0.75, 1.0, 1.25, 1.5, 2.0, 4.0, 8.0, 16.0]
        self.current_zoom_index = -1
        self.fitwidth_flag = True

        self.horispacing = 3
        self.vertspacing = 5

        self.horizontalScrollBar().valueChanged.connect(self.onScrollValueChanged)
        self.verticalScrollBar().valueChanged.connect(self.onScrollValueChanged)

        self.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAsNeeded)
        self.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOn)

        # self.setRenderHint(QtGui.QPainter.Antialiasing)
        self.setViewportUpdateMode(QtWidgets.QGraphicsView.FullViewportUpdate)
        # self.setViewportUpdateMode(QtWidgets.QGraphicsView.SmartViewportUpdate)
        # self.setViewportUpdateMode(QtWidgets.QGraphicsView.MinimalViewportUpdate)
        self.setDragMode(QtWidgets.QGraphicsView.ScrollHandDrag)

        self.setMouseTracking(True)

        self.setTransform(QtGui.QTransform()) # set identity matrix for transformation

        # handler for croll value changed
        self.scrollValueChanged_flag = False
        self.scrollValueChanged_timer = QtCore.QTimer(self)
        self.scrollValueChanged_timer.timeout.connect(self.scrollValueChangedHandler)
        self.scrollValueChanged_timer.start(20)

        # resize handler
        self.resized_flag = False
        self.resize_timer = QtCore.QTimer(self)
        self.resize_timer.timeout.connect(self.resizeHandler)
        self.resize_timer.start(200)

        # read the queue periodically
        self.queue_timer = QtCore.QTimer(self)
        self.queue_timer.timeout.connect(self.retrieveQueueResults)
        self.queue_timer.start(20)

    def clear(self):
        self.scene.clear()
        self.page_items = []
        self.pages_size_inch = [] # (width, height) in inch, invarient
        self.current_pages_size_pix = [] # varient depends on the view
        self.current_pages_rect = []
        self.pageMarkedAsCurrent = 0
        self.current_visible_regions = {}
        self.current_rendering_dpi = []
        self.rendered_info = {}
        self.current_highlighted_pages = []
        self.load_finished_flag = False

    def setDocument(self, filename, screen_dpi):
        self.clear()

        self.current_filename = filename
        self.screen_dpi = screen_dpi

        # reSET for all render processes
        for rd in self.render_list:
            rd.commandQ.put(['SET', [self.current_filename]])

        # query page size using the first worker
        self.render_list[0].commandQ.put(['PAGESIZES', [None]])

        # query Toc using the first worker
        self.render_list[0].commandQ.put(['TOC', [None]])

    def onPageSizesReceived(self, pages_size_inch):
        debug("%d Page Sizes Received" % len(pages_size_inch))

        # time_0 = time.time()
        self.page_counts = len(pages_size_inch)
        self.pages_size_inch = pages_size_inch

        for i in range(self.page_counts):
            pageItem = PageGraphicsItem(i)
            self.scene.addItem(pageItem)
            self.page_items.append(pageItem)

        self.fitwidth_flag = True
        # time_a = time.time()
        # debug('A', time_a - time_0)

        self.computePagesDPI()
        # time_b = time.time()
        # debug('B', time_b - time_a)

        self.__rearrangePages()
        # time_c = time.time()
        # debug('C', time_c - time_b)

        self.setColumnNumber(min(self.view_column_count, self.page_counts))
        self.leading_empty_pages = 0
        self.emptyLeadingPageChanged.emit(self.leading_empty_pages)
        # 
        self.load_finished_flag = True
        self.onViewportChanged()
        self.loadFinished.emit()

    def onViewportChanged(self):
        self.renderCurrentVisiblePages()
        # 
        # prepare normalized visible regions
        if len(self.current_visible_regions) == 0:
            return
        vRegions = {}
        for pg_no in self.current_visible_regions:
            _, x, y, w, h = self.current_pages_rect[pg_no]
            rect = self.current_visible_regions[pg_no]
            normalized_rect = [rect.x() / w, rect.y()/ h, rect.width() / w, rect.height() / h]
            vRegions[pg_no] = normalized_rect
        self.viewportChanged.emit(self.current_filename, self.page_counts, vRegions)

    def computePagesDPI(self):
        self.current_rendering_dpi = []
        self.current_pages_size_pix =[]
        if self.page_counts == 0:
            return

        if self.fitwidth_flag:
            # all pages will have the same width, but may different height
            viewport = self.viewport()
            viewWidth = viewport.width()
            viewHeight = viewport.height()
            
            viewWidth -= (self.horispacing * (self.view_column_count + 1))
            viewWidth /= self.view_column_count
            
            avg_zLevel = 0 # compute the nearest zoom level for fitting width mode
            for i in range(self.page_counts):
                dpi = viewWidth / self.pages_size_inch[i][0]
                height = self.pages_size_inch[i][1] * dpi
                self.current_rendering_dpi.append(dpi)
                self.current_pages_size_pix.append([int(viewWidth), int(height)])
                # 
                avg_zLevel += (dpi / self.screen_dpi)
            # 
            avg_zLevel /= self.page_counts
            candi_zLevels = np.array(self.zoom_levels)
            diff = np.abs(candi_zLevels - avg_zLevel)
            self.current_zoom_index = np.argmin(diff)
        else:
            zLevel = self.zoom_levels[self.current_zoom_index]
            dpi = self.screen_dpi * zLevel # every page will have the same dpi
            for i in range(self.page_counts):
                width = self.pages_size_inch[i][0] * dpi
                height = self.pages_size_inch[i][1] * dpi
                self.current_rendering_dpi.append(dpi)
                self.current_pages_size_pix.append([int(width), int(height)])

    def getVisibleRegions(self):
        if not self.load_finished_flag:
            return {}

        visRect = self.viewport().rect() # visible area
        visRect = self.mapToScene(visRect).boundingRect() # change to scene coordinates
        # 
        regions = {}
        for pg_no in range(self.page_counts):
            flag, x, y, w, h = self.current_pages_rect[pg_no]
            pageRect = QtCore.QRectF(x, y, w, h)
            intsec = visRect.intersected(pageRect)
            # change to item coordinate
            intsec = QtCore.QRectF(
                intsec.x() - x, intsec.y() - y, 
                intsec.width(), intsec.height()
                )
            if intsec.isEmpty():
                continue
            regions[pg_no] = intsec

        self.current_visible_regions = regions

    def renderRequest(self, page_no, dpi, roi, render_idx, visible_regions):
        self.render_list[render_idx].commandQ.put(['RENDER', [page_no, dpi, roi, visible_regions]])

    def initializePage(self, page_no):
        if not self.current_pages_rect[page_no][0]:
            _, x, y, w, h = self.current_pages_rect[page_no]
            self.page_items[page_no].initialize(x, y, w, h)
            self.current_pages_rect[page_no][0] = True

    def renderCurrentVisiblePages(self):
        self.getVisibleRegions()

        if len(self.current_visible_regions) == 0:
            return

        # debug("Visible Regions: ", self.current_visible_regions)
        
        # update the cached images for visible pages first (for smoothing transitions)
        for page_no in self.current_visible_regions:
            # initilize page first
            self.initializePage(page_no)
            self.page_items[page_no].updateTransientItems(self.current_visible_regions[page_no])

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

                # debug("<- Render %d Requested : <page:%d> <dpi:%.2f> <roi_raw: %.1f %.1f %.1f %.1f> <roi: %.1f %.1f %.1f %.1f>" % (
                #     render_idx, page_no, dpi, 
                #     roi_raw.left(), roi_raw.top(), roi_raw.width(), roi_raw.height(), 
                #     roi.left(), roi.top(), roi.width(), roi.height()
                #     ))

    def handleSingleRenderedImage(self, render_idx, filename, page_no, dpi, roi, img_byte_array):
        # debug("-> Rendering %d Completed : <page:%d> <dpi:%.2f> <roi: %.1f %.1f %.1f %.1f>" % (
        #     render_idx, page_no, dpi, roi.left(), roi.top(), roi.width(), roi.height()
        # ))

        # if page_no not in self.current_visible_regions:
        #     debug("become unvisible: %d. skipping" % page_no)
        #     return
        
        if page_no in self.rendered_info \
           and self.rendered_info[page_no][0] == dpi \
           and roi in self.rendered_info[page_no][1]:
            # debug("duplicated rendering. skipping")
            return

        if len(self.current_rendering_dpi) == 0:
            return
        # too late, the current rendering dpi is already changed
        if dpi != self.current_rendering_dpi[page_no]:
            # debug("unmatched DPI: %.2f -> %.2f. skipping" % (dpi, self.current_rendering_dpi[page_no]))
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
                message = item[0]
                filename = item[1]
                if filename != self.current_filename: # the doc has changed, too late
                    continue
                # 
                if message == 'PAGESIZES_RES':
                    pages_size_inch = item[2]
                    self.onPageSizesReceived(pages_size_inch)
                if message == 'TOC_RES':
                    toc = item[2]
                    self.tocLoaded.emit(toc)
                elif message == 'RENDER_RES':
                    page_no, dpi, roi, img_byte_array = item[2:]
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

        self.current_pages_rect = []
        for i in range(self.page_counts):
            row = int((i + self.leading_empty_pages) / self.view_column_count)
            col = int((i + self.leading_empty_pages) % self.view_column_count)

            startx = colCumWidths[col - 1] if col > 0 else 0
            starty = rowCumHeights[row - 1] if row > 0 else 0

            # add spacing 
            startx += (self.horispacing * (col + 1))
            starty += (self.vertspacing * (row + 1))

            # center it
            startx += (colWidths[col] - pages_width_pix[row][col]) / 2
            starty += (rowHeights[row] - pages_height_pix[row][col]) / 2

            # save page rect, False means uninitialized
            self.current_pages_rect.append([False, startx, starty, pages_width_pix[row][col], pages_height_pix[row][col]])
            
            # make all pages invisible first
            self.page_items[i].setVisible(False)

        sceneWidthFix = colWidths.sum() + (self.view_column_count + 1) * self.horispacing
        sceneHeightFix = rowHeights.sum() + (rowNum + 1) * self.vertspacing
        self.scene.setSceneRect(0, 0, sceneWidthFix, sceneHeightFix)
        
        # after rearrangement, the cached rendering information is useless
        # that means, everything should be re-rendered
        self.rendered_info = {}

    def centerOnPage(self, page_no, x_ratio, y_ratio):
        _, x, y, w, h = self.current_pages_rect[page_no]
        cx = x + x_ratio * w
        cy = y + y_ratio * h
        self.centerOn(cx, cy)

    def getPageByPos(self, view_x, view_y):
        item = self.itemAt(view_x, view_y)
        if item:
            item = item.parentItem() if item.parentItem() else item
            assert(isinstance(item, PageGraphicsItem))
            page_no_cursor_at = self.page_items.index(item)
        else:
            # at empty places, find the nearest page
            scene_pos = self.mapToScene(view_x, view_y)
            page_rects = np.array(self.current_pages_rect)[:, 1:]
            pages_cx = page_rects[:, 0] + page_rects[:, 2] / 2
            pages_cy = page_rects[:, 1] + page_rects[:, 3] / 2
            distance = np.abs(pages_cx - scene_pos.x()) + np.abs(pages_cy - scene_pos.y()) # L1 distance is enough
            page_no_cursor_at = np.argmin(distance)
        # 
        _, x, y, w, h = self.current_pages_rect[page_no_cursor_at]
        cursor_in_scene = self.mapToScene(self.current_cursor_x, self.current_cursor_y)
        x_ratio = (cursor_in_scene.x() - x) / w # the relative position
        y_ratio = (cursor_in_scene.y() - y) / h

        return page_no_cursor_at, x_ratio, y_ratio

    def redrawPages(self):
        if self.page_counts == 0 or len(self.current_pages_rect) == 0:
            return

        # time_0 = time.time()

        # save previous cursor position
        page_no_cursor_at, x_ratio, y_ratio = self.getPageByPos(
            self.current_cursor_x, self.current_cursor_y
            )
        viewRect = self.viewport()
        dx_center = viewRect.width() / 2 - self.current_cursor_x
        dy_center = viewRect.height() / 2 - self.current_cursor_y

        # compute DPI
        self.computePagesDPI()
        # time_a = time.time()
        # debug("A ", time_a - time_0)

        self.__rearrangePages()
        # time_b = time.time()
        # debug("B ", time_b - time_a)

        # set viewport after rearranging (make page position under cursor unchanged)
        _, new_x, new_y, new_w, new_h = self.current_pages_rect[page_no_cursor_at]
        scene_cx = new_x + x_ratio * new_w + dx_center
        scene_cy = new_y + y_ratio * new_h + dy_center
        self.centerOn(scene_cx, scene_cy)

        self.onViewportChanged()

    def setColumnNumber(self, colNum):
        if self.page_counts > 0:
            self.view_column_count = min(self.page_counts, colNum)
            if self.view_column_count == 1:
                self.leading_empty_pages = 0
                self.emptyLeadingPageChanged.emit(0)
            self.redrawPages()
            self.viewColumnChanged.emit(self.view_column_count)

    def setPrecedingEmptyPage(self, emptyPage):
        if self.page_counts > 0:
            if self.view_column_count > 1 and emptyPage == 1:
                self.leading_empty_pages = 1
            else:
                self.leading_empty_pages = 0
            self.redrawPages()
            self.emptyLeadingPageChanged.emit(self.leading_empty_pages)

    def zoomIn(self):
        if self.current_zoom_index == len(self.zoom_levels) - 1:
            return
        self.current_zoom_index += 1
        self.fitwidth_flag = False
        self.redrawPages()
        self.zoomRatioChanged.emit(self.zoom_levels[self.current_zoom_index])

    def zoomOut(self):
        if self.current_zoom_index == 0:
            return
        self.current_zoom_index -= 1
        self.fitwidth_flag = False
        self.redrawPages()
        self.zoomRatioChanged.emit(self.zoom_levels[self.current_zoom_index])

    def zoomFitWidth(self):
        self.fitwidth_flag = True
        self.redrawPages()
        self.zoomRatioChanged.emit(0)

    def goPrevPage(self):
        if len(self.current_visible_regions) == 0:
            return
        curent_page_idx = next(iter(self.current_visible_regions)) # first key as the current
        self.gotoPage(curent_page_idx - self.view_column_count)

    def goNextPage(self):
        if len(self.current_visible_regions) == 0:
            return
        curent_page_idx = next(iter(self.current_visible_regions)) # first key as the current
        self.gotoPage(curent_page_idx + self.view_column_count)

    def gotoPage(self, pg_no):
        # make the page as the first visible one (it can not guarantee for multi-column cases)
        if not self.load_finished_flag:
            return
        visRect = self.viewport().rect() # visible area
        visRect = self.mapToScene(visRect).boundingRect() # change to scene coordinates
        flag, x, y, w, h = self.current_pages_rect[pg_no]
        scene_cx = x + visRect.width() / 2
        scene_cy = y + visRect.height() / 2
        self.centerOn(scene_cx, scene_cy)

    # def showEvent(self, ev):
    #     debug('showEvent in BaseDocGraphicsView')
    #     ev.ignore()

    def closeEvent(self, ev):
        debug('closeEvent in BaseDocGraphicsView')
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

    def onScrollValueChanged(self):
        self.scrollValueChanged_flag = True

    def scrollValueChangedHandler(self):
        if self.scrollValueChanged_flag:
            self.onViewportChanged()
            self.scrollValueChanged_flag = False

    def resizeHandler(self):
        if self.resized_flag:
            self.redrawPages()
            self.resized_flag = False

    def resizeEvent(self, ev):
        # debug('resizeEvent in BaseDocGraphicsView')
        self.resized_flag = True
        # call the parent's handler, it will do some alignments
        return super().resizeEvent(ev)

    def mousePressEvent(self, ev):
        # debug('mousePressEvent in BaseDocGraphicsView')
        return super().mousePressEvent(ev)

    def mouseReleaseEvent(self, ev):
        # debug('mouseReleaseEvent in BaseDocGraphicsView')
        return super().mouseReleaseEvent(ev)

    def mouseMoveEvent(self, ev):
        # debug('mouseMoveEvent in BaseDocGraphicsView')
        self.current_cursor_x = ev.x()
        self.current_cursor_y = ev.y()
        # debug(self.current_cursor_x, self.current_cursor_y)
        return super().mouseMoveEvent(ev)
