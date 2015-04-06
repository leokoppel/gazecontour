from PySide import QtGui, QtCore
from PySide.QtCore import Qt

def dot(d):
    dot = QtGui.QGraphicsEllipseItem(-d/2,-d/2,d, d)
    dot.setBrush(QtGui.QBrush(Qt.black))
    return dot

def dot30():
    return dot(30)

def dot5():
    return dot(5)

def circle(d):
    circle = QtGui.QGraphicsEllipseItem(-d/2,-d/2,d,d)
    circle.setPen(QtGui.QPen(Qt.black, 3))
    return circle

def circle600():
    return circle(600)

def organ():
    p = QtGui.QPainterPath()
    d = 0.8 #scale
    p.moveTo(d*-278.051, d*42.0093)
    p.cubicTo(d*-298.703, d*-172.636, d*-125.349, d*-257.14, d*-15.88, d*-263.5)
    p.cubicTo(d*104.256, d*-270.48, d*240.363, d*-140.299, d*257.68, d*-73.2373)
    p.cubicTo(d*283.252, d*25.792, d*280.424, d*86.7851, d*270.742, d*164.151)
    p.cubicTo(d*259.518, d*253.839, d*140.499, d*133.087, d*33.3116, d*139.426)
    p.cubicTo(d*-92.4161, d*146.862, d*-280.599, d*267.807, d*-278.051, d*42.0093)
    
    item = QtGui.QGraphicsPathItem(p)
    item.setPen(QtGui.QPen(Qt.black, 2))
    brush = QtGui.QBrush(Qt.darkGray, Qt.Dense6Pattern)
    brush.setTransform(QtGui.QTransform(0.8, 0, 0, 0.8, 0, 0))
    item.setBrush(brush)
    return item

def ct():
    p = QtGui.QPainterPath()
    p.moveTo(7.99702, -207.977)
    p.cubicTo(108.706, -211.455, 155.229, -168.755, 203.768, -104.033)
    p.cubicTo(239.917, -55.8314, 237.367, -17.0192, 231.915, 59.8563)
    p.cubicTo(229.582, 92.7493, 218.106, 127.332, 197.976, 150.454)
    p.cubicTo(182.797, 167.889, 163.098, 178.362, 139.823, 180.355)
    p.cubicTo(93.8109, 184.294, 51.4568, 157.181, 5.70595, 157.711)
    p.cubicTo(-39.0911, 158.23, -85.581, 171.207, -131.05, 168.968)
    p.cubicTo(-148.886, 168.089, -166.671, 163.663, -181.743, 154.659)
    p.cubicTo(-196.436, 145.882, -214.551, 127.753, -223.688, 112.866)
    p.cubicTo(-237.653, 90.1136, -234.519, 16.175, -226.434, -10.0246)
    p.cubicTo(-200.118, -95.2954, -186.138, -130.67, -134.662, -166.566)
    p.cubicTo(-96.174, -193.405, -76.5979, -206.538, 7.02049, -207.978)
    
    pixmap = QtGui.QPixmap('images/ct.png')
    item = QtGui.QGraphicsPixmapItem(pixmap)
    item.setOffset(-pixmap.width()/2, -pixmap.height()/2)
    
    pathItem = QtGui.QGraphicsPathItem(p, item)
    pathItem.setPen(QtGui.QPen(Qt.red, 2))
    pathItem.hide()
    
    item.path = pathItem.path
    return item

stimuli = [dot5, dot30, circle600, organ, ct]
