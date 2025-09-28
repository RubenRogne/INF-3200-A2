# How to Use This Code (Chord DHT)

This project is a Chord Distributed Hash Table (DHT)  
You can start multiple servers across IFI compute nodes, store and get values with keys, and measure performance

---

## Files

- server.py  
  Runs one DHT server. Each server knows about the ring, stores keys, or forwards requests.  
  You normally don’t start this by hand; run.sh does it for you

- chord.py  
  The math and routing logic (hashing, finger tables, finding who owns a key).  
  Used inside server.py, not run directly

- bench.py  
    Benchmark client. It generates random keys and a random value string, then:  
    Sends N PUT requests to random nodes
    Sends N GET requests for those same keys from random nodes
    Measures how long it took and how many operations per second
    Saves results to results.csv
    This shows how throughput and latency change when more nodes are added.

- chord-tester.py  
  Correctness checker 
  Stores and fetches keys, including across different nodes, and checks /network

- run-tester.py  
  Very simple check: calls /helloworld on each node to confirm it replies with its address

- run.sh  
  Main cluster script. Automates everything:
   Picks compute nodes from /share/ifi/available-nodes.sh.   (Skips frontend c0-0 because it’s weak)  
   Picks random free ports.  
  Creates peers.json with all node addresses.  
  Starts server.py on each compute node with SSH.  
  Waits until each server is listening.  
  Runs chord-tester.py, run-tester.py, and/or bench.py depending on mode.  
  Kills servers at the end if you use --kill.  
  Logs from each remote server go to /tmp/inf3200_a2_${USER}_${node}_${port}.log on that node.

---

## Running on the Cluster with run.sh

First make it executable:
chmod +x run.sh

### Start servers, test, and benchmark
./run.sh 4 --all --kill

This starts 4 servers on 4 compute nodes, runs correctness tests, runs the benchmark, and then kills the servers.

### Only benchmark
./run.sh 8 --bench --kill --ops 2000 --repeats 3 --value-size 256

This starts 8 servers, skips the testers, runs bench.py with 2000 operations per run, repeated 3 times, payload size 256 bytes, then kills the servers

### Only test
./run.sh 4 --test --kill

Runs chord-tester and run-tester on 4 servers, no benchmarking

### Kill everything from old runs
./run.sh --killall

This stops any leftover server.py processes across all compute nodes

----

## What the Benchmark Measures

bench.py measures how fast the system can handle PUT and GET requests

For each run:
- It generates 1000 random keys (default)
- It picks one random string value of  size
- It sends a PUT for each key to a random node
- It measures how many succeeded and how long it took
- It then does the same with GET requests for the same keys

Results go into results.csv


