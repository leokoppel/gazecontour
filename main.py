import sys
from PySide.QtCore import Qt
from PySide.QtGui import QApplication
from PySide import QtGui

import gazecontour.eyetribe
from gazecontour.gazewindow import GazeWindow
from gazecontour.analysiswindow import AnalysisWindow
from gazecontour.recorder import Recorder
from gazecontour import images

# Set up logging
import logging
logging.basicConfig(format='[%(levelname)-8s] %(name)15s: %(message)s', level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Set up crash report
import faulthandler
faulthandler.enable()


class MainWindowContainer(QtGui.QTabWidget):
    """
    Container window holding both the gaze recorder and analysis widgets in
    a tabbed view (though both are basically stand-alone).
    """

    def __init__(self):
        super().__init__()
        self.gazeWindow = GazeWindow(self, None)
        self.analysisWindow = AnalysisWindow(self, self.gazeWindow.recorder)
        self.addTab(self.gazeWindow, 'Gaze')
        self.addTab(self.analysisWindow, 'Analyze')

        # Stop recording on tab switch
        self.currentChanged.connect(self.tabChanged)

    def tabChanged(self, index):
        if index == self.indexOf(self.gazeWindow):
            self.gazeWindow.tracker.start()
        else:
            self.gazeWindow.tracker.stop()
            self.gazeWindow.recorder.setRecording(False)



def main():
    # Set up application object
    qt_app = QApplication(sys.argv)
    win = MainWindowContainer()
    win.setWindowTitle('Gaze GUI')
    win.show()
    
    # save time
#    win.analysisWindow.loadFile('D:\workspace\gazecontour\gazecontour\data\dot1.xlsx')
#    win.setCurrentIndex(1)
    
    return qt_app.exec_()

if __name__ == '__main__':
    sys.exit(main())
