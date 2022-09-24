import json

import docker
import sys

if __name__ == '__main__':
    client = docker.from_env()
    with open(sys.argv[1], "rb", ) as docker_image_tar:
        images = client.images.load(docker_image_tar)

    with open(sys.argv[2], "w") as image_names_output:
        json.dump(images[0].attrs["RepoTags"], image_names_output)
