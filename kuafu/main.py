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

from dialogs import ExportToImageDialog, DocInfoDialog

from docgraphicsview import DocGraphicsView

HOMEDIR = os.path.expanduser("~")

class MainWindow(QtWidgets.QMainWindow, Ui_window):
    def __init__(self, screens, app_data_path):
        super(MainWindow, self).__init__() # Call the inherited classes __init__ method
        self.setupUi(self)

        self.screen_dpi = screens[0].logicalDotsPerInch()
        self.app_data_path = app_data_path
        
        self.libWidget = LibraryView(self.centraltabwidget, self.screen_dpi, self.app_data_path)
        self.libWidget.fileReselected.connect(self.onFileReselected)
        self.libWidget.showStatusRequested.connect(self.onShowStatusRequested)
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
        self.libWidget.pushButton_open.clicked.connect(self.openFile)
        
        # self.pageToImageAction.triggered.connect(self.exportPageToImage)
        # self.docInfoAction.triggered.connect(self.docInfo)
        # self.toPSAction.triggered.connect(self.exportToPS)
        # self.printAction.triggered.connect(self.printFile)

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
        geometry = self.settings.value('geometry', bytes('', 'utf-8'))
        self.restoreGeometry(geometry)
        
        state = self.settings.value('library/spliter', bytes('', 'utf-8'))
        self.libWidget.splitter.restoreState(state)
        # state = self.settings.value('library/spliter_doc', bytes('', 'utf-8'))
        # self.libWidget.splitter_doc.restoreState(state)

        # self.offset_x = int(self.settings.value("OffsetX", 4))
        # self.offset_y = int(self.settings.value("OffsetY", 26))
        # self.available_area = [desktop.availableGeometry().width(), desktop.availableGeometry().height()]
        # self.zoomLevelCombo.setCurrentIndex(int(self.settings.value("ZoomLevel", 2)))

        # Connect Signals
        # self.findTextEdit.returnPressed.connect(self.findNext)
        # self.findNextButton.clicked.connect(self.findNext)
        # self.findBackButton.clicked.connect(self.findBack)
        # self.findCloseButton.clicked.connect(self.dockSearch.hide)
        # self.dockSearch.visibilityChanged.connect(self.toggleFindMode)

        self.recent_files_actions = []
        self.addRecentFiles()

        self.show()

        self.loadPDFfile(self.recent_files[0]) # load the latest one

    def onShowStatusRequested(self, msg):
        self.showStatus(msg)

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

    def onFileReselected(self, filefullpath):
        filename = os.path.split(filefullpath)[1]
        self.setWindowTitle(filename + ' -- kuafu')

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
        self.libWidget.setDocument(filename, self.screen_dpi)
        

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
        # if isinstance(widget, DocumentView):
        # remove
        widget.close()
        self.centraltabwidget.removeTab(tabIdx)

    def onAppQuit(self):
        debug("OnAppQuit")
        """ Close running threads """
        tabCnt = self.centraltabwidget.count()
        for i in range(tabCnt):
            self.centraltabwidget.widget(i).close()

        # filename = widget.filename
        # current_page = widget.current_page
        if len(self.libWidget.filename) > 0:
            self.saveFileData(self.libWidget.filename, 0)
        # 
        geometry = self.saveGeometry()
        self.settings.setValue('geometry', geometry)

        state = self.libWidget.splitter.saveState()
        self.settings.setValue('library/spliter', state)
        # state = self.libWidget.splitter_doc.saveState()
        # self.settings.setValue('library/spliter_doc', state)

        # self.settings.setValue("OffsetX", self.geometry().x()-self.x())
        # self.settings.setValue("OffsetY", self.geometry().y()-self.y())
        # self.settings.setValue("ZoomLevel", self.zoom_level)
        if len(self.history_filenames) > 0:
            self.settings.setValue("HistoryFileNameList", self.history_filenames[:100])
        if len(self.history_page_no) > 0:
            self.settings.setValue("HistoryPageNoList", self.history_page_no[:100])
        if len(self.recent_files) > 0:
            self.settings.setValue("RecentFiles", self.recent_files[:10]) 

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
    # 
    # https://stackoverflow.com/questions/32525196/how-to-get-a-settings-storage-path-in-a-cross-platform-way-in-qt
    app.setOrganizationDomain("huyinlin@gmail.com")
    app.setApplicationName("kuafu")
    app_data_path = QtCore.QStandardPaths.writableLocation(QtCore.QStandardPaths.AppDataLocation)
    if not os.path.exists(app_data_path):
        os.makedirs(app_data_path)
    # 
    win = MainWindow(app.screens(), app_data_path)
    if len(sys.argv)>1 and os.path.exists(os.path.abspath(sys.argv[-1])):
        win.loadPDFfile(os.path.abspath(sys.argv[-1]))
    app.aboutToQuit.connect(win.onAppQuit)
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
