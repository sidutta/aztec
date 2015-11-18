#!/usr/bin/python           # This is client.py file

import ConfigParser
import socket               # Import socket module
import time

config = ConfigParser.ConfigParser()
config.read('aztec.cfg')
host = config.get('Main_Config','master_ip_addr')
port = config.getint('Main_Config','master_controller_port')

s = socket.socket()         # Create a socket object
s.connect((host, port))
while True:
    s.send("alive")
    time.sleep(10)       
s.close                     # Close the socket when done
