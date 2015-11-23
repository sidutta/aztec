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
import os

config = ConfigParser.ConfigParser()
config.read('aztec.cfg')
master_ip = config.get('Main_Config','master_ip_addr')
aztecport = config.getint('Main_Config','master_controller_port')

client = MongoClient()
client = MongoClient(master_ip, 27017)
db = client.aztecdb
db.online_nodes.drop()
host_collection = db.online_nodes

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

def check_node_status():
    collection = db.online_nodes
    nodes = collection.find()
    for node in nodes:
    	if(node['ip'] == master_ip):
    		continue
        if(time.time()-node['timestamp']>=timeout_threshold):
            collection.update_one({"ip":node['ip']},{"$set":{"status":"offline"}})
            print "Lost connection with", node['ip']
	else:
	    print "Everything is fine with",node['ip']

def choose_least_loaded(privelege_level):
    hosts = host_collection.find()
    minimum_so_far = 0
    best_host = -1
    for host in hosts:
        if host['status'] == "online":
            if best_host == -1 or host[privelege_level] < minimum_so_far:
                best_host = host['ip']
                minimum_so_far = host[privelege_level]
    return best_host

def node_exit_handler(addr):
    collection = db.containers
    containers = collection.find()
    resource_shares = {'high':{'cpu_shares' : 1000, 'mem_limit' : '600m'}, 'medium':{'cpu_shares' : 100, 'mem_limit' : '400m'}, 'low':{'cpu_shares' : 10, 'mem_limit' : '200m'}}
    for container in containers:
    	if container['host_ip'] == addr and container['checkpointed'] == "true":
            host_ip = choose_least_loaded(container['privelege_level'])
            cli = Client(base_url=host_ip+":2375")
            cli.pull(repository=registry+"/"+container['source_image'], tag=container['username']+"_"+container['container_name'], stream=False)
            #Create
            image_name = registry+"/"+container['source_image']+":"+container['username']+"_"+container['container_name']
            privelege_level = container['privelege_level']
            portlist = []
            portmap = {}
            if container['source_image'] == "tomcat":
                portlist.append(22)
                portmap[22] = container['ssh_port']

            host_config = cli.create_host_config(mem_limit=resource_shares[privelege_level]['mem_limit'], port_bindings=portmap)
            container_new = cli.create_container(image=image_name,cpu_shares=resource_shares[privelege_level]['cpu_shares'],host_config=host_config,ports=portlist)

            original_load = host_collection.find({"ip":host_ip})[0][privelege_level]
            host_collection.update_one({"ip":host_ip},{"$set":{privelege_level:original_load+1}})
            collection.update_one({"container_id":container['container_id']},{"$set":{"host_ip":host_ip}})
            collection.update_one({"container_id":container['container_id']},{"$set":{"container_id":container_new['Id']}})
            #Start
            if container['status'] == "Started":
                container_id = container_new['Id']
                response = cli.start(container=container_id)
                executor = cli.exec_create(container=container_id,cmd="bash service ssh start")
                response = cli.exec_start(executor.get('Id'))
    print "Failure handler called"

def check_container_status():
    collection = db.containers
    containers = collection.find()
    for container in containers:
        if host_collection.find({"ip":container['host_ip']})[0]['status'] == "online":
            cli = Client(base_url=container['host_ip']+":2375")
            status = cli.inspect_container(container['container_id'])['State']
            if status['Running'] is True:
                collection.update_one({"container_id":container['container_id']},{"$set":{"status":"Started"}})
            else:
                collection.update_one({"container_id":container['container_id']},{"$set":{"status":"Stopped"}})             

def checkpoint():
    collection = db.containers
    containers = collection.find()
    for container in containers:
        cli = Client(base_url=container['host_ip']+":2375")
        status = cli.inspect_container(container['container_id'])['State']
        if status['Running'] is True:
            if container['checkpointed'] == "false":
                collection.update_one({"container_id":container['container_id']},{"$set":{"checkpointed":"true"}})
            #cli.commit(container=container['container_id'],repository=registry+"/"+container['source_image'],tag=container['username']+"_"+container['container_name'])
            commit_cmd = "docker -H " + container['host_ip'] + ":2375 commit --pause=false "+container['container_id']+" "+registry+"/"+container['source_image']+":"+container['username']+"_"+container['container_name']
            os.system(commit_cmd)
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
port = aztecport                # Reserve a port for your service.
s.bind((master_ip, port))        # Bind to the port

s.listen(5)                 # Now wait for client connection.

timeout_threshold = 20

RepeatedTimer(10, check_node_status)
RepeatedTimer(30, check_container_status)
RepeatedTimer(300, checkpoint)
collection = db.online_nodes

collection.insert({"ip":master_ip, "status":"online", "timestamp":time.time(), "high":0, "medium":0, "low":0})

while True:
    conn, addr = s.accept()     # Establish connection with client.
    print 'Got connection request from', addr[0]
    present = collection.find({"ip":addr[0]}).count()
    if(present<=0):	
        collection.insert({"ip":addr[0], "status":"online", "timestamp":time.time(), "high":0, "medium":0, "low":0})
    else:
        collection.update_one({"ip":addr[0]},{"$set":{"status":"online","timestamp":time.time()}})
    start_new_thread(clientthread, (conn, addr[0]))
