#!/usr/bin/env python3

import argparse
import http.client
import json
import random
import textwrap
import uuid

def arg_parser():
    parser = argparse.ArgumentParser(prog="client", description="DHT client")

    parser.add_argument("nodes", type=str, nargs="+",
            help="addresses (host:port) of nodes to test")

    return parser

class Lorem(object):
    """ Generates lorem ipsum placeholder text"""

    sample = """
        Lorem ipsum dolor sit amet, consectetur adipiscing elit, sed do eiusmod
        tempor incididunt ut labore et dolore magna aliqua. Ut enim ad minim
        veniam, quis nostrud exercitation ullamco laboris nisi ut aliquip ex ea
        commodo consequat. Duis aute irure dolor in reprehenderit in voluptate
        velit esse cillum dolore eu fugiat nulla pariatur. Excepteur sint occaecat
        cupidatat non proident, sunt in culpa qui officia deserunt mollit anim id
        est laborum.
        """

    def __init__(self):
        # Lowercase words and strip leading/trailing whitespace
        s = self.sample.lower().strip()
        # Filter out punctuation and other non-alpha non-space characters
        s = filter(lambda c: c.isalpha() or c.isspace(), s)
        # Collect filtered letters back into a string, then split into words
        s = ''.join(s).split()
        # Collapse into a set to dedupe words, then turn back into a list
        self.word_list = sorted(list(set(s)))

        self.min_words = 5
        self.max_words = 20

        self.min_sentences = 3
        self.max_sentences = 6

        self.min_paras = 1
        self.max_paras = 5

    def sentence(self):
        nwords = random.randrange(self.min_words, self.max_words)
        rand_words = [random.choice(self.word_list) for _ in range(0, nwords)]
        rand_words[0] = rand_words[0].capitalize()
        return " ".join(rand_words) + "."

    def paragraph(self):
        nsens = random.randrange(self.min_sentences, self.max_sentences)
        rand_sens = [self.sentence() for _ in range(0, nsens)]
        return textwrap.fill(" ".join(rand_sens))

    def text(self):
        nparas = random.randrange(self.min_paras, self.max_paras)
        rand_paras = [self.paragraph() for _ in range(0, nparas)]
        return "\n\n".join(rand_paras)

lorem = Lorem()

def generate_pairs(count):
    pairs = {}
    for x in range(0, count):
        key = str(uuid.uuid4())
        value = lorem.text()
        pairs[key] = value
    return pairs

def put_value(node, key, value):
    conn = None
    try:
        conn = http.client.HTTPConnection(node)
        conn.request("PUT", "/storage/"+key, value)
        conn.getresponse()
    finally:
        if conn:
            conn.close()

def get_value_raw(node, key):
    conn = None
    try:
        # Make request
        conn = http.client.HTTPConnection(node)
        conn.request("GET", "/storage/"+key)
        resp = conn.getresponse()
        status = resp.status
        headers = resp.getheaders()
        value = resp.read()

        # Extract headers
        contenttype = "text/plain"
        for h, hv in headers:
            if h.lower() == "Content-type".lower():
                contenttype = hv

        # Decode value, if text
        if contenttype == "text/plain":
            value = value.decode("utf-8")
        elif contenttype.startswith("text/plain"):
            # TODO: check charset
            value = value.decode("utf-8")

        return status, value, contenttype
    finally:
        if conn:
            conn.close()

def get_value(node, key):
    status, value, contenttype = get_value_raw(node, key)

    if status != 200:
        value = None

    return value

def get_neighbours(node):
    conn = http.client.HTTPConnection(node)
    conn.request("GET", "/network")
    resp = conn.getresponse()
    if resp.status != 200:
        neighbors = []
    else:
        body = resp.read()
        neighbors = json.loads(body)
    conn.close()
    return neighbors

def walk_neighbours(start_nodes):
    to_visit = start_nodes
    visited = set()
    while to_visit:
        next_node = to_visit.pop()
        visited.add(next_node)
        neighbors = get_neighbours(next_node)
        for neighbor in neighbors:
            if neighbor not in visited:
                to_visit.append(neighbor)
    return visited

def simple_check(nodes):
    print("Simple put/get check, retreiving from same node ...")

    tries = 10
    pairs = generate_pairs(tries)

    successes = 0
    node_index = 0
    for key, value in pairs.items():
        node = nodes[node_index]
        node_index = (node_index+1) % len(nodes)

        try:
            put_value(node, key, value)
        except Exception as e:
            print("PUT/GET to {}: EXCEPTION DURING PUT: {}".format(node, e))
            continue

        try:
            status, returned, contenttype = get_value_raw(node, key)
        except Exception as e:
            print("PUT/GET to {}: EXCEPTION DURING GET: {}".format(node, e))
            continue

        if status in range(200,300) and returned == value:
            successes+=1
        elif not contenttype.startswith("text/plain"):
            print("PUT/GET to {}: UNEXPECTED CONTENT TYPE: {}".format(node, contenttype))
        elif status in range(200,300) and returned != value:
            print("=========================")
            print("PUT/GET to {}: VALUE MISMATCH".format(node))
            print("EXPECTED:\n{}\n".format(value))
            print("RECIEVED:\n{}\n".format(returned))
            print()
        else:
            print("PUT/GET to {}: GET STATUS {}".format(node, status))

    success_percent = float(successes) / float(tries) * 100
    print("Stored and retrieved %d of %d pairs (%.1f%%)" % (
            successes, tries, success_percent ))


def retrieve_from_different_nodes(nodes):
    print("Retrieving from different nodes ...")

    tries = 10
    pairs = generate_pairs(tries)

    successes = 0
    for key, value in pairs.items():
        put_node = random.choice(nodes)
        get_node = random.choice(nodes)

        try:
            put_value(put_node, key, value)
        except Exception as e:
            print("PUT/GET to {} / {}: EXCEPTION DURING PUT: {}".format(put_node, get_node, e))
            continue
        try:
            status, returned, contenttype = get_value_raw(get_node, key)
        except Exception as e:
            print("PUT/GET to {} / {}: EXCEPTION DURING GET: {}".format(put_node, get_node, e))
            continue

        if status in range(200,300) and returned == value:
            successes+=1
        elif not contenttype.startswith("text/plain"):
            print("PUT/GET to {} / {}: UNEXPECTED CONTENT TYPE: {}".format(put_node, get_node, contenttype))
        elif status in range(200,300) and returned != value:
            print("PUT/GET to {} / {}: VALUE MISMATCH".format(put_node, get_node))
        else:
            print("PUT/GET to {} / {}: GET STATUS {}".format(put_node, get_node, status))

    success_percent = float(successes) / float(tries) * 100
    print("Stored and retrieved %d of %d pairs (%.1f%%)" % (
            successes, tries, success_percent ))

def get_nonexistent_key(nodes):
    print("Retrieving a nonexistent key ...")

    key = str(uuid.uuid4())
    node = random.choice(nodes)
    print("%s -- GET /%s" % (node, key))
    try:
        conn = http.client.HTTPConnection(node)
        conn.request("GET", "/storage/"+key)
        resp = conn.getresponse()
        value = resp.read().strip()
        conn.close()
        print("Status: %s (expected 404)" % resp.status)
        print("Data  : %s" % value)
    except Exception as e:
        print("GET failed with exception:")
        print(e)

def main(args):

    nodes = set(args.nodes)
    nodes |= walk_neighbours(args.nodes)
    nodes = list(nodes)
    print("%d nodes registered: %s" % (len(nodes), ", ".join(nodes)))

    if len(nodes)==0:
        raise RuntimeError("No nodes registered to connect to")

    print()

    simple_check(nodes)
    print()

    retrieve_from_different_nodes(nodes)
    print()

    get_nonexistent_key(nodes)
    print()

if __name__ == "__main__":

    parser = arg_parser()
    args = parser.parse_args()
    main(args)
