import os

from resources.ui_document import Ui_doc_view
from PyQt5 import QtCore
from PyQt5 import QtGui
from PyQt5 import QtWidgets

from popplerqt5 import Poppler

import math

from utils import debug

from pdfworker import PdfReader
from annotations import AnnotationFrame, AnnotationItemWidget

from __init__ import __version__

class DocumentView(QtWidgets.QWidget, Ui_doc_view):
    readAnnotationRequested = QtCore.pyqtSignal(Poppler.Document)
    readOutlineRequested = QtCore.pyqtSignal(Poppler.Document, QtGui.QStandardItemModel)
    findTextRequested = QtCore.pyqtSignal(str, int, bool)
    pagePositionChanged = QtCore.pyqtSignal(int, int)
    showStatusRequested = QtCore.pyqtSignal(str)

    def __init__(self, parent, filename, screen_dpi):
        super(DocumentView, self).__init__(parent) # Call the inherited classes __init__ method
        self.setupUi(self)

        self.filename = filename
        self.screen_dpi = screen_dpi

        self.doc = None
        self.setWindowTitle(os.path.basename(self.filename)+ " - kuafu " + __version__)

        # hide some parts in splitters
        self.splitter_main.setSizes([1,5,1])
        self.splitter_doc.setSizes([1,0])

        self.splitter_main.setCollapsible(0, False) # make the thumb view uncollapsible
        self.splitter_main.setCollapsible(2, False) # make the annotationview uncollapsible
        self.splitter_doc.setCollapsible(0, False) # make the first document view uncollapsible

        # Create separate thread for reading pdf metainformations
        self.pdf_reader_thread = QtCore.QThread(self)
        self.pdf_reader_obj = PdfReader()
        self.pdf_reader_obj.moveToThread(self.pdf_reader_thread) # this must be moved before connecting signals
        # self.renderRequested.connect(self.pdf_reader_obj.render)
        self.readAnnotationRequested.connect(self.pdf_reader_obj.readAnnotation)
        self.readOutlineRequested.connect(self.pdf_reader_obj.readOutline)
        # self.findTextRequested.connect(self.pdf_reader_obj.findText)
        self.pdf_reader_obj.annotationFound.connect(self.onAnnotaionFound)
        self.pdf_reader_obj.outlineFound.connect(self.onOutlineFound)
        # self.pdf_reader_obj.textFound.connect(self.onTextFound)
        self.pdf_reader_thread.start()

        # self.doc = Poppler.Document.load(filename)
        # if not self.doc : return

        # if self.doc.isLocked() :
        #     password = QInputDialog.getText(self, 'This PDF is locked', 'Enter Password :', 2)[0]
        #     if password == '' : sys.exit(1)
        #     self.doc.unlock(password.encode(), password.encode())
        # if not self.first_document:
        #     self.removeOldDoc()

        password = ""
        self.doc = Poppler.Document.load(filename, password.encode(), password.encode())
        self.doc.setRenderHint(
            Poppler.Document.TextAntialiasing
            | Poppler.Document.TextHinting
            | Poppler.Document.Antialiasing
            # | Poppler.Document.ThinLineSolid
            )

        self.pages_count = self.doc.numPages()

        self.outline_model = QtGui.QStandardItemModel(self)

        self.readOutlineRequested.emit(self.doc, self.outline_model)
        self.readAnnotationRequested.emit(self.doc)
        
        # self.zoomLevelCombo.setCurrentIndex()

        # if collapseUser(self.filename) in self.history_filenames:
        #     self.current_page = int(self.history_page_no[self.history_filenames.index(collapseUser(self.filename))])
        # self.current_page = min(self.current_page, self.pages_count)
        self.current_page = 0

        self.graphicsView_doc1.setDocument(self.doc, self.screen_dpi, render_num=4)
        self.graphicsView_doc2.setDocument(self.doc, self.screen_dpi, render_num=4)
        self.graphicsView_thumbs.setDocument(self.doc, self.screen_dpi, render_num=4)
        
        # # Add document 1 widgets
        # self.doc_frame1 = DocumentFrame(self.docScrollAreaContents1, self.docScrollArea1, self.doc, self.screen_dpi, threads=4)
        # self.docScrollAreaContents1_Layout.addWidget(self.doc_frame1)
        # self.doc_frame1.pagePositionChanged.connect(self.handlePagePositionChanged)

        self.graphicsView_doc1.pagePositionChanged.connect(self.onPagePositionChanged)
        # self.docScrollArea1.verticalScrollBar().valueChanged.connect(self.onDocScrollAreaChanged)

        # # Add document 2 widgets
        # self.view_doc1 = DocumentFrame(self.docScrollAreaContents2, self.docScrollArea2, self.doc, self.screen_dpi, threads=4)
        # self.docScrollAreaContents2_Layout.addWidget(self.doc_frame2)
        # self.doc_frame2.pagePositionChanged.connect(self.handlePagePositionChanged)

        # # Add thumbs widgets
        # self.thumbs_frame = DocumentFrame(self.thumbsScrollAreaContents, self.thumbsScrollArea, self.doc, self.screen_dpi, threads=4)
        # self.thumbScrollAreaContents_Layout.addWidget(self.thumbs_frame)

        # Add annotation widgets
        self.annotation_frame = AnnotationFrame(self.annotScrollAreaContents, self.annotScrollArea)
        self.annotScrollAreaContents_Layout.addWidget(self.annotation_frame)

        # self.thumbsScrollArea.resizeRequested.connect(self.thumbs_frame.handleScrollAreaResized)
        # self.thumbsScrollArea.verticalScrollBar().setValue(0)
        # self.thumbsScrollArea.verticalScrollBar().valueChanged.connect(self.thumbs_frame.renderCurrentVisiblePages)

        # self.doc_frame1.showStatusRequested.connect(self.showStatus)
        # self.doc_frame2.showStatusRequested.connect(self.showStatus)
        # self.thumbs_frame.showStatusRequested.connect(self.showStatus)

        # Set style
        # self.thumbs_frame.setStyleSheet("border: 0; background-color: white")

        # self.annotationItemModel = QtGui.QStandardItemModel()
        # self.annotationView.setModel(self.annotationItemModel)
        # self.annotationView.resizeRequested.connect(self.onAnnotaionViewResized)
 
        # self.annotationListView.setAlternatingRowColors(True)
        # self.annotationListView.clicked.connect(self.onOutlineClick)

        # self.doc_frame1.jumpToRequested.connect(self.jumpToPage)
        # self.doc_frame1.copyTextRequested.connect(self.copyText)
        # self.doc_frame1.showStatusRequested.connect(self.showStatus)

        # self.pageNoLabel.setText('<b>%i/%i</b>' % (self.current_page, self.pages_count) )
        # self.gotoPageValidator.setTop(self.pages_count)

        # if self.current_page != 0 :
        #     QtCore.QTimer.singleShot(150+self.pages_count//3, self.jumpToCurrentPage)

    def showStatus(self, msg):
        self.showStatusRequested.emit(msg)

    def onAnnotaionFound(self, annotList):
        assert(len(annotList) == self.pages_count)
        for pg_no in range(self.pages_count):
            for annot in annotList[pg_no]:
                image = None
                author = annot['author']
                boundary = annot['boundary']
                contents = annot['contents']
                modificationDate = annot['modificationDate']
                style = annot['style']
                if annot['type'] == 'highlight':
                    text = annot['text']
                    self.annotation_frame.addItem(style.color(), author, modificationDate, text, contents)
                elif annot['type'] == 'geom':
                    image = annot['image']
                    self.annotation_frame.addItem(style.color(), author, modificationDate, image, contents)

    def onOutlineFound(self, itemModel):
        debug("outline found")

        self.treeView_outline.setModel(itemModel)
        if itemModel.invisibleRootItem().rowCount() < 4:
            self.treeView_outline.expandToDepth(0)
        self.treeView_outline.setHeaderHidden(True)
        self.treeView_outline.header().setSectionResizeMode(0, 1)
        self.treeView_outline.header().setSectionResizeMode(1, 3)
        self.treeView_outline.header().setStretchLastSection(False)
        self.treeView_outline.expandAll()
        self.treeView_outline.setAlternatingRowColors(True)
        self.treeView_outline.clicked.connect(self.onOutlineClick)

    def onPagePositionChanged(self, current_page, pages_count):
        return
        
        target_view = self.graphicsView_doc1
        thumb_view = self.graphicsView_thumbs

        for i in range(target_view.page_counts-1, -1, -1):

            docItem = target_view.page_items[i]
            thumbItem = thumb_view.page_items[i]
            thumbMaskItem = thumb_view.page_mask_items[i]

            visRegion = target_view.visible_regions[i]

            if visRegion.isEmpty():
                thumbMaskItem.setRect(0,0,0,0)
            else:
                thumbItem.ensureVisible()

                ratio = thumbItem.boundingRect().width() / docItem.boundingRect().width()
                x = round(visRegion.x() * ratio)
                y = round(visRegion.y() * ratio)
                width = round(visRegion.width() * ratio) - 1
                height = round(visRegion.height() * ratio) - 1
                thumbMaskItem.setRect(x,y,width,height)

        self.pagePositionChanged.emit(current_page, pages_count)

    def docInfo(self):
        info_keys = list(self.doc.infoKeys())
        values = [self.doc.info(key) for key in info_keys]
        page_size = self.doc.page(self.current_page).pageSizeF()
        page_size = "%s x %s pts"%(page_size.width(), page_size.height())
        info_keys += ['Embedded FIles', 'Page Size']
        values += [str(self.doc.hasEmbeddedFiles()), page_size]
        dialog = DocInfoDialog(self)
        dialog.setInfo(info_keys, values)
        dialog.exec_()

    def setColumnNumber(self, columNum):
        self.graphicsView_doc1.setColumnNumber(columNum)
        self.graphicsView_thumbs.setColumnNumber(columNum)

    def setPrecedingEmptyPage(self, emptyCount):
        self.graphicsView_doc1.setPrecedingEmptyPage(emptyCount)
        self.graphicsView_thumbs.setPrecedingEmptyPage(emptyCount)

    def zoomIn(self):
        self.graphicsView_doc1.zoomIn()

    def zoomOut(self):
        self.graphicsView_doc1.zoomOut()

    def zoomFitWidth(self):
        self.graphicsView_doc1.zoomFitWidth()

    def toggleFindMode(self, enable):
        if enable:
          self.findTextEdit.setText('')
          self.findTextEdit.setFocus()
          self.search_text = ''
          self.search_result_page = 0
        elif self.search_result_page != 0:
          self.pages[self.search_result_page].highlight_area = None
          self.pages[self.search_result_page].updateImage()

    def findNext(self):
        """ search text in current page and next pages """
        text = self.findTextEdit.text()
        if text == "" : return
        # search from current page when text changed
        if self.search_text != text or self.search_result_page == 0:
            search_from_page = self.current_page
        else:
            search_from_page = self.search_result_page + 1
        self.findTextRequested.emit(text, search_from_page, False)
        if self.search_result_page != 0:     # clear previous highlights
            self.pages[self.search_result_page].highlight_area = None
            self.pages[self.search_result_page].updateImage()
            self.search_result_page = 0
        self.search_text = text

    def findBack(self):
        """ search text in pages before current page """
        text = self.findTextEdit.text()
        if text == "" : return
        if self.search_text != text or self.search_result_page == 0:
            search_from_page = self.current_page
        else:
            search_from_page = self.search_result_page - 1
        self.findTextRequested.emit(text, search_from_page, True)
        if self.search_result_page != 0:
            self.pages[self.search_result_page].highlight_area = None
            self.pages[self.search_result_page].updateImage()
            self.search_result_page = 0
        self.search_text = text

    def onTextFound(self, page_no, areas):
        self.pages[page_no].highlight_area = areas
        self.search_result_page = page_no
        if self.pages[page_no].pixmap():
            self.pages[page_no].updateImage()
        first_result_pos = areas[0].y()/self.doc.page(page_no).pageSize().height()
        self.jumpToPage(page_no, first_result_pos)

    def toggleCopyText(self, checked):
        self.doc_frame1.enableCopyTextMode(checked)

    def copyText(self, page_no, top_left, bottom_right):
        zoom = self.pages[page_no].height()/self.doc.page(page_no).pageSize().height()
        # Copy text to clipboard
        text = self.doc.page(page_no).text(QtCore.QRectF(top_left/zoom, bottom_right/zoom))
        QApplication.clipboard().setText(text)
        self.copyTextAction.setChecked(False)
        self.toggleCopyText(False)

    def onOutlineClick(self, m_index):
        page_num = self.outlineTreeView.model().data(m_index, QtCore.Qt.UserRole+1)
        top = self.outlineTreeView.model().data(m_index, QtCore.Qt.UserRole+2)
        if not page_num: return
        self.jumpToPage(page_num, top)

    def closeEvent(self, ev):
        """ Save all settings on window close """
        debug('closeEvent in DocView')

        # wait for the reader thread to exit
        loop = QtCore.QEventLoop()
        self.pdf_reader_thread.finished.connect(loop.quit)
        self.pdf_reader_thread.quit()
        loop.exec_()
        debug('pdf_reader_thread exit')

        self.graphicsView_doc1.close()
        self.graphicsView_doc2.close()
        self.graphicsView_thumbs.close()
