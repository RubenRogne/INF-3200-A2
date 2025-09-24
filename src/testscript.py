import requests
import sys
import json

addresses = json.loads(sys.argv[1])

failed = False

for address in addresses:
    try:
        response = requests.get(f"http://{address}/helloworld")
        print(f'received "{response.text}"')
        if response.text != address:
            failed = True
        response = requests.get(f"http://{address}/storage/1")
        print(f'received "{response.text}"')
        response = requests.get(f"http://{address}/storage/2")
        print(f'received "{response.text}"')
        response = requests.get(f"http://{address}/network")
        print(f'received "{response.text}"')
    except Exception as e:
        print(f"\nRequest to {address} failed: {e}\n")
        failed = True

if failed:
    print("Failure")
else:
    print("Success!")