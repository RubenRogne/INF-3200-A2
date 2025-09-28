#!/usr/bin/env python3

import sys
import signal
import socket

import threading
import http.server
import socketserver
import http.client
import json
from urllib.parse import urlsplit

from chord import ChordNode, hash_to_id  # chord main algo

# get name
HOSTNAME = socket.gethostname().split(".")[0]

# arg check
if len(sys.argv) not in (2, 3):
    print("usage: python3 server.py <port> [<peers_json>]")
    sys.exit(1)

try:
    PORT = int(sys.argv[1])  # convert
    if not (49152 <= PORT <= 65535):
        raise ValueError
except ValueError:
    print("error: port must be int in range 49152–65535")
    sys.exit(1)

# start with empty peers
PEERS = []

# check if peers were given
if len(sys.argv) == 3:
    try:
        PEERS = json.loads(sys.argv[2])
        if type(PEERS) != list:
            raise ValueError
    except Exception:
        print("error: peers list not valid")
        sys.exit(1)

# make my address (name:port)
SELF_ADDR = HOSTNAME + ":" + str(PORT)

# create chord node (knows id, pred, succ, fingers)
CHORD = ChordNode(SELF_ADDR, PEERS)

# empty storage for key-values
STORE = {}

# stop endless forward loops / bug safety
DEFAULT_TTL = 32


class DHTHandler(http.server.BaseHTTPRequestHandler):
    server_version = "INF3200"
    sys_version = ""
    protocol_version = "HTTP/1.0"   # no keep alive

    def _ok_headers(self, content_length: int) -> None:
        
        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.send_header("Content-Length", str(content_length))
        self.send_header("Cache-Control", "no-store")
        self.send_header("Connection", "close")
        self.end_headers()

    def _write_plain(self, status, body):

        self.send_response(status)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        # no cache
        self.send_header("Cache-Control", "no-store")
        self.send_header("Connection", "close")
        self.end_headers()
        # only send body if not HEAD request
        if self.command != "HEAD":
            try:
                self.wfile.write(body)
                self.wfile.flush()
            except Exception:
                pass

    def _write_json(self, obj):
        
        # turn object into json text
        text = json.dumps(obj)
        body = text.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("Connection", "close")
        self.end_headers()

        # write body if not HEAD
        try:
            self.wfile.write(body)
            self.wfile.flush()
        except Exception:
            pass

    # TTL = Time To Live
    # counter to stop endless loops = bug safety
    # each forward = ttl - 1
    # if ttl == 0 = give up (error 504)
    # 32 chosen: bigger than log2(N) hops, safe but not too big

    def _ttl(self):
        value = self.headers.get("X-Chord-TTL", str(DEFAULT_TTL))
        try:
            return int(value)
        except:
            return DEFAULT_TTL

    def _forward(self, method, path, body, next_addr, ttl):

        # stop if ttl is 0
        if ttl <= 0:
            self._write_plain(504, b"TTL exceeded")
            return

        conn = None #connection varaible

        try:
            # open connection
            conn = http.client.HTTPConnection(next_addr, timeout=5)

            # build headers
            headers = {}
            headers["Content-Type"] = "text/plain; charset=utf-8"
            headers["X-Chord-TTL"] = str(ttl - 1)
            headers["Connection"] = "close"

            # send request
            if method == "PUT":
                conn.request("PUT", path, body, headers)
            else:
                conn.request(method, path, None, headers)

            # get response
            resp = conn.getresponse()
            data = resp.read()

            # assume plain text
            content_type = "text/plain"

            # check if response gave a type
            for h, v in resp.getheaders():
                if h.lower() == "content-type":
                    content_type = v
                    break

            # send reply back to client
            self.send_response(resp.status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Connection", "close")
            self.end_headers()

            # write body if not HEAD
            if self.command != "HEAD":
                try:
                    self.wfile.write(data)
                    self.wfile.flush()
                except:
                    pass

        except Exception as e: 
            # if failed, send error (502) (stored in var "e")
            msg = "forward error to " + next_addr + ": " + str(e)
            self._write_plain(502, msg.encode("utf-8"))

        finally:
            if conn is not None:
                try:
                    conn.close()
                except:
                    pass



    def do_GET(self):
        # clean path (remove query)
        path = urlsplit(self.path).path

        # ---------- /helloworld 
        if path == "/helloworld":
            text = f"{HOSTNAME}:{PORT}"
            body = text.encode("utf-8")
            length = len(body)

            self._ok_headers(length)

            try:
                self.wfile.write(body)
                self.wfile.flush()
            except Exception:
                pass
            return

        # ---------- /network 
        if path == "/network":
            # ask chord for pred,succ,fingers
            peers = CHORD.network_view()
            self._write_json(peers)
            return

        # ---------- /storage/<key> 
        if path.startswith("/storage/"):
            # cut the key name
            parts = path.split("/storage/", 1)
            key = parts[1]

            # hash key to id
            key_id = hash_to_id(key)

            # if i own this key
            if CHORD.is_responsible(key_id) == True:
                if key in STORE:
                    value = STORE[key]
                    body = value.encode("utf-8")
                    self._write_plain(200, body)
                else:
                    self._write_plain(404, b"")
            else:
                # forward to next hop
                next_addr = CHORD.shortcut_step(key_id)
                self._forward("GET", path, b"", next_addr, self._ttl())
            return

        # ---------- other path 
        self.send_error(404, "not found")


    def do_PUT(self):
        # clean path
        path = urlsplit(self.path).path

        # only allow storage
        if not path.startswith("/storage/"):
            self.send_error(404, "not found")
            return

        # cut key name
        parts = path.split("/storage/", 1)
        key = parts[1]

        # hash to id
        key_id = hash_to_id(key)

        # read content length
        length_str = self.headers.get("Content-Length", "0")
        try:
            length = int(length_str)
        except Exception:
            length = 0

        # read body
        body = b""
        if length > 0:
            body = self.rfile.read(length)

        # if i own this key
        if CHORD.is_responsible(key_id) == True:
            try:
                STORE[key] = body.decode("utf-8")

            except Exception:

                STORE[key] = body.decode("utf-8", errors="replace")
            self._write_plain(200, b"")

        else:
            # forward to next hop
            next_addr = CHORD.shortcut_step(key_id)
            self._forward("PUT", path, body, next_addr, self._ttl())

    def do_HEAD(self):
        # clean path
        path = urlsplit(self.path).path

        if path == "/helloworld":
            text = f"{HOSTNAME}:{PORT}"
            body = text.encode("utf-8")
            length = len(body)

            self._ok_headers(length)
            return

        self.send_error(404, "not found")


    def log_message(self, *_args, **_kwargs) -> None:
        # quiet logs
        return


class ThreadingHTTPServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True          # kill threads when server closes
    allow_reuse_address = True     # faster restart


def main():
    # try to start threaded server
    try:
        httpd = ThreadingHTTPServer(("", PORT), DHTHandler)
    except OSError as e:
        print("[ERROR] cant start server on", PORT, ":", e)
        sys.exit(1)

    # ----------- clean shutdown 
    def _stop(_signum, _frame):
        httpd.shutdown()

    # stop on kill (TERM)
    signal.signal(signal.SIGTERM, _stop)

    # stop on ctrl+c (INT)
    signal.signal(signal.SIGINT, _stop)

    # ----------- auto stop after 15 min 
    timer = threading.Timer(900, httpd.shutdown)
    timer.start()

    # ----------- main loop 
    try:
        httpd.serve_forever()

    finally:
        # always cleanup
        timer.cancel()
        httpd.server_close()


if __name__ == "__main__":
    main()
