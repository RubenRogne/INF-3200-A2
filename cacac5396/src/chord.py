#!/usr/bin/env python3
# ------ chord.py

import hashlib

# 160 bits because SHA1 hashing produce IDs as binary numbers (hence 2^160 possibilities)
# example 3 bits = 2^3 = 8 IDs
M_BITS = 160
RING_SIZE = 2 ** M_BITS #tot

# ----------- hash_to_id : provide the cobnversion by hashing string to ID
def hash_to_id(text):
    #convert the nodes name and keys into numbers through hashing
    hashed_text = hashlib.sha1(text.encode("utf-8")).digest()
    ID_number = int.from_bytes(hashed_text, "big") # big = first byte is the "big end" 
    # reads left to right like int numbers
    return ID_number

# ----------- in_interval_open_closed : check where the key belong
def in_interval_open_closed(key_id, pred_id, self_id):
    # normal interval (no wrap)
    if pred_id < self_id: #check if predecessor is smaller then self
        if key_id > pred_id and key_id <= self_id: #check the key
            return True
        else:
            return False

    # wrap interval (pred > self, crossing 0) , we reach the end of the circle
    else:
        if key_id > pred_id or key_id <= self_id: #check key
            return True
        else:
            return False

# ----------- finger_in_open_interval : check if finger node in path to the final node
def finger_in_open_interval(finger_id, current_id, target_id): 

    # no wrap (forward interval)
    if current_id < target_id:
        if (current_id < finger_id) and (finger_id < target_id): #open interval because
            # never want to "forward" to myself or directly to the target (need to follow the path, hops)
            return True
        else:
            return False

    # wrap around (interval crosses 0 on the ring, loops to start)
    else:
        if (finger_id > current_id) or (finger_id < target_id):
            return True
        else:
            return False
        

# ----------- how_many_fingers : choose finger table size
# PATCH : use pow doubling to simulate log2(n) (how many times we divide n by 2 until we reach 1)
# (count how many times we double 1 until reaching node_count)
# then add +1 finger for safety (rounding and extra shortcut)
def how_many_fingers(node_count):
    
    if node_count <= 1:
        return 1
    power = 1
    count = 0
    while power < node_count:
        count = count + 1
        power = power * 2
    count = count + 1
    if count > M_BITS:
        count = M_BITS
    return count


class ChordNode:
    def __init__(self, self_address, peer_addresses):

        # remember own address
        self.self_address = self_address

        # hash it into a number (ID on the ring)
        self.self_id = hash_to_id(self_address)


        # build the list of all nodes (peers + me) with no duplicates
        all_addresses = []
        if peer_addresses is not None:
            for a in peer_addresses:
                all_addresses.append(a)           # copy peers

        all_addresses.append(self_address)        # add me

        all_addresses = list(set(all_addresses))  # remove duplicates (set is for unique list)

        # build ring as list of (address, id)
        ring = []
        for addr in all_addresses:
            node_id = hash_to_id(addr)            # hash conversion
            pair = (addr, node_id)                # (address, ID)
            ring.append(pair)
        
        # sort ring by id
        def get_id(pair):
            return pair[1] #get the ID since we use that to organize
        
        ring.sort(key=get_id) #sort (built in funct) using the ID value (smallest to biggest)

        #--- find myself (node) in the ring

        my_index = -1 #always invalid for safety at declaration

        for i in range(len(ring)): #check each index
            current_address = ring[i][0]
            if current_address == self_address:
                my_index = i #found myself and stored

        if my_index == -1:
            raise RuntimeError("self not found in ring list")

        #--- predecessor and successor
        if len(ring) == 1: #if single node ring (both are me)
            pred = ring[0]
            succ = ring[0]
        else:
            # PATCH: use (index + or - 1) % len(ring) to wrap around
            # example with 4 nodes: (0 - 1) % 4 = 3 = predecessor of first node is last node
            # (3 + 1) % 4 = 0 = successor of last node is first node

            pred_index = (my_index - 1) % len(ring)
            succ_index = (my_index + 1) % len(ring)

            pred = ring[pred_index] #take the specific tuple out from array [(adress,ID),(adress,ID)]
            succ = ring[succ_index]

        # store predecessor and successor info from tuple = (adress,ID)
        self.pred_address = pred[0] 
        self.pred_id = pred[1]
        self.succ_address = succ[0]
        self.succ_id = succ[1]

        #--- build finger table
        finger_count = how_many_fingers(len(ring)) #amount per table

        self.fingers = [] #fingers list

        for i in range(finger_count): #do for numbers of fingers needed
            step_size = 2 ** i # finger start = self_id + 2^i (then wrap)
            start_pre = self.self_id + step_size 
            #wraps around
            start = start_pre % RING_SIZE

            chosen = None

            for j in range(len(ring)): #loop in the sorted ring itself

                node_address = ring[j][0] # [j] is the couple of adress,ID at j inside the ring
                node_id = ring[j][1] # [1] or [0] is which part of the couple is [(address,ID)] so address or ID  
                
                if node_id >= start: 
                    chosen = (node_address, node_id) #picks it
                    break

            if chosen is None:
                chosen = ring[0]  # wrap around to first in ring 

            self.fingers.append(chosen) #add it to the finger table list

        # after init, the local variable "ring" disappears (not saved to self)
        # so this node only keeps pred, succ, and fingers to self 

    # ---------------------------------------

    # ----------- is_responsible : check if the node is responsible for a certain key
    def is_responsible(self, key_id):
        
        result = in_interval_open_closed(key_id, self.pred_id, self.self_id)
        return result

    # ----------- shortcut_step : choose the closest immediate "neighbor" node to the target (sometimes target itself)
    def shortcut_step(self, target_id):

        # go through fingers from last to first
        index = len(self.fingers) - 1

        while index >= 0:
            node_address = self.fingers[index][0]
            node_id = self.fingers[index][1]

            if node_address != self.self_address: #check that is not himself 
                # PATCH (could cause infinite loop if himself in table, could happen in small rings)
                in_range = finger_in_open_interval(node_id, self.self_id, target_id)
                if in_range == True:
                    return node_address

            index = index - 1

        # if no finger fits, use direct successor (fallback to the slow way)
        return self.succ_address

    # ----------- network_view : return addresses of known neighbors (pred, succ, fingers) 
    def network_view(self):
        
        seen = set() #remove duplicates

        if self.pred_address != self.self_address:
            seen.add(self.pred_address)

        if self.succ_address != self.self_address:
            seen.add(self.succ_address)

        for m in range(len(self.fingers)):
            node_address = self.fingers[m][0]
            if node_address != self.self_address:
                seen.add(node_address)

        out = list(seen) #turn the set into a list.
        out.sort() #sort it alphabetically or by ascending order if ints
        return out #return it

