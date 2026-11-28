#!/usr/bin/env python3
"""Split the North American TV Passport grabs into country feeds and publish a combined XMLTV feed."""
from __future__ import annotations
import gzip
import os
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parent
WORK = ROOT / "epg-source" / "work"
COUNTRY_RE = re.compile(r"\.(ca|us)(?=@|$)", re.I)

def read_root(path: Path) -> ET.Element:
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rb") as f:
        return ET.parse(f).getroot()

def country_of(channel_id: str | None) -> str | None:
    if not channel_id:
        return None
    match = COUNTRY_RE.search(channel_id)
    return match.group(1).lower() if match else None

def merge(paths: list[Path], only_country: str | None = None) -> ET.Element:
    channels: dict[str, ET.Element] = {}
    programmes: dict[tuple, ET.Element] = {}
    for path in paths:
        if not path.exists() or path.stat().st_size == 0:
            raise RuntimeError(f"Required source missing or empty: {path}")
        root = read_root(path)
        for channel in root.findall("channel"):
            cid = channel.get("id")
            if not cid or (only_country and country_of(cid) != only_country):
                continue
            channels.setdefault(cid, channel)
        for p in root.findall("programme"):
            cid = p.get("channel")
            if not cid or (only_country and country_of(cid) != only_country):
                continue
            key = (cid, p.get("start"), p.get("stop"), (p.findtext("title") or "").strip())
            programmes.setdefault(key, p)
    if not channels or not programmes:
        raise RuntimeError(f"No usable data in {only_country or 'merged'} guide: {len(channels)} channels, {len(programmes)} programmes")
    # XMLTV convention: channel declarations precede programme records.
    out = ET.Element("tv", {"generator-info-name": "IncyZ TV Guide"})
    out.extend(channels.values())
    out.extend(programmes.values())
    return out

def counts(root: ET.Element) -> tuple[int, int]:
    return len(root.findall("channel")), len(root.findall("programme"))

def write_pair(root: ET.Element, stem: str) -> tuple[Path, Path]:
    xml_tmp = ROOT / f"{stem}.xml.tmp"
    gz_tmp = ROOT / f"{stem}.xml.gz.tmp"
    tree = ET.ElementTree(root)
    ET.indent(tree, space="  ")
    tree.write(xml_tmp, encoding="utf-8", xml_declaration=True)
    with open(xml_tmp, "rb") as src, gzip.open(gz_tmp, "wb", compresslevel=9) as dst:
        dst.write(src.read())
    return xml_tmp, gz_tmp

def promote(pair: tuple[Path, Path], stem: str) -> None:
    pair[0].replace(ROOT / f"{stem}.xml")
    pair[1].replace(ROOT / f"{stem}.xml.gz")

def main() -> None:
    na_main = WORK / "north-america.xml"
    na_extra = WORK / "north-america-extra.xml"
    # The source configs have IDs ending in .ca/.us or .ca@region/.us@region.
    # The extra list deliberately adds more provider IDs and is merged before splitting.
    for country, minimum_channels, minimum_programmes in (
        ("ca", 30, 500), ("us", 100, 1000)
    ):
        result = merge([na_main, na_extra], only_country=country)
        ch, pr = counts(result)
        print(f"{country.upper()}: {ch} channels, {pr} programmes")
        if ch < minimum_channels or pr < minimum_programmes:
            raise RuntimeError(f"{country.upper()} coverage below safety threshold ({minimum_channels} channels / {minimum_programmes} programmes)")
        pair = write_pair(result, country)
        promote(pair, country)

    for country, source_paths, min_channels, min_programmes in (
        (
            "au",
            [
                WORK / "abc.net.au.xml",
                WORK / "foxtel.com.au.xml",
                WORK / "foxsports.com.au.xml",
                WORK / "eurotrasz-au.xml",
            ],
            1,
            50,
        ),
        ("nz", [WORK / "sky.co.nz.xml"], 1, 50),
    ):
        result = merge(source_paths)
        ch, pr = counts(result)
        print(f"{country.upper()}: {ch} channels, {pr} programmes")
        if ch < min_channels or pr < min_programmes:
            raise RuntimeError(f"{country.upper()} coverage below safety threshold")
        pair = write_pair(result, country)
        promote(pair, country)

    combined = merge([
        ROOT / "ie.xml", ROOT / "ua.xml.gz",
        ROOT / "au.xml.gz", ROOT / "nz.xml.gz",
        ROOT / "ca.xml.gz", ROOT / "us.xml.gz",
    ])
    ch, pr = counts(combined)
    print(f"COMBINED: {ch} channels, {pr} programmes")
    if ch < 100 or pr < 1000:
        raise RuntimeError("Combined guide failed minimum coverage validation")
    pair = write_pair(combined, "combined")
    promote(pair, "combined")

if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise
