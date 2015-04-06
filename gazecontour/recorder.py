import inspect
from PySide import QtCore, QtGui
import pandas

class Recorder(QtCore.QObject):
    """
    Takes incoming frame dicts, stores them, and records them to csv file on command
    """
    recordingChanged = QtCore.Signal(bool)

    def __init__(self, statusLabel):
        super().__init__()
        self._statusLabel = statusLabel

        self.data = [] # Save data as list of frame dicts, for now
        self.extraData = {}
        self.pathData = {}
        self.recording = False
        self._desktopWidget = QtGui.QDesktopWidget()
        self.clear()

    def _flatten(self, d, parent_key=''):
        """
        Flatten a dict like {'avg':{'x':42, 'y':0}} into {'avg_x':42, 'avg_y':0}
        """
        import collections
        items = []
        for k, v in d.items():
            new_key = parent_key + '_' + k if parent_key else k
            if isinstance(v, collections.MutableMapping):
                items.extend(self._flatten(v, new_key).items())
            else:
                items.append((new_key, v))
        return dict(items)

    def handleFrame(self, frame):
        """
        Save the gaze frame to memory, along with mouse position
        """
        if self.recording:
            # Flatten frame dict to one level
            datapoint = self._flatten(frame)

            # Add to memory
            self.data.append(datapoint)

            self._statusLabel.setText('Recorded {} frames'.format(len(self.data)))


    def setRecording(self, rec):
        if self.recording != rec:
            self.recording = rec
            self.recordingChanged.emit(rec)
            
    def saveStim(self, stimItem, stimPos):
        """
        Keep track of what function was used to draw a stimulus, and it's position (QPoint)
        """
        if stimItem is None:
            self.extraData.clear()
        else:
            self.extraData.update({'stim_item': stimItem.__name__,
                 'stim_module': stimItem.__module__,
                 'stim_x': stimPos.x(),
                 'stim_y': stimPos.y()})
    
    def savePath(self, points):
        """
        Similar to saveStim, save the drawn path (currently only one)
        points = array of QPointF
        """
        if points is None:
            self.pathData.clear()
        else:
            self.pathData.update({'x': [p.x() for p in points],
                                  'y': [p.y() for p in points]})
        
    
    def clear(self):
        self.data.clear()
        self._statusLabel.setText('Recorder ready')

    def toDataFrame(self):
        """ Return a pandas.DataFrame with all data in memory up to this point """
        df = pandas.DataFrame(self.data)
        if len(df) > 0:
            df.set_index('timestamp', inplace=True)
            df.index.name = None
        return df

    def saveToFile(self):
        """ Save data to csv file, after opening a file dialog """
        filename, _ = QtGui.QFileDialog.getSaveFileName(self.parent(), 'Save File', '',
                                                        'Excel Workbook (*.xlsx);; Excel 97-2003 Workbook (*.xls)')
        if filename:
            writer = pandas.ExcelWriter(filename)
            self.toDataFrame().to_excel(writer, 'GazeData')
            pandas.DataFrame.from_dict(self.extraData, orient='index').to_excel(writer, 'Extra')
            pandas.DataFrame.from_dict(self.pathData).to_excel(writer, 'Path')
            writer.save()
