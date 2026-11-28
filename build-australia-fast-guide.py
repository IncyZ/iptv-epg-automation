#!/usr/bin/env python3
"""Refresh the Australian guide and rebuild the single combined XMLTV feed."""

from __future__ import annotations

import gzip
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parent
WORK = ROOT / "epg-source" / "work"


def read_root(path: Path) -> ET.Element:
    opener = gzip.open if path.name.endswith(".gz") else open
    with opener(path, "rb") as stream:
        root = ET.parse(stream).getroot()
    if root.tag != "tv":
        raise RuntimeError(f"Unexpected XMLTV root in {path}: {root.tag}")
    return root


def merge(paths: list[Path], label: str) -> ET.Element:
    channels: dict[str, ET.Element] = {}
    programmes: dict[tuple[str, str, str, str], ET.Element] = {}

    for path in paths:
        if not path.is_file() or path.stat().st_size == 0:
            raise RuntimeError(f"Required EPG source missing or empty: {path}")
        root = read_root(path)

        for channel in root.findall("channel"):
            channel_id = channel.get("id")
            if channel_id:
                channels.setdefault(channel_id, channel)

        for programme in root.findall("programme"):
            channel_id = programme.get("channel", "")
            if not channel_id:
                continue
            key = (
                channel_id,
                programme.get("start", ""),
                programme.get("stop", ""),
                (programme.findtext("title") or "").strip(),
            )
            programmes.setdefault(key, programme)

    if not channels or not programmes:
        raise RuntimeError(
            f"{label} guide is empty: {len(channels)} channels, "
            f"{len(programmes)} programmes"
        )

    output = ET.Element("tv", {"generator-info-name": "IncyZ TV Guide"})
    output.extend(channels.values())
    output.extend(programmes.values())
    return output


def write_temp(root: ET.Element, stem: str) -> tuple[Path, Path]:
    xml_path = ROOT / f"{stem}.xml.tmp"
    gzip_path = ROOT / f"{stem}.xml.gz.tmp"
    tree = ET.ElementTree(root)
    ET.indent(tree, space="  ")
    tree.write(xml_path, encoding="utf-8", xml_declaration=True)

    with open(xml_path, "rb") as source, open(gzip_path, "wb") as raw:
        with gzip.GzipFile(
            fileobj=raw, mode="wb", compresslevel=9, mtime=0
        ) as target:
            target.write(source.read())

    # Validate the exact files before publishing either one.
    parsed = ET.parse(xml_path).getroot()
    with gzip.open(gzip_path, "rb") as stream:
        compressed_parsed = ET.parse(stream).getroot()
    if len(parsed.findall("programme")) != len(compressed_parsed.findall("programme")):
        raise RuntimeError(f"{stem} gzip validation failed")

    return xml_path, gzip_path


def promote(pair: tuple[Path, Path], stem: str) -> None:
    pair[0].replace(ROOT / f"{stem}.xml")
    pair[1].replace(ROOT / f"{stem}.xml.gz")


def main() -> None:
    # Refresh only Australian source sites plus Eurotrasz FAST listings.
    au = merge(
        [
            WORK / "abc.net.au.xml",
            WORK / "foxtel.com.au.xml",
            WORK / "foxsports.com.au.xml",
            WORK / "eurotrasz-au.xml",
        ],
        "Australia",
    )
    au_channels = len(au.findall("channel"))
    au_programmes = len(au.findall("programme"))
    print(f"AU: {au_channels} channels, {au_programmes} programmes")
    if au_channels < 1 or au_programmes < 50:
        raise RuntimeError("Australian coverage is below the safety threshold")

    au_temp = write_temp(au, "au")

    # Rebuild the one-file TiviMate feed using the refreshed AU data and
    # the latest published feeds for the other countries.
    combined = merge(
        [
            ROOT / "ie.xml",
            ROOT / "ua.xml.gz",
            au_temp[0],
            ROOT / "nz.xml.gz",
            ROOT / "ca.xml.gz",
            ROOT / "us.xml.gz",
        ],
        "Combined",
    )
    combined_channels = len(combined.findall("channel"))
    combined_programmes = len(combined.findall("programme"))
    print(
        f"COMBINED: {combined_channels} channels, "
        f"{combined_programmes} programmes"
    )
    if combined_channels < 100 or combined_programmes < 1000:
        raise RuntimeError("Combined guide failed minimum coverage validation")

    combined_temp = write_temp(combined, "combined")

    # Publish only after both new feeds have passed XML and gzip validation.
    promote(au_temp, "au")
    promote(combined_temp, "combined")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise
