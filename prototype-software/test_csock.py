import socket

msgFromClient       = "ni hao my friend"
bytesToSend         = str.encode(msgFromClient)
serverAddressPort   = ("192.169.1.17", 420)
bufferSize          = 1024

# Create a UDP socket at client side
UDPClientSocket = socket.socket(family=socket.AF_INET, type=socket.SOCK_DGRAM)

# Send to server using created UDP socket
while True:
    UDPClientSocket.sendto(bytesToSend, serverAddressPort)
    input("sent packet")
 
# msgFromServer = UDPClientSocket.recvfrom(bufferSize)
# msg = "Message from Server {}".format(msgFromServer[0])
# print(msg)