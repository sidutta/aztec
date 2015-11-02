import signal, os
from docker import Client
import pymongo
from pymongo import MongoClient

debug = True

client = MongoClient()
client = MongoClient('localhost', 27017)

db = client.aztecdb
collection = db.users
print "Yo World! Welcome to Aztec!"

def handler(signum, frame):
    print('Signal handler called with signal', signum)
    exit()

signal.signal(signal.SIGINT, handler)
signal.signal(signal.SIGTERM, handler)
signal.signal(signal.SIGQUIT, handler)
signal.signal(signal.SIGTSTP, handler)

if(debug is False):
    username = raw_input("Enter username: ")
    password = raw_input("Enter password: ")
else:
    username = "tu1"
    password = "a"

user_count = 0
user_count = collection.find({"username":username,"password":password}).count()

if user_count==0:
    print "Invalid username/password"
    exit()

print "Logged in as", username
cli = Client(base_url='192.168.0.108:2375')


# for internal use
def list_containers_admin():
    containers = cli.containers()
    for container in containers:
        print container


##################
def list_containers_users():
    collection = db.containers
    containers = collection.find({"username":username})
    for container in containers:
        print container['container_name'], "		" , container_status(container['container_name']), "        ", container['source_image']

def help():
    print "exit: exit the session"
    print "containers: list all your containers"
    print "create: create an image instance"
    print "erase [instance_name]: deletes the instance, can't be retrieved later"
    print "start [instance_name]: starts an instance already created"
    print "stop [instance_name]: stops a running instance"
    print "status [instance_name]: check the status of an instance"
    print "enter [instance_name]: ssh into an instance"

def create():
    print "Type options to find out various apps that you can create"
    command = raw_input("Enter your choice: ")
    collection = db.containers
    if command == "options":
        print "tomcat: "
        print "postgres: "
    elif command == "tomcat" or command == "postgres":
        while True:
            container_name = raw_input("Name the "+ command +" instance: ")
            if container_name == "":
                print "No name specified, ignoring command create"
                return
            container_already_present = collection.find({"username":username,"container_name":container_name}).count()
            if container_already_present == 1: print "Name already present. Try again!"
            else: break
        image_name = command + ":aztec"
        container = cli.create_container(image=image_name)
        print container['Id']
        container_id = container['Id']
        collection.insert({"username":username,"container_name":container_name,"container_id":container_id,"source_image":command})
        print "Successfully created",command,"instance:", container_name

def erase(container_name):
    collection = db.containers
    container = collection.find({"username":username,"container_name":container_name})
    container_already_present = container.count()
    if container_already_present == 0:
        print "No instance",container_name,"exists!"
        return
    elif(container_status(container_name)=="Running"):
        print "Stop",container_name,"first!"
        return
    else:
        cli.remove_container(container[0]['container_id'])
        collection.delete_one({"username":username,"container_name":container_name})
    print "Successfully removed:", container_name

def start_container(container_name):
    collection = db.containers
    container = collection.find({"username":username,"container_name":container_name})
    container_already_present = container.count()
    if container_already_present == 0:
        print "No instance",container_name,"exists!"
        return
    if(container_status(container_name)=="Running"):
        print container_name,"is already running!"
        return
    container_id = container[0]['container_id']
    response = cli.start(container=container_id)
    print container_name,"started successfully!"


def stop_container(container_name):
    collection = db.containers
    container = collection.find({"username":username,"container_name":container_name})
    container_already_present = container.count()
    if container_already_present == 0:
        print "No instance",container_name,"exists!"
        return
    if(container_status(container_name)!="Running"):
        print container_name,"is not running!"
        return
    container_id = container[0]['container_id']
    response = cli.stop(container=container_id)
    print container_name,"stopped successfully!"


def container_status(container_name):
    collection = db.containers
    container = collection.find({"username":username,"container_name":container_name})
    container_already_present = container.count()
    if container_already_present == 0:
        return "No instance "+container_name+" exists!"
    container_id = container[0]['container_id']
    status = cli.inspect_container(container_id)['State']
    if status['Running'] is True: return "Running"
    else: return "Not running"

def enter_container(container_name):
    collection = db.containers
    container = collection.find({"username":username,"container_name":container_name})
    container_already_present = container.count()
    if container_already_present == 0:
        return "No instance "+container_name+" exists!"
    container_id = container[0]['container_id']
    status = cli.inspect_container(container_id)['State']
    if status['Running'] is False: 
        return container_name + " not running. Start it first."
    else:
        processId = cli.inspect_container(container_id)['State']['Pid']
        os.system("docker exec -it " + container_id + " bash")
        return ""

def main():
    while True:
        command = raw_input("guest@aztec:$ ").strip()
        if command == "":
            continue
        elif command == "exit" or command == "logout":
            exit()
        elif command == "help":
            help()
        elif command == "containers":
            list_containers_users()
        elif command.split(" ")[0] == "erase":
            if len(command.split(" "))<2:
                print("Usage: erase [instance_name]")
                continue
            erase(command.split(" ")[1])
        elif command == "create":
            create()
        elif command.split(" ")[0] == "start":
            if len(command.split(" "))<2:
                print("Usage: start [instance_name]")
                continue
            start_container(command.split(" ")[1])
        elif command.split(" ")[0] == "enter":
            if len(command.split(" "))<2:
                print("Usage: enter [instance_name]")
                continue
            print enter_container(command.split(" ")[1])
        elif command.split(" ")[0] == "stop":
            if len(command.split(" "))<2:
                print("Usage: stop [instance_name]")
                continue
            stop_container(command.split(" ")[1])
        elif command.split(" ")[0] == "status":
            if len(command.split(" "))<2:
                print("Usage: status [instance_name]")
                continue
            print container_status(command.split(" ")[1])
        else:
            print command + " is not valid. Type help for options."

if __name__ == "__main__":
    main()
