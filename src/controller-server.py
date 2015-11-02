#!/usr/bin/python           # This is server.py file
import pymongo
import time
from pymongo import MongoClient
import socket               # Import socket module
from threading import Timer
from thread import *
import thread

class RepeatedTimer(object):
    def __init__(self, interval, function, *args, **kwargs):
        self._timer     = None
        self.interval   = interval
        self.function   = function
        self.args       = args
        self.kwargs     = kwargs
        self.is_running = False
        self.start()

    def _run(self):
        self.is_running = False
        self.start()
        self.function(*self.args, **self.kwargs)

    def start(self):
        if not self.is_running:
            self._timer = Timer(self.interval, self._run)
            self._timer.start()
            self.is_running = True

    def stop(self):
        self._timer.cancel()
        self.is_running = False

ip_to_socket = {}

def check():
    nodes = collection.find()
    for node in nodes:
        if(time.time()-node['timestamp']>=timeout_threshold):
            collection.update({"ip":node['ip']},{"ip":node['ip'],"status":"offline","timestamp":node['timestamp']})   
            print "Lost connection with", node['ip']
	else:
	    print "Everything is fine with",node['ip']

def clientthread(conn, addr):
    while True:
        data = conn.recv(1024)
        if data=="alive":
            collection.update({"ip":addr},{"ip":addr,"status":"online","timestamp":time.time()})   
            print addr,"is alive"
        else:
            print "Something somewhere went terribly wrong!", data, addr
            conn.close()
            thread.exit()


s = socket.socket()         # Create a socket object
host = "192.168.0.106"      # Get local machine name
port = 12345                # Reserve a port for your service.
s.bind((host, port))        # Bind to the port

client = MongoClient()
client = MongoClient('localhost', 27017)
db = client.aztecdb
db.online_nodes.drop()
collection = db.online_nodes


s.listen(5)                 # Now wait for client connection.

timeout_threshold = 20

RepeatedTimer(10, check)


while True:
    conn, addr = s.accept()     # Establish connection with client.
    print 'Got connection request from', addr[0]
    present = collection.find({"ip":addr[0]}).count()
    if(present<=0):	
        collection.insert({"ip":addr[0], "status":"online", "timestamp":time.time()})
    else:
        collection.update({"ip":addr[0]},{"ip":addr[0],"status":"online","timestamp":time.time()}) 
    start_new_thread(clientthread, (conn, addr[0]))
