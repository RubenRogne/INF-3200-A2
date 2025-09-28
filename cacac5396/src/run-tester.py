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
            if response.text.replace(".ifi.uit.no", "") != address:
                failed = True
    except Exception as e:
        print(f"\nRequest to {address} failed: {e}\n")
        failed = True

if failed:
    print("Failure")
else:
    print("Success!")