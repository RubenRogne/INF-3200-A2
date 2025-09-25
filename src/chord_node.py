import requests

class Chord_node:
    def __init__(self, name, address, follower, keys):
        self.name = name
        self.address = address
        self.follower = follower #ADDRESS
        self.fingertable = None
        self.keys = {} #should enforce a dict maybe?
        self.keys.update(keys)
        
    def assign_follower(self, new_follower):
        self.follower = new_follower
        return 1


    def ask_follower_for_network(self, known_nodes):
        #print(f"http://{self.follower}/network/"+known_nodes+"\n")
        return (requests.get(f"http://{self.follower}/network/"+str(known_nodes))).text
    
    def get_network(self, address, known_nodes): #realised i dont need address, it knows itself
        if address in known_nodes.split("_"):
            return known_nodes
        else:
            known_nodes = known_nodes + "_" + self.address
            return self.ask_follower_for_network(known_nodes)
        
    
    def ask_follower_for_key(self, checked_names, unknown_key):
        print(f"http://{self.follower}/storage/"+str(unknown_key)+"\n")
        return requests.get(f"http://{self.follower}/storage/"+str(unknown_key)+"/"+str(checked_names)).text
    
    def get_key(self, checked_names, unknown_key):
        if self.name in checked_names:
            return False 
        else: 
            checked_names = checked_names+"_"+self.name #SHOULD BE DONE BY ADDING A NUMBER, TEMPORARY FIX
        for key in self.keys:
            if key == unknown_key:
                return self.keys.get(key)
        return self.ask_follower_for_key(checked_names, unknown_key)
    
    def add_key(self, key, value):
        self.keys.update({key : value})
        return self.keys
    
    def get_name(self):
        return str(self.name)
    def get_address(self):
        return str(self.address)