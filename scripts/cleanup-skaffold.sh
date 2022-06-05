#!/usr/bin/env bash

set -ex
command -v parallel

docker network ls -q --filter 'name=skaffold-network-.*' | parallel 'docker network rm {}'
docker ps -qa --filter 'name=tavern-.*' | parallel 'docker rm -f {}'
