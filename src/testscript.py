import requests
import sys
import json

addresses = json.loads(sys.argv[1])

failed = False
print(f"{addresses[-1]}")
print("http://"+addresses[0]+"/helloworld")
print(f"http://{addresses[0]}/helloworld")
node = requests.get("http://"+addresses[0]+"/follower/"+addresses[-1])
print(node.text)
for address in addresses:
    try:
        print("new set of addresses")
        response = requests.get(f"http://{address}/helloworld")
        print(f'received "{response.text}"')
        if response.text != address:
            failed = True
        requests.put(f"http://{address}/storage/3", data="3")
        print(f'received "{response.text}" attempted a put')
        response = requests.get(f"http://{address}/storage/1")
        print(f'received "{response.text}" should be 1')
        response = requests.get(f"http://{address}/storage/2")
        print(f'received "{response.text}" should be False')
        response = requests.get(f"http://{address}/storage/3")
        print(f'received "{response.text}" should be 3')
        response = requests.get(f"http://{address}/network")
        print(f'received "{response.text}" should be the network')
    except Exception as e:
        print(f"\nRequest to {address} failed: {e}\n")
        failed = True

if failed:
    print("Failure")
else:
    print("Success!")