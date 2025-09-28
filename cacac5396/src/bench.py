#!/usr/bin/env python3
# bench.py
# measure PUT/GET throughput

import sys
import time
import json
import random
import string
import http.client
import argparse
import os #for csv file

# -------- helpers

def now_s():
    # precise timer in seconds
    # perf_counter gives detailed time
    t = time.perf_counter()
    return t

def rand_text(n):
    # build a random string of length n
    # control the size for PUT
    letters = string.ascii_letters + string.digits
    out = ""
    i = 0
    while i < n:
        ch = random.choice(letters) #create the string
        out = out + ch
        i = i + 1
    return out

def do_put(address, key, value):
    # send PUT /storage/<key> with value to one entry node 
    conn = http.client.HTTPConnection(address, timeout=5) # timeout if nothing answers in 5 seconds (clean connection exit)

    try:
        path = "/storage/" + key 

        headers = {}
        headers["Content-Type"] = "text/plain; charset=utf-8"
        headers["Connection"] = "close"

        body_bytes = value.encode("utf-8") #send plain text 

        conn.request("PUT", path, body=body_bytes, headers=headers)
        resp = conn.getresponse()
        _data = resp.read()  # drain body, stored but not used

        if resp.status == 200:
            return True
        else:
            return False

    except Exception:
        return False

    finally: #alwyas run
        try:
            conn.close()
        except Exception: #ignore errors
            pass

def do_get(address, key):
    # GET /storage/<key> from one entry node
    conn = http.client.HTTPConnection(address, timeout=5)
    try:
        path = "/storage/" + key

        headers = {}
        headers["Connection"] = "close"

        conn.request("GET", path, headers=headers)
        resp = conn.getresponse()
        data = resp.read()

        if resp.status == 200:
            return True, data #read full body into data
        else:
            # 404 = not found
            return False, data

    except Exception:
        return False, b"" #empty bytes

    finally:
        try:
            conn.close()
        except Exception:
            pass

# -------- main

def main():

    # --- arguments
    ap = argparse.ArgumentParser()
    ap.add_argument("nodes", nargs="*", help="entry nodes like MSI:55001 MSI:55002 ... (optional if --peers is used)")
    ap.add_argument("--peers", default="", help="path to a JSON file with a list of nodes (e.g., peers.json)")
    ap.add_argument("--ops", type=int, default=1000, help="ops per run for PUT and GET (default 1000)")
    ap.add_argument("--repeats", type=int, default=5, help="number of runs to repeat (default 5)")
    ap.add_argument("--value-size", type=int, default=100, help="bytes per value (default 100)")
    ap.add_argument("--csv", default="results.csv", help="output CSV file")
    args = ap.parse_args()

    # --- build nodes list: --peers file is better
    nodes = []
    if args.peers != "":
        try:
            f = open(args.peers, "r", encoding="utf-8")
            text = f.read()
            f.close()
            data = json.loads(text)           # expects ["HOST:PORT","HOST:PORT"..] from json
            i = 0
            while i < len(data):
                nodes.append(str(data[i]))
                i = i + 1
        except Exception:
            print("[error] cannot read peers file: " + args.peers)
            sys.exit(1)
    else:
        i = 0
        while i < len(args.nodes):
            nodes.append(args.nodes[i])
            i = i + 1

    if len(nodes) == 0:
        print("[error] no nodes provided (use --peers peers.json or list nodes on the command line)")
        sys.exit(1)


    n_nodes = len(nodes) #  how many nodes are there

    print("[info] nodes: " + str(nodes)) #safety check
    print("[info] ops per run: " + str(args.ops) + ", repeats: " + str(args.repeats) + ", value_size: " + str(args.value_size))

    if os.path.exists(args.csv) == False: #update or create a csv file with header
        try:
            f = open(args.csv, "w", encoding="utf-8")
            f.write("n_nodes,op,run_idx,count,duration_s,ops_per_s\n")
            f.close()
        except Exception:
            print("[error] cannot open csv file for write: " + args.csv)
            sys.exit(1)

    run_idx = 0 #loop for each run
    while run_idx < args.repeats: #   counts which run

        # ----- build keys and one value for this run

        keys = []
        i = 0
        while i < args.ops:
            # build a list of keys for this run 
            key = "k" + str(run_idx) + "_" + str(i)
            keys.append(key)
            i = i + 1
        # all use the same random value string of length value_size
        value = rand_text(args.value_size)
        #random strings here because for benchmarking we only care about size
        # and speed, not the actual content


        # ----- PUT phase
        t0 = now_s() #start timer
        ok_put = 0

        i = 0
        while i < len(keys): #loop over the keys
            k = keys[i]
            addr = random.choice(nodes)  #pick a random node from nodes to contact
            ok = do_put(addr, k, value)
            if ok == True:
                ok_put = ok_put + 1 #count the successs
            i = i + 1

        t1 = now_s() #stop timer
        dt_put = t1 - t0 #timing saved

        if dt_put > 0:
            ops_per_s_put = ok_put / dt_put #calc per second
        else:
            ops_per_s_put = 0.0

        print("[run " + str(run_idx) + "] PUT: " + str(ok_put) + "/" + str(args.ops) +
              " in " + format(dt_put, ".3f") + "s = " + format(ops_per_s_put, ".1f") + " ops/s")

        try: #append in csv
            f = open(args.csv, "a", encoding="utf-8")
            line = str(n_nodes) + ",PUT," + str(run_idx) + "," + str(ok_put) + "," + format(dt_put, ".6f") + "," + format(ops_per_s_put, ".3f") + "\n"
            f.write(line)
            f.close()
        except Exception:
            print("[error] cannot append csv (PUT)")

        # ----- GET phase
        #same as PUT but each key
        t0 = now_s()
        ok_get = 0

        i = 0
        while i < len(keys):
            k = keys[i]
            addr = random.choice(nodes)
            ok, data = do_get(addr, k)
            if ok == True:
                ok_get = ok_get + 1
            i = i + 1

        t1 = now_s()
        dt_get = t1 - t0

        if dt_get > 0:
            ops_per_s_get = ok_get / dt_get
        else:
            ops_per_s_get = 0.0

        print("[run " + str(run_idx) + "] GET: " + str(ok_get) + "/" + str(args.ops) +
              " in " + format(dt_get, ".3f") + "s = " + format(ops_per_s_get, ".1f") + " ops/s")

        try:
            f = open(args.csv, "a", encoding="utf-8")
            line = str(n_nodes) + ",GET," + str(run_idx) + "," + str(ok_get) + "," + format(dt_get, ".6f") + "," + format(ops_per_s_get, ".3f") + "\n"
            f.write(line)
            f.close()
        except Exception:
            print("[error] cannot append csv (GET)")

        run_idx = run_idx + 1

    print("[done] wrote " + args.csv)

if __name__ == "__main__":
    main()
