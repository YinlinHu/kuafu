
from resources.ui_library import Ui_librarywidget
 
from PyQt5 import QtCore
from PyQt5 import QtGui
from PyQt5 import QtWidgets

from popplerqt5 import Poppler

from utils import debug
from pdfworker import PdfReader

import os

class LibraryView(QtWidgets.QWidget, Ui_librarywidget):
    # renderRequested = QtCore.pyqtSignal(int, float)
    # loadFileRequested = QtCore.pyqtSignal(str, str)
    # findTextRequested = QtCore.pyqtSignal(str, int, bool)
    readAnnotationRequested = QtCore.pyqtSignal(str)
    # readOutlineRequested = QtCore.pyqtSignal(Poppler.Document, QtGui.QStandardItemModel)
    # findTextRequested = QtCore.pyqtSignal(str, int, bool)
    # pagePositionChanged = QtCore.pyqtSignal(int, int)
    # showStatusRequested = QtCore.pyqtSignal(str)

    def __init__(self, parent, screen_dpi, thumbView):
        super(LibraryView, self).__init__(parent) # Call the inherited classes __init__ method
        self.setupUi(self)

        self.screen_dpi = screen_dpi
        # self.thumb_view = thumbView

        self.splitter_main.setSizes([2,4]) # set relative widths of its children

        self.splitter_main.setCollapsible(1, False) 
        # self.splitter_main.setCollapsible(0, False) 

        self.repos = ["/home/yhu/下载/", "/home/yhu/tmp/"]

        self.fileview_model = QtGui.QStandardItemModel(self)
        self.fileview.setModel(self.fileview_model)
        self.fileview.clicked.connect(self.onFileClick)

        self.fileview.setAlternatingRowColors(True)
        self.annotview.setAlternatingRowColors(True)

        self.annotview_model = QtGui.QStandardItemModel()
        self.annotview.setModel(self.annotview_model)
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

        dirname = self.repos[0]
        self.setFileList(dirname)

    def setFileList(self, dirname):
        # remove all file list first
        self.fileview_model.removeRows(0, self.fileview_model.rowCount())
        
        parent_file_item = self.fileview_model.invisibleRootItem()

        pdf_filenames = os.listdir(dirname)
        for name in pdf_filenames:
            path = dirname + name
            if os.path.isfile(path) and path.endswith('.pdf'):
                item = QtGui.QStandardItem(path)
                item.setData(path, QtCore.Qt.UserRole + 1)
                parent_file_item.appendRow(item)

    def onFileClick(self, m_index):
        # remove all annotatoin first
        self.annotview_model.removeRows(0, self.annotview_model.rowCount())

        self.filename = self.fileview_model.data(m_index, QtCore.Qt.UserRole + 1)
        print(self.filename)

        self.preview_graphicsview.setDocument(self.filename, self.screen_dpi)
        # self.thumb_view.setDocument(self.filename, self.screen_dpi)
        
        # self.readAnnotationRequested.emit(self.filename)

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

    def setColumnNumber(self, colNum):
        # self.thumb_view.setColumnNumber(colNum)
        return self.preview_graphicsview.setColumnNumber(colNum)

    def setPrecedingEmptyPage(self, emptyNum):
        # self.thumb_view.setPrecedingEmptyPage(emptyNum)
        return self.preview_graphicsview.setPrecedingEmptyPage(emptyNum)

    def zoomIn(self):
        self.preview_graphicsview.zoomIn()

    def zoomOut(self):
        self.preview_graphicsview.zoomOut()

    def zoomFitWidth(self):
        self.preview_graphicsview.zoomFitWidth()

    def closeEvent(self, ev):
        debug('closeEvent in LibraryView')
        self.preview_graphicsview.close()
        # self.thumb_view.close()
        
        # #  wait for the reader thread to exit
        # loop = QtCore.QEventLoop()
        # self.pdf_reader_thread.finished.connect(loop.quit)
        # self.pdf_reader_thread.quit()
        # loop.exec_()
        # debug('pdf_reader_thread exit')