import sys
import logging
import datetime
import importlib

from PySide import QtCore, QtGui
from PySide.QtCore import Qt
import pandas
import numpy as np
import pyqtgraph
import matplotlib.pyplot as plt
from scipy.optimize import curve_fit


import gazecontour.realtime
from gazecontour import basewindow
from gazecontour.recorder import Recorder
import bezier


logger = logging.getLogger(__name__)


class AnalysisWindow(basewindow.BaseMainWindow):
    """
    Widget which analyzes previously recorded gaze gazeData
    """

    def initPlotItems(self):
        """
        Set up the appearances and plotting functions of items in the gaze plot
        """
        @self.plotElement('raw', pyqtgraph.PlotDataItem(symbol='o', symbolSize=3, symbolBrush='r', pen={'color':'e36', 'width':1}, symbolPen=None))
        def plot_raw(df):
            return (df['raw_x'], df['raw_y'])

        @self.plotElement('avg', pyqtgraph.PlotDataItem(symbol='o', symbolSize=5, symbolBrush='b', pen={'color':'88b', 'width':1}, symbolPen=None))
        def plot_avg(df):
            return (df['avg_x'], df['avg_y'])

        @self.plotElement('cursor', pyqtgraph.PlotDataItem(symbol='+', symbolSize=5, symbolBrush='g', pen={'color':'ada', 'width':1}, symbolPen=None))
        def plot_cursor(df):
            return (df['cursor_x'], df['cursor_y'])

        @self.plotElement('fix', pyqtgraph.PlotDataItem(symbol='o', symbolSize=5, symbolBrush='c', pen={'color':'99f', 'width':1}, symbolPen=None))
        def fixations(df):
            N = 15 # length of buffer
            px_thresh= 100 # pixel distance threshold for saccades
                        
            # This is actually post-processing, but simulate real-time
            p = gazecontour.realtime.GazeProcessor(N, px_thresh)
            
            (fixation_x, fixation_y) = p.process_dataframe(df)
                                  
            
            # for output
            df['fixation_x'] = pandas.Series(fixation_x, index=df.index)
            df['fixation_y'] = pandas.Series(fixation_y, index=df.index)
            return (df['fixation_x'], df['fixation_y'])
        
        @self.plotElement('path', pyqtgraph.PlotDataItem(symbol='x', symbolSize=5, symbolBrush='m', pen={'color':'4B0082', 'width':1}, symbolPen=None))
        def plot_path(df):
            pass
        
        self.stimItem = None

    def __init__(self, parent=None, recorder=None):
        super().__init__(parent)

        # Use given recorder, to load just-collected gazeData, if available
        self.recorder = recorder

        self.gazeData = pandas.DataFrame()
        self.path = None

        pyqtgraph.setConfigOption('background', 'w')
        pyqtgraph.setConfigOption('foreground', 'k')

        analysisWidget = pyqtgraph.GraphicsLayoutWidget(self)

        # Prepare plots
        self.gazePlot = analysisWidget.addPlot(row=1, col=1)
        self.speedPlot = analysisWidget.addPlot(row=2, col=1, colspan=2)
        self.gazePlot.setSizePolicy(QtGui.QSizePolicy.Expanding, QtGui.QSizePolicy.Expanding)
        self.gazePlot.invertY()
        self.xPlot = analysisWidget.addPlot(row=1, col=2)

        self.speedPlot.setSizePolicy(QtGui.QSizePolicy.Expanding, QtGui.QSizePolicy.Maximum)
        self.gazePlot.setLabels(left='px', bottom='px')
        self.xPlot.setLabels(left='px', bottom='Time (s)')
        self.speedPlot.setLabels(left='Speed (px/s)', bottom='Time (s)')

        # A region on the bottom (speed) plot is used to select the
        # time interval to show on the top (gaze) plot
        self.timeRegion = pyqtgraph.LinearRegionItem()
        self.gazePlot.setAspectLocked(ratio=1)
        self.gazePlot.disableAutoRange()

        self.regionBeingDragged = False
        self.timeRegion.sigRegionChanged.connect(self.handleRegionChanged)
        self.timeRegion.sigRegionChangeFinished.connect(self.handleRegionChangeFinished)


        self.setCentralWidget(analysisWidget)

        # Actions
        if self.recorder:
            loadRecAction = QtGui.QAction(self.style().standardIcon(QtGui.QStyle.SP_BrowserReload), 'Load rec.', self)
            self.toolbar.addAction(loadRecAction)
            loadRecAction.triggered.connect(self.loadFromRecorder)

        loadFileAction = QtGui.QAction(self.style().standardIcon(QtGui.QStyle.SP_DirHomeIcon), 'Load file', self)
        self.toolbar.addAction(loadFileAction)
        loadFileAction.triggered.connect(self.loadFile)

        # Set up plot items and add checkboxes to the toolbar
        self.plotElements = {}
        self.toolbar.addSeparator()
        self.initPlotItems()
        
        self.initPlayAnimation()
        
        
    def initPlayAnimation(self):
        """
        Initialize actions, timer, and buttons for play/pause/stop animation of the
        gaze plot
        """
        
        # Start a timer for "play" animation Note QTimer is not reliable in its
        # interval, thus we use an elapsedTimer to calculate the correct
        # animation size
        self.animTimer = QtCore.QTimer(self)
        self.animTimer.setInterval(1000.0 / 30) # 30 fps, not precise -- will be somewhat less
        self.animElapsedTimer = QtCore.QElapsedTimer()
        self.animElapsedTimer.start()

        # Play/stop buttons
        playAct = QtGui.QAction(self.style().standardIcon(QtGui.QStyle.SP_MediaPlay), 'Play', self)
        pauseAct = QtGui.QAction(self.style().standardIcon(QtGui.QStyle.SP_MediaPause), 'Pause', self)
        stopAct = QtGui.QAction(self.style().standardIcon(QtGui.QStyle.SP_MediaStop), 'Stop', self)

        def pauseRegion():
            self.animTimer.stop()
            self.timeRegion.lineMoveFinished()
        def stopRegion():
            self.animTimer.stop()
            x1, x2 = self.timeRegion.getRegion()
            self.timeRegion.setRegion((0, x2 - x1))

        def _setRegionDirect(r, rgn):
                if r.lines[0].value() == rgn[0] and self.lines[1].value() == rgn[1]:
                    return
                r.blockLineSignal = True
                r.lines[0].setValue(rgn[0])
                r.blockLineSignal = False
                r.lines[1].setValue(rgn[1])
                r.lineMoved()

        def advanceRegion():
            # Call out own version of setRegion because we don't want to emit sigRegionChangeFinished
            try:
                frameSecs = self.animElapsedTimer.restart() / 1000.0
                print(frameSecs)
                x1, x2 = self.timeRegion.getRegion()
                if x1 < self.gazeData['time'][-1]:
                    _setRegionDirect(self.timeRegion, (x1 + frameSecs, x2 + frameSecs))
                else:
                    pauseRegion()
            except KeyError:
                pauseRegion()
        def playRegion():
            self.animElapsedTimer.restart()
            self.animTimer.start()

        self.animTimer.timeout.connect(advanceRegion)
        playAct.triggered.connect(playRegion)
        pauseAct.triggered.connect(self.animTimer.stop)
        stopAct.triggered.connect(stopRegion)
        self.toolbar.addSeparator()
        self.toolbar.addActions([playAct, pauseAct, stopAct])



    class PlotElementWrapper(object):
        """ convenience wrapper for a plot item with 'enable' checkbox """
        def __init__(self, plotItem, xPlotItem, checkbox, dataFunc, parent):
            self.plotItem = plotItem
            self.xPlotItem = xPlotItem
            self.checkbox = checkbox
            self.dataFunc = dataFunc
            self.parent = parent
            self.data = (pandas.DataFrame(), pandas.DataFrame())
            try:
                self.origSymbol = self.plotItem.opts['symbol']
            except AttributeError: #this type of item has no symbol
                self.origSymbol = None
        
        def loadData(self, df):
            self.data = self.dataFunc(df)

        def update(self, timeSlice):
            """
            Called while dragging the time region and after loading data. Update
            the plot, but if dragging first set to plot as lines (not with
            symbols) to avoid pyqtgraph's performance issues with scatter plots
            """
            if self.checkbox.isChecked():
                self.plotItem.show()
                self.xPlotItem.show()
                try:
                    if self.data and len(self.data[0]):
                        data = (self.data[0][timeSlice], self.data[1][timeSlice])
                        opts = {'symbol' : None if self.parent.regionBeingDragged else self.origSymbol}
                        self.plotItem.setSymbol(opts['symbol'])
                        self.plotItem.setData(*data, opts=opts)
                        self.xPlotItem.setData(self.parent.gazeData['time'][timeSlice], data[0])
                except AttributeError: # e.g. ImageItems have no symbols
                    pass
            else:
                self.plotItem.hide()
                self.xPlotItem.hide()


    def plotElement(self, name, plotItem):
        """Decorator to add plot items to gazePlot, and store wrapper objects in a dict"""
        plotItem = plotItem
        import copy
        xPlotItem = plotItem.__class__()
        try:
            xPlotItem.opts = plotItem.opts
        except AttributeError:
            pass
        self.gazePlot.addItem(plotItem)
        self.xPlot.addItem(xPlotItem)
        checkbox = QtGui.QCheckBox(name.capitalize(), self)
        self.toolbar.addWidget(checkbox)
        checkbox.setChecked(True)
        checkbox.toggled.connect(self.updatePlot)

        def decorator(f):
            """ Process the plotting function being decorated"""
            self.plotElements[name] = self.PlotElementWrapper(plotItem, xPlotItem, checkbox, f, self)
            return f
        return decorator

    def handleRegionChanged(self):
        self.regionBeingDragged = True
        self.updatePlot()

    def handleRegionChangeFinished(self):
        self.regionBeingDragged = False
        self.updatePlot()

    def updatePlot(self):
        """
        Replot gaze, showing points only between minSecs and maxSecs in the recording
        """
        minSecs, maxSecs = self.timeRegion.getRegion()
        if len(self.gazeData) > 0:
            timeSlice = slice(self.gazeData.index[0] + datetime.timedelta(seconds=minSecs),
                              self.gazeData.index[0] + datetime.timedelta(seconds=maxSecs))
            # TODO: can optimize this
            # Update gaze and mouse plots
            for m in self.plotElements.values():
                try:
                    m.update(timeSlice)
                except:
                    pass


    def loadData(self, df):
        # Want index as seconds relative to first data point
        df.index = pandas.to_datetime(df.index)
        df['time'] = (df['time'] - df['time'][0]) / 1000.0
        df = df[df['raw_x'] != 0.0]
        
        self.gazeData = df
        
        # Get speed of gaze over time (calcluate from components)
        t = df['time']
        dt = np.gradient(t)
        v = (np.gradient(df['avg_x'].values, dt), np.gradient(df['avg_y'].values, dt))
        speed = np.linalg.norm(v, axis=0) # speed in pixels/sec

        # Plot speed
        self.speedPlot.clear()
        self.speedPlot.plot(t, speed)
        self.speedPlot.addItem(self.timeRegion, ignoreBounds=True)

        # Plot gaze over entire time interval
        maxSecs = df['time'][-1]
        self.speedPlot.setXRange(0, maxSecs)
        self.timeRegion.setRegion((0, maxSecs))
        
        # Update gaze plots
        for m in self.plotElements.values():
            m.loadData(df)
        self.updatePlot()
        self.gazePlot.autoRange()


    def loadFromRecorder(self):
        """ Load data from the gaze recorder into memory """
        self.loadData(self.recorder.toDataFrame())
        
        try:
            self.info = d = self.recorder.extraData
            self.loadStim(d['stim_module'], d['stim_item'], QtCore.QPoint(d['stim_x'], d['stim_y']))
        except KeyError:
            pass
        
        d = self.recorder.pathData
        if 'x' in d:
            self.loadPath(d['x'], d['y'])
        self.path = d
        
        self.analyze()

    def loadFile(self, filename=None):
        if not filename:
            filename, _ = QtGui.QFileDialog.getOpenFileName(self.parent(), 'Load File', '',
                                                            'Excel Workbook (*.xlsx *.xls)')
        if filename:
            self.loadData(pandas.read_excel(filename, 0, index_col=None))
            self.info = None
            self.path = None
            try:
                extraseries = pandas.read_excel(filename, 1, index_col=None)[0]
            except IndexError:
                # no other (or unexpected format of) worksheet
                self.loadStim(None, None, None)
            else:
                d = extraseries.to_dict()
                self.loadStim(d['stim_module'], d['stim_item'], QtCore.QPoint(d['stim_x'], d['stim_y']))
                self.info = d
            
            try:
                pathseries = pandas.read_excel(filename, 2, index_col=None)
            except IndexError:
                # no other (or unexpected format of) worksheet
                self.loadPath(None, None)
            else:
                d = pathseries
                self.loadPath(d['x'], d['y'])
                self.path = d
        
        self.analyze()

    def loadStim(self, modname, funcname, pos):
        """
        Load a stimulus and draw it on the plot.
        """
        logger.debug('loading stim {}'.format(funcname))
        if self.stimItem:
            self.gazePlot.removeItem(self.stimItem)
        try:
            mod = importlib.import_module(modname)
            stimFunc = getattr(mod, funcname)
            
            self.stimItem = stimFunc()
            self.stimItem.setPos(pos)
            self.gazePlot.addItem(self.stimItem)
            self.stimItem.setZValue(-10)
        except:
            self.stimItem = None
    
    def loadPath(self, x, y):
        """
        Load a path as lists of x, y
        """
        if x is None:
            self.plotElements['path'].plotItem.clear()
        else:
            self.plotElements['path'].plotItem.setData(x, y)
            
    def analyze(self):
        """
        Perform error analysis after loading the data.
        Currently: if there is a stimulus, check the intersection
        """
        import shapely.geometry      
        
        userPoints = zip(self.path['x'], self.path['y'])
        userPolygon=shapely.geometry.Polygon(userPoints)
        stimPoints = bezier.BezierPath.interpolateToPoints(self.stimItem.path())
        stimPolygon=shapely.geometry.Polygon(bezier.geometry.xyFromPoints(stimPoints, self.stimItem.pos()))
        
        print('Areas: Path={}, Stim={}'.format(userPolygon.area, stimPolygon.area))
        print(stimPolygon, '\n', userPolygon)
        intersection = userPolygon.intersection(stimPolygon)
        print('Intersect = {}'.format(intersection.area))
        
        DSC = 2*intersection.area/(userPolygon.area+ stimPolygon.area)
        print('DSC = {}'.format(DSC))
        
        # Plot
        from descartes import PolygonPatch
        plt.ion()
        f, ax = plt.subplots()
        A = PolygonPatch(userPolygon, fc='b', alpha=0.5)
        B = PolygonPatch(stimPolygon, fc='r', alpha=0.5)
        C = PolygonPatch(intersection, fc='m', ec='m', alpha=0.5)
        ax.add_patch(A)
        ax.add_patch(B)
        ax.add_patch(C)
        ax.invert_yaxis()
        ax.autoscale_view()
                
    def paintEvent(self, ev):
        p = QtGui.QPainter(self)

