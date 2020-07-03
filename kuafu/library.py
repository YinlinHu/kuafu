
from resources.ui_library import Ui_librarywidget
 
from PyQt5 import QtCore
from PyQt5 import QtGui
from PyQt5 import QtWidgets

from popplerqt5 import Poppler

from utils import debug
from pdfworker import PdfReader
from toc import TocManager

import os
import numpy as np
import json

class LibraryView(QtWidgets.QWidget, Ui_librarywidget):
    # renderRequested = QtCore.pyqtSignal(int, float)
    # loadFileRequested = QtCore.pyqtSignal(str, str)
    # findTextRequested = QtCore.pyqtSignal(str, int, bool)
    readAnnotationRequested = QtCore.pyqtSignal(str)
    # readOutlineRequested = QtCore.pyqtSignal(Poppler.Document, QtGui.QStandardItemModel)
    # findTextRequested = QtCore.pyqtSignal(str, int, bool)
    # pagePositionChanged = QtCore.pyqtSignal(int, int)
    showStatusRequested = QtCore.pyqtSignal(str)
    fileReselected = QtCore.pyqtSignal(str)

    def __init__(self, parent, screen_dpi, app_data_path):
        super(LibraryView, self).__init__(parent) # Call the inherited classes __init__ method
        self.setupUi(self)

        self.screen_dpi = screen_dpi
        self.app_data_path = app_data_path
        self.filename = None

        self.splitter_doc.setSizes([1, 0]) # the second view is folded by default
        self.splitter_doc.setCollapsible(0, False) 

        self.pushButton_oneColumn.clicked.connect(self.onOneColumnClicked)
        self.pushButton_twoColumn.clicked.connect(self.onTwoColumnClicked)
        self.pushButton_fourColumn.clicked.connect(self.onFourColumnClicked)
        self.pushButton_emptyPage.clicked.connect(self.setPrecedingEmptypage)
        self.pushButton_zoomIn.clicked.connect(self.zoomIn)
        self.pushButton_zoomOut.clicked.connect(self.zoomOut)
        self.pushButton_zoomFitWidth.clicked.connect(self.zoomFitWidth)

        self.pushButton_oneColumn_thumb.clicked.connect(lambda:self.thumb_graphicsview.setColumnNumber(1))
        self.pushButton_twoColumn_thumb.clicked.connect(lambda:self.thumb_graphicsview.setColumnNumber(2))
        self.pushButton_fourColumn_thumb.clicked.connect(lambda:self.thumb_graphicsview.setColumnNumber(4))
        self.pushButton_emptyPage_thumb.clicked.connect(self.setThumbPrecedingEmptypage)

        self.doc_graphicsview_1.loadFinished.connect(self.onDoc1LoadFinished)
        self.doc_graphicsview_1.viewColumnChanged.connect(self.onViewColumnChanged)
        self.doc_graphicsview_1.emptyLeadingPageChanged.connect(self.onEmptyLeadingPageChanged)
        self.doc_graphicsview_1.zoomRatioChanged.connect(self.onZoomRatioChanged)
        self.doc_graphicsview_1.tocLoaded.connect(self.onTocLoaded)
        self.doc_graphicsview_1.viewportChanged.connect(self.onDocViewportChanged)
        self.doc_graphicsview_1.focusIn.connect(self.OnDoc1FocusIn)

        self.doc_graphicsview_2.loadFinished.connect(self.onDoc1LoadFinished)
        self.doc_graphicsview_2.viewColumnChanged.connect(self.onViewColumnChanged)
        self.doc_graphicsview_2.emptyLeadingPageChanged.connect(self.onEmptyLeadingPageChanged)
        self.doc_graphicsview_2.zoomRatioChanged.connect(self.onZoomRatioChanged)
        self.doc_graphicsview_2.tocLoaded.connect(self.onTocLoaded)
        self.doc_graphicsview_2.viewportChanged.connect(self.onDocViewportChanged)
        self.doc_graphicsview_2.focusIn.connect(self.OnDoc2FocusIn)

        self.thumb_graphicsview.viewColumnChanged.connect(self.onThumbViewColumnChanged)
        self.thumb_graphicsview.emptyLeadingPageChanged.connect(self.onThumbEmptyLeadingPageChanged)
        self.thumb_graphicsview.loadFinished.connect(self.onThumbLoadFinished)
        self.thumb_graphicsview.pageRelocationRequest.connect(self.onThumbPageRelocationRequest)
        self.thumb_graphicsview.zoomRequest.connect(self.onThumbZoomRequest)

        self.lineEdit_pageNo.gotoPageTrigger.connect(self.onGotoPageTrigger)

        # self.repos = ["/home/yhu/下载/", "/home/yhu/tmp/"]
        self.current_graphicsview = self.doc_graphicsview_1

        self.fileview_model = QtGui.QStandardItemModel(self)
        self.fileview.setModel(self.fileview_model)
        self.fileview.clicked.connect(self.onFileClick)

        self.fileview.setAlternatingRowColors(True)
        # self.annotview.setAlternatingRowColors(True)

        # self.annotview_model = QtGui.QStandardItemModel()
        # self.annotview.setModel(self.annotview_model)
        # self.annotationView.resizeRequested.connect(self.onAnnotaionViewResized)

        # # Create separate thread for reading pdf metainformations
        # self.pdf_reader_thread = QtCore.QThread(self)
        # self.pdf_reader_obj = PdfReader()
        # self.pdf_reader_obj.moveToThread(self.pdf_reader_thread) # this must be moved before connecting signals
        # # self.renderRequested.connect(self.pdf_reader_obj.render)
        # self.readAnnotationRequested.connect(self.pdf_reader_obj.readAnnotation)
        # # self.readOutlineRequested.connect(self.pdf_reader_obj.readOutline)
        # # self.findTextRequested.connect(self.pdf_reader_obj.findText)
        # self.pdf_reader_obj.annotationFound.connect(self.onAnnotationFound)
        # # self.pdf_reader_obj.outlineFound.connect(self.onOutlineFound)
        # # self.pdf_reader_obj.textFound.connect(self.onTextFound)
        # self.pdf_reader_thread.start()

        # dirname = self.repos[0]
        # self.setFileList(dirname)
        self.current_dir = None
        self.tocManager = TocManager(self.tocButton_1)
        self.tocManager.tocIndexChanged.connect(self.onTocIndexChanged)
        self.current_page_idx = -1
        self.pageCounts = 0

    def setFileList(self, filename):
        # remove all file list first
        self.fileview_model.removeRows(0, self.fileview_model.rowCount())

        dirname = os.path.dirname(filename)

        self.current_dir = dirname
        self.fileview_model.setHorizontalHeaderLabels([self.current_dir])

        parent_file_item = self.fileview_model.invisibleRootItem()

        pdf_filenames = os.listdir(dirname)
        pdf_filenames.sort()
        for name in pdf_filenames:
            path = dirname + os.sep + name
            if os.path.isfile(path) and path.endswith('.pdf'):
                item = QtGui.QStandardItem(name)
                item.setData(name, QtCore.Qt.UserRole + 1)
                parent_file_item.appendRow(item)
                if path == filename:
                    modelIndex = self.fileview_model.indexFromItem(item)
        self.fileview.scrollTo(modelIndex, QtWidgets.QAbstractItemView.ScrollHint.PositionAtCenter)
        self.fileview.selectionModel().setCurrentIndex(modelIndex, QtCore.QItemSelectionModel.Select)

    def setDocument(self, filename, screep_dpi):
        self.setFileList(filename)
        # 
        self.filename = filename
        self.screen_dpi = screep_dpi
        self.loadDocument(filename, screep_dpi)
        self.fileReselected.emit(self.filename)

    def onFileClick(self, m_index):
        # remove all annotatoin first
        # self.annotview_model.removeRows(0, self.annotview_model.rowCount())

        # save view status of the last file
        self.saveDocumentViewStatus(self.filename)

        self.filename = self.current_dir + os.sep + self.fileview_model.data(m_index, QtCore.Qt.UserRole + 1)
        print(self.filename)
        
        self.loadDocument(self.filename, self.screen_dpi)
        self.fileReselected.emit(self.filename)
                
    def loadDocument(self, filename, screen_dpi):
        viewStatus = self.loadDocumentViewStatus(filename)
        status = viewStatus['docView1'] if viewStatus else None
        self.doc_graphicsview_1.setDocument(filename, screen_dpi, status)
        status = viewStatus['docView2'] if viewStatus else None
        self.doc_graphicsview_2.setDocument(filename, screen_dpi, status)
        status = viewStatus['thumbView'] if viewStatus else None
        self.thumb_graphicsview.setDocument(filename, screen_dpi, status)
        status = viewStatus['docSplitter'] if viewStatus else None
        if status:
            status = QtCore.QByteArray.fromHex(bytes(status, 'utf-8'))
            self.splitter_doc.restoreState(status)
        else:
            self.splitter_doc.setSizes([1, 0]) # the second view is folded by default

    def onTocLoaded(self, toc):
        self.tocManager.setToc(toc)
        self.tocManager.update(self.current_page_idx)

    def onTocIndexChanged(self, page_no):
        debug("onTocIndexChanged: %d" % page_no)
        self.current_graphicsview.gotoPage(page_no)

    def onDoc1LoadFinished(self):
        # debug("onDoc1LoadFinished")
        # self.thumb_graphicsview.setDocument(self.filename, self.screen_dpi)
        pass

    def onThumbLoadFinished(self):
        # debug("onThumbLoadFinished")
        pass

    def onDocViewportChanged(self, filename, page_counts, visible_regions):
        # debug("Doc viewport changed: ", visible_regions)
        self.thumb_graphicsview.highlightVisibleMasks(filename, visible_regions)
        # 
        self.current_page_idx = next(iter(visible_regions)) # fetch first key
        self.pageCounts = page_counts
        self.tocManager.update(self.current_page_idx)
        # 
        self.lineEdit_pageNo.setPageInfo(self.current_page_idx+1, page_counts)
        self.label_pageCount.setText(" %d " % page_counts)

    def OnDoc1FocusIn(self):
        # debug("OnDoc1FocusIn")
        self.current_graphicsview = self.doc_graphicsview_1
        self.current_graphicsview.refreshSignals()

    def OnDoc2FocusIn(self):
        # debug("OnDoc2FocusIn")
        self.current_graphicsview = self.doc_graphicsview_2
        self.current_graphicsview.refreshSignals()

    def onGotoPageTrigger(self, page_no):
        self.gotoPage(page_no)
        self.lineEdit_pageNo.clearFocus()

    def onThumbPageRelocationRequest(self, page_no, x_ratio, y_ratio):
        # debug("onPageRelocationRequest: <%d> (%.2f, %.2f)" % (page_no, x_ratio, y_ratio))
        viewRect = self.current_graphicsview.viewport()
        self.current_graphicsview.viewAtPageAnchor([page_no, x_ratio, y_ratio, viewRect.width()/2, viewRect.height()/2])

    def onThumbZoomRequest(self, zoomInFlag, page_no, x_ratio, y_ratio):
        # debug("onThumbZoomRequest: %d, <%d> (%.2f, %.2f)" % (zoomInFlag, page_no, x_ratio, y_ratio))
        viewRect = self.current_graphicsview.viewport()
        if zoomInFlag:
            self.current_graphicsview.zoomIn([page_no, x_ratio, y_ratio, viewRect.width()/2, viewRect.height()/2])
        else:
            self.current_graphicsview.zoomOut([page_no, x_ratio, y_ratio, viewRect.width()/2, viewRect.height()/2])

    def onViewColumnChanged(self, viewColumn):
        if viewColumn == 1:
            self.pushButton_oneColumn.setChecked(True)
            self.pushButton_twoColumn.setChecked(False)
            self.pushButton_fourColumn.setChecked(False)
        elif viewColumn == 2:
            self.pushButton_oneColumn.setChecked(False)
            self.pushButton_twoColumn.setChecked(True)
            self.pushButton_fourColumn.setChecked(False)
        elif viewColumn == 4:
            self.pushButton_oneColumn.setChecked(False)
            self.pushButton_twoColumn.setChecked(False)
            self.pushButton_fourColumn.setChecked(True)
        else:
            assert(0)

    def onThumbViewColumnChanged(self, viewColumn):
        if viewColumn == 1:
            self.pushButton_oneColumn_thumb.setChecked(True)
            self.pushButton_twoColumn_thumb.setChecked(False)
            self.pushButton_fourColumn_thumb.setChecked(False)
        elif viewColumn == 2:
            self.pushButton_oneColumn_thumb.setChecked(False)
            self.pushButton_twoColumn_thumb.setChecked(True)
            self.pushButton_fourColumn_thumb.setChecked(False)
        elif viewColumn == 4:
            self.pushButton_oneColumn_thumb.setChecked(False)
            self.pushButton_twoColumn_thumb.setChecked(False)
            self.pushButton_fourColumn_thumb.setChecked(True)
        else:
            assert(0)
    
    def onZoomRatioChanged(self, zoomRatio):
        if zoomRatio == 0:
            self.pushButton_zoomFitWidth.setChecked(True)
            self.showStatusRequested.emit('Zoom fitted to width')
        else:
            self.pushButton_zoomFitWidth.setChecked(False)
            self.showStatusRequested.emit("Zoom to %d%%" % int(zoomRatio * 100))


    def onOneColumnClicked(self):
        self.current_graphicsview.setColumnNumber(1)

    def onTwoColumnClicked(self):
        self.current_graphicsview.setColumnNumber(2)

    def onFourColumnClicked(self):
        self.current_graphicsview.setColumnNumber(4)

    def setPrecedingEmptypage(self):
        if self.pushButton_emptyPage.isChecked():
            self.current_graphicsview.setPrecedingEmptyPage(1)
        else:
            self.current_graphicsview.setPrecedingEmptyPage(0)

    def setThumbPrecedingEmptypage(self):
        if self.pushButton_emptyPage_thumb.isChecked():
            self.thumb_graphicsview.setPrecedingEmptyPage(1)
        else:
            self.thumb_graphicsview.setPrecedingEmptyPage(0)

    def onEmptyLeadingPageChanged(self, emptyPages):
        if emptyPages == 0:
            self.pushButton_emptyPage.setChecked(False)
        elif emptyPages == 1:
            self.pushButton_emptyPage.setChecked(True)
        else:
            assert(0)

    def onThumbEmptyLeadingPageChanged(self, emptyPages):
        if emptyPages == 0:
            self.pushButton_emptyPage_thumb.setChecked(False)
        elif emptyPages == 1:
            self.pushButton_emptyPage_thumb.setChecked(True)
        else:
            assert(0)

    def onAnnotationFound(self, filename, annotList):
        # the view has changed, too late
        debug(self.filename, filename)

        parent_item = self.annotview_model.invisibleRootItem()

        for pg_no in range(len(annotList)):
            for annot in annotList[pg_no]:
                image = None
                boundary = annot['boundary']
                contents = annot['contents']
                modificationDate = annot['modificationDate']
                item = QtGui.QStandardItem()
                item.setData(pg_no, QtCore.Qt.UserRole + 1)
                item.setData(boundary, QtCore.Qt.UserRole + 2)
                item.setData(contents, QtCore.Qt.UserRole + 3)
                item.setData(modificationDate, QtCore.Qt.UserRole + 4)
                # 
                timeStr = ("<%s>" % modificationDate.toString())
                if annot['type'] == 'highlight':
                    text = annot['text']
                    item.setText(text)
                elif annot['type'] == 'geom':
                    image = annot['image']
                    image = image.scaled(30, 30)
                    item.setData(QtGui.QPixmap.fromImage(image), QtCore.Qt.DecorationRole)
                    item.setData(image, QtCore.Qt.UserRole + 5)
                # item.setTextAlignment(QtCore.Qt.AlignLeft)

                dateItem = QtGui.QStandardItem()
                dateItem.setText(timeStr)
                dateItem.setTextAlignment(QtCore.Qt.AlignRight)

                parent_item.appendRow([item, dateItem])

    def gotoPage(self, pg_no):
        self.current_graphicsview.gotoPage(pg_no)

    def zoomIn(self):
        self.current_graphicsview.zoomIn()

    def zoomOut(self):
        self.current_graphicsview.zoomOut()

    def zoomFitWidth(self):
        self.current_graphicsview.zoomFitWidth()

    def closeEvent(self, ev):
        debug('closeEvent in LibraryView')
        self.saveDocumentViewStatus(self.filename)
        self.doc_graphicsview_1.close()
        self.doc_graphicsview_2.close()
        self.thumb_graphicsview.close()

    def loadDocumentViewStatus(self, filename):
        dataFileName = self.app_data_path + os.sep + filename.replace(os.sep, '_') + '.json'
        try:
            with open(dataFileName, 'r') as f:
                status = json.load(f)
                return status
        except:
            return None

    def saveDocumentViewStatus(self, filename):
        if filename is None or not os.path.exists(filename):
            return
            
        assert(self.doc_graphicsview_1.current_filename == filename)
        docViewStatus1 = self.doc_graphicsview_1.getViewStatus()
        docViewStatus2 = self.doc_graphicsview_2.getViewStatus()
        thumbViewStatus = self.thumb_graphicsview.getViewStatus()
        splitterState = self.splitter_doc.saveState()
        # https://stackoverflow.com/questions/44257184/pyqt5-save-qbytearray-to-json-format
        splitterState = bytes(splitterState.toHex()).decode('utf-8')
        outDict = {
            "docView1": docViewStatus1,
            "docView2": docViewStatus2,
            'docSplitter': splitterState,
            "thumbView": thumbViewStatus
        }
        dataFileName = self.app_data_path + os.sep + filename.replace(os.sep, '_') + '.json'
        with open(dataFileName, 'w') as f:
            json.dump(outDict, f, indent=True)