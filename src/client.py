#!/usr/bin/python           # This is client.py file

import socket               # Import socket module
import time
s = socket.socket()         # Create a socket object
host = "192.168.0.104" # Get local machine name
port = 12345                # Reserve a port for your service.

#ni.ifaddresses('wlan0')
s.connect((host, port))
while True:
    s.send("alive")
    time.sleep(10)       
s.close                     # Close the socket when done
