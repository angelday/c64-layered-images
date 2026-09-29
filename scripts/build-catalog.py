#!/usr/bin/env python3
"""Print the collection catalog as JSON.

Reads every images/<id>/manifest.json, dates each image by the commit that
first put it on the main line, and prints one catalog, newest image first.
Preview paths are relative to the repository root, where the previews
already are, so nothing is copied and nothing is written.

The catalog is data, not a page. Whoever presents the collection - the C64
Graphics Explorer website builds its gallery from it - renders it in their
own design, and the collection stays the single source it is built from.

Standard library only, so it runs unchanged on a Mac and on a CI runner.
Publish dates come from git history, so a shallow clone is refused rather
than silently dating everything to the clone's first commit.

Usage:
  python3 scripts/build-catalog.py > catalog.json
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REPOSITORY_URL = "https://github.com/angelday/c64-layered-images"
BRANCH = "main"
OPEN_URL = "c64ge://layered?id={id}"

# Same thresholds as C64 Graphics Explorer's C64ArtworkGeometry: two screens
# across or down, allowing for border.
MULTISCREEN_WIDTH = 640
MULTISCREEN_HEIGHT = 400

FOLDER_NAME = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
UNPUBLISHED = datetime.max.replace(tzinfo=timezone.utc)


def jpeg_size(path: Path) -> tuple[int, int]:
    data = path.read_bytes()
    index = 2
    while index + 9 < len(data):
        if data[index] != 0xFF:
            index += 1
            continue
        marker = data[index + 1]
        if marker == 0xFF or marker in (0x01, 0xD8) or 0xD0 <= marker <= 0xD7:
            index += 1 if marker == 0xFF else 2
            continue
        length = int.from_bytes(data[index + 2:index + 4], "big")
        if marker in (0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7,
                      0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF):
            height = int.from_bytes(data[index + 5:index + 7], "big")
            width = int.from_bytes(data[index + 7:index + 9], "big")
            return width, height
        index += 2 + length
    raise ValueError(f"{path}: no JPEG frame header")


def png_size(path: Path) -> tuple[int, int]:
    data = path.read_bytes()[:24]
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError(f"{path}: not a PNG")
    return int.from_bytes(data[16:20], "big"), int.from_bytes(data[20:24], "big")


def git(*arguments: str) -> str:
    return subprocess.run(["git", *arguments], cwd=ROOT, capture_output=True,
                          text=True, check=True).stdout


def published_at(image_id: str) -> datetime | None:
    """When the image's manifest first appeared on the main line.

    First-parent history with merges diffed against their first parent, so an
    image that arrived through a pull request dates from the merge, not from
    whenever the contributor happened to write the commit. None for a folder
    that is not committed yet, which sorts it to the top as unpublished.
    """
    # --no-patch because --diff-merges turns on diff output, which would
    # otherwise follow each date.
    stamps = git("log", "--first-parent", "--diff-merges=first-parent",
                 "--diff-filter=A", "--no-patch", "--format=%cI", "--",
                 f"images/{image_id}/manifest.json").split()
    if not stamps:
        return None
    return datetime.fromisoformat(stamps[-1]).astimezone(timezone.utc)


def base_artwork_file(manifest: dict) -> str:
    layers = manifest.get("layers")
    if not layers:
        return manifest.get("image", "artwork.png")
    first = layers[0]
    if first.get("file"):
        return first["file"]
    frame = first["animation"]["frames"][0]
    return frame if isinstance(frame, str) else frame["file"]


def describe(folder: Path) -> dict:
    image_id = folder.name
    manifest = json.loads((folder / "manifest.json").read_text(encoding="utf-8"))
    layers = manifest.get("layers") or []
    roles = {layer.get("role", "data") for layer in layers}

    preview_width, preview_height = jpeg_size(folder / "preview.jpg")
    base_width, base_height = png_size(folder / base_artwork_file(manifest))

    csdb = manifest.get("csdb")
    if csdb and not csdb.startswith("https://"):
        csdb = None

    return {
        "id": image_id,
        "name": manifest["name"],
        "author": manifest["author"],
        "released": manifest.get("released"),
        "csdb": csdb,
        "published": published_at(image_id),
        "preview": {
            "path": f"images/{image_id}/preview.jpg",
            "width": preview_width,
            "height": preview_height,
        },
        "layers": len(layers),
        "sprites": "sprite" in roles or bool(manifest.get("hasSprites")),
        "interlaced": bool(roles & {"phaseA", "phaseB"}),
        "animated": any("animation" in layer for layer in layers),
        "multiscreen": base_width >= MULTISCREEN_WIDTH or base_height >= MULTISCREEN_HEIGHT,
        "open": OPEN_URL.format(id=image_id),
        "folder": f"{REPOSITORY_URL}/tree/{BRANCH}/images/{image_id}",
    }


def newest_first(images: list[dict]) -> list[dict]:
    """Newest publish first. Images published together - the initial import
    put most of them in one commit - fall back to newest release, then title."""
    images = sorted(images, key=lambda image: image["name"].lower())
    images.sort(key=lambda image: image["released"] or 0, reverse=True)
    images.sort(key=lambda image: image["published"] or UNPUBLISHED, reverse=True)
    return images


def timestamp(moment: datetime | None) -> str | None:
    return moment.strftime("%Y-%m-%dT%H:%M:%SZ") if moment else None


def main() -> int:
    argparse.ArgumentParser(description=__doc__.splitlines()[0]).parse_args()

    if git("rev-parse", "--is-shallow-repository").strip() == "true":
        print("error: publish dates need full history; fetch with depth 0", file=sys.stderr)
        return 1

    folders = sorted(path.parent for path in (ROOT / "images").glob("*/manifest.json"))
    images = []
    for folder in folders:
        if not FOLDER_NAME.match(folder.name):
            print(f"error: {folder.name}: folder name is not lowercase kebab-case", file=sys.stderr)
            return 1
        images.append(describe(folder))
    images = newest_first(images)

    # Numbered in publishing order, so the first image published is 1 and a
    # new one takes the next number without renumbering the rest.
    for index, image in enumerate(images):
        image["number"] = len(images) - index
        image["published"] = timestamp(image["published"])

    catalog = {
        "generated": timestamp(datetime.now(timezone.utc)),
        "repository": REPOSITORY_URL,
        "images": images,
    }
    sys.stdout.write(json.dumps(catalog, indent=2, ensure_ascii=False) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
