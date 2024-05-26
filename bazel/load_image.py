import json
import os
import sys
import tempfile
import zipfile

import docker

if __name__ == "__main__":
    repo_tags = []

    client = docker.from_env()
    for image_name in sys.argv[2:]:
        with tempfile.NamedTemporaryFile(suffix=".tar") as tmp_file:
            with zipfile.ZipFile(tmp_file, mode="w") as zip_file:
                for root, _, files in os.walk(image_name):
                    for file in files:
                        zip_file.write(os.path.join(root, file))
        images = client.images.load(tmp_file.name)
        repo_tags += [image.attrs["RepoTags"] for image in images]

    with open(sys.argv[1], "w") as image_names_output:
        json.dump(repo_tags, image_names_output)
