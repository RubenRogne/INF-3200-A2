#!/usr/bin/env python3

import sys
import signal
import socket
import threading
import http.server
import socketserver
import argparse

#new imports
from chord_node import Chord_node as CN
import requests

from urllib.parse import urlsplit

CHORDSIZE = 65536
#todo
"""
linked list structure with pointer from first to last as well
do get /sorage/key
    return storage key if within adress space
    else get/storage/key neighbour
do get /network
    run through list and get all nodes
    return in a list
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


def main() -> None:
    node_address = str(sys.argv[2]) #requires that we pass the node a second time
    follower = str(sys.argv[3])
    node = CN(hash(node_address), node_address, CN(hash(follower), follower, None, node_address, {1:2}), follower, {1:1})
    node.follower.assign_follower(node)
    HelloWorldHandler.node = node
    #print(requests.get(sys.argv(3)+"/helloworld"))
    print(follower, "and the main node: ", node_address)
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

    def do_GET(self) -> None:
        path = urlsplit(self.path).path  # ignore ?query
        if path == "/helloworld":
            body = f"{HOSTNAME}:{PORT}".encode("utf-8")
            self._ok_headers(len(body))
            self.wfile.write(body)
            #print(requests.get("http://"+sys.argv(3)+"/helloworld"))
            try:
                self.wfile.flush()  # avoid buffers
            except Exception:
                pass
        
        elif path == "/storage/1":
            body = (str(self.node.get_key([], 1))).encode("utf-8")
            self._ok_headers(len(body))
            self.wfile.write(body)
        elif path == "/network": #must format output to json
            body = (str(self.node.get_network(self.node.get_name(), []))).encode("utf-8")
            self._ok_headers(len(body))
            self.wfile.write(body)
        
        else:
            self.send_error(404, "not found")

    def do_HEAD(self) -> None:
        path = urlsplit(self.path).path
        if path == "/helloworld":
            self._ok_headers(len(f"{HOSTNAME}:{PORT}".encode("utf-8")))
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
