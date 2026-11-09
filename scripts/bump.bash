#!/usr/bin/env bash

# Bump the project version, update the changelog, and create the release commit
# and annotated tag. Replaces tbump - the version lives only in the 'version'
# key of pyproject.toml, and 'uv version' is what updates it (and re-locks).
#
# Usage:
#   ./scripts/bump.bash <new-version> --tag-message "<message>" [--push]
#
# <new-version> is anything 'uv version' accepts as a value, eg '4.0.0rc1'.
# The tag message is required: CHANGELOG.md is generated from the messages of
# annotated tags by scripts/update_changelog.py.

set -eu

cd "$(dirname "$0")/.."

usage() {
    echo "usage: $0 <new-version> --tag-message \"<message>\" [--push]" >&2
    exit 2
}

new_version=""
tag_message=""
push=0

while [ $# -gt 0 ]; do
    case "$1" in
        --tag-message)
            [ $# -ge 2 ] || usage
            tag_message="$2"
            shift 2
            ;;
        --tag-message=*)
            tag_message="${1#--tag-message=}"
            shift
            ;;
        --push)
            push=1
            shift
            ;;
        -h | --help)
            usage
            ;;
        -*)
            echo "unknown option: $1" >&2
            usage
            ;;
        *)
            [ -z "$new_version" ] || usage
            new_version="$1"
            shift
            ;;
    esac
done

[ -n "$new_version" ] || usage
[ -n "$tag_message" ] || usage

if [ -n "$(git status --porcelain)" ]; then
    echo "working tree is not clean, refusing to bump" >&2
    exit 1
fi

if git rev-parse -q --verify "refs/tags/$new_version" >/dev/null; then
    echo "tag $new_version already exists" >&2
    exit 1
fi

set -x

# Updates 'version' in pyproject.toml and re-locks
uv version "$new_version"
version=$(uv version --short)

git commit --all --message "Bump to $version"
git tag --annotate "$version" --message "$tag_message"

# The changelog is built from the tags, so it can only be generated once the new
# tag exists - regenerate it and fold it into the release commit
./scripts/update_changelog.py
git commit --all --amend --no-edit
git tag --force --annotate "$version" --message "$tag_message"

set +x

if [ "$push" -eq 1 ]; then
    git push
    git push origin "refs/tags/$version"
else
    echo
    echo "Created release commit and tag $version. To push:"
    echo "  git push && git push origin refs/tags/$version"
fi
