#!/usr/bin/env python3
"""Merge country source XMLTV guides and publish country + combined feeds."""
from __future__ import annotations

import gzip
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parent
WORK = ROOT / "epg-source" / "work"

COUNTRIES = {
    "au": ["abc.net.au", "foxtel.com.au", "foxsports.com.au"],
    "nz": ["sky.co.nz"],
    "ca": ["watch.sportsnet.ca"],
    "us": ["tvtv.us"],
}

def open_xml(path: Path):
    if path.suffix == ".gz":
        return gzip.open(path, "rb")
    return path.open("rb")

def read_guide(path: Path):
    with open_xml(path) as source:
        return ET.parse(source).getroot()

def merge_guides(paths: list[Path]) -> ET.Element:
    root = ET.Element("tv", {"generator-info-name": "IncyZ TV Guide"})
    seen_channels = set()
    seen_programmes = set()
    channel_count = 0
    programme_count = 0

    for path in paths:
        if not path.exists() or path.stat().st_size == 0:
            raise RuntimeError(f"Missing or empty guide: {path}")
        source_root = read_guide(path)
        for channel in source_root.findall("channel"):
            channel_id = channel.get("id")
            if not channel_id or channel_id in seen_channels:
                continue
            seen_channels.add(channel_id)
            root.append(channel)
            channel_count += 1

        for programme in source_root.findall("programme"):
            key = (
                programme.get("channel"),
                programme.get("start"),
                programme.get("stop"),
                (programme.findtext("title") or "").strip(),
            )
            if key in seen_programmes:
                continue
            seen_programmes.add(key)
            root.append(programme)
            programme_count += 1

    if channel_count == 0 or programme_count == 0:
        raise RuntimeError(f"Guide has no usable data: {channel_count} channels, {programme_count} programmes")
    return root

def save_guide(root: ET.Element, xml_path: Path, gzip_path: Path | None = None):
    tree = ET.ElementTree(root)
    ET.indent(tree, space="  ")
    tree.write(xml_path, encoding="utf-8", xml_declaration=True)
    if gzip_path:
        with xml_path.open("rb") as source, gzip.open(gzip_path, "wb", compresslevel=9) as target:
            target.write(source.read())

def main():
    for country, sites in COUNTRIES.items():
        paths = [WORK / f"{site}.xml" for site in sites]
        root = merge_guides(paths)
        xml_path = ROOT / f"{country}.xml"
        gz_path = ROOT / f"{country}.xml.gz"
        save_guide(root, xml_path, gz_path)
        print(f"{country.upper()}: {len(root.findall('channel'))} channels, {len(root.findall('programme'))} programmes")

    # Keep the existing Ireland and Ukraine feeds as inputs; do not modify them.
    combined_inputs = [
        ROOT / "ie.xml",
        ROOT / "ua.xml.gz",
        ROOT / "au.xml.gz",
        ROOT / "nz.xml.gz",
        ROOT / "ca.xml.gz",
        ROOT / "us.xml.gz",
    ]
    combined = merge_guides(combined_inputs)
    save_guide(combined, ROOT / "combined.xml", ROOT / "combined.xml.gz")
    print(f"COMBINED: {len(combined.findall('channel'))} channels, {len(combined.findall('programme'))} programmes")

if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise
