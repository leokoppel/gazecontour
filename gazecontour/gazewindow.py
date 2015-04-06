import sys
import math

from PySide import QtCore, QtGui
from PySide.QtCore import Qt, QPoint, QPointF
from PySide.QtNetwork import QAbstractSocket

from gazecontour import basewindow
from gazecontour.recorder import Recorder
from gazecontour.eyetribe import EyeTribe
import gazecontour.realtime
import gazecontour.images

from vectorbrush import bezier

# Set up logging
import logging
logging.basicConfig(format='[%(levelname)-8s] %(name)15s: %(message)s', level=logging.DEBUG)
logger = logging.getLogger(__name__)

class GazeWindow(basewindow.BaseMainWindow):

    def __init__(self, parent=None, stimFunc=None):
        # Initialize the object as a QWidget and
        # set its title and minimum width
        super().__init__(parent)
        self.setWindowTitle('Gaze UI')
        
        self.resize(self.parent().rect().size())

        self._desktopWidget = QtGui.QDesktopWidget()

        # Initialize Eye Tribe object
        self.tracker = EyeTribe()
        self.tracker.newFrame.connect(self.handleFrame)
        self.tracker.socket.stateChanged.connect(self.handleTrackerStateChange)
        self.controlCursor = False

        # Status bar
        self.statusLabelTracker = QtGui.QLabel()
        self.statusLabelRec = QtGui.QLabel()
        self.statusBar().addPermanentWidget(self.statusLabelTracker)
        self.statusBar().addPermanentWidget(self.statusLabelRec)

        # Initialize data recorder
        self.recorder = Recorder(statusLabel=self.statusLabelRec)
            
        # Child widgets
        gazeWidget = GazeWidget(self.tracker, parent=self)
        self.gazeWidget = gazeWidget
        self.gazeWidget.lower()
        self.setCentralWidget(gazeWidget)
        self._desktopWidget = QtGui.QDesktopWidget()

        # Stimulus (the image to trace)
        self.setStimFunc(stimFunc)

        #Actions
        playIcon = self.style().standardIcon(QtGui.QStyle.SP_MediaPlay)
        pauseIcon = self.style().standardIcon(QtGui.QStyle.SP_MediaPause)
        editIcon = self.style().standardIcon(QtGui.QStyle.SP_FileDialogDetailedView)
        recAction = QtGui.QAction(playIcon, "Record", self)
        recAction.setCheckable(True)
        recAction.triggered.connect(lambda: recAction.setIcon(pauseIcon if recAction.isChecked() else playIcon))
        recAction.setShortcut(QtGui.QKeySequence(Qt.Key_R))
        saveAction = QtGui.QAction(self.style().standardIcon(QtGui.QStyle.SP_DialogSaveButton), "Save", self)
        saveAction.setShortcut(QtGui.QKeySequence.Save)
        clearAction = QtGui.QAction(self.style().standardIcon(QtGui.QStyle.SP_DialogDiscardButton), "Clear", self)
        clearAction.setShortcut(QtGui.QKeySequence.New)
        editAction = QtGui.QAction(editIcon, "Edit", self)
        editAction.setCheckable(True)
        editAction.setShortcut(QtGui.QKeySequence(Qt.Key_Space))
        
        # Connect actions
        recAction.toggled.connect(self.recorder.setRecording)
        def recTrig(v):
            if not v:
                # Save path when stopping recording (for now just one)
                try:
                    points = self.gazeWidget.bezierPaths[0].bezierPath().interpolateToPoints()
                    screenpos = self._desktopWidget.screenGeometry(self._desktopWidget.screenNumber(self)).topLeft()
                    w = self.gazeWidget
                    points = [w.mapToGlobal(w.mapFromScene(p)) - screenpos for p in points]
                    self.recorder.savePath(points)
                except IndexError:
                    pass
        recAction.toggled.connect(recTrig)
        self.recorder.recordingChanged.connect(lambda rec: recAction.setChecked(rec))

        recAction.triggered.connect(lambda: logger.debug(self.tracker.get('calibresult')))
        saveAction.triggered.connect(self.recorder.saveToFile)
        clearAction.triggered.connect(self.recorder.clear)
        clearAction.triggered.connect(lambda: gazeWidget.clear())

        editAction.toggled.connect(gazeWidget.setEditMode)
        
        controlCursorAction = QtGui.QAction('Control cursor', self)
        controlCursorAction.setCheckable(True)
        controlCursorAction.setShortcut(QtGui.QKeySequence(Qt.Key_C))
        def setControlCursor(v):
            self.controlCursor = v
        controlCursorAction.toggled.connect(setControlCursor)
        
        simplifyAction = QtGui.QAction('Re-fit curves', self)
        simplifyAction.triggered.connect(gazeWidget.simplifyAllPaths)

        # Toolbar
        self.toolbar.addActions([recAction, clearAction, saveAction, editAction])
        drawGazeCheckbox = QtGui.QCheckBox('Show Gaze', self)
        showRawCheckbox = QtGui.QCheckBox('Show Raw', self)
        editHandlesCheckbox = QtGui.QCheckBox('Edit handles', self)

        self.toolbar.addSeparator()
        self.toolbar.addWidget(drawGazeCheckbox)
        self.toolbar.addWidget(showRawCheckbox)
        self.toolbar.addWidget(editHandlesCheckbox)
        self.toolbar.addAction(controlCursorAction)
        
        space = QtGui.QWidget(self)
        space.setMinimumHeight(50)
        self.toolbar.addWidget(space)
        self.toolbar.addAction(simplifyAction)
        
        # Sliders
        smoothSlider = QtGui.QSlider(Qt.Horizontal, self)
        smoothSlider.setRange(1, 60)
        smoothSlider.valueChanged.connect(gazeWidget.setSmoothness)
        smoothSlider.setValue(5)
        smoothLabel = QtGui.QLabel("Smoothness", self)
        self.toolbar.addWidget(smoothLabel)
        self.toolbar.addWidget(smoothSlider)
        
        radiusSlider = QtGui.QSlider(Qt.Horizontal, self)
        radiusSlider.setRange(10, 500)
        radiusSlider.valueChanged.connect(gazeWidget.setWarpRadius)
        radiusSlider.setValue(100)
        radiusLabel = QtGui.QLabel("Warp size", self)
        
        space = QtGui.QWidget(self)
        space.setMinimumHeight(50)
        self.toolbar.addWidget(space)
        self.toolbar.addWidget(radiusLabel)
        self.toolbar.addWidget(radiusSlider)
        
        # Stim dropdown
        self.stimBox = QtGui.QComboBox(self)
        for k in gazecontour.images.stimuli:
            self.stimBox.addItem(k.__name__, k)
        self.stimBox.addItem('None', None)
        self.stimBox.setCurrentIndex(self.stimBox.findText(self.stimFunc.__name__ if self.stimFunc else None))
        self.stimBox.currentIndexChanged.connect(lambda i: self.setStimFunc(self.stimBox.itemData(i)))
        
        space = QtGui.QWidget(self)
        space.setMinimumHeight(50)
        self.toolbar.addWidget(space)
        self.toolbar.addWidget(self.stimBox)

        drawGazeCheckbox.toggled.connect(gazeWidget.setdrawGazeEnabled)
        gazeWidget.setdrawGazeEnabled(False)
        showRawCheckbox.toggled.connect(gazeWidget.setShowRaw)
        editHandlesCheckbox.toggled.connect(gazeWidget.setEditHandles)

        # Start streaming gaze data
        self.tracker.start()

        # Want to update stimulus position on top-most window move
        # Inconveniently, only the very top-most widget gets the move event.
        # TODO: better not to monkey patch
        def move(evt):
            if self.stimFunc:
                self.saveStim()
        win = self.window().parent() or self.window() # The "real" main window will be one of those, depending on how script started
        win.moveEvent = move

        N = 15 # length of buffer
        px_thresh = 30 # pixel distance threshold for saccades
        self.gazeProcessor = gazecontour.realtime.GazeProcessor(N, px_thresh)


    def setStimFunc(self, stimFunc):
        self.stimFunc = stimFunc
        if stimFunc:
            stimItem = stimFunc()
            self.gazeWidget.loadStim(stimItem)
        else:
            self.gazeWidget.loadStim(None)
        self.saveStim()
            
    def handleFrame(self, frame):
        """
        Deal with a new gaze sample
        """
        # Add some data to the frame:
        # Get cursor position (as QPoint) relative to the current screen
        cpos = QtGui.QCursor.pos() - self._desktopWidget.screenGeometry(self.tracker.get('screenindex')).topLeft()
        frame['cursor_x'], frame['cursor_y'] = cpos.x(), cpos.y()

        # Record the extended frame
        self.recorder.handleFrame(frame)

        if frame['state'] & EyeTribe.STATE_TRACKING_GAZE:
            # get smoothed values
            x, y = self.gazeProcessor.process_frame(frame['raw']['x'], frame['raw']['y'])
            #temp
            x, y = frame['avg']['x'], frame['avg']['y']
                
            # Draw
#            if 1 or self.gazeProcessor.new_fixation:
            if not (self.gazeWidget.editMode and QtGui.QApplication.mouseButtons() == Qt.LeftButton): 
                point = QtCore.QPoint(x, y) + self._desktopWidget.screenGeometry(self._desktopWidget.screenNumber(self)).topLeft()
                # Move the cursor?
                if self.controlCursor:
                    QtGui.QCursor.setPos(point.x(), point.y())

    def handleTrackerStateChange(self, state):
        status_messages = {QAbstractSocket.SocketState.UnconnectedState : 'Not connected to tracker server',
                           QAbstractSocket.SocketState.HostLookupState : 'Looking up host',
                           QAbstractSocket.SocketState.ConnectedState : 'Connecting to tracker server',
                           QAbstractSocket.SocketState.ConnectedState : 'Connected to tracker server',
                           QAbstractSocket.SocketState.ClosingState : 'Disconnecting',
                           }
        # Change status bar message
        if state in status_messages:
            msg = status_messages[state]
        else:
            msg = 'Unknown state'
        self.statusLabelTracker.setText(msg)

    def saveStim(self):
        """ Save stimulus function and position on screen """
        # Get position relative to top left corner of THIS screen
        screenpos = self._desktopWidget.screenGeometry(self._desktopWidget.screenNumber(self)).topLeft()
        stim = self.gazeWidget.stimItem
        if stim is not None:
            view = stim.scene().parent()
            pos = view.mapToGlobal(view.mapFromScene(stim.pos())) - screenpos
            logger.debug('Saving stim at position {}'.format(pos))
            self.recorder.saveStim(self.stimFunc, pos)
        else:
            self.recorder.saveStim(None, None)

    def resizeEvent(self, ev):
        if self.stimFunc:
#            self.stimLabel.move(self.mapFromParent(self.geometry().center()) - self.stimLabel.rect().center())
            # Note position of stimPixmap (top-left, pixels):
            self.saveStim()



class GazeWidget(QtGui.QGraphicsView):
    """
    Widget which shows real-time EyeTribe gaze data
    """

    def __init__(self, tracker, parent=None):
        super().__init__(parent)
      
        
        self._desktopWidget = QtGui.QDesktopWidget()
        self.drawGazeEnabled = False

        # Prepare scene and path groups
        self.scene = QtGui.QGraphicsScene(self)
        self.scene.setSceneRect(0,0,100,100)
        self.setFrameShape(QtGui.QFrame.NoFrame)
        self.setScene(self.scene)
        
        self.scribbling = False
        self.scribblePath = bezier.BezierPath()
        self.scribblePathItem = self.scene.addPath(self.scribblePath)
        self.scribblePathItem.setPen(QtGui.QPen(Qt.blue, 1))
        self.rawPaths =[]
        self.bezierPaths = []
        self.stimItem = None
        
        size = 20
        self.warpIndicatorItem = self.scene.addEllipse(-size/2, -size/2, size, size)
        self.warpIndicatorItem.setPen(QtGui.QPen(Qt.red, 10))
        
        self._showRaw = False
        self.setEditMode(False)
        self.setEditHandles(False)
        self.nearestPath = None
        self.nearestPoint = None
        self.warping = False
        self.warpPoints =[]
        self.warpPos = None
        
        self.simpleness = 10
        self.smoothness = 5
        self.warpRadius = 100

        # Gaze items
        self._gazeActive = False
        self.setRenderHints(QtGui.QPainter.Antialiasing)
        self._gazeRaw = self.scene.addEllipse(0, 0, 4, 4, Qt.NoPen, QtGui.QBrush(Qt.red))
        self._gazeLeft = self.scene.addEllipse(0, 0, 2, 2, Qt.NoPen, QtGui.QBrush(Qt.magenta))
        self._gazeRight = self.scene.addEllipse(0, 0, 2, 2, Qt.NoPen, QtGui.QBrush(Qt.cyan))
        self._gazeAvg = self.scene.addEllipse(0, 0, 4, 4, Qt.NoPen, QtGui.QBrush(Qt.blue))
        
        # Connections
        self.tracker = tracker
        self.tracker.newFrame.connect(self.handleFrame)

    def loadStim(self, stimItem):
        if self.stimItem is not None:
            self.scene.removeItem(self.stimItem)

        self.stimItem = stimItem

        if stimItem is not None:
            self.scene.addItem(stimItem)
            stimItem.setZValue(-1)
    
    def updateZValues(self, pos):
        """
        We need to select the closest object to the cursor, if one is within a certain threshold.
        The items all have large bounding boxes - but this is a problem when they are close together and
        they overlap. As a quick fix, we still rely on the built-in GraphicsScene item selection, but
        re-order the items in Z based on which is closer.
        """
        for p in self.bezierPaths:
            for k in p.handles.values():
                distance = QtCore.QLineF(pos, k.pos()).length()
                z = max(k.Z_MAX - round(distance), k.Z_MIN)
                k.setZValue(z)
            p.update()

    def getNearestPath(self, pos, maxDistance=200):
        # Paint line to nearest point
        
        nearestPath = None
        minDist = None
        for p in self.bezierPaths:
            # Get rough distances to find nearest path
            _, distance = p.bezierPath().nearestPointT(pos, 0.01, 0.1)
            if nearestPath is None or distance < minDist:
                nearestPath = p
                minDist = distance
        
        if minDist is not None and minDist > maxDistance:
            nearestPath = None
           
        return nearestPath
    
    def updateNearestPoint(self, path, pos):
        if path is not None:
            # Get more precise nearest point on path
            t, _ = path.bezierPath().nearestPointT(pos)
            point =  path.path().pointAtPercent(t)
            self.warpIndicatorItem.setPos(point)
            self.warpIndicatorItem.show()
        else:
            self.warpIndicatorItem.hide()
            point = None
        return point
        
    
    def unsetClosestPoint(self):
        self.updateNearestPoint(None, None) # hide indicator
    
    def mousePressEvent(self, event):
        if self.editMode:
            mousePos = self.mapToScene(event.pos());
            if self.editHandles:
                self.updateZValues(mousePos)
            else:
                self.nearestPath = self.getNearestPath(mousePos)
                self.nearestPoint = self.updateNearestPoint(self.nearestPath, mousePos)
                if self.nearestPath:
                    self.warping = True
                    self.warpPos = mousePos
                    self.warpPoints = self.nearestPath.bezierPath().interpolateToPoints(self.nearestPath.path().length())
                    self.nearestPath.deleteHandles()
            return super().mousePressEvent(event)
                

        if (event.button() == Qt.LeftButton):
            self.scribbling = True;
            self.scribblePath.moveTo(self.mapToScene(event.pos()))
            self.updateScribblePath()
            self.update()

    def mouseMoveEvent(self, event):
        if self.editMode:        
            mousePos = self.mapToScene(event.pos());
            if self.editHandles:
                self.updateZValues(mousePos)
                return super().mouseMoveEvent(event)
            else:
                if not self.warping:
                    self.nearestPath = self.getNearestPath(mousePos)
                    self.nearestPoint = self.updateNearestPoint(self.nearestPath, mousePos)
                if self.nearestPath:
                    if self.warping and (event.buttons() & Qt.LeftButton):
                        delta = mousePos - self.warpPos
                        self.warpPoints = bezier.BezierPath.warpPoints(self.warpPoints, self.nearestPoint, delta, strength=0.9, radius=self.warpRadius)
                        self.nearestPath.setPath(bezier.BezierPath.pathFromPoints(self.warpPoints))
                        self.warpPos = mousePos
                        self.nearestPoint += delta
                        self.warpIndicatorItem.setPos(self.nearestPoint)
                        
        
        if (event.buttons() & Qt.LeftButton) and self.scribbling:
            self.scribblePath.lineTo(self.mapToScene(event.pos()))
            self.updateScribblePath()
            self.update()

    def mouseReleaseEvent(self, event):
        if self.editMode:
            
            if self.editHandles:
                pass
            else:
                if self.warping:
                    self.nearestPath.setPath(self.nearestPath.bezierPath().simplify(self.simpleness).interpolateBSpline2(self.smoothness))
                    self.nearestPath.makeHandles()
                    self.warping = False
                
            return super().mouseReleaseEvent(event)
        
        if event.button() == Qt.LeftButton and self.scribbling:
            self.scribbling = False;

            # Finalize path
            try:
                if self.scribblePath.elementCount() > 1:
                    
                    finalPath = self.scribblePath.simplify(self.simpleness)
                    logger.debug('Finalizing path of {} -> {} elements (length {} -> {})'.format(self.scribblePath.elementCount(), finalPath.elementCount(),
                                                                                            self.scribblePath.length(), finalPath.length() ))
                    
                    if self.editHandles or 1:
                        finalPath = finalPath.interpolateBSpline2(self.smoothness)
                    
                    newItem = bezier.BezierPathItem(finalPath, None, self.scene) # This adds it to the scene
                    
                    self.bezierPaths.append(newItem)
                    rawItem = QtGui.QGraphicsPathItem(self.scribblePath, None, self.scene)
                    self.rawPaths.append(rawItem)
                    if(self._showRaw):
                        newItem.hide()
                    else:
                        rawItem.hide()
                    
                        
                else:
                    logger.debug('Discarding path of insufficient length.')
            except:
                raise
            finally:
                # clear temp path
                self.scribblePath = bezier.BezierPath()
                self.updateScribblePath()
                self.update()
    
    def wheelEvent(self, event):
        """ Change warp radius using mouse wheel """ 
        self.setWarpRadius(self.warpRadius + event.delta()/10)
    
    def simplifyAllPaths(self):
        for p in self.bezierPaths:
            path = bezier.BezierPath.pathFromPoints(p.bezierPath().interpolateToPoints(p.path().length()))
            path = path.simplify(self.simpleness)
            if self.editHandles or 1:
                path = path.interpolateBSpline2(self.smoothness)
            p.setPath(path)
            p.makeHandles()

    def _translate(self, p):
        """
        Take floating point, screen coordinates as {'x':x, 'y':y} 
        Return integer, scene coordinates as QPointF(x,y) 
        """
        # We want to return floating point coords but mapFromGlobal only works with integers
        # So, simply truncate, mapFromGlobal, and add the decimal part back
        xf, xint = math.modf(p['x'])
        yf, yint = math.modf(p['y'])

        # Multi-monitor support:
        # The coords from the tracker are relative to the screen. Add the global offset of this screen.
        globalCoords = QPoint(xint, yint) + self._desktopWidget.screenGeometry(self.tracker.get('screenindex')).topLeft()

        # Get widget coordinates, and add back the decimal parts
        wCoords = QPointF(self.mapFromGlobal(globalCoords))
        return self.mapToScene(wCoords.toPoint()) + QPointF(xf, yf)

    def handleFrame(self, frame):
        """
        Deal with a new gaze sample
        """
        # We translate the global (screen) coordinates to coordinated *within*
        # the widget when the frame is received.
        self._gazeActive = bool(frame['state'] & self.tracker.STATE_TRACKING_PRESENCE)
        
        self._gazeRaw.setPos(self._translate(frame['raw']))
        self._gazeLeft.setPos(self._translate(frame['lefteye']['raw']))
        self._gazeRight.setPos(self._translate(frame['righteye']['raw']))
        self._gazeAvg.setPos(self._translate(frame['avg']))
        
        if self.drawGazeEnabled:
            self._gazeRaw.setVisible(self._gazeActive)
            self._gazeLeft.setVisible(self._gazeActive)
            self._gazeRight.setVisible(self._gazeActive)
            self._gazeAvg.setVisible(self._gazeActive)
            
        self.update()

    def clear(self):
        for p in self.bezierPaths:
            self.scene.removeItem(p)
        self.bezierPaths.clear()
        self.rawPaths.clear()
        self.update()
    
    def setdrawGazeEnabled(self, v):
        logger.debug('gazeWidget toggling show gaze: {}'.format(v))
        self.drawGazeEnabled = v
        if not v:
            self._gazeRaw.hide()
            self._gazeLeft.hide()
            self._gazeRight.hide()
            self._gazeAvg.hide()
    
    def setEditMode(self, v):
        logger.debug('gazeWidget toggling edit mode: {}'.format(v))
        self.editMode = v
        self.unsetClosestPoint()
    
    def setShowRaw(self, v):
        logger.debug('gazeWidget toggling raw mode: {}'.format(v))
        self._showRaw = v
        for p in self.rawPaths:
            p.setVisible(v)
        for p in self.bezierPaths:
            p.setVisible(not v)
            
    def setEditHandles(self, v):
        """
        Set whether clicks in edit mode move handles or produce a warp effect
        """
        self.editHandles = v
        if v:
            logger.info('Now moving Bezier handles in Edit mode')
            self.unsetClosestPoint()
        else:
            logger.info('Now using Warp effect in Edit mode')
    
    def setSmoothness(self, x):
        self.simpleness = x/2
    
    def setWarpRadius(self, x):
        self.warpRadius = x
        self.warpIndicatorItem.setRect(-x/2, -x/2, x, x)
        
    def updateScribblePath(self):
        self.scribblePathItem.setPath(self.scribblePath)
            


class BezierCurve(object):
    def __init__(self, endPoint, controlPoint1, controlPoint2):
        self.endPoint = endPoint
        self.controlPoint1 = controlPoint1
        self.controlPoint2 = controlPoint2

## monkey path the qpainterpath
#def _qpp_draw_bezierCurve(self, curve):
#    self.cubicTo(curve, )
#QtGui.QPainterPath.
