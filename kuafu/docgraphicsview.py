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
import numpy as np

class DocGraphicsView(QtWidgets.QGraphicsView):
    pagePositionChanged = QtCore.pyqtSignal(int, int)

    def __init__(self, parent):
        super(DocGraphicsView, self).__init__(parent)

        # self.setViewport(QtOpenGL.QGLWidget()) # opengl

        self.scene = QtWidgets.QGraphicsScene(self)
        self.scene.setBackgroundBrush(QtGui.QBrush(QtCore.Qt.gray)) # set gray background

        self.current_cursor_x = 0
        self.current_cursor_y = 0

        self.setScene(self.scene)

        self.page_items = [] # instances of PageGraphicsItem

        self.doc = None
        self.current_filename = None

        self.page_counts = 0
        self.pages_size_inch = [] # (width, height) in inch, invarient
        self.current_pages_size_pix = [] # varient depends on the view

        self.current_page = 0
        self.current_visible_regions = {}
        self.view_column_count = 1
        self.leading_empty_pages = 0

        self.render_num = 1
        self.render_list = []
        self.rendered_info = {}
        self.current_rendering_dpi = []

        for i in range(self.render_num):
            tmpRender = PdfRender(Queue(), Queue())
            tmpRender.start()
            self.render_list.append(tmpRender)

        self.fitwidth_flag = True
        self.screen_dpi = 0

        self.horispacing = 7
        self.vertspacing = 7

        self.horizontalScrollBar().valueChanged.connect(self.onScrolling)
        self.verticalScrollBar().valueChanged.connect(self.onScrolling)

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
        self.queue_timer.timeout.connect(self.receivedRenderedImage)
        self.queue_timer.start(50)

    def clear(self):
        self.scene.clear() # clear all items
        self.pages_size_inch = [] # (width, height) in inch, invarient
        self.current_pages_size_pix = [] # varient depends on the view
        self.page_items = [] # instances of parent item
        self.visible_pages = []
        self.current_rendering_dpi = []
        self.rendered_info = {}

    def setDocument(self, filename, screen_dpi):
        self.clear()

        self.current_filename = filename
        # self.doc = fitz.open(filename)
        # self.page_counts = len(self.doc)

        password = ""
        self.doc = Poppler.Document.load(self.current_filename, password.encode(), password.encode())
        self.doc.setRenderHint(
            Poppler.Document.TextAntialiasing
            | Poppler.Document.TextHinting
            | Poppler.Document.Antialiasing
            )
        self.page_counts = self.doc.numPages()
        self.screen_dpi = screen_dpi
        
        # extract page sizes for all pages
        for i in range(self.page_counts):
            # dlist = self.doc[i].getDisplayList()
            # pg_width = dlist.rect.width / 72.0
            # pg_height = dlist.rect.height / 72.0
            pg_width = self.doc.page(i).pageSizeF().width() / 72.0 # width in inch
            pg_height = self.doc.page(i).pageSizeF().height() / 72.0
            self.pages_size_inch.append([pg_width, pg_height])

        # reSET for all render processes
        for rd in self.render_list:
            rd.commandQ.put(['SET', [self.current_filename]])

        # put all pages on scene (empty now)
        for i in range(self.page_counts):
            pageItem = PageGraphicsItem()
            self.scene.addItem(pageItem)
            self.page_items.append(pageItem)

        self.fitwidth_flag = True
        self.computePagesDPI(self.viewport().width())
        self.__rearrangePages()
        self.renderCurrentVisiblePages()
        self.pagePositionChanged.emit(self.current_page, self.page_counts)

    def onScrolling(self):
        self.renderCurrentVisiblePages()
        self.pagePositionChanged.emit(self.current_page, self.page_counts)

    def computePagesDPI(self, viewPixelWidth):
        if self.fitwidth_flag:
            # all pages will have the same width, but may different height
            self.current_rendering_dpi = []
            self.current_pages_size_pix =[]

            viewPixelWidth -= (self.horispacing * (self.view_column_count + 1))
            viewPixelWidth /= self.view_column_count
            
            for i in range(self.page_counts):
                dpi = viewPixelWidth / self.pages_size_inch[i][0]
                height = self.pages_size_inch[i][1] * dpi
                self.current_rendering_dpi.append(dpi)
                self.current_pages_size_pix.append([int(viewPixelWidth), int(height)])
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

    def renderCurrentVisiblePages(self):

        self.getVisibleRegions()

        if len(self.current_visible_regions) == 0:
            return

        # first key as current page
        self.current_page = next(iter(self.current_visible_regions))

        for page_no in self.current_visible_regions:
            if page_no in self.rendered_info:
                dpi, roi = self.rendered_info[page_no]
                dpi_r = self.current_rendering_dpi[page_no]
                if page_no in self.current_visible_regions:
                    roi_r = self.current_visible_regions[page_no]
                    if dpi == dpi_r and roi.contains(roi_r):
                        continue
            self.renderRequest(page_no, self.current_rendering_dpi[page_no], self.current_visible_regions[page_no])

    def handleSingleRenderedImage(self, filename, page_no, dpi, roi, img_byte_array):
        debug("-> Rendering Completed : <page:%d> <dpi:%.1f> <roi: %d %d %d %d>" % (page_no, dpi, roi.left(), roi.top(), roi.width(), roi.height()))

        # the doc has changed, too late
        if filename != self.current_filename:
            debug("file name changed: %s -> %s. skipping" % (filename, self.current_filename))
            return

        if page_no in self.rendered_info and self.rendered_info[page_no] == dpi:
            debug("duplicated rendering. skipping")
            return

        if page_no not in self.current_visible_regions:
            debug("become unvisible: %d. skipping" % page_no)
            return

        # check if the rendering info is matched
        if dpi != self.current_rendering_dpi[page_no] :
            debug("unmatched DPI: %.1f -> %.1f. skipping" % (dpi, self.current_rendering_dpi[page_no]))
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

        self.page_items[page_no].setPixmap(QtGui.QPixmap.fromImage(image), roi.x(), roi.y())

        self.rendered_info[page_no] = [dpi, roi]

        # # Request to render next page
        # if self.current_page <= page_no < (self.current_page + self.max_preload - 2):
        #     if (page_no+2 not in self.rendered_pages) and (page_no+2 <= self.pages_count):
        #       self.renderRequested.emit(page_no+2, self.pages[page_no+1].dpi)
        # Replace old rendered pages with blank image

        if len(self.rendered_info) > 10:
            self.getVisibleRegions() # update visible regions again
            firstKey = next(iter(self.rendered_info))
            if self.current_visible_regions is None or firstKey not in self.current_visible_regions:
                self.rendered_info.pop(firstKey)
                debug("Clear Page :", firstKey)
                self.page_items[firstKey].clear()

        # debug("Rendered Images: ", self.rendered_pages)

    def receivedRenderedImage(self):
        for rd in self.render_list:
            resultsQ = rd.resultsQ
            # collect all results
            size = resultsQ.qsize()
            for i in range(size):
                item = resultsQ.get() # will be blocked until when some data are avaliable
                filename, page_no, dpi, roi, img_byte_array = item
                self.handleSingleRenderedImage(filename, page_no, dpi, roi, img_byte_array)

    def renderRequest(self, page_no, dpi, roi):
        # refine the roi for better visual performance
        if self.current_pages_size_pix[page_no][0] < 1024:
            # render full image for small sizes
            roi.setCoords(0, 0, 
                self.current_pages_size_pix[page_no][0], 
                self.current_pages_size_pix[page_no][1])
        else:
            # enlarge the roi for smooth reading
            horiExt = 0
            vertExt = 0
            x1 = max(0, roi.x() - horiExt)
            y1 = max(0, roi.y() - vertExt)
            x2 = min(self.current_pages_size_pix[page_no][0], roi.x() + roi.width() + horiExt)
            y2 = min(self.current_pages_size_pix[page_no][1], roi.y() + roi.height() + vertExt)
            roi.setCoords(x1, y1, x2, y2)

        tgtWorkerIdx = page_no % self.render_num
        self.render_list[tgtWorkerIdx].commandQ.put(['RENDER', [page_no, dpi, roi, self.current_visible_regions]])
        debug("<- Render %d Requested : <page:%d> <dpi:%.1f> <roi: %d %d %d %d>" % (
            tgtWorkerIdx, page_no, dpi, roi.left(), roi.top(), roi.width(), roi.height()))

    def __rearrangePages(self):
        if self.doc is None:
            return

        self.getVisibleRegions()

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

        for i in range(self.page_counts):
            row = int((i + self.leading_empty_pages) / self.view_column_count)
            col = int((i + self.leading_empty_pages) % self.view_column_count)
            startx = colWidths[:col].sum()
            starty = rowHeights[:row].sum()
            
            startx += (self.horispacing * (col + 1))
            starty += (self.vertspacing * (row + 1))

            # center it
            startx += (colWidths[col] - pages_width_pix[row][col]) / 2
            starty += (rowHeights[row] - pages_height_pix[row][col]) / 2

            if i in self.current_visible_regions:
                self.page_items[i].setSize(pages_width_pix[row][col], pages_height_pix[row][col], transition=True)
            else:
                self.page_items[i].setSize(pages_width_pix[row][col], pages_height_pix[row][col], transition=False)
            self.page_items[i].setPosition(startx, starty)

        sceneWidthFix = colWidths.sum() + (self.view_column_count + 1) * self.horispacing
        sceneHeightFix = rowHeights.sum() + (rowNum + 1) * self.vertspacing
        self.scene.setSceneRect(0, 0, sceneWidthFix, sceneHeightFix)

    def __resizePages(self, ratio):

        # make sure the page size will not be too large or too small
        firstPageDpi = self.current_rendering_dpi[0] * ratio
        if firstPageDpi < 5 or firstPageDpi > 1200:
            return

        # save previous cursor position
        viewRect = self.viewport()
        cursor_in_scene = self.mapToScene(self.current_cursor_x, self.current_cursor_y)
        scene_cx = cursor_in_scene.x() * ratio - (self.current_cursor_x - viewRect.width() / 2)
        scene_cy = cursor_in_scene.y() * ratio - (self.current_cursor_y - viewRect.height() / 2)

        for i in range(self.page_counts):
            self.current_pages_size_pix[i][0] *= ratio
            self.current_pages_size_pix[i][1] *= ratio
            self.current_rendering_dpi[i] *= ratio

        self.__rearrangePages()
        
        # set viewport
        self.centerOn(scene_cx, scene_cy)

        self.renderCurrentVisiblePages()

    def setColumnNumber(self, colNum):
        if self.page_counts > 0:
            self.view_column_count = min(self.page_counts, colNum)
            self.computePagesDPI(self.viewport().width())
            self.__rearrangePages()
            self.renderCurrentVisiblePages()
            return True
        else:
            return False

    def setPrecedingEmptyPage(self, emptyPages):
        if self.view_column_count > 1:
            self.leading_empty_pages = emptyPages
            self.computePagesDPI(self.viewport().width())
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
        self.computePagesDPI(self.viewport().width())
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
        debug('resizeEvent in DocGraphicsView')
        debug(self.width(), self.height())
        # 
        self.computePagesDPI(self.viewport().width())
        self.__rearrangePages()
        self.renderCurrentVisiblePages()

        # call the parent's handler, it will do some alignments
        super().resizeEvent(ev)

    def wheelEvent(self, ev):
        # debug("wheelEvent in DocGraphicsView")
        modifiers = QtWidgets.QApplication.keyboardModifiers()
        if modifiers == QtCore.Qt.ControlModifier:
            debug(self.transform().m11(), self.transform().m22())
            delta = ev.angleDelta()
            if delta.y() > 0:
                self.__resizePages(1.2)
            else:
                self.__resizePages(0.8)
            self.fitwidth_flag = False
            ev.accept() # accept an event in order to stop it from propagating further
        else:
            super().wheelEvent(ev) # call parent's handler

    # def mousePressEvent(self, ev):
    #     debug('mousePressEvent in DocGraphicsView')

    # def mouseReleaseEvent(self, ev):
    #     debug('mouseReleaseEvent in DocGraphicsView')

    # def mouseDoubleClickEvent(self, ev):
    #     debug('mouseDoubleClickEvent in DocGraphicsView')

    def mouseMoveEvent(self, ev):
        # debug('mouseMoveEvent in DocGraphicsView')
        self.current_cursor_x = ev.x()
        self.current_cursor_y = ev.y()
        # debug(self.current_cursor_x, self.current_cursor_y)
        super().mouseMoveEvent(ev)
