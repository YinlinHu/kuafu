from PyQt5 import QtWidgets
from PyQt5 import QtCore
from PyQt5 import QtGui
from PyQt5 import QtOpenGL

# import fitz #PyMuPDF
from popplerqt5 import Poppler

from pdfworker import PdfRender
from multiprocessing import Queue

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

        self.setScene(self.scene)

        self.page_items = [] # instances of parent item
        self.page_pixmap_items = []
        self.page_mask_items = []

        self.cached_page_width = 100 # 1K pages will use about 30M, rather safe for a modern computer
        self.cached_page_images = []

        self.doc = None
        self.filename = None

        self.page_counts = 0
        self.pages_size_inch = [] # (width, height) in inch, invarient
        self.pages_size_pix = [] # varient depends on the view

        self.current_page = 0
        self.visible_pages = []
        self.visible_regions = []
        self.view_column_count = 1
        self.leading_empty_pages = 0

        self.render_num = 4
        self.render_list = []
        self.rendered_pages = {}

        for i in range(self.render_num):
            tmpRender = PdfRender(Queue(), Queue())
            tmpRender.start()
            self.render_list.append(tmpRender)

        self.zoom_fitwidth = True
        self.screen_dpi = 0
        self.pages_dpi = []

        self.horispacing = 4
        self.vertspacing = 4

        self.horizontalScrollBar().valueChanged.connect(self.onScrolling)
        self.verticalScrollBar().valueChanged.connect(self.onScrolling)

        self.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOn)

        # self.setRenderHint(QtGui.QPainter.Antialiasing)
        self.setViewportUpdateMode(QtWidgets.QGraphicsView.FullViewportUpdate)
        # self.setViewportUpdateMode(QtWidgets.QGraphicsView.SmartViewportUpdate)
        # self.setViewportUpdateMode(QtWidgets.QGraphicsView.MinimalViewportUpdate)
        self.setDragMode(QtWidgets.QGraphicsView.ScrollHandDrag)
        self.setTransformationAnchor(QtWidgets.QGraphicsView.AnchorUnderMouse)

        self.setTransform(QtGui.QTransform()) # set identity matrix for transformation

        # handle the resize event slowly
        self.resized_flag = False
        self.resize_timer = QtCore.QTimer(self)
        self.resize_timer.timeout.connect(self.resizeTrigger)
        self.resize_timer.start(3000)

        # read the queue periodically
        self.queue_timer = QtCore.QTimer(self)
        self.queue_timer.timeout.connect(self.receivedRenderedImage)
        self.queue_timer.start(10)

    def clear(self):
        self.scene.clear() # clear all items
        self.pages_size_inch = [] # (width, height) in inch, invarient
        self.pages_size_pix = [] # varient depends on the view
        self.page_items = [] # instances of parent item
        self.page_pixmap_items = []
        self.page_mask_items = []
        self.visible_pages = []
        self.pages_dpi = []
        self.rendered_pages = {}

    def setDocument(self, filename, screen_dpi):
        self.clear()

        self.filename = filename
        # self.doc = fitz.open(filename)
        # self.page_counts = len(self.doc)

        password = ""
        self.doc = Poppler.Document.load(self.filename, password.encode(), password.encode())
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
            rd.commandQ.put(['SET', [self.filename]])

        # clear cache
        self.cached_page_images = []
        for i in range(self.page_counts):
            self.cached_page_images.append(None)

        # put all pages on scene (empty now)
        for i in range(self.page_counts):
            item = QtWidgets.QGraphicsRectItem()
            item.setRect(0, 0, 0, 0)
            item.setPos(0, 0)

            # pen = QtGui.QPen(QtCore.Qt.NoPen) # remove rect border
            pen = QtGui.QPen(QtCore.Qt.black)
            pen.setWidth(1)
            # item.setPen(pen)
            item.setBrush(QtCore.Qt.white) # fill white color

            self.scene.addItem(item)

            # pixmap
            pixmapItem = QtWidgets.QGraphicsPixmapItem(QtGui.QPixmap())
            pixmapItem.setOffset(1, 1) # leave border space
            pixmapItem.setParentItem(item)

            # mask
            maskItem = QtWidgets.QGraphicsRectItem()
            maskItem.setRect(0, 0, 0, 0)

            pen = QtGui.QPen(QtCore.Qt.yellow)
            pen.setWidth(1)
            maskItem.setPen(pen)
            maskItem.setBrush(QtGui.QBrush(QtGui.QColor(0, 0, 0, 100))) # fill color

            maskItem.setParentItem(item)

            # 
            item.setZValue(0)
            pixmapItem.setZValue(1)
            maskItem.setZValue(2)

            self.page_items.append(item)
            self.page_pixmap_items.append(pixmapItem)
            self.page_mask_items.append(maskItem)

        self.computePagesDPI(self.viewport().width())
        self.__rearrangePages()
        self.pagePositionChanged.emit(self.current_page, self.page_counts)

    def onScrolling(self):
        self.renderCurrentVisiblePages()
        self.pagePositionChanged.emit(self.current_page, self.page_counts)

    def computePagesDPI(self, viewPixelWidth):
        self.pages_dpi = []
        self.pages_size_pix =[]

        if self.zoom_fitwidth:
            # all pages will have the same width, but may different height
            viewPixelWidth -= (self.horispacing * (self.view_column_count + 1))
            viewPixelWidth /= self.view_column_count

            for i in range(self.page_counts):
                dpi = viewPixelWidth / self.pages_size_inch[i][0]
                height = self.pages_size_inch[i][1] * dpi
                self.pages_dpi.append(dpi)
                self.pages_size_pix.append([int(viewPixelWidth), int(height)])
        else:
            for i in range(self.page_counts):
                dpi = 30
                width = self.pages_size_inch[i][0] * dpi
                height = self.pages_size_inch[i][1] * dpi
                self.pages_dpi.append(dpi)
                self.pages_size_pix.append([int(width), int(height)])

    def getVisibleRegions(self):
        # visRect = self.rect() # visible area (with scrollbars)
        visRect = self.viewport().rect() # visible area (without scrollbars)
        if visRect.isEmpty():
            return None

        visRect = self.mapToScene(visRect).boundingRect() # change to scene coordinates
        # 
        regions = []
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
            regions.append(intsec)
        return regions
            
    def getVisiblePages(self):
        self.visible_regions = self.getVisibleRegions()
        if self.visible_regions is None:
            return []
        visible_pages = []
        for pg_no in range(self.page_counts):
            if not self.visible_regions[pg_no].isEmpty():
                visible_pages.append(pg_no)
        return visible_pages

    def renderCurrentVisiblePages(self):
        self.visible_pages = self.getVisiblePages()
        # debug("Visible Pages: ", self.visible_pages)

        if len(self.visible_pages) == 0:
            return

        if self.current_page != self.visible_pages[0]:
            self.current_page = self.visible_pages[0]

        for page_no in self.visible_pages:
            if page_no < 0 or page_no >= self.page_counts:
                continue
            if page_no in self.rendered_pages and abs(self.rendered_pages[page_no] - self.pages_dpi[page_no]) < 1:
                continue
            self.renderRequest(page_no, self.pages_dpi[page_no])

    def handleSingleRenderedImage(self, filename, page_no, dpi, img_byte_array):
        debug("-> Rendering Completed : <page:%d> <dpi:%.1f>" % (page_no, dpi))

        # the doc has changed, too late
        if filename != self.filename:
            debug("%s -> %s: skipped" % (filename, self.filename))
            return

        if page_no in self.rendered_pages and self.rendered_pages[page_no] == dpi:
            debug("duplicated rendering")
            return
            
        # QByteArray to QImage
        img_buffer = QtCore.QBuffer(img_byte_array)
        img_buffer.open(QtCore.QIODevice.ReadOnly)
        image = QtGui.QImageReader(img_buffer).read()

        debug("dim: <%d x %d>" % (image.width(), image.height()))

        # crop to container's size
        containerSize = self.page_items[page_no].rect()
        roi = QtCore.QRect(1,1,containerSize.width()-2, containerSize.height()-2)
        image = image.copy(roi)
        self.page_pixmap_items[page_no].setPixmap(QtGui.QPixmap.fromImage(image))

        self.rendered_pages[page_no] = dpi

        # save to cache 
        if self.cached_page_images[page_no] is None:
            self.cached_page_images[page_no] = image.scaledToWidth(self.cached_page_width)

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
                debug("Clear Page :", firstKey)
                self.page_pixmap_items[firstKey].setPixmap(QtGui.QPixmap())

        # debug("Rendered Images: ", self.rendered_pages)

    def receivedRenderedImage(self):
        for rd in self.render_list:
            resultsQ = rd.resultsQ
            while not resultsQ.empty(): # check if there is data
                item = resultsQ.get() # will be blocked until when some data are avaliable
                filename, page_no, dpi, img_byte_array = item
                self.handleSingleRenderedImage(filename, page_no, dpi, img_byte_array)

    def renderRequest(self, page_no, dpi):
        tgtWorkerIdx = page_no % self.render_num
        self.render_list[tgtWorkerIdx].commandQ.put(['RENDER', [page_no, dpi, self.visible_pages]])
        debug("<- Render %d Requested : <page:%d> <dpi:%.1f>" % (tgtWorkerIdx, page_no, dpi))

    def __rearrangePages(self):
        if self.doc is None:
            return

        pages_width_pix = np.array(self.pages_size_pix)[:, 0]
        pages_height_pix = np.array(self.pages_size_pix)[:, 1]

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

            self.__setPageSize(i, pages_width_pix[row][col], pages_height_pix[row][col])
            self.__setPagePosition(i, startx, starty)

        sceneWidthFix = colWidths.sum() + (self.view_column_count + 1) * self.horispacing
        sceneHeightFix = rowHeights.sum() + (rowNum + 1) * self.vertspacing
        self.scene.setSceneRect(0, 0, sceneWidthFix, sceneHeightFix)

        # 
        self.renderCurrentVisiblePages()

    def __setPageSize(self, idx, width, height):
        # check the page size that if it is readlly changed
        rawRect = self.page_items[idx].rect()
        if rawRect.width() == width and rawRect.height() == height:
            return

        self.page_items[idx].setRect(0, 0, width, height)
        self.page_mask_items[idx].setRect(0,0,0,0)
        
        pixmap = self.page_pixmap_items[idx].pixmap()
        if not pixmap.isNull():
            # cached_image = cached_image.scaled(width-2, height-2)
            # tmp_pixmap = QtGui.QPixmap.fromImage(cached_image)
            # self.page_pixmap_items[idx].setPixmap(tmp_pixmap) # tmporary image showing, need update
            self.page_pixmap_items[idx].setPixmap(QtGui.QPixmap())

            # clear the rendered flag
            if idx in self.rendered_pages:
                self.rendered_pages.pop(idx)

    def __setPagePosition(self, idx, x, y):
        self.page_items[idx].setPos(x, y)

    def __resizePages(self, ratio):
        sceneRect = self.sceneRect() # save raw rect

        self.computePagesDPI(sceneRect.width() * ratio)

        for i in range(self.page_counts):
            # 
            width = self.page_items[i].rect().width()
            height = self.page_items[i].rect().height()
            x = self.page_items[i].scenePos().x()
            y = self.page_items[i].scenePos().y()

            x *= ratio
            y *= ratio
            width *= ratio
            height *= ratio

            self.__setPageSize(i, width, height)
            self.__setPagePosition(i, x, y)

        self.scene.setSceneRect(0, 0, sceneRect.width()*ratio, sceneRect.height()*ratio)

    def setColumnNumber(self, colNum):
        if colNum != self.view_column_count:
            self.view_column_count = colNum
            self.computePagesDPI(self.viewport().width())
            self.__rearrangePages()

    def setPrecedingEmptyPage(self, emptyPages):
        if emptyPages != self.leading_empty_pages:
            self.leading_empty_pages = emptyPages
            self.computePagesDPI(self.viewport().width())
            self.__rearrangePages()

    def zoomIn(self):
        self.__resizePages(1.2)

    def zoomOut(self):
        self.__resizePages(0.8)

    def zoomFitWidth(self):
        self.zoom_fitwidth = True
        self.computePagesDPI(self.viewport().width())
        self.__rearrangePages()

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
        self.resized_flag = True
        # 
        # the parent handler will do the centering
        QtWidgets.QGraphicsView.resizeEvent(self, ev)

    def resizeTrigger(self):
        if self.resized_flag == True:
            ratio = self.transform().m11()
            debug(ratio)
            self.__resizePages(ratio) # real scaling (rearrange and redraw)
            self.setTransform(QtGui.QTransform()) # no scaling after rearrange
            # 
            self.resized_flag = False

    def wheelEvent(self, ev):
        # debug("wheelEvent in DocGraphicsView")
        modifiers = QtWidgets.QApplication.keyboardModifiers()
        if modifiers == QtCore.Qt.ControlModifier:
            debug(self.transform().m11(), self.transform().m22())
            delta = ev.angleDelta()
            if delta.y() > 0:
                self.scale(1.2, 1.2) # inital scaling (fast)
                self.resized_flag = True
            else:
                self.scale(0.8, 0.8)
                self.resized_flag = True
            ev.accept() # accept an event in order to stop it from propagating further
        else:
            QtWidgets.QGraphicsView.wheelEvent(self, ev) # call parent's handler

    # def mousePressEvent(self, ev):
    #     debug('mousePressEvent in DocGraphicsView')

    # def mouseReleaseEvent(self, ev):
    #     debug('mouseReleaseEvent in DocGraphicsView')

    # def mouseDoubleClickEvent(self, ev):
    #     debug('mouseDoubleClickEvent in DocGraphicsView')

    # def mouseMoveEvent(self, ev):
    #     debug('mouseMoveEvent in DocGraphicsView')
