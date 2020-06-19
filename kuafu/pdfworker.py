from PyQt5 import QtCore
from PyQt5 import QtGui

# https://hzqtc.github.io/2012/04/poppler-vs-mupdf.html
# MuPDF is much faster, but also use more memories
BACKEND_MuPDF = False

if BACKEND_MuPDF:
    import fitz
else: 
    from popplerqt5 import Poppler

from multiprocessing import Process

from utils import debug
import time

class PdfRender(Process):

    # considering realtime, the request may be dropped
    # rendered = QtCore.pyqtSignal(str, int, float, QtGui.QImage)

    def __init__(self, commandQ, resultsQ):
        super(PdfRender, self).__init__()
        #
        self.commandQ = commandQ
        self.resultsQ = resultsQ

        self.doc = None
        self.filename = None
        # 
        self.painter = QtGui.QPainter()
        self.link_color = QtGui.QColor(0,0,127, 40)
        self.exit_flag = False

        self.requests_list = []
        self.requests_params = []
        # self.mutex = QtCore.QMutex()

    def set_document(self, filename):
        self.filename = filename

        if BACKEND_MuPDF:
            self.doc = fitz.open(filename)
        else:
            password = ""
            self.doc = Poppler.Document.load(self.filename, password.encode(), password.encode())
            self.doc.setRenderHint(
                Poppler.Document.TextAntialiasing
                | Poppler.Document.TextHinting
                | Poppler.Document.Antialiasing
                )
                
    def save_rendering_command(self, page_no, dpi, roi, visible_regions):
        # remove old duplicated
        if page_no in self.requests_list:
            index = self.requests_list.index(page_no)
            self.requests_list.pop(index)
            self.requests_params.pop(index)
        # 
        self.requests_list.append(page_no)
        self.requests_params.append([dpi, roi])
        # 
        # too many candidate, can only garentee current visible pages
        candi_num = len(self.requests_list)
        if candi_num >= 2:
            new_request_list = []
            new_request_params = []
            for idx in range(candi_num):
                if self.requests_list[idx] in visible_regions:
                    new_request_list.append(self.requests_list[idx])
                    new_request_params.append(self.requests_params[idx])
            self.requests_list = new_request_list
            self.requests_params = new_request_params
    
    def command_dispatcher(self):
        # collect all commands in queue
        size = self.commandQ.qsize()
        # debug("Qsize: ", size)
        for i in range(size):
             # will be blocked until when some data are avaliable
             # as we get qsize first, so there's no block here
            item = self.commandQ.get()
            command, params = item
            if command == 'SET':
                filename = params[0]
                self.set_document(filename)
            elif command == 'RENDER':
                page_no, dpi, roi, visible_regions =params
                self.save_rendering_command(page_no, dpi, roi, visible_regions)
            elif command == 'STOP':
                self.exit_flag = True
            else:
                # not supported command
                assert(0)

    def run(self):
        """ render(int, float)
        This slot takes page no. and dpi and renders that page, then emits a signal with QImage"""

        debug('render entered.')
        print(self.pid)

        while self.exit_flag == False:
            QtCore.QThread.msleep(50)

            self.command_dispatcher()

            # no file or no request even after reading pipe
            if self.doc is None or len(self.requests_list) == 0:
                continue

            # render the first one in queue
            # debug("Request List: ", self.requests_list)
            page_no = self.requests_list.pop(0)
            params = self.requests_params.pop(0)

            dpi, roi = params

            if BACKEND_MuPDF:
                page = self.doc.loadPage(page_no)
            else:
                page = self.doc.page(page_no)

            if page is None:
                continue

            # debug('rendering page %d.' % (page_no))
            if BACKEND_MuPDF:
                zoom_ratio = dpi / 72.0
                clip = fitz.Rect(
                    roi.x() / zoom_ratio, 
                    roi.y() / zoom_ratio, 
                    (roi.x() + roi.width()) / zoom_ratio, 
                    (roi.y() + roi.height()) / zoom_ratio)
                pix = page.getPixmap(matrix=fitz.Matrix(zoom_ratio, zoom_ratio), clip=clip, alpha=False)
                # set the correct QImage format depending on alpha
                fmt = QtGui.QImage.Format_RGBA8888 if pix.alpha else QtGui.QImage.Format_RGB888
                img = QtGui.QImage(pix.samples, pix.width, pix.height, pix.stride, fmt)
            else:
                img = page.renderToImage(dpi, dpi, roi.left(), roi.top(), roi.width(), roi.height())

            # # Add Heighlight over Link Annotation
            # self.painter.begin(img)
            # annots = page.annotations()
            # for annot in annots:
            #     # if annot.subType() == Poppler.Annotation.ALink:
            #     x, y = annot.boundary().left()*img.width(), annot.boundary().top()*img.height()
            #     w, h = annot.boundary().width()*img.width()+1, annot.boundary().height()*img.height()+1
            #     self.painter.fillRect(x, y, w, h, self.link_color)
            # self.painter.end()
            # 
            # self.rendered.emit(self.filename, page_no, dpi, img)

            # QImage to QByteArray
            img_byte_array = QtCore.QByteArray()
            img_buffer = QtCore.QBuffer(img_byte_array)
            img_buffer.open(QtCore.QIODevice.WriteOnly)
            img.save(img_buffer, "png", quality=100)
            
            self.resultsQ.put([self.filename, page_no, dpi, roi, img_byte_array])

        debug('render exited.')

class PdfReader(QtCore.QObject):
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