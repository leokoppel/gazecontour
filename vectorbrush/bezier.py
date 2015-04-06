from PySide import QtCore, QtGui
from PySide.QtGui import QPainterPath
from PySide.QtCore import Qt
import numpy as np
import scipy

from vectorbrush import geometry

class BezierPath(QtGui.QPainterPath):
    """
    Some functions in this class were ported from Andy Finnell's vector brush:
    https://bitbucket.org/andyfinnell/vectorbrush
    
    Used under the MIT license - see LICENSE.txt. 
    """
    
    
    def simplify(self, threshold):
        """
        Simplify a QPainterPath using Ramer-Douglas-Peucker algorithm
        Right now, only works if path is composed of lineTo's, and no curve elements
        """
        if self.elementCount() <= 2:
            return self

        maximumDistance = 0.0
        maximumIndex = 0

        # Find the point the furtherest away
        for i in range (1, self.elementCount()-1):
            distance = geometry.distancePointToLine(self.pointAtIndex(i), self.pointAtIndex(0), self.pointAtIndex(self.elementCount() - 1));
            if distance > maximumDistance:
                maximumDistance = distance;
                maximumIndex = i;
        
        if maximumDistance >= threshold:
            #The distance is too great to simplify, so recurse
            results1 = self.subpathWithRange(range(0, maximumIndex + 1)).simplify(threshold)
            results2 = self.subpathWithRange(range(maximumIndex, self.elementCount())).simplify(threshold)

            results1.appendPath(results2.subpathWithRange(range(1, results2.elementCount())))
            return results1
        else:
            # The greatest distance from our end points isn't that much, so we can simplify
            path = BezierPath();

            path.moveTo(self.pointAtIndex(0))
            path.lineTo(self.pointAtIndex(self.elementCount() - 1))
            return path

    def pointAtIndex(self, index):
        element = self.elementAt(index)
        return QtCore.QPointF(element.x, element.y)

    def subpathWithRange(self, target_range):
        """ Make a copy of the path, and return it """
        path = BezierPath()

        for i in target_range:
            element = self.elementAt(i)
            point = QtCore.QPointF(element.x, element.y)
                        
            if i == target_range.start:
                if (element.type == QPainterPath.CurveToElement or
                    (element.type == QPainterPath.CurveToDataElement and self.elementAt(i+1).type == QPainterPath.CurveToDataElement)):
                        raise ValueError('Invalid range; cannot start on curve element control points.')
                path.moveTo(point)
            else:
                path.appendElement(element, self.elementAt(i-1), self.elementAt(i-2))
            
        return path;
    
    def appendElement(self, element, prev1, prev2):
        """ append an element
        Requires previous two in case of curves"""
        
        point = QtCore.QPointF(element.x, element.y)
      
        if element.type == QPainterPath.MoveToElement:
            self.moveTo(point);
        elif element.type == QPainterPath.LineToElement:
            self.lineTo(point)
        elif element.type == QPainterPath.CurveToElement:
            # Can't do anything. Need the next element (a data element)
            pass
        elif element.type == QPainterPath.CurveToDataElement:
            if prev1.type == QPainterPath.CurveToElement:
                pass
            elif prev2.type != QPainterPath.CurveToElement or prev1.type != QPainterPath.CurveToDataElement:
                raise ValueError('CurveToDataElement not in correct sequence')
            else:
                # Have all three elements needed for curve
                prev1Point = QtCore.QPointF(prev1.x, prev1.y)
                prev2Point = QtCore.QPointF(prev2.x, prev2.y)
                self.cubicTo(prev2Point, prev1Point, point)


    def appendPath(self, path):
        """ append a path to this one"""
        previousElement = self.elementAt(self.elementCount() - 1)
        previousElement2 = self.elementAt(self.elementCount() - 2)
        previousPoint = QtCore.QPointF(previousElement.x, previousElement.y)
        for i in range(path.elementCount()):
            element = path.elementAt(i)
            point = QtCore.QPointF(element.x, element.y)
            
            # If the first element is a move to where we left off, skip it
            if element.type == QPainterPath.MoveToElement:
                if point == previousPoint:
                    continue
                else:
                    element.type = QPainterPath.LineToElement # change it to a line to
            
            self.appendElement(element, previousElement, previousElement2)
            previousElement2 = previousElement
            previousElement = element
            
    
    def interpolateBSpline(self, smoothness):
        """ simplfy the path using a b-spline and return XY points"""
        tck, u = scipy.interpolate.splprep(self.getXY(), s=smoothness)
        unew = np.linspace(0,1,100)
        out =  scipy.interpolate.splev(unew,tck)
        return out
    
    def interpolateBSpline2(self, smoothness):
        """ simplfy the path using a b-spline and return fitted path"""
        try:
            tck, u = scipy.interpolate.splprep(self.getXY(), s=smoothness)
        except TypeError:
            raise Exception("Path too short (<3 points)")
        
        # Wrap Zachary Pincus's function and convert result to a QPainterPath
        curves = geometry.b_spline_to_bezier_series(tck)
        newPath = BezierPath()
        newPath.moveTo(curves[0][0][0], curves[0][0][1])
        for curve in curves:
            newPath.cubicTo(curve[1][0], curve[1][1], curve[2][0], curve[2][1], curve[3][0], curve[3][1])
        return newPath
    
    def nearestPoint(self, targetPoint, threshold=1e-4, initialRes = 0.1):
        """
        Given a QPointF, return the (approximate) nearest point on the path.
        """
        t, _ =  self.nearestPointT(targetPoint, threshold, initialRes)
        return self.pointAtPercent(t)
        
    def nearestPointT(self, targetPoint, threshold=1e-4, initialRes = 0.1):
        """
        Given a QPointF, return the parameter t of the (approximate) nearest point on the path,
        and the distance to that point.
        Use a binary search as described here: http://pomax.github.io/bezierinfo/#projections
        """
        # Begin with a reasonable guess based on linear search
        ts = np.linspace(0,1,1/initialRes + 1)
        initialDistances = [geometry.distanceBetweenPoints(targetPoint, self.pointAtPercent(t)) for t in ts]
        ind = np.argmin(initialDistances)
        t = ts[ind]
        distance = initialDistances[ind]
        interval = initialRes*2
        
        # Then the binary search
        while interval > threshold:
            tMinus = max(t - interval/2, 0)
            tPlus = min(t + interval/2, 1)
            distanceMinus = geometry.distanceBetweenPoints(targetPoint, self.pointAtPercent(tMinus))
            distancePlus = geometry.distanceBetweenPoints(targetPoint, self.pointAtPercent(tPlus))
            if distanceMinus < distance:
                t = tMinus
                distance = distanceMinus
            elif distancePlus < distance:
                t = tPlus
                distance = distancePlus
            else:
                # Distance smallest at current t
                interval /= 2
    
        return t, distance
    
    @staticmethod
    def pathFromPoints(points):
        path = BezierPath()
        try:
            path.moveTo(points[0])
            for p in points[1:]:
                path.lineTo(p)
        except IndexError:
            pass
        return path
        
    def interpolateToPoints(self, n=None):
        """ Split up the curve into points """
        n = n or self.length()
        ts = np.linspace(0, 1, n)
        return [self.pointAtPercent(t) for t in ts]
        
    @staticmethod
    def warpPoints(points, target, delta, strength, radius, falloff='cos'):
        """
        Take an array of QPointFs and warp them radially toward a target
        target = QPointF, current cursor position
        delta = QPointF, last movement in cursor position
        strength = scale of effect (0 to 1)
        radius = maximum distance of influence
        falloff = function used to calculate influence ('linear' or 'cos2')
        
        Return new points (do not change in place)
        """
        
        newPoints = []
        for p in points:
            # line from target to p
            dist = geometry.distanceBetweenPoints(p, target)
            if dist < radius:
                # Calculate size of effect
                if falloff is 'cos':
                    m = strength*(np.cos(np.pi*dist/radius)+1)/2
                else:
                    m = strength*(1 - dist/radius)
                
                # Move the point in the direction of the delta
                newPoints.append(p + m*delta)
            else:
                newPoints.append(p)
        return newPoints
        
        
        

    def getXY(self):
        """ Return the x and y points of each element in this path as a list of arrays """
        x = []
        y = []
        for element in self.elements():
            x.append(element.x)
            y.append(element.y)
        return [x,y]


    def elements(self):
        """ generator of this path's elements """
        for i in range(self.elementCount()):
            yield self.elementAt(i)

class BezierPathItem(QtGui.QGraphicsPathItem):

    def __init__(self, path, parent=None, scene=None):
        super().__init__(path, parent, scene)
        self.handles = dict()
        
        self.makeHandles()
        
        self.setPen(QtGui.QPen(QtGui.QColor('lightseagreen'), 1))

    def deleteHandles(self):
        """ Remove old handles """
        for h in self.handles.values():
            h.scene().removeItem(h)
            h.deleteLater()
        self.handles.clear()
    
    def makeHandles(self):
        """ Construct new control handles to match the path
            Works for a curve if it well formed, with 2 CurveToDataElements following each CurveToElement,
            or for a path without any curves
        """
        self.deleteHandles()
        
        prevType = None
        for i in range(self.path().elementCount()):
            el = self.path().elementAt(i)
           
            if el.type == QPainterPath.CurveToElement:
                # Add control handle as child (first control point -> controls previous point)
                self.handles[i] = ControlHandleItem(i, i-1, parent=self)
#                self.handles[i].setZValue(90)
            elif (el.type == QPainterPath.CurveToDataElement and prevType == QPainterPath.CurveToElement):
                # Add control handle as child (second control point -> controls next point)
                self.handles[i] = ControlHandleItem(i, i+1, parent=self)
#                self.handles[i].setZValue(90)
            else:
                # Add point handle as child
                self.handles[i] = HandleItem(i, parent=self)
            prevType = el.type
        

    def bezierPath(self):
        return BezierPath(super().path())
    
    def updateAll(self):
        for k in self.handles.values():
            k.update()
                

class HandleItem(QtGui.QGraphicsObject):
    """
    Graphics item for Bezier point handles
    
    Inherit QGraphicsObject and not QGraphicsItem to avoid some issues with deletion
    during a mouse event - we can use QObject.deleteLater().
    """    
    Z_MIN = 100
    Z_MAX = 300
    
    def __init__(self, index, parent):
        super().__init__(parent)
        self.index = index
        
        self.size = 10
        
        el = self.parentItem().path().elementAt(self.index)
        self.setPos(el.x, el.y)
        
        self.setAcceptedMouseButtons(Qt.LeftButton)
        G = QtGui.QGraphicsItem
        self.setFlag(G.ItemIsSelectable)
        self.setFlag(G.ItemIsMovable)
        self.setFlag(G.ItemSendsGeometryChanges)
        self.setAcceptHoverEvents(True)
        self.setZValue(self.Z_MAX)
        
        self.highlightColor = QtGui.QColor('orange')
        self.highlightScale = 2
        self.pressColor = QtGui.QColor('cyan')
        self.pressScale = 3
        self.color = QtGui.QColor('seagreen')

    
    def boundingRect(self, *args, **kwargs):
        """ Set the bounds of the item """
        radius = self.size*10
        return QtCore.QRect(-radius, -radius, 2*radius, 2*radius)

    def shape(self):
        """ Set the shape for collision detection to a circle """
        path = QtGui.QPainterPath()
        path.addEllipse(self.boundingRect())
        return path
    
    def getElementAt(self, i):
        return self.parentItem().path().elementAt(i)
    
    def element(self):
        return self.parentItem().path().elementAt(self.index)
    
    def elementPos(self):
        return QtCore.QPointF(self.element().x, self.element().y)
    
    def elementPosAt(self, i):
        return QtCore.QPointF(self.getElementAt(i).x, self.getElementAt(i).y)
    
    def paint(self, p, option, widget):
        p.save()
        if option.state & QtGui.QStyle.State_Sunken:
            p.setBrush(self.pressColor)
            size = self.size*self.pressScale
        elif option.state & QtGui.QStyle.State_MouseOver:
            p.setBrush(self.highlightColor)
            size = self.size*self.highlightScale
        else:
            p.setBrush(self.color)
            size = self.size

        p.setPen(Qt.NoPen)
            
        p.drawEllipse(-size/2, -size/2, size, size)
        p.restore()
    
    def mouseReleaseEvent(self, event):
        """ Un-highlight immediately: reset appearance and re-draw handles """
        self.parentItem().updateAll()
        return super().mouseReleaseEvent(event)
                   
    def itemChange (self, change, value):
        if change == QtGui.QGraphicsItem.ItemPositionHasChanged and self.isSelected():
            # Move this point and its control handles (unless it's an endpoint)
            path = self.parentItem().path()
            
            newPos = self.pos() # item has already moved with the mouse
            posDelta = newPos - QtCore.QPointF(path.elementAt(self.index).x, path.elementAt(self.index).y)
            
            path.setElementPositionAt(self.index, newPos.x(), newPos.y())
            if self.index>0 and self.index < path.elementCount()-1:
                for i in [self.index-1, self.index+1]:
                    newX = posDelta.x() + path.elementAt(i).x
                    newY = posDelta.y() + path.elementAt(i).y
                    path.setElementPositionAt(i, newX, newY)
                    
                    # update the display of the handles
                    self.parentItem().handles[i].updateHandle()
            self.parentItem().setPath(path)
        return value
        
        
    def updateHandle(self):
        el = self.parentItem().path().elementAt(self.index)
        self.setPos(el.x, el.y)


class ControlHandleItem(HandleItem):
    def __init__(self, index, masterIndex, parent):
        super().__init__(index, parent)
        self.size = 5
        self.color = QtGui.QColor('mediumseagreen')
        
        self.masterIndex = masterIndex # index of the point this is controlling     
        if self.masterIndex - self.index == 1:
            self.partnerIndex = self.masterIndex + 1
        else:
            self.partnerIndex = self.masterIndex - 1
                
    def paint(self, p, option, widget):
        p.save()
        super().paint(p, option, widget)
        
        # Draw connector to master
        p.setPen(QtGui.QColor('mediumseagreen'))
        p.drawLine(QtCore.QPointF(), self.elementPosAt(self.masterIndex) - self.pos())
        p.restore()
    
    def masterElement(self):
        return self.getElementAt(self.masterIndex)
    
    def partnerElement(self):
        return self.getElementAt(self.partnerIndex)
    
    def mouseMoveEvent(self, *args, **kwargs):
        super().mouseMoveEvent(*args)  
        
    def itemChange (self, change, value):
        if change == QtGui.QGraphicsItem.ItemPositionHasChanged and self.isSelected():
            # Move this control point and its partner (unless it's on an endpoint)
            # Use semi-constrained motion
            path = self.parentItem().path()
            
            newPos = self.pos() # item has already moved with the mouse
            path.setElementPositionAt(self.index, newPos.x(), newPos.y())
    
            if self.masterIndex>0 and self.masterIndex < path.elementCount()-1:
                # Want the partner point to have the opposite angle from the master
                lineFromMaster = QtCore.QLineF(self.elementPosAt(self.masterIndex), newPos)
                angleFromMaster = lineFromMaster.angle() # angle in degrees
                
                linePartnerFromMaster = QtCore.QLineF(self.elementPosAt(self.masterIndex), self.elementPosAt(self.partnerIndex))
                linePartnerFromMaster.setAngle(180 + angleFromMaster)
                
                newX = linePartnerFromMaster.x2()
                newY = linePartnerFromMaster.y2()
                path.setElementPositionAt(self.partnerIndex, newX, newY)
                
                # update the display of the handles
                self.parentItem().handles[self.partnerIndex].updateHandle()
            self.parentItem().setPath(path)
        
        return value
