 
from PyQt5 import QtCore
from PyQt5 import QtGui
from PyQt5 import QtWidgets

from resources.ui_annotation_item import Ui_annotationItemWidget

from popplerqt5 import Poppler

from utils import debug

class AnnotationFrame(QtWidgets.QFrame):
    """ This widget is a container of PageWidgets. PageWidget communicates
        Window through this widget """
    # jumpToRequested = QtCore.pyqtSignal(int, float)
    # copyTextRequested = QtCore.pyqtSignal(int, QtCore.QPoint, QtCore.QPoint)
    # showStatusRequested = QtCore.pyqtSignal(str)
    # pagePositionChanged = QtCore.pyqtSignal(int, int)

    # parent is scrollAreaWidgetContents
    def __init__(self, parent, scrollArea):
        super(AnnotationFrame, self).__init__(parent)

        self.setFrameShape(QtWidgets.QFrame.StyledPanel)
        self.setFrameShadow(QtWidgets.QFrame.Raised)

        self.vScrollbar = scrollArea.verticalScrollBar()
        self.hScrollbar = scrollArea.horizontalScrollBar()

        self.itemCount = 0

        self.setMouseTracking(True)
        self.clicked = False
        
        self.setContentsMargins(0, 0, 0, 0)

        # self.copy_text_mode = False

        # # 
        # self.doc = doc
        # self.pages_count = self.doc.numPages()
        # #
        # self.pre_empty_page_count = 0
        # self.view_column_count = 1

        self.layout = QtWidgets.QGridLayout(self)
        self.layout.setContentsMargins(0, 6, 0, 6) # left, top, right, bottom
        self.layout.setAlignment(QtCore.Qt.AlignTop | QtCore.Qt.AlignCenter)
        # self.layout.setHorizontalSpacing(3)
        self.layout.setVerticalSpacing(15)

        # self.page_widgets = []
        # self.rearrangePages()

        # self.current_page = 0
        # self.current_render_dpi = 0 
        # self.zoom_fit_width = True # default on
        # self.screen_dpi = screen_dpi

        # self.visible_pages = [0]
        # self.rendered_pages = {}
        # self.scrollAreaSize = [0, 0] # width and height of the parent scroll area size

        # # create render threads
        # self.num_threads = threads
        # self.render_list = []
        # for i in range(self.num_threads):
        #     tmpRender = PdfRender()
        #     tmpRender.rendered.connect(self.setRenderedImage)
        #     tmpRender.start()
        #     self.render_list.append(tmpRender)

        # # set document in other threads
        # for rd in self.render_list:
        #     rd.set_document(self.doc)

    
    def addItem(self, color, author, date, title, comments):
        annotItem = AnnotationItemWidget(0, self)
        annotItem.setData(color, author, date, title, comments)
        self.layout.addWidget(annotItem, self.itemCount, 0, QtCore.Qt.AlignCenter)
        self.itemCount += 1

    def handleScrollAreaResized(self, width, height):
        debug('scrollAreaResized in AnnotationFrame')
        debug(width, height)
        width = width - 30
        itemCount = self.layout.count()
        for i in range(itemCount):
            self.layout.itemAt(i).widget().setFixedWidth(width)

    def showEvent(self, ev):
        debug('showEvent in AnnotationFrame')
        # QtWidgets.QWidget.showEvent(self, ev)
        # self.resizePages(self.current_render_dpi)

    def closeEvent(self, ev):
        """ Save all settings on window close """
        debug('closeEvent in AnnotationFrame')
        # for rd in self.render_list:
        #     rd.stop_async()
        # for rd in self.render_list:
        #     rd.wait()
        # return QtWidgets.QFrame.closeEvent(self, ev)

    def wheelEvent(self, ev):
        debug("wheelEvent in AnnotationFrame")
        # modifiers = QtWidgets.QApplication.keyboardModifiers()
        # if modifiers == QtCore.Qt.ControlModifier:
        #     delta = ev.angleDelta()
        #     if delta.y() > 0:
        #         self.zoomIn()
        #     else:
        #         self.zoomOut()
        #     ev.accept() # accept an event in order to stop it from propagating further

    def mousePressEvent(self, ev):
        debug("mousePressEvent in AnnotationFrame")
        self.click_pos = ev.globalPos()
        self.v_scrollbar_pos = self.vScrollbar.value()
        self.h_scrollbar_pos = self.hScrollbar.value()
        self.clicked = True

    def mouseReleaseEvent(self, ev):
        debug("mouseReleaseEvent in AnnotationFrame")
        self.clicked = False
        self.setCursor(QtCore.Qt.OpenHandCursor)

    def mouseMoveEvent(self, ev):
        # debug("mouseMoveEvent in DocFrame")
        if not self.clicked : return
        self.setCursor(QtCore.Qt.ClosedHandCursor)
        self.vScrollbar.setValue(self.v_scrollbar_pos + self.click_pos.y() - ev.globalY())
        self.hScrollbar.setValue(self.h_scrollbar_pos + self.click_pos.x() - ev.globalX())

    # def showStatus(self, msg):
    #     self.showStatusRequested.emit(msg)


class AnnotationItemWidget(QtWidgets.QWidget, Ui_annotationItemWidget):
    """ This widget shows a rendered page """
    def __init__(self, page_num, frame=None):
        super(AnnotationItemWidget, self).__init__(frame)
        self.setupUi(self)

        self.manager = frame
        self.setMouseTracking(True)
        self.setSizePolicy(0,0)
        self.link_areas = []
        self.link_annots = []
        self.annots_listed, self.copy_text_mode = False, False
        self.click_point, self.highlight_area = None, None
        self.page_num = page_num
        self.image = QtGui.QPixmap()

        self.groupBox.setContentsMargins(0, 0, 0, 0)

        # self.setStyleSheet("border-width: 1px; border-style: solid; border-color: black; background-color: white")
    
    def setData(self, color, author, date, title, comments):
        # 
        self.label_indicator.setAutoFillBackground(True)
        self.label_indicator.setText("")

        self.label_indicator.setStyleSheet(
            "background-color: rgb(%d,%d,%d)" % (color.red(), color.green(), color.blue()))

        self.groupBox.setStyleSheet("QGroupBox {border-width: 0px; border-style: solid}")

        self.label_author.setText(author)
        self.label_date.setText(date.toString())

        if isinstance(title, QtGui.QImage):
            self.label_title.setScaledContents(True)
            self.label_title.setPixmap(QtGui.QPixmap.fromImage(title))
        else:
            self.label_title.setText(title)
            # self.label_title.setMinimumSize(self.label_title.sizeHint())
            # self.label_title.setWordWrap(True)
        self.edit_comments.setText(comments)

    def clear(self):
        QtWidgets.QLabel.clear(self)
        self.setText("Loading ...")
        self.image = QtGui.QPixmap()

    # def resizeEvent(self, ev):
    #     debug("resizeEvent in AnnotationItemWidget")
    #     # print(self.width(), self.height())
    #     # QtWidgets.QScrollArea.resizeEvent(self, ev) # call parent's event handler
    #     # self.resizeRequested.emit(self.width(), self.height())

    # def mouseMoveEvent(self, ev):
    #     pass
    # def mousePressEvent(self, ev):
    #     pass

    # def mouseReleaseEvent(self, ev):
    #     pass

    def updateImage(self):
        """ repaint page widget, and draw highlight areas """
        if self.highlight_area:
            img = self.image.copy()
            painter = QPainter(img)
            zoom = self.dpi / 72.0
            for area in self.highlight_area:
                box = QtCore.QRectF(area.left()*zoom, area.top()*zoom,
                                    area.width()*zoom, area.height()*zoom)
                painter.fillRect(box, QColor(0,255,0, 127))
            painter.end()
            self.setPixmap(img.scaled(self.width(), self.height()))
            # self.setPixmap(img)
        else:
            # self.setPixmap(self.image)
            self.setPixmap(self.image.scaled(self.width(), self.height()))
