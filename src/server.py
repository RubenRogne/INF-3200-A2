#!/usr/bin/env python3

import sys
import signal
import socket
import threading
import http.server
import socketserver
import argparse
from urllib.parse import urlsplit
#new imports
from chord_node import Chord_node as CN
import requests

CHORDSIZE = 65536

"""
TODO:
linked list structure with pointer from first to last as well

do get /storage/key
    does now only support keys as ints in a dict
    else get/storage/key neighbour
    
do get /network
    missing json formating
    #do this by only allowing the node itself and its successor to be known and written into the list at startup
    
do put /storage/key
    add key to storage space, adress is decided by hash
"""
# hostname
HOSTNAME = socket.gethostname().split(".")[0]

# arg check
"""
if len(sys.argv) <= 2:
    print("usage: python3 server.py <port>")
    sys.exit(1)
"""
try:
    PORT = int(sys.argv[1])
    if not (49152 <= PORT <= 65535):
        raise ValueError
except ValueError:
    print("error: port must be int in range 49152–65535")
    sys.exit(1)
    
#NOTE: CURRENT NODENAME ARE NOT LIKELY TO, BUT COMPLETELY ABLE, TO CAUSE CONFUSION WITH DULPICATE NAMES
def nodename(address):
    return address.split(":")[-1]

def main() -> None:
    node_address = str(sys.argv[2]) #requires that we pass the node a second time
    follower_address = str(sys.argv[3])
    
    node = CN(nodename(node_address), node_address, None, {"1":"1"})
    #follower = CN(nodename(follower_address), follower_address, None, {2:2})
    
    node.assign_follower(follower_address)
    #fprint(node.follower, "and ", follower)
    #follower.assign_follower(node.address)#Connects them trivially to each other (no sequence)
    
    HelloWorldHandler.node = node
    #HelloWorldHandler.follower = follower
    
    #print(requests.get(sys.argv(3)+"/helloworld"))
    #print(follower.get_name(), "and the main node: ", node.get_name())
    
    try:
        httpd = ThreadingHTTPServer(("", PORT), HelloWorldHandler)  # bind all ifaces
    except OSError as e:
        print(f"[ERROR] cant start server on {PORT}: {e}")
        sys.exit(1)

    # clean shutdown on SIGTERM/SIGINT
    def _stop(_signum, _frame):
        httpd.shutdown()

    signal.signal(signal.SIGTERM, _stop)
    signal.signal(signal.SIGINT, _stop)

    # autostop after 15 min
    timer = threading.Timer(30, httpd.shutdown)
    timer.start()

    try:
        httpd.serve_forever()
    finally:
        timer.cancel()
        httpd.server_close()
        
class HelloWorldHandler(http.server.BaseHTTPRequestHandler):
    # no spam
    server_version = "INF3200"
    sys_version = ""
    protocol_version = "HTTP/1.0"   # auto closes

    def _ok_headers(self, content_length: int) -> None:
        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.send_header("Content-Length", str(content_length))  # must match body
        self.send_header("Cache-Control", "no-store")
        self.send_header("Connection", "close")
        self.end_headers()

    def do_GET(self) -> None: #works, reminder to self: DONT BREAK IT
        path = urlsplit(self.path).path  # ignore ?query
        path = path.split("/")
        path = path[1:] #remove first empty split
        #print(path)
        if path[0] == "helloworld":
            body = f"{HOSTNAME}:{PORT}".encode("utf-8")
            self._ok_headers(len(body))
            self.wfile.write(body)
            #print(requests.get("http://"+sys.argv(3)+"/helloworld"))
            try:
                self.wfile.flush()  # avoid buffers
            except Exception:
                pass
        
        elif path[0] == "storage":
            if len(path)>2:
                body = (str(self.node.get_key(str(path[2]), str(path[1])))).encode("utf-8")
                self._ok_headers(len(body))
                self.wfile.write(body)
            else:
                body = (str(self.node.get_key("", str(path[1])))).encode("utf-8")
                self._ok_headers(len(body))
                self.wfile.write(body)
            
        elif path[0] == "network": 
            if len(path)>1:
                body = (str(self.node.get_network(self.node.get_address(), path[1]))).encode("utf-8")
                self._ok_headers(len(body))
                self.wfile.write(body)
            else:
                body = (str(self.node.get_network(self.node.get_address(), ""))).encode("utf-8")
                self._ok_headers(len(body))
                self.wfile.write(body)
        
        elif path[0] == "follower":
            #body = str(assignment(path[1], self.node))
            #body = "Node reassigned"
            body = str(self.node.assign_follower(path[1]))
            self._ok_headers(len(body.encode("utf-8")))
            self.wfile.write(body.encode("utf-8"))
        
        else:
            self.send_error(404, "not found")

    def do_HEAD(self) -> None:
        path = urlsplit(self.path).path
        if path == "/helloworld":
            self._ok_headers(len(f"{HOSTNAME}:{PORT}".encode("utf-8")))
        else:
            self.send_error(404, "not found")
    
    def do_PUT(self) -> None:
        path = urlsplit(self.path).path  # ignore ?query
        path = path.split("/")
        path = path[1:] #remove first empty split
        
        if path[0] == "storage":
            correct_dict = True #assuming correct spot
            if correct_dict:
                data = (self.rfile.read(int(self.headers.get('Content-Length')))).decode("utf-8")
                returnvalue = self.node.add_key(path[1], data)
                print(path[1], data, returnvalue, " THIS is a put")
            #data = (self.rfile.read(self.headers.get(int('Content-Length')))).decode("utf-8")
            #print(data)
            self._ok_headers(0)
        
        if path[0] == "fixfollower": ##DOES NOT CURRENTLY WORK
            #print(path[1])
            
            #data = (self.rfile.read(self.headers.get(int('Content-Length')))).decode("utf-8")
            #print(data)
            #self.node.assign_follower = CN(nodename(path[1]), path[1], node, {})
            #self.node.
            
            #body = (str(self.node.get_network(self.node.get_name(), []))).encode("utf-8")
            self._ok_headers((self.node.get_name()).encode("utf-8"))
            self.wfile.write(len((self.node.get_name()).encode("utf-8")))

        else:
            self.send_error(404, "not found")

    def log_message(self, *_args, **_kwargs) -> None:
        # keep stoutt clean
        return
    
    
class ThreadingHTTPServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True          # kill threads w server
    allow_reuse_address = True     # faster restart

if __name__ == "__main__":
    main()
