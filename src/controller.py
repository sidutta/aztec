import signal, os
from docker import Client
import pymongo
from pymongo import MongoClient

debug = True

client = MongoClient()
client = MongoClient('192.168.0.108', 27017)

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

user_count = collection.find({"username":username,"password":password}).count()

if user_count==0:
    print "Invalid username/password"
    exit()

print "Logged in as", username
cli = Client(base_url='unix://var/run/docker.sock')


# for internal use
def list_containers_admin():
    containers = cli.containers()
    for container in containers:
        print container

def list_containers_user():
    print "xyz"

def help():
    print "exit: exit from your VM"
    print "containers: list all your containers"

def create():
    print "Type options to find out various apps that you can create"
    command = raw_input("Enter your choice: ")
    collection = db.containers
    if command == "options":
        print "tomcat: "
        print "postgres: "
    elif command == "tomcat":
        while True:
            container_name = raw_input("Name the tomcat instance: ")
            if container_name == "":
                print "No name specified, ignoring command create"
                return
            container_already_present = collection.find({"username":username,"container_name":container_name}).count()
            if container_already_present == 1: print "Name already present. Try again!"
            else: break
        container = cli.create_container(image='tomcat:latest')
        print container['Id']
        container_id = container['Id']
        collection.insert({"username":username,"container_name":container_name,"container_id":container_id})
        print "Successfully created tomcat instance:", container_name
    elif command == "postgres":
        while True:
            container_name = raw_input("Name the postgres instance: ")
            if container_name == "":
                print "No name specified, ignoring command create"
                return
            container_already_present = collection.find({"username":username,"container_name":container_name}).count()
            if container_already_present == 1: print "Name already present. Try again!"
            else: break
        container = cli.create_container(image='postgres:latest')
        print container['Id']
        container_id = container['Id']
        collection.insert({"username":username,"container_name":container_name,"container_id":container_id})
        print "Successfully created postgres instance:", container_name

def erase():
    collection = db.containers
    container_name = raw_input("Enter the name of the instance to be removed: ")
    if container_name == "":
        print "No name specified, ignoring command create"
        return
    container = collection.find({"username":username,"container_name":container_name})
    container_already_present = container.count()
    if container_already_present == 0:
        print "No instance",container_name,"exists!"
        return
    else:
        cli.remove_container(container[0]['container_id'])
        collection.delete_one({"username":username,"container_name":container_name})
    print "Successfully removed:", container_name

def main():
    while True:
        command = raw_input("guest@aztec:$ ")
        if command == "exit" or command == "logout":
            exit()
        elif command == "help":
            help()
        elif command == "containers":
            list_containers_admin()
        elif command == "erase":
            erase()
        elif command == "create":
            create()
        else:
            print command + " is not valid. Type help for options."

if __name__ == "__main__":
    main()
