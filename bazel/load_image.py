import json

import docker
import sys

if __name__ == "__main__":
    repo_tags = []

    client = docker.from_env()
    for image_name in sys.argv[2:]:
        with open(
            image_name,
            "rb",
        ) as docker_image_tar:
            images = client.images.load(docker_image_tar)
            repo_tags += [image.attrs["RepoTags"] for image in images]

    with open(sys.argv[1], "w") as image_names_output:
        json.dump(repo_tags, image_names_output)
