import yaml
from coreapi import Client
import openapi_codec

client = Client()
json_path = "https://raw.githubusercontent.com/OAI/OpenAPI-Specification/master/examples/v2.0/json/petstore-simple.json"
d = client.get(json_path, format="openapi")

test_dict = {}
for test_name in d.links.keys():
    test_dict["test_name"] = test_name

    request = {
        "url": d.links[test_name].url,
        "method": str.upper(d.links[test_name].action),
    }

    response = {"strict": False, "status_code": 200}
    inner_dict = {"name": test_name, "request": request, "response": response}

    test_dict["stages"] = [inner_dict]
    print(test_dict)
    print(yaml.dump(test_dict, explicit_start=True, default_flow_style=False))
