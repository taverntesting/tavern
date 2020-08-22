import re

import more_itertools
import sys


def strip_generated_names(name):
    regex = re.compile(r"(.+?)\[.*")
    match = regex.match(name)
    if match:
        return match.group(1)
    else:
        return name


def split():
    all_tests = sys.stdin.readlines()
    has_colon = re.compile(r"::")
    all_tests = filter(lambda x: has_colon.search(x), all_tests)
    all_tests = map(lambda x: strip_generated_names(x), all_tests)
    unique = more_itertools.unique_everseen(all_tests, strip_generated_names)

    for t in unique:
        print(t.strip())


if __name__ == "__main__":
    split()
