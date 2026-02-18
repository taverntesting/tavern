#!/usr/bin/env python3

import re
import subprocess


def get_tags():
    """Get git tags sorted by creator date, filtered to exclude certain patterns."""
    result = subprocess.run(
        ["git", "tag", "--sort=creatordate"], capture_output=True, text=True, check=True
    )
    tags = result.stdout.strip().split("\n")
    # Filter out prerelease tags according to PEP 440
    # Matches versions with a/alpha, b/beta, or rc suffixes
    return [
        tag
        for tag in tags
        if not re.search(r"(a|alpha|b|beta|rc)\d*$", tag, re.IGNORECASE)
    ]


def get_tag_date(tag):
    """Get the date of a tag."""
    result = subprocess.run(
        ["git", "log", "-1", "--pretty=format:%ad", "--date=short", tag],
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()


def get_tag_name(tag):
    """Get tag name with message."""
    result = subprocess.run(
        ["git", "tag", "-n1", tag], capture_output=True, text=True, check=True
    )
    return result.stdout.strip()


def get_tag_content(tag):
    """Get tag content (excluding first line)."""
    result = subprocess.run(
        ["git", "tag", "-n9", tag], capture_output=True, text=True, check=True
    )
    lines = result.stdout.strip().split("\n")
    if len(lines) > 1:
        content = "\n".join(lines[1:])
        # Remove leading whitespace from each line
        return "\n".join(line.lstrip() for line in content.split("\n"))
    return ""


def print_changelog():
    """Generate changelog content."""
    tags = get_tags()

    # Reverse to put oldest at bottom
    tags.reverse()

    output = ["# Changelog", ""]

    for current_tag in tags:
        tag_date = get_tag_date(current_tag)

        # Determine header level - minor releases (patch == 0) get '#', patch releases get '##'
        hashes = "##"
        parts = current_tag.split(".")
        if len(parts) >= 3 and parts[2] == "0":
            hashes = "#"

        tag_name = get_tag_name(current_tag)
        output.append(f"{hashes} {tag_name} ({tag_date})")

        tag_content = get_tag_content(current_tag)
        if tag_content:
            output.append("")
            output.append(tag_content)

        output.append("")

    return "\n".join(output)


if __name__ == "__main__":
    changelog = print_changelog()
    with open("CHANGELOG.md", "w") as f:
        f.write(changelog)
