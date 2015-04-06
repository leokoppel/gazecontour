import math
import numpy as np
import scipy.interpolate.fitpack as fitpack


from PySide import QtCore, QtGui

def distanceBetweenPoints(point1, point2):
    return math.hypot(point2.x() - point1.x(), point2.y() - point1.y())

def distancePointToLine(point, lineStartPoint, lineEndPoint):
    lineLength = distanceBetweenPoints(lineStartPoint, lineEndPoint);
    if lineLength == 0:
        return 0
    u = ((point.x() - lineStartPoint.x()) * (lineEndPoint.x() - lineStartPoint.x()) + (point.y() - lineStartPoint.y()) * (lineEndPoint.y() - lineStartPoint.y())) / (lineLength ** 2);
    intersectionPoint = (1 - u) * lineStartPoint + u * lineEndPoint

    return distanceBetweenPoints(point, intersectionPoint)


def b_spline_to_bezier_series(tck, per=False):
    """Convert a parametric b-spline into a sequence of Bezier curves of the same degree.
    
    By Zachary Pincus, from http://mail.scipy.org/pipermail/scipy-dev/2007-February/006651.html
    
    Inputs:
        tck : (t,c,k) tuple of b-spline knots, coefficients, and degree returned by splprep.
        per : if tck was created as a periodic spline, per *must* be true, else per *must* be false.
    
    Output:
        A list of Bezier curves of degree k that is equivalent to the input spline.
        Each Bezier curve is an array of shape (k+1,d) where d is the dimension of the
        space; thus the curve includes the starting point, the k-1 internal control
        points, and the endpoint, where each point is of d dimensions.
    """
    t, c, k = tck
    t = np.asarray(t)
    try:
        c[0][0]
    except:
        # I can't figure out a simple way to convert nonparametric splines to
        # parametric splines. Oh well.
        raise TypeError("Only parametric b-splines are supported.")
    new_tck = tck
    if per:
        # ignore the leading and trailing k knots that exist to enforce periodicity
        knots_to_consider = np.unique(t[k:-k])
    else:
        # the first and last k+1 knots are identical in the non-periodic case, so
        # no need to consider them when increasing the knot multiplicities below
        knots_to_consider = np.unique(t[k + 1:-k - 1])
    # For each np.unique knot, bring it's multiplicity up to the next multiple of k+1
    # This removes all continuity constraints between each of the original knots,
    # creating a set of independent Bezier curves.
    desired_multiplicity = k + 1
    for x in knots_to_consider:
        current_multiplicity = np.sum(t == x)
        remainder = current_multiplicity % desired_multiplicity
        if remainder != 0:
            # add enough knots to bring the current multiplicity up to the desired multiplicity
            number_to_insert = desired_multiplicity - remainder
            new_tck = fitpack.insert(x, new_tck, number_to_insert, per)
    tt, cc, kk = new_tck
    # strip off the last k+1 knots, as they are redundant after knot insertion
    # correction: except for short curves -LK
    bezier_points = np.transpose(cc)
    if len(bezier_points)>desired_multiplicity:
        bezier_points = bezier_points[:-desired_multiplicity]
        
    if per:
        # again, ignore the leading and trailing k knots
        bezier_points = bezier_points[k:-k]
    # group the points into the desired bezier curves
    return np.split(bezier_points, len(bezier_points) / desired_multiplicity, axis=0)
   
def areaOfPolygon(points):
    """
    Return area enclosed by points, assuming it is a simple polygon.
    See http://mathworld.wolfram.com/PolygonArea.html
    """
    x,y = zip(*points)
    A = np.sum(x[n]*y[n+1] - x[n+1]*y[n] for n in range(len(x)-1))/2
    return abs(A)

def xyFromPoints(points, offset=QtCore.QPointF(0,0)):
    """ Return list of point tuples from sequence of QPointF """
    return [(p.x() + offset.x(), p.y() + offset.y()) for p in points]
    
    
    