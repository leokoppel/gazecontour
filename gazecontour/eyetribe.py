from PySide import QtCore, QtNetwork
import json
import logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


# attributes we can get/set on the tracker, except for 'frame'
trackerAttributes = ['push', 'heartbeatinterval', 'version', 'trackerstate',
                   'framerate', 'iscalibrated', 'iscalibrating', 'calibresult',
                   'screenindex', 'screenresw', 'screenresh',
                   'screenpsyw', 'screenpsyh']

class EyeTribe(QtCore.QObject):
    """
    EyeTribe client for PySide
    """
    newFrame = QtCore.Signal(dict)

    # State masks
    STATE_TRACKING_GAZE = 0x1
    STATE_TRACKING_EYES = 0x2
    STATE_TRACKING_PRESENCE = 0x4
    STATE_TRACKING_FAIL = 0x8
    STATE_TRACKING_LOST = 0x10

    def __init__(self):
        """
        Connect to tracker and get all attribute values
        """
        super().__init__()
        self.socket = QtNetwork.QTcpSocket(self)
        self.socket.readyRead.connect(self.handleReadyRead)
        self.socket.stateChanged.connect(lambda state: logger.info('Tracker socket: {}'.format(state)))

        self._inBuffer = QtCore.QByteArray()
        self._inBraceCounter = 0
        self._inBraceFlag = False

        self._trackerAttributes = {}
        for attr in trackerAttributes:
            self._trackerAttributes[attr] = None

        self._heartbeatTimer = QtCore.QTimer(self)
        self._heartbeatTimer.timeout.connect(self.sendHeartbeat)


    def start(self, ip='127.0.0.1', port=6555):
        self.socket.connectToHost(ip, port)
        self._heartbeatTimer.start(1000)

        # Send initial requests: set push and get all attributes
        self.set({"push": True, "version": 1})
        self.requestGet(trackerAttributes)

    def stop(self):
        self._heartbeatTimer.stop()
        self.socket.disconnectFromHost()

    def sendMessage(self, category, request=None, values=None):
        msg = {'category': category}
        if request is not None:
            msg['request'] = request
        if values is not None:
            msg['values'] = values

#        logger.debug('Request: {}'.format(msg))
        json.dump(msg, self.socket)

    def sendHeartbeat(self):
        self.sendMessage('heartbeat')

    def handleReadyRead(self):
        """
        Read from the socket, one byte at a time, until a valid JSON object is found.
        
        We judge the end of the JSON object by counting braces. For simplicity assume EyeTribe
        sends no braces within strings.
        """
        while self.socket.bytesAvailable():
            c = self.socket.read(1)
            self._inBuffer.append(c)
            if c == '{':
                self._inBraceCounter += 1
                self._inBraceFlag = True
            elif c == '}':
                self._inBraceCounter -= 1
            if self._inBraceCounter < 0:
                raise Exception('Bad response received: too many closing braces')
            if self._inBraceFlag and self._inBraceCounter == 0:
                # A complete response!
                self._inBraceFlag = False
                self.handleResponse(json.loads(str(self._inBuffer)))
                self._inBuffer.clear()

    def get(self, attr):
        """
        Get the latest value of a tracker attribute
        """
        return self._trackerAttributes[attr]

    def requestGet(self, attr):
        """
        Send a new request for tracker attributes
        """
        if not isinstance(attr, list):
            attr = [attr]
        self.sendMessage('tracker', 'get', attr)

    def set(self, attr, value=None):
        """
        Set the value of a tracker attribute via a new request
        If attr is a dict of name:value pairs, set all of them.
        """
        if value is not None:
            attr = {attr: value}

        for name, value in attr.items():
            self._trackerAttributes[name] = value
        self.sendMessage('tracker', 'set', attr)

    def handleResponse(self, resp):
        """
        Take one complete resp (one JSON object) and parse it,
        and emit a signal if needed
        """
        logger.debug('Response: {}'.format(resp))

        if resp['statuscode'] == 200:
            if resp['category'] == 'tracker':
                if resp['request'] == 'get':
                    for k, v in resp['values'].items():
                        # assign tracker attributes to self
                        self._trackerAttributes[k] = v
                    if 'heartbeatinterval' in resp['values']:
                        self._heartbeatTimer.setInterval(resp['values']['heartbeatinterval'])
                    if 'frame' in resp['values']:
                        self.handleFrame(resp['values']['frame'])
                elif resp['request'] == 'set':
                    # All good - new values have already been set
                    pass
            elif resp['category'] == 'calibration':
                pass
            elif resp['category'] == 'heartbeat':
                pass
        elif resp['statuscode'] == 800:
            # Calibration change
            self.sendMessage('tracker', 'get', ['iscalibrated', 'iscalibrating', 'calibresult'])
        elif resp['statuscode'] == 801:
            # Display change
            self.sendMessage('tracker', 'get', ['screenindex', 'screenresw', 'screenresh',
                                                'screenpsyw', 'screenpsyh'])
        elif resp['statuscode'] == 802:
            # Tracker state change
            self.sendMessage('tracker', 'get', ['trackerstate'])
        else:
            # some error
            try:
                raise Exception('Tracker returned {}: {}'.format(resp['statuscode'], resp['values']['statusmessage']))
            except KeyError:
                raise Exception('Tracker returned {}'.format(resp['statuscode']))
        return None

    def handleFrame(self, frame):
        """
        Handle a new received frame:
        Emit a signal with the latest frame object (a dict)
        """
        self.newFrame.emit(frame)

if __name__ == '__main__':
    from PySide.QtGui import QApplication
    import sys
    qt_app = QApplication(sys.argv)
    testClient = EyeTribe()
    qt_app.exec_()




