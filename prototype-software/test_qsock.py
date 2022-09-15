from PyQt5.QtWidgets import QApplication, QMainWindow, QAction
from PyQt5.QtNetwork import QTcpSocket, QHostAddress, QUdpSocket
from PyQt5.QtCore import QByteArray
import sys

QP_UDP_IP   = '192.169.1.17'
QP_UDP_PORT = 420

class QPIX_GUI(QMainWindow):
    def __init__(self):
        super(QMainWindow, self).__init__()

        self._udpsocket = QUdpSocket(self)
        self._nPackets = 0

        bound = self._udpsocket.bind(QHostAddress(QP_UDP_IP), QP_UDP_PORT)
        print("UDP..", end=" ")
        if bound:
            print("connected!")
        else:
            print("WARNING unconnected!..")

        if bound:
            print("connecting socket..")
            # connect the udp listening socket
            self._udpsocket.readyRead.connect(lambda: self._readUDPData())

    def _readUDPData(self):
        print("reading UDP data")
        while self._udpsocket.hasPendingDatagrams():

            datagram = QByteArray()
            datagram.resize(self._udpsocket.pendingDatagramSize())
            (data, sender, port) = self._udpsocket.readDatagram(datagram.size())
            self._nPackets += 1

if __name__ == "__main__":

    app = QApplication(sys.argv)
    window = QPIX_GUI()
    window.resize(800,700)
    app.exec_()
