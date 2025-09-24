class Chord_node:
    def __init__(self, name, address, follower, follower_address, keys):
        self.name = name
        self.address = address
        self.follower = follower
        self.follower_address = follower_address
        self.fingertable = None
        self.keys = {} #should enforce a dict maybe?
        self.keys.update(keys)
        #checked_names
        
    def assign_follower(self, follower):
        self.follower = follower
    
    def get_network(self, name, known_nodes):
        if name in known_nodes or self.follower is None:
            return known_nodes
        else:
            known_nodes.append(name)
            self.follower.get_network(self.follower.get_name(), known_nodes)
            return known_nodes
    
    def get_key(self, checked_names, unknown_key):
        if self.name in checked_names:
            checked_names=()
            return False 
        else: 
            checked_names.append(self.name)
        for key in self.keys:
            if key == unknown_key:
                return self.keys.get(key)
        
        return self.follower.get_key(checked_names, unknown_key)
        
    def get_name(self):
        return str(self.name)