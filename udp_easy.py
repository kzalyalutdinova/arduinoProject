import socket


sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.sendto(b'\x01\x02\x03', ('192.168.5.140', 5276))
print("Sent")