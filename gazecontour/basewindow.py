import sys
from PySide import QtGui
from PySide.QtCore import Qt

class BaseMainWindow(QtGui.QMainWindow):
    """
    A common base for the main window widgets
    """
    def __init__(self, parent=None):
        # Initialize the object as a QWidget and
        # set its title and minimum width
        super().__init__(parent)

        self.setMinimumSize(640, 480)
        self.setSizePolicy(QtGui.QSizePolicy.Expanding, QtGui.QSizePolicy.Expanding)

        self.toolbar = QtGui.QToolBar('Toolbar', self)
        self.toolbar.setMovable(False)
        self.toolbar.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self.toolbar.setAutoFillBackground(True)
        self.addToolBar(Qt.LeftToolBarArea, self.toolbar)

        self.statusBar().setAutoFillBackground(True)

    def sizeHint(self):
        """
        Return a large size hint. (though Qt will still limit the initial 
        window size to 2/3 of the screen dimensions)
        """
        d = QtGui.QDesktopWidget()
        return d.availableGeometry().size()

    @classmethod
    def runApp(cls):
        """
        Initialize a QApplication and run this as the main window.
        """
        qt_app = QtGui.QApplication(sys.argv)
        win = cls()
        win.show()
        return qt_app.exec_()
