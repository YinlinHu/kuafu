#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys, os

from subprocess import Popen

from PyQt5 import QtCore
from PyQt5 import QtGui
from PyQt5 import QtWidgets

# add parent directory to path
currentDir = os.path.dirname(os.path.abspath(__file__))
parentDir = os.path.dirname(currentDir)
# debug(currentDir)
# debug(parentDir)
sys.path.append(currentDir)
# sys.path.append(parentDir)
sys.path.append(currentDir + os.path.sep + 'resources')

from utils import debug

from resources.ui_main import Ui_window

from document import DocumentView
from library import LibraryView

from lineedit import PageNoLineEdit, FindLineEdit

from dialogs import ExportToImageDialog, DocInfoDialog

from docgraphicsview import DocGraphicsView

HOMEDIR = os.path.expanduser("~")

class MainWindow(QtWidgets.QMainWindow, Ui_window):
    def __init__(self, screens):
        super(MainWindow, self).__init__() # Call the inherited classes __init__ method
        self.setupUi(self)

        # self.dockWidget = QtWidgets.QDockWidget('Dock Test', self)
        # self.thumbView = DocGraphicsView(self.dockWidget, render_num=2)
        # self.dockWidget.setWidget(self.thumbView)
        # self.dockWidget.setFloating(False)
        # self.addDockWidget(QtCore.Qt.RightDockWidgetArea, self.dockWidget)

        self.screen_dpi = screens[0].logicalDotsPerInch()
        
        self.libWidget = LibraryView(self.centraltabwidget, self.screen_dpi, None)
        self.libWidget.preview_graphicsview.pagePositionChanged.connect(self.setPageInfoOnToolbar)
        self.libWidget.preview_graphicsview.zoomRatioChanged.connect(self.onZoomRatioChanged)
        self.libWidget.preview_graphicsview.viewColumnChanged.connect(self.onViewColumnChanged)
        self.libWidget.preview_graphicsview.emptyLeadingPageChanged.connect(self.onEmptyLeadingPageChanged)
        self.centraltabwidget.addTab(self.libWidget, "My Library")
        
        self.centraltabwidget.setTabsClosable(True)

        # https://stackoverflow.com/questions/2616483/close-button-only-for-some-tabs-in-qt
        # make the first tab unclosable
        self.centraltabwidget.tabBar().tabButton(0, QtWidgets.QTabBar.RightSide).resize(0,0)

        self.centraltabwidget.currentChanged.connect(self.onTabChanged)
        self.centraltabwidget.tabCloseRequested.connect(self.onTabClose)
        self.centraltabwidget.setStyleSheet("QTabWidget::pane {margin: 0 0 0 0}")

        # self.dockSearch.hide()
        # self.dockWidget.hide()
        # self.dockWidget.setMinimumWidth(310)
        # self.findTextEdit.setFocusPolicy(QtCore.Qt.StrongFocus)

        # resizing pages requires some time to take effect
        # self.resize_page_timer = QtCore.QTimer(self)
        # self.resize_page_timer.setSingleShot(True)
        # self.resize_page_timer.timeout.connect(self.onWindowResize)
        # Add shortcut actions
        # self.gotoPageAction = QtWidgets.QAction(QIcon(":/goto.png"), "GoTo Page", self)
        # self.gotoPageAction.triggered.connect(self.gotoPage)
        # self.copyTextAction = QtWidgets.QAction(QIcon(":/copy.png"), "Copy Text", self)
        # self.copyTextAction.setCheckable(True)
        # self.copyTextAction.triggered.connect(self.toggleCopyText)
        # self.findTextAction = QtWidgets.QAction(QIcon(":/search.png"), "Find Text", self)
        # self.findTextAction.setShortcut('Ctrl+F')
        # self.findTextAction.triggered.connect(self.dockSearch.show)

        # connect menu actions signals
        self.openFileAction.triggered.connect(self.openFile)
        # self.printAction.triggered.connect(self.printFile)
        # self.quitAction.triggered.connect(self.close)
        # self.toPSAction.triggered.connect(self.exportToPS)
        # self.pageToImageAction.triggered.connect(self.exportPageToImage)
        # self.docInfoAction.triggered.connect(self.docInfo)
        self.zoominAction.triggered.connect(self.zoomIn)
        self.zoomoutAction.triggered.connect(self.zoomOut)
        self.zoomFitwidthAction.triggered.connect(self.zoomFitWidth)
        
        self.zoomFitwidthAction.setChecked(True)

        self.actionViewInOneColumn.triggered.connect(self.onViewInOneColumn)
        self.actionViewInTwoColumns.triggered.connect(self.onViewInTwoColumns)
        self.actionViewInFourColumns.triggered.connect(self.onViewInFourColumns)
        self.actionPrecedingEmptyPage.triggered.connect(self.onPrecedingEmptyPage)

        # default is one column
        self.actionViewInOneColumn.setChecked(True)

        # self.undoJumpAction.triggered.connect(self.undoJump)
        self.prevPageAction.triggered.connect(self.goPrevPage)
        self.nextPageAction.triggered.connect(self.goNextPage)
        self.actionFind.triggered.connect(self.onActionFind)
        # self.lastPageAction.triggered.connect(self.goLastPage)

        self.pageNoEdit = PageNoLineEdit(self)
        self.pageNoEdit.returnPressed.connect(self.gotoPage)

        self.findTxtEdit = FindLineEdit(self)

        self.pageNoLabel = QtWidgets.QLabel(self)
        self.pageNoLabel.setFrameShape(QtWidgets.QFrame.StyledPanel)
        self.pageNoLabel.setText('of')

        # self.viewColumnNumberCombo = QtWidgets.QComboBox(self)
        # self.viewColumnNumberCombo.activated.connect(self.setViewColumnNumber)
        # self.viewColumnNumberCombo.addItems(["1", "2", "3", "4", "5", "6", "7", "8", "9", "10"])
        # self.zoom_levels = [0, 75, 90, 100, 110 , 121, 133, 146, 175, 200, 400, 800, 1600]

        # Add toolbar actions
        self.toolBar.addAction(self.undoJumpAction)
        self.toolBar.addAction(self.redoJumpAction)
        self.toolBar.addSeparator()
        self.toolBar.addAction(self.openFileAction)
        self.toolBar.addAction(self.printAction)
        # self.toolBar.addAction(self.docInfoAction)
        self.toolBar.addSeparator()
        self.toolBar.addAction(self.zoomoutAction)
        self.toolBar.addAction(self.zoominAction)
        self.toolBar.addAction(self.zoomFitwidthAction)
        self.toolBar.addSeparator()
        self.toolBar.addAction(self.actionViewInOneColumn)
        self.toolBar.addAction(self.actionViewInTwoColumns)
        self.toolBar.addAction(self.actionViewInFourColumns)
        self.toolBar.addAction(self.actionPrecedingEmptyPage)
        self.toolBar.addSeparator()
        # self.toolBar.addAction(self.firstPageAction)
        self.toolBar.addAction(self.prevPageAction)
        self.toolBar.addWidget(self.pageNoEdit)
        self.toolBar.addWidget(self.pageNoLabel)
        self.toolBar.addAction(self.pageCountAction)
        self.toolBar.addAction(self.nextPageAction)
        # self.toolBar.addAction(self.lastPageAction)
        self.toolBar.addSeparator()
        self.toolBar.addAction(self.actionFind)
        self.toolBar.addWidget(self.findTxtEdit)
        # self.toolBar.addAction(self.redoModificationAction)
        spacer = QtWidgets.QWidget(self)
        spacer.setSizePolicy(1|2|4,1|4)
        self.toolBar.addWidget(spacer)
        self.toolBar.addSeparator()
        # self.toolBar.addAction(self.quitAction)

        # # Add widgets
        # self.statusbar = QLabel(self)
        # self.statusbar.setStyleSheet("QLabel { font-size: 12px; border-radius: 2px; padding: 2px; background: palette(highlight); color: palette(highlighted-text); }")
        # self.statusbar.setMaximumHeight(16)
        # self.statusbar.hide()

        # Import settings
        desktop = QtWidgets.QApplication.desktop()
        self.settings = QtCore.QSettings("kuafu", "main", self)
        self.recent_files = self.settings.value("RecentFiles", [])
        self.history_filenames = self.settings.value("HistoryFileNameList", [])
        self.history_page_no = self.settings.value("HistoryPageNoList", [])
        self.offset_x = int(self.settings.value("OffsetX", 4))
        self.offset_y = int(self.settings.value("OffsetY", 26))
        self.available_area = [desktop.availableGeometry().width(), desktop.availableGeometry().height()]
        # self.zoomLevelCombo.setCurrentIndex(int(self.settings.value("ZoomLevel", 2)))

        # Connect Signals
        # self.findTextEdit.returnPressed.connect(self.findNext)
        # self.findNextButton.clicked.connect(self.findNext)
        # self.findBackButton.clicked.connect(self.findBack)
        # self.findCloseButton.clicked.connect(self.dockSearch.hide)
        # self.dockSearch.visibilityChanged.connect(self.toggleFindMode)

        self.recent_files_actions = []
        self.addRecentFiles()

        # Show Window
        width = int(self.settings.value("WindowWidth", 1040))
        height = int(self.settings.value("WindowHeight", 717))

        self.resize(width, height)
        self.show()

    def showStatus(self, msg):
        self.statusBar.showMessage(msg, msecs=5000)
        # if url=="":
        #     self.statusbar.hide()
        #     return
        # self.statusbar.setText(url)
        # self.statusbar.adjustSize()
        # self.statusbar.move(0, self.height()-self.statusbar.height())
        # self.statusbar.show()

    def onActionFind(self):
        self.findTxtEdit.setFocus()

    def onViewInOneColumn(self):
        cIdx = self.centraltabwidget.currentIndex()
        widget = self.centraltabwidget.widget(cIdx)
        # if isinstance(widget, DocumentView):
        widget.setColumnNumber(1)

    def onViewInTwoColumns(self):
        cIdx = self.centraltabwidget.currentIndex()
        widget = self.centraltabwidget.widget(cIdx)
        # if isinstance(widget, DocumentView):
        widget.setColumnNumber(2)

    def onViewInFourColumns(self):
        cIdx = self.centraltabwidget.currentIndex()
        widget = self.centraltabwidget.widget(cIdx)
        # if isinstance(widget, DocumentView):
        widget.setColumnNumber(4)

    def onPrecedingEmptyPage(self):
        cIdx = self.centraltabwidget.currentIndex()
        widget = self.centraltabwidget.widget(cIdx)
        # if isinstance(widget, DocumentView):
        if self.actionPrecedingEmptyPage.isChecked():
            widget.setPrecedingEmptyPage(1)
        else:
            widget.setPrecedingEmptyPage(0)

    def zoomIn(self):
        cIdx = self.centraltabwidget.currentIndex()
        widget = self.centraltabwidget.widget(cIdx)
        # if isinstance(widget, DocumentView):
        self.zoomFitwidthAction.setChecked(False)
        widget.zoomIn()

    def zoomOut(self):
        cIdx = self.centraltabwidget.currentIndex()
        widget = self.centraltabwidget.widget(cIdx)
        # if isinstance(widget, DocumentView):
        self.zoomFitwidthAction.setChecked(False)
        widget.zoomOut()

    def zoomFitWidth(self):
        cIdx = self.centraltabwidget.currentIndex()
        widget = self.centraltabwidget.widget(cIdx)
        # if isinstance(widget, DocumentView):
        self.zoomFitwidthAction.setChecked(True)
        widget.zoomFitWidth()

    def goPrevPage(self):
        debug("goPrevPage")
        cIdx = self.centraltabwidget.currentIndex()
        widget = self.centraltabwidget.widget(cIdx)
        if isinstance(widget, DocumentView):
            widget.goPrevPage()

    def goNextPage(self):
        debug("goNextPage")
        cIdx = self.centraltabwidget.currentIndex()
        widget = self.centraltabwidget.widget(cIdx)
        if isinstance(widget, DocumentView):
            widget.goNextPage()

    def gotoPage(self):
        debug("gotoPage")
        page_no = int(self.pageNoEdit.text())
        cIdx = self.centraltabwidget.currentIndex()
        widget = self.centraltabwidget.widget(cIdx)
        if isinstance(widget, DocumentView):
            widget.gotoPage(page_no - 1)
            self.pageNoEdit.clearFocus()

    def onZoomRatioChanged(self, zoomRatio):
        if zoomRatio == 0:
            self.showStatus("Zoom fitted to width")
        else:
            self.zoomFitwidthAction.setChecked(False)
            self.showStatus("Zoom to %d%%" % int(zoomRatio * 100))
    
    def onViewColumnChanged(self, viewColumn):
        if viewColumn == 1:
            self.actionViewInOneColumn.setChecked(True)
            self.actionViewInTwoColumns.setChecked(False)
            self.actionViewInFourColumns.setChecked(False)
        elif viewColumn == 2:
            self.actionViewInOneColumn.setChecked(False)
            self.actionViewInTwoColumns.setChecked(True)
            self.actionViewInFourColumns.setChecked(False)
        elif viewColumn == 4:
            self.actionViewInOneColumn.setChecked(False)
            self.actionViewInTwoColumns.setChecked(False)
            self.actionViewInFourColumns.setChecked(True)
        else:
            assert(0)

    def onEmptyLeadingPageChanged(self, emptyPages):
        if emptyPages == 0:
            self.actionPrecedingEmptyPage.setChecked(False)
        elif emptyPages == 1:
            self.actionPrecedingEmptyPage.setChecked(True)
        else:
            assert(0)

    def setPageInfoOnToolbar(self, current_idx, total_count):
        self.pageNoEdit.setMaxLength(len(str(total_count)))
        self.pageNoEdit.setText("%d" % (current_idx +1))
        self.pageCountAction.setText("%d" % total_count)

    def addRecentFiles(self):
        self.recent_files_actions[:] = [] # pythonic way to clear list
        self.menuRecentFiles.clear()
        for each in self.recent_files:
            name = elideMiddle(os.path.basename(each), 60)
            action = self.menuRecentFiles.addAction(name, self.openRecentFile)
            self.recent_files_actions.append(action)
        self.menuRecentFiles.addSeparator()
        self.menuRecentFiles.addAction(QtGui.QIcon(':/edit-clear.png'), 'Clear Recents', self.clearRecents)

    def openRecentFile(self):
        action = self.sender()
        index = self.recent_files_actions.index(action)
        self.loadPDFfile(self.recent_files[index])

    def clearRecents(self):
        self.recent_files_actions[:] = []
        self.menuRecentFiles.clear()
        self.recent_files[:] = []

    def removeOldDoc(self):
        # Save current page number
        self.saveFileData()
        # Remove old document
        for i in range(len(self.pages)):
            self.verticalLayout.removeWidget(self.pages[-1])
        for i in range(len(self.pages)):
            self.pages.pop().deleteLater()
        self.frame.deleteLater()
        self.jumped_from = None
        #self.addRecentFiles()

    def loadPDFfile(self, filename):
        """ Loads pdf document in all threads """
        filename = os.path.expanduser(filename)
        
        # widget = DocumentView(self.centraltabwidget, filename, self.screen_dpi)
        # widget.showStatusRequested.connect(self.showStatus)
        # self.centraltabwidget.addTab(widget, filename)
        # self.centraltabwidget.setCurrentWidget(widget)

        # self.annotview_model.removeRows(0, self.annotview_model.rowCount())
        self.libWidget.preview_graphicsview.setDocument(filename, self.screen_dpi)
        

    def openFile(self):
        filename, sel_filter = QtWidgets.QFileDialog.getOpenFileName(self,
                                      "Select Document to Open", "",
                                      "Portable Document Format (*.pdf);;All Files (*)" )
        if filename != "":
            self.loadPDFfile(filename)

    def printFile(self):
        Popen(["quikprint", self.filename])

    def exportToPS(self):
        width = self.doc.page(self.current_page-1).pageSizeF().width()
        height = self.doc.page(self.current_page-1).pageSizeF().height()
        filename, sel_filter = QtWidgets.QFileDialog.getSaveFileName(self, "Select File to Save",
                                       os.path.splitext(self.filename)[0]+'.ps',
                                      "Adobe Postscript Format (*.ps)" )
        if filename == '' : return
        conv = self.doc.psConverter()
        conv.setPaperWidth(width)
        conv.setPaperHeight(height)
        conv.setOutputFileName(filename)
        conv.setPageList([i+1 for i in range(self.pages_count)])
        ok = conv.convert()
        if ok:
            QMessageBox.information(self, "Successful !","File has been successfully exported")
        else:
            QMessageBox.warning(self, "Failed !","Failed to export to Postscript")

    def exportPageToImage(self):
        dialog = ExportToImageDialog(self.current_page, self.pages_count, self)
        if dialog.exec_() == QDialog.Accepted:
            try:
                dpi = int(dialog.dpiEdit.text())
                page_no = dialog.pageNoSpin.value()
                filename = os.path.splitext(self.filename)[0]+'-'+str(page_no)+'.jpg'
                page = self.doc.page(page_no-1)
                if not page : return
                img = page.renderToImage(dpi, dpi)
                img.save(filename)
                QMessageBox.information(self, "Successful !","Page has been successfully exported")
            except:
                QMessageBox.warning(self, "Failed !","Failed to export to Image")

    def onTabChanged(self, tabIdx):
        debug("tab changed")
        widget = self.centraltabwidget.widget(tabIdx)
        if isinstance(widget, DocumentView):
            currentPage = widget.current_page
            currentPageCount = widget.pages_count
            self.setPageInfoOnToolbar(currentPage, currentPageCount)
            widget.pagePositionChanged.connect(self.setPageInfoOnToolbar)

    def saveFileData(self, filename, current_page):
        if filename != '':
            filename = collapseUser(filename)
            if filename in self.history_filenames:
                index = self.history_filenames.index(filename)
                self.history_page_no[index] = current_page
            else:
                self.history_filenames.insert(0, filename)
                self.history_page_no.insert(0, current_page)
            if filename in self.recent_files:
                self.recent_files.remove(filename)
            self.recent_files.insert(0, filename)

    def onTabClose(self, tabIdx):
        widget = self.centraltabwidget.widget(tabIdx)
        # save information if necessary
        if isinstance(widget, DocumentView):
            filename = widget.filename
            current_page = widget.current_page
            self.saveFileData(filename, current_page)
            # 
            self.settings.setValue("OffsetX", self.geometry().x()-self.x())
            self.settings.setValue("OffsetY", self.geometry().y()-self.y())
            # self.settings.setValue("ZoomLevel", self.zoom_level)
            self.settings.setValue("HistoryFileNameList", self.history_filenames[:100])
            self.settings.setValue("HistoryPageNoList", self.history_page_no[:100])
            self.settings.setValue("RecentFiles", self.recent_files[:10]) 
        # remove
        widget.close()
        self.centraltabwidget.removeTab(tabIdx)

    def onAppQuit(self):
        debug("OnAppQuit")
        """ Close running threads """
        tabCnt = self.centraltabwidget.count()
        for i in range(tabCnt):
            self.centraltabwidget.widget(i).close()

def wait(millisec):
    loop = QtCore.QEventLoop()
    QtCore.QTimer.singleShot(millisec, loop.quit)
    loop.exec_()

def elideMiddle(text, length):
    if len(text) <= length: return text
    return text[:length//2] + '...' + text[len(text)-length+length//2:]

def collapseUser(path):
    ''' converts /home/user/file.ext to ~/file.ext '''
    if path.startswith(HOMEDIR):
        return path.replace(HOMEDIR, '~', 1)
    return path

def main():
    app = QtWidgets.QApplication(sys.argv)
    win = MainWindow(app.screens())
    if len(sys.argv)>1 and os.path.exists(os.path.abspath(sys.argv[-1])):
        win.loadPDFfile(os.path.abspath(sys.argv[-1]))
    app.aboutToQuit.connect(win.onAppQuit)
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
