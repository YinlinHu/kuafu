from PyQt5 import QtCore
from PyQt5 import QtGui
from multiprocessing import Process, Queue
from utils import debug
import time
import cv2
import numpy as np

# https://hzqtc.github.io/2012/04/poppler-vs-mupdf.html
# MuPDF is much faster at rendering, but slower at loading (get_page_sizes()) and also use more memories
# 
# PyMuPDF will freeze when zoom at 1600% for some files 
# PyMuPDF will fail in opening some files

PDF_BACKEND = 'PDFIUM'
# PDF_BACKEND = 'POPPLER'
# PDF_BACKEND = 'MUPDF'

if PDF_BACKEND == 'PDFIUM':
    # follow https://github.com/BlockSigner/wowpng, and https://github.com/bblanchon/pdfium-binaries
    import ctypes
    import pypdfium as PDFIUM
    PDFIUM.FPDF_InitLibraryWithConfig(PDFIUM.FPDF_LIBRARY_CONFIG(2, None, None, 0))

elif PDF_BACKEND == 'POPPLER':
    from popplerqt5 import Poppler

elif PDF_BACKEND == 'MUPDF':
    import fitz # PyMuPDF

class PdfInternalWorker(Process):

    # considering realtime, the request may be dropped
    # rendered = QtCore.pyqtSignal(str, int, float, QtGui.QImage)

    def __init__(self, commandQ, resultsQ):
        super(PdfInternalWorker, self).__init__()
        #
        self.commandQ = commandQ
        self.resultsQ = resultsQ

        self.doc = None
        self.filename = None
        # 
        # self.painter = QtGui.QPainter()
        # self.link_color = QtGui.QColor(0,0,127, 40)
        # 
        self.exit_flag = False

        self.requests_queue = {}
        
        # self.mutex = QtCore.QMutex()

    def set_document(self, filename):
        self.filename = filename
        self.requests_queue = {}
        if PDF_BACKEND == 'PDFIUM':
            self.doc = PDFIUM.FPDF_LoadDocument(self.filename, None)
        elif PDF_BACKEND == 'POPPLER':
            password = ''
            self.doc = Poppler.Document.load(self.filename, password.encode(), password.encode())
            self.doc.setRenderHint(
                Poppler.Document.TextAntialiasing
                | Poppler.Document.TextHinting
                | Poppler.Document.Antialiasing
                )
        elif PDF_BACKEND == 'MUPDF':
            self.doc = fitz.open(self.filename)

    def get_page_sizes_mupdf(self, doc):
        pages_size_inch = []
        page_counts = len(doc)
        for i in range(page_counts):
            page_rect = doc[i].MediaBox
            pg_width = page_rect.width / 72.0 # width in inch
            pg_height = page_rect.height / 72.0
            pages_size_inch.append([pg_width, pg_height])
        return pages_size_inch

    def get_page_sizes_poppler(self, doc):
        pages_size_inch = []
        page_counts = doc.numPages()  
        for i in range(page_counts):
            pageSz = doc.page(i).pageSizeF()
            pg_width = pageSz.width() / 72.0 # width in inch
            pg_height = pageSz.height() / 72.0
            pages_size_inch.append([pg_width, pg_height])  
        return pages_size_inch

    def get_page_sizes_pdfium(self, doc):
        pages_size_inch = []
        page_counts = PDFIUM.FPDF_GetPageCount(doc)
        width = ctypes.c_double()
        height = ctypes.c_double()
        for i in range(page_counts):
            PDFIUM.FPDF_GetPageSizeByIndex(doc, i, ctypes.byref(width), ctypes.byref(height))
            pg_width = width.value / 72.0 # width in inch
            pg_height = height.value / 72.0
            pages_size_inch.append([pg_width, pg_height])
        return pages_size_inch

    def get_page_sizes(self):
        # extract page sizes for all pages
        if PDF_BACKEND == 'PDFIUM':
            return self.get_page_sizes_pdfium(self.doc)
        elif PDF_BACKEND == 'POPPLER':
            return self.get_page_sizes_poppler(self.doc)
        elif PDF_BACKEND == 'MUPDF':
            return self.get_page_sizes_mupdf(self.doc)

    def save_rendering_command(self, page_no, dpi, roi, visible_regions):
        if page_no in self.requests_queue:
            # remove old command with the same page number but different dpi                        
            dpi_list, roi_list = self.requests_queue[page_no]
            assert(len(dpi_list) == len(roi_list))
            cnt = len(dpi_list)
            duplicate_flag = False
            for i in range(cnt):
                if dpi_list[i] != dpi:
                    dpi_list[i] = None # mark deleted item as None
                    roi_list[i] = None
                elif roi_list[i] == roi:
                    duplicate_flag = True
            if not duplicate_flag:
                dpi_list.append(dpi)
                roi_list.append(roi)
        else:
            self.requests_queue[page_no] = [[dpi], [roi]]
            
        # only garentee current visible pages
        emptyKeys = []
        for page_no in self.requests_queue:
            if page_no not in visible_regions:
                emptyKeys.append(page_no)
                continue
            dpi_list, roi_list = self.requests_queue[page_no]
            assert(len(dpi_list) == len(roi_list))
            cnt = len(dpi_list)            
            for i in range(cnt):
                roi = roi_list[i]
                if roi is None:
                    continue
                if roi.intersected(visible_regions[page_no]).isEmpty():
                    roi_list[i] = None # mark deleted item as None
                    dpi_list[i] = None            
        for page_no in emptyKeys:
            self.requests_queue.pop(page_no)

    def get_command_from_queue(self):
        if len(self.requests_queue) == 0:
            return None
        emptyKeys = []
        command = None
        for page_no in self.requests_queue:
            dpi_list, roi_list = self.requests_queue[page_no]
            dpi = None
            roi = None
            while dpi is None:
                if len(dpi_list) == 0:
                    break
                dpi = dpi_list.pop(0)
                roi = roi_list.pop(0)
            if dpi is None:
                assert(len(dpi_list) == 0 and len(roi_list) == 0)
                emptyKeys.append(page_no)
            else:
                command = [page_no, dpi, roi]
                break
        for page_no in emptyKeys:
            self.requests_queue.pop(page_no)
        return command
        
    def get_toc_item_poppler(self, doc, node):
        element = node.toElement()
        title = element.tagName()
        # 
        linkDestination = None
        if element.hasAttribute("Destination"):
            linkDestination = Poppler.LinkDestination(element.attribute("Destination"))
        elif element.hasAttribute("DestinationName"):
            linkDestination = doc.linkDestination(element.attribute("DestinationName"))

        if linkDestination:
            # NOTE: in some files page_num may be in range 1 -> pages_count,
            # also, top may be not in range 0.0->1.0, we have to take care of that
            page_num = linkDestination.pageNumber()
            top = linkDestination.top() if linkDestination.isChangeTop() else 0
        else:
            page_num = -1
            top = -1
        return title, page_num, top

    def get_toc_item_pdfium(self, doc, bookmark_node):
        buflen = 4096
        titleBuf = ctypes.create_string_buffer(buflen)
        titleByteLen = PDFIUM.FPDFBookmark_GetTitle(bookmark_node, titleBuf, buflen)
        assert(titleByteLen <= buflen)
        titleStr = titleBuf.raw[:titleByteLen].decode('utf-16-le')[:-1]
        dest = PDFIUM.FPDFBookmark_GetDest(doc, bookmark_node)
        page_num = PDFIUM.FPDFDest_GetDestPageIndex(doc, dest)
        return titleStr, page_num + 1, None

    def getTableOfContents(self):
        if PDF_BACKEND == 'PDFIUM':
            firstBookmark = PDFIUM.FPDFBookmark_GetFirstChild(self.doc, None)
            if firstBookmark is None:
                return []
            # construct toc
            # each item will contain [level (the first entry is always 1), title, page (1-based), extra]
            # consistent with MuPDF
            toc_list = []
            current_level = 1
            nodes_queue = []
            #  
            # push children of the first level in queue in reverse order
            childrens = []
            child_node = firstBookmark
            while child_node:
                childrens.append(child_node)
                child_node = PDFIUM.FPDFBookmark_GetNextSibling(self.doc, child_node)
            for i in reversed(range(0, len(childrens))):
                nodes_queue.append([childrens[i], current_level])
            # 
            while len(nodes_queue) > 0:
                current_node, current_level = nodes_queue.pop(-1) # get the last one
                # 
                title, page_num, _ = self.get_toc_item_pdfium(self.doc, current_node)
                toc_list.append([current_level, title, page_num, None])
                # 
                # push children in queue in reverse order
                childrens = []
                child_node = PDFIUM.FPDFBookmark_GetFirstChild(self.doc, current_node)
                while child_node:
                    childrens.append(child_node)
                    child_node = PDFIUM.FPDFBookmark_GetNextSibling(self.doc, child_node)
                for i in reversed(range(0, len(childrens))):
                    nodes_queue.append([childrens[i], current_level + 1])
                # 
            return toc_list
        elif PDF_BACKEND == 'POPPLER':
            toc = self.doc.toc()
            if not toc:
                return []
            # construct toc from QDomDocument tree
            # each item will contain [level (the first entry is always 1), title, page (1-based), extra]
            # consistent with MuPDF
            toc_list = []
            current_level = 0
            nodes_queue = [[toc, current_level]]
            while len(nodes_queue) > 0:
                current_node, current_level = nodes_queue.pop(-1) # get the last one
                # 
                if current_level > 0:
                    # the root toc item contains nothing, the first valid level is always 1
                    title, page_num, _ = self.get_toc_item_poppler(self.doc, current_node)
                    toc_list.append([current_level, title, page_num, None])
                # 
                # push children in queue in reverse order
                current_node = current_node.lastChild()
                while not current_node.isNull():
                    nodes_queue.append([current_node, current_level + 1])
                    current_node = current_node.previousSibling()
            return toc_list
        elif PDF_BACKEND == 'MUPDF':
            return self.doc.getToC(simple=False)

    def receive_commands(self):
        # collect all commands in queue
        while True:
            try:
                item = self.commandQ.get(block=False)
            except:
                # will raise the Queue.Empty exception if the queue is empty
                break
            command, params = item
            if command == 'SET':
                filename = params[0]
                self.set_document(filename)
                # debug('[SET] for ', self.filename)
            elif command == 'PAGESIZES':
                pages_size_inch = self.get_page_sizes()
                self.resultsQ.put(['PAGESIZES_RES', self.filename, pages_size_inch])
                # debug('[PAGESIZES] for ', self.filename)
            elif command == 'TOC':
                toc = self.getTableOfContents()
                self.resultsQ.put(['TOC_RES', self.filename, toc])
                # debug('[TOC] for ', self.filename)
            elif command == 'RENDER':
                page_no, dpi, roi, visible_regions =params
                self.save_rendering_command(page_no, dpi, roi, visible_regions)
                # debug('[RENDER] for ', self.filename)
            elif command == 'STOP':
                self.exit_flag = True
                # debug('[STOP] for ', self.filename)
            else:
                # not supported command
                assert(0)

    def render_mupdf(self, doc, page_no, dpi, roi):
        page = doc.loadPage(page_no)
        page_rect = page.MediaBox
        # 
        zoom_ratio = dpi / 72.0
        x1 = roi.x() / zoom_ratio
        y1 = roi.y() / zoom_ratio
        x2 = (roi.x() + roi.width()) / zoom_ratio 
        y2 = (roi.y() + roi.height()) / zoom_ratio
        # 
        x1 = min(max(x1, 0), page_rect.width)
        y1 = min(max(y1, 0), page_rect.height)
        x2 = min(max(x2, 0), page_rect.width)
        y2 = min(max(y2, 0), page_rect.height)
        clip = fitz.Rect(x1, y1, x2, y2)
        debug("Render (MuPDF) In: ", zoom_ratio, clip)
        pix = page.getPixmap(matrix=fitz.Matrix(zoom_ratio, zoom_ratio), colorspace='RGB', clip=clip, alpha=False)
        # set the correct QImage format depending on alpha
        fmt = QtGui.QImage.Format_RGBA8888 if pix.alpha else QtGui.QImage.Format_RGB888
        img = QtGui.QImage(pix.samples, pix.width, pix.height, pix.stride, fmt)
        debug("Render (MuPDF) Out: ", img.width(), img.height())
        # 
        roi.setCoords(x1 * zoom_ratio, y1 * zoom_ratio, x2 * zoom_ratio, y2 * zoom_ratio) # write back roi

        return img, roi

    def render_poppler(self, doc, page_no, dpi, roi):
        page = doc.page(page_no)
        pageSz = page.pageSizeF()
        pg_width_pix = dpi * (pageSz.width() / 72.0) # DPI * width in inch
        pg_height_pix = dpi * (pageSz.height() / 72.0)
        x1 = roi.x()
        y1 = roi.y()
        x2 = x1 + roi.width()
        y2 = y1 + roi.height()
        # 
        x1 = min(max(x1, 0), pg_width_pix)
        y1 = min(max(y1, 0), pg_height_pix)
        x2 = min(max(x2, 0), pg_width_pix)
        y2 = min(max(y2, 0), pg_height_pix)
        debug("Render (Poppler) In: ", x1, y1, x2 - x1, y2 - y1)
        img = page.renderToImage(dpi, dpi, x1, y1, x2 - x1, y2 - y1)
        debug("Render (Poppler) Out: ", img.width(), img.height())
        # 
        roi.setCoords(x1, y1, x2, y2) # write back roi

        # # Add Heighlight over Link Annotation
        # self.painter.begin(img)
        # annots = page.annotations()
        # for annot in annots:
        #     # if annot.subType() == Poppler.Annotation.ALink:
        #     x, y = annot.boundary().left()*img.width(), annot.boundary().top()*img.height()
        #     w, h = annot.boundary().width()*img.width()+1, annot.boundary().height()*img.height()+1
        #     self.painter.fillRect(x, y, w, h, self.link_color)
        # self.painter.end()
        return img, roi

    def render_pdfium(self, doc, page_no, dpi, roi):
        page = PDFIUM.FPDF_LoadPage(doc, page_no)
        page_width = PDFIUM.FPDF_GetPageWidthF(page)
        page_height = PDFIUM.FPDF_GetPageHeightF(page)
        # 
        zoom_ratio = dpi / 72.0
        x1 = roi.x() / zoom_ratio
        y1 = roi.y() / zoom_ratio
        x2 = (roi.x() + roi.width()) / zoom_ratio 
        y2 = (roi.y() + roi.height()) / zoom_ratio
        # 
        x1 = min(max(x1, 0), page_width)
        y1 = min(max(y1, 0), page_height)
        x2 = min(max(x2, 0), page_width)
        y2 = min(max(y2, 0), page_height)
        # 

        debug("Render (PDFium) In: ", zoom_ratio)
        # time_0 = time.time()
        
        # prepare white bitmap
        img_width = int((x2 - x1)*zoom_ratio + 0.5)
        img_height = int((y2 - y1)*zoom_ratio + 0.5)
        bitmap = PDFIUM.FPDFBitmap_Create(img_width, img_height, 0)
        PDFIUM.FPDFBitmap_FillRect(bitmap, 0, 0, img_width, img_height, 0xFFFFFFFF)

        # compute transform matrix and clip region
        dx = -x1 * zoom_ratio
        dy = -y1 * zoom_ratio
        matrix = PDFIUM.FS_MATRIX(zoom_ratio, 0, 0, zoom_ratio, dx, dy)
        valid_region = PDFIUM.FS_RECTF(0, 0, img_width, img_height)

        # render
        PDFIUM.FPDF_RenderPageBitmapWithMatrix(bitmap, page, matrix, valid_region, PDFIUM.FPDF_LCD_TEXT | PDFIUM.FPDF_ANNOT)
        
        # convert rendered image
        buffer = PDFIUM.FPDFBitmap_GetBuffer(bitmap)
        buffer_ = ctypes.cast(buffer, ctypes.POINTER(ctypes.c_ubyte * (img_width * img_height * 4)))
        # 
        cvImg = np.frombuffer(buffer_.contents, dtype=np.uint8)
        cvImg = cvImg.reshape(img_height, img_width, 4)
        cvImg = cv2.cvtColor(cvImg, cv2.COLOR_BGRA2RGBA)
        img = QtGui.QImage(cvImg.data, img_width, img_height, img_width*4, QtGui.QImage.Format_RGBA8888)
        # 
        debug("Render (PDFium) Out: ", img.width(), img.height())
        # time_a = time.time()
        # debug("render time ", time_a - time_0)

        # release resources
        if bitmap is not None:
            PDFIUM.FPDFBitmap_Destroy(bitmap)
        PDFIUM.FPDF_ClosePage(page)

        roi.setCoords(x1 * zoom_ratio, y1 * zoom_ratio, x2 * zoom_ratio, y2 * zoom_ratio) # write back roi
        return img, roi

    def render(self, page_no, dpi, roi):
        if PDF_BACKEND == 'PDFIUM':
            return self.render_pdfium(self.doc, page_no, dpi, roi)
        elif PDF_BACKEND == 'POPPLER':
            return self.render_poppler(self.doc, page_no, dpi, roi)
        elif PDF_BACKEND == 'MUPDF':
            return self.render_mupdf(self.doc, page_no, dpi, roi)

    def run(self):
        """ render(int, float)
        This slot takes page no. and dpi and renders that page, then emits a signal with QImage"""

        debug('PdfInternalWorker entered.')

        while self.exit_flag == False:
            QtCore.QThread.msleep(20)

            self.receive_commands()

            # no file or no request even after reading pipe
            if self.doc is None or len(self.requests_queue) == 0:
                continue

            # render the first one in queue
            # debug("Request List: ", self.requests_list)
            
            command = self.get_command_from_queue()
            if command is None:
                continue
            
            page_no, dpi, roi = command

            img, roi = self.render(page_no, dpi, roi)
            
            # QImage to QByteArray
            img_byte_array = QtCore.QByteArray()
            img_buffer = QtCore.QBuffer(img_byte_array)
            img_buffer.open(QtCore.QIODevice.WriteOnly)
            img.save(img_buffer, "png", quality=100)
            
            self.resultsQ.put(['RENDER_RES', self.filename, page_no, dpi, roi, img_byte_array])

        debug('PdfInternalWorker exited.')

class PdfWorker(QtCore.QObject):
    pageSizesReceived = QtCore.pyqtSignal(str, list)
    bookmarksReceived = QtCore.pyqtSignal(str, list)
    renderedImageReceived = QtCore.pyqtSignal(str, int, float, QtCore.QRectF, QtGui.QImage)
    # 
    def __init__(self):
        super(PdfWorker, self).__init__()
        self.commandQ = Queue()
        self.resultsQ = Queue()
        self.worker = PdfInternalWorker(self.commandQ, self.resultsQ)
        self.worker.start()

        # read the queue periodically
        self.queue_timer = QtCore.QTimer(self)
        self.queue_timer.timeout.connect(self._retrieveQueueResults)
        self.queue_timer.start(20)

    def __del__(self):
        self.stop()

    def setDocument(self, filename):
        self.commandQ.put(['SET', [filename]])

    def requestGetPageSizes(self):
        self.commandQ.put(['PAGESIZES', [None]])

    def requestGetBookmarks(self):
        self.commandQ.put(['TOC', [None]])
        
    def requestRender(self, page_no, dpi, roi, visible_regions):
        self.commandQ.put(['RENDER', [page_no, dpi, roi, visible_regions]])

    def stop(self):
        self.commandQ.put(['STOP', []])
        self.worker.join()

    def _retrieveQueueResults(self):
        while True:
            try:
                item = self.resultsQ.get(block=False)
            except:
                # will raise the Queue.Empty exception if the queue is empty
                break
            # 
            message = item[0]
            filename = item[1]
            # 
            if message == 'PAGESIZES_RES':
                pages_size_inch = item[2]
                self.pageSizesReceived.emit(filename, pages_size_inch)
            elif message == 'TOC_RES':
                toc = item[2]
                self.bookmarksReceived.emit(filename, toc)
            elif message == 'RENDER_RES':
                page_no, dpi, roi, img_byte_array = item[2:]

                # QByteArray to QImage
                img_buffer = QtCore.QBuffer(img_byte_array)
                img_buffer.open(QtCore.QIODevice.ReadOnly)
                image = QtGui.QImageReader(img_buffer).read()
                # 
                self.renderedImageReceived.emit(filename, page_no, dpi, roi, image)
            else:
                assert(0)
    
class PdfReaderDraft(QtCore.QObject):
    """
    will be run in thread
    """
    # rendered = QtCore.pyqtSignal(int, QImage)
    # textFound = QtCore.pyqtSignal(int, list)
    annotationFound = QtCore.pyqtSignal(str, list)
    outlineFound = QtCore.pyqtSignal(QtGui.QStandardItemModel)

    def __init__(self):
        super(PdfReader, self).__init__()
        self.doc = None
        # self.page_set = page_set
        # self.painter = QPainter()
        # self.link_color = QColor(0,0,127, 40)

    def readAnnotation(self, filename):
        debug("start reading annotation")
        
        password = ""
        self.doc = Poppler.Document.load(filename, password.encode(), password.encode())
        self.doc.setRenderHint(
            Poppler.Document.TextAntialiasing
            | Poppler.Document.TextHinting
            | Poppler.Document.Antialiasing
            )

        page_num = self.doc.numPages()
        results = []
        for idx in range(page_num):
            
            # release the global interpreter lock (GIL) to make GUI interactable
            # if idx % 100 == 0:
            #     QtCore.QThread.msleep(10)

            pageAnnots = []
            doc_page = self.doc.page(idx)
            pg_width = doc_page.pageSize().width()
            pg_height = doc_page.pageSize().height()
            annots = doc_page.annotations()
            for item in annots:
                singleAnnot = {}
                singleAnnot['author'] = item.author()
                singleAnnot['boundary'] = item.boundary()
                singleAnnot['contents'] = item.contents()
                singleAnnot['modificationDate'] = item.modificationDate()
                singleAnnot['style'] = item.style()
                if item.subType() == Poppler.Annotation.AHighlight:
                    quads = item.highlightQuads()
                    txt = ""
                    for qd in quads:
                        x1 = qd.points[0].x() * pg_width
                        y1 = qd.points[0].y() * pg_height
                        x2 = qd.points[2].x() * pg_width
                        y2 = qd.points[2].y() * pg_height
                        # hacks: some pdfs have different meanings for these end points
                        rect = QtCore.QRectF(min(x1, x2), min(y1, y2), abs(x1 - x2), abs(y1 - y2))
                        txt = txt + doc_page.text(rect)
                        if len(txt) > 0 and txt[-1] == "-": # handle the last "-"
                            if txt[-2].islower():
                                txt = txt[:-1]
                        else:
                            txt += " "
                    singleAnnot['type'] = 'highlight'
                    singleAnnot['text'] = txt
                elif item.subType() == Poppler.Annotation.AGeom:
                    bounds = item.boundary()
                    custom_dpi = 150
                    page_pixel_width = custom_dpi * pg_width / 72.0
                    page_pixel_height = custom_dpi * pg_height / 72.0
                    roi = QtCore.QRectF(
                            bounds.left() * page_pixel_width, 
                            bounds.top() * page_pixel_height, 
                            bounds.width() * page_pixel_width, 
                            bounds.height() * page_pixel_height
                        )
                    
                    img = doc_page.renderToImage(custom_dpi, custom_dpi, roi.left(), roi.top(), roi.width(), roi.height())
                    singleAnnot['type'] = 'geom'
                    singleAnnot['image'] = img
                else:
                    continue # other types are not supported now
                pageAnnots.append(singleAnnot)
            results.append(pageAnnots)

        self.annotationFound.emit(filename, results)
        debug("finish reading annotation")

    def readOutline(self, doc, itemModel):
        parent_item = itemModel.invisibleRootItem()
        toc = doc.toc()
        if not toc:
            return
        node = toc.firstChild()
        loadOutline(doc, node, parent_item)
        self.outlineFound.emit(itemModel)

    def findText(self, doc, text, find_reverse):
        if find_reverse:
            pages = [i for i in range(1,page_num+1)]
            pages.reverse()
        else:
            pages = [i for i in range(page_num, self.doc.numPages()+1)]
        for page_no in pages:
            page = doc.page(page_no-1)
            textareas = page.search(text,Poppler.Page.CaseInsensitive,0)
            if textareas != []:
                self.textFound.emit(page_no, textareas)
                break

def loadOutline(doc, node, parent_item):
    """loadOutline(Poppler::Document* doc, const QDomNode& node, QStandardItem* parent_item) """
    element = node.toElement()
    item = QtGui.QStandardItem(element.tagName())

    linkDestination = None
    if element.hasAttribute("Destination"):
        linkDestination = Poppler.LinkDestination(element.attribute("Destination"))
    elif element.hasAttribute("DestinationName"):
        linkDestination = doc.linkDestination(element.attribute("DestinationName"))

    if linkDestination:
        # NOTE: in some files page_num may be in range 1 -> pages_count,
        # also, top may be not in range 0.0->1.0, we have to take care of that
        page_num = linkDestination.pageNumber()
        top = linkDestination.top() if linkDestination.isChangeTop() else 0

        item.setData(page_num, QtCore.Qt.UserRole + 1)
        item.setData(top, QtCore.Qt.UserRole + 2)

        pageItem = item.clone()
        pageItem.setText(str(page_num))
        pageItem.setTextAlignment(QtCore.Qt.AlignRight)

        parent_item.appendRow([item, pageItem])
    else:
        parent_item.appendRow(item)

    # Load next sibling
    siblingNode = node.nextSibling()
    if not siblingNode.isNull():
        loadOutline(doc, siblingNode, parent_item)

    # Load its child
    childNode = node.firstChild()
    if not childNode.isNull():
        loadOutline(doc, childNode, item)