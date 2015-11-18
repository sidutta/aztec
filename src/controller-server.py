#!/usr/bin/python           # This is server.py file
import pymongo
import time
from pymongo import MongoClient
from docker import Client
import socket               # Import socket module
from threading import Timer
from thread import *
import thread
import ConfigParser

config = ConfigParser.ConfigParser()
config.read('aztec.cfg')
master_ip = config.get('Main_Config','master_ip_addr')

cli_master = Client(base_url=master_ip+":2375")    
registry = master_ip+":5000"

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

def check_status():
    collection = db.online_nodes
    nodes = collection.find()
    for node in nodes:
        if(time.time()-node['timestamp']>=timeout_threshold):
            collection.update_one({"ip":node['ip']},{"$set":{"status":"offline"}})
            print "Lost connection with", node['ip']
	else:
	    print "Everything is fine with",node['ip']

def node_exit_handler(addr):
    # Shift containers here

def checkpoint():
    collection = db.containers
    containers = collection.find()
    for container in containers:
        cli = Client(base_url=container['host_ip']+":2375")
        status = cli.inspect_container(container['container_id'])['State']
        if status['Running'] is True:
            if container['checkpointed'] == "true":
                cli.remove_image(image=container['source_image']+':'+container['username']+"_"+container['container_name'])
            else:
                collection.update_one({"container_id":container['container_id']},{"$set":{"checkpointed":"true"}})
            cli.commit(container=container['container_id'],repository=registry+"/"+container['source_image'],tag=container['username']+"_"+container['container_name'])
            cli.push(repository=registry+"/"+container['source_image'], tag=container['username']+"_"+container['container_name'], stream=False)
            print container['container_name']+"'s checkpointing is complete!"

def clientthread(conn, addr):
    while True:
        data = conn.recv(1024)
        if data=="alive":
            collection.update_one({"ip":addr},{"$set":{"status":"online","timestamp":time.time()}})   
            print addr,"is alive"
        else:
            print "Something somewhere went terribly wrong!", data, addr
            node_exit_handler(addr)
            conn.close()
            thread.exit()


s = socket.socket()         # Create a socket object
port = 12355                # Reserve a port for your service.
s.bind((master_ip, port))        # Bind to the port

client = MongoClient()
client = MongoClient(master_ip, 27017)
db = client.aztecdb
db.online_nodes.drop()

s.listen(5)                 # Now wait for client connection.

timeout_threshold = 20

RepeatedTimer(10, check_status)
RepeatedTimer(300, checkpoint)
collection = db.online_nodes

while True:
    conn, addr = s.accept()     # Establish connection with client.
    print 'Got connection request from', addr[0]
    present = collection.find({"ip":addr[0]}).count()
    if(present<=0):	
        collection.insert({"ip":addr[0], "status":"online", "timestamp":time.time(), "high":0, "medium":0, "low":0})
    else:
        collection.update_one({"ip":addr[0]},{"$set":{"status":"online","timestamp":time.time()}})
    start_new_thread(clientthread, (conn, addr[0]))
