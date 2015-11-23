import signal, os
from docker import Client
import pymongo
from pymongo import MongoClient
from prettytable import PrettyTable
import ConfigParser

def handler(signum, frame):
    print('Signal handler called with signal', signum)
    exit()

signal.signal(signal.SIGINT, handler)
signal.signal(signal.SIGTERM, handler)
signal.signal(signal.SIGQUIT, handler)
signal.signal(signal.SIGTSTP, handler)

config = ConfigParser.ConfigParser()
config.read('aztec.cfg')
debug = config.getboolean('Main_Config','debug')
master_ip = config.get('Main_Config','master_ip_addr')

# defining privelege levels
resource_shares = {'high':{'cpu_shares' : 1000, 'mem_limit' : '600m'}, 'medium':{'cpu_shares' : 100, 'mem_limit' : '400m'}, 'low':{'cpu_shares' : 10, 'mem_limit' : '200m'}}

client = MongoClient()
client = MongoClient(master_ip, 27017)

db = client.aztecdb
collection = db.users
print "Yo World! Welcome to Aztec!"

if(debug is False):
    username = raw_input("Enter username: ")
    password = raw_input("Enter password: ")
else:
    username = "tu1"
    password = "a"

config_collection = db.configs
host_collection = db.online_nodes
con = config_collection.find({"key":"freeport"})
con_already_present = con.count()
if con_already_present == 0:
    freeport = 20005
    config_collection.insert({"key":"freeport","value":20005})
else:
    freeport = con[0]['value']

user_count = 0
user_count = collection.find({"username":username,"password":password}).count()

if user_count==0:
    print "Invalid username/password"
    exit()

print "Logged in as", username

def docker_client(host_ip):
    return Client(base_url=host_ip+":2375")

def choose_least_loaded(privelege_level):
    hosts = host_collection.find()
    minimum_so_far = 0
    best_host = -1
    for host in hosts:
        if best_host == -1 or host[privelege_level] < minimum_so_far:
            best_host = host['ip']
            minimum_so_far = host[privelege_level]
    return best_host

##################
def list_containers_users():
    collection = db.containers
    containers = collection.find({"username":username})
    table = PrettyTable(['Container Name','Status','Image','Resource Allocation'])
    for container in containers:
        table.add_row([container['container_name'], container_status(container['container_name']), container['source_image'], container['privelege_level']])
    print table

def help():
    print "exit: exit the session"
    print "containers: list all your containers"
    print "create: create an image instance"
    print "erase [instance_name]: deletes the instance, can't be retrieved later"
    print "start [instance_name]: starts an instance already created"
    print "stop [instance_name]: stops a running instance"
    print "status [instance_name]: check the status of an instance"
    print "get-ssh-link [instance_name]: get link to ssh into an instance"
    print "add-key [instance_name] [key]: add your public key"
    print "update-repo [instance_name]: update your git repository after pushing into git"
    print "get-git-clone-link [instance_name]: get link to clone your tomcat repo to your local machine"

def create():
    print "Type options to find out various apps that you can create"
    command = raw_input("Enter your choice: ").strip()
    collection = db.containers
    if command == "options":
        print "tomcat: "
        print "postgres: "
        create()
    elif command == "tomcat" or command == "postgres":
        while True:
            container_name = raw_input("Name the "+ command +" instance: ")
            if container_name == "":
                print "No name specified, ignoring command create"
                return
            container_already_present = collection.find({"username":username,"container_name":container_name}).count()
            if container_already_present == 1: print "Name already present. Try again!"
            else: break
        while True:
            privelege_level = raw_input("Please assign the level of resources to be allocated (high/medium/low): ").strip()
            if privelege_level not in ["high", "medium", "low"]:
                print "Wrong input!"
                continue
            break
        image_name = command + ":git1"
        portlist = []
        portmap = {}
        ssh_port = -1
        con = config_collection.find({"key":"freeport"})
        freeport = con[0]['value']
        if command == "tomcat":
            portlist.append(22)
            portmap[22] = freeport
            ssh_port = freeport
        
        host_ip = choose_least_loaded(privelege_level)
        cli = docker_client(host_ip)
        host_config = cli.create_host_config(mem_limit=resource_shares[privelege_level]['mem_limit'], port_bindings=portmap)
        container = cli.create_container(image=image_name,cpu_shares=resource_shares[privelege_level]['cpu_shares'],host_config=host_config,ports=portlist)

        container_id = container['Id']

        collection.insert({"username":username,"container_name":container_name,"container_id":container_id,"source_image":command,"privelege_level":privelege_level,"ssh_port":ssh_port,"host_ip":host_ip,"checkpointed":"false"})
        original_load = host_collection.find({"ip":host_ip})[0][privelege_level]
        host_collection.update_one({"ip":host_ip},{"$set":{privelege_level:original_load+1}})
        if command == "tomcat":
            freeport = freeport + 1
            config_collection.update_one({"key":"freeport"},{"$set":{"value":freeport}})
        print "Successfully created",command,"instance:", container_name
    else:
        print "Wrong Input!"

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
        cli = docker_client(container[0]['host_ip'])
        cli.remove_container(container[0]['container_id'])
        collection.delete_one({"username":username,"container_name":container_name})
        original_load = host_collection.find({"ip":container[0]['host_ip']})[0][container[0]['privelege_level']]
        host_collection.update_one({"ip":container[0]['host_ip']},{"$set":{privelege_level:original_load-1}})
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
    cli = docker_client(container[0]['host_ip'])
    response = cli.start(container=container_id)
    executor = cli.exec_create(container=container_id,cmd="bash service ssh start")
    response = cli.exec_start(executor.get('Id'))
    print container_name,"started successfully!"

def add_key(container_name, key1, key2, key3):
    collection = db.containers
    container = collection.find({"username":username,"container_name":container_name})
    container_already_present = container.count()
    if container_already_present == 0:
        print "No instance",container_name,"exists!"
        return
    was_running = True
    if(container_status(container_name)!="Running"):
        print container_name,"is not running, attempting to start it!"
        was_running = False
        start_container(container_name)
    container_id = container[0]['container_id']
    print "container id is", container_id
    cli = docker_client(container[0]['host_ip'])
    executor = cli.exec_create(container=container_id,cmd="/bin/bash add-key "+key1+" "+key2+" "+key3)
    response = cli.exec_start(executor.get('Id'))
    print "restarting ssh on container"
    executor = cli.exec_create(container=container_id,cmd="/bin/bash service ssh restart")
    response = cli.exec_start(executor.get('Id'))
    executor = cli.exec_create(container=container_id,cmd="/bin/bash service ssh start")
    response = cli.exec_start(executor.get('Id'))
    print "Key added successfully!"
    if not was_running:
        stop_container(container_name)
    

def get_ssh_link(container_name):
    collection = db.containers
    container = collection.find({"username":username,"container_name":container_name})
    container_already_present = container.count()
    if container_already_present == 0:
        print "No instance",container_name,"exists!"
        return
    print "root@"+container[0]['host_ip']+" -p "+str(container[0]['ssh_port'])


def get_git_clone_link(container_name):
    collection = db.containers
    container = collection.find({"username":username,"container_name":container_name})
    container_already_present = container.count()
    if container_already_present == 0:
        print "No instance",container_name,"exists!"
        return
    print "git clone ssh://root@"+container[0]['host_ip']+":"+str(container[0]['ssh_port'])+"/usr/local/tomcat-repo ." 
    print "Do not forget to execute update-repo to update your working directory!"

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
    cli = docker_client(container[0]['host_ip'])
    response = cli.stop(container=container_id)
    print container_name,"stopped successfully!"


def update_repo(container_name):
    collection = db.containers
    container = collection.find({"username":username,"container_name":container_name})
    container_already_present = container.count()
    if container_already_present == 0:
        print "No instance",container_name,"exists!"
        return
    container_id = container[0]['container_id']
    cli = docker_client(container[0]['host_ip'])
    executor = cli.exec_create(container=container_id,cmd="bash -c \'cd /usr/local/tomcat ;  git pull\'")
    response = cli.exec_start(executor.get('Id'))
    print response
        

def container_status(container_name):
    collection = db.containers
    container = collection.find({"username":username,"container_name":container_name})
    container_already_present = container.count()
    if container_already_present == 0:
        return "No instance "+container_name+" exists!"
    container_id = container[0]['container_id']
    cli = docker_client(container[0]['host_ip'])
    status = cli.inspect_container(container_id)['State']
    if status['Running'] is True: return "Running"
    else: return "Not running"

def enter_container(container_name):
    collection = db.containers
    container = collection.find({"username":username,"container_name":container_name})
    status = container_status(container_name)
    if status == "No instance "+container_name+" exists!":
        return status
    elif status == "Not running":
        return container_name + " not running. Start it first."
    else:
        cli = docker_client(container[0]['host_ip'])
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
        elif command.split(" ")[0] == "get-ssh-link":
            if len(command.split(" "))<2:
                print("Usage: get-ssh-link [instance_name]")
                continue
            get_ssh_link(command.split(" ")[1])
        elif command.split(" ")[0] == "get-git-clone-link":
            if len(command.split(" "))<2:
                print("Usage: get-git-clone-link [instance_name]")
                continue
            get_git_clone_link(command.split(" ")[1])
        elif command.split(" ")[0] == "add-key":
            if len(command.split(" "))<3:
                print("Usage: add-key [container] [key]")
                continue
            add_key(command.split(" ")[1],command.split(" ")[2],command.split(" ")[3],command.split(" ")[4])
        elif command == "create":
            create()
        elif command.split(" ")[0] == "update-repo":
            if len(command.split(" "))<2:
                print("Usage: update-repo [instance_name]")
                continue
            update_repo(command.split(" ")[1])
        elif command.split(" ")[0] == "start":
            if len(command.split(" "))<2:
                print("Usage: start [instance_name]")
                continue
            start_container(command.split(" ")[1])
        # elif command.split(" ")[0] == "enter":
        #     if len(command.split(" "))<2:
        #         print("Usage: enter [instance_name]")
        #         continue
        #     print enter_container(command.split(" ")[1])
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
