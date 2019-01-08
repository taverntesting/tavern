import yaml
from coreapi import Client
import openapi_codec
import sys


def generate_tavern_yaml(json_path):
    client = Client()
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


def display_help():
    print("pub_tavern.py <url to openapi.json>")
    print(
        "eg: pub_tavern.py https://raw.githubusercontent.com/OAI/OpenAPI-Specification/master/examples/v2.0/json/petstore-simple.json"
    )
    exit(-1)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        display_help()
    generate_tavern_yaml(sys.argv[1])
