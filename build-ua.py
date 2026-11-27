#!/usr/bin/env python3
"""Build a compact, Ukraine-only XMLTV guide from Ukrainian IPTV-org channels.

The channel selection is sourced only from ua.m3u. EPG listings are matched
by channel display names from the configured XMLTV providers.
"""
import datetime as dt
import gzip
import json
import re
import ssl
import tempfile
import urllib.request
import xml.etree.ElementTree as ET

UA_PLAYLIST = "https://iptv-org.github.io/iptv/countries/ua.m3u"
CHANNELS_DB = "https://iptv-org.github.io/api/channels.json"
EPG_SOURCES = [
    "https://iptvx.one/EPG",
    "https://epg.pw/xmltv/epg_RU.xml.gz",
]
OUTPUT = "ua-epg.xml.gz"
DAYS_AHEAD = 7
DAYS_BACK = 1
CTX = ssl.create_default_context()
CTX.check_hostname = False
CTX.verify_mode = ssl.CERT_NONE
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; UA-EPG-Automation/1.0)"}


def get(url, timeout=300):
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=timeout, context=CTX) as response:
        data = response.read()
    if data[:2] == b"\x1f\x8b":
        return gzip.decompress(data)
    return data


def norm(value):
    value = re.sub(r"\(.*?\)|\[.*?\]", "", value.lower())
    for word in (" hd", " fhd", " uhd", " 4k", "телеканал ", "tv channel"):
        value = value.replace(word, "")
    value = value.replace("плюс", "+").replace("plus", "+")
    return re.sub(r"[^a-zа-яёіїєґ0-9+]", "", value)


def parse_ua_channels(text, db):
    lines = text.splitlines()
    channels = []
    for i, line in enumerate(lines):
        if not line.startswith("#EXTINF"):
            continue
        name = line.rsplit(",", 1)[-1].strip()
        match = re.search(r'tvg-id="([^"]*)"', line)
        tvg_id = match.group(1).split("@", 1)[0] if match else ""
        aliases = [name] + db.get(tvg_id, [])
        channels.append((name, aliases))
    return channels


def load_epg(url, lo, hi):
    print(f"Reading EPG source: {url}", flush=True)
    tmp = tempfile.TemporaryFile()
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=600, context=CTX) as response:
        while True:
            chunk = response.read(1024 * 1024)
            if not chunk:
                break
            tmp.write(chunk)
    tmp.seek(0)
    magic = tmp.read(2)
    tmp.seek(0)
    stream = gzip.GzipFile(fileobj=tmp) if magic == b"\x1f\x8b" else tmp

    index, channel_xml, programmes = {}, {}, {}
    for _, element in ET.iterparse(stream, events=("end",)):
        if element.tag == "channel":
            channel_id = element.get("id")
            if channel_id:
                channel_xml[channel_id] = ET.tostring(element, encoding="unicode")
                for display in element.findall("display-name"):
                    if display.text:
                        index.setdefault(norm(display.text), channel_id)
            element.clear()
        elif element.tag == "programme":
            start = (element.get("start") or "")[:8]
            stop = (element.get("stop") or "")[:8]
            if start and stop and stop >= lo and start <= hi:
                channel_id = element.get("channel")
                if channel_id:
                    programmes.setdefault(channel_id, []).append(
                        ET.tostring(element, encoding="unicode")
                    )
            element.clear()
    return index, channel_xml, programmes


def main():
    now = dt.datetime.now(dt.timezone.utc)
    lo = (now - dt.timedelta(days=DAYS_BACK)).strftime("%Y%m%d")
    hi = (now + dt.timedelta(days=DAYS_AHEAD)).strftime("%Y%m%d")
    print(f"Keeping programme data from {lo} through {hi} UTC", flush=True)

    channels_db = json.loads(get(CHANNELS_DB).decode("utf-8"))
    db = {
        channel["id"]: [channel.get("name", "")] + channel.get("alt_names", [])
        for channel in channels_db
    }
    ua_channels = parse_ua_channels(get(UA_PLAYLIST).decode("utf-8", "replace"), db)
    print(f"Ukrainian source channels: {len(ua_channels)}", flush=True)

    sources = []
    for url in EPG_SOURCES:
        try:
            sources.append(load_epg(url, lo, hi))
        except Exception as error:
            print(f"WARNING: EPG source failed: {url}: {error}", flush=True)
            sources.append(({}, {}, {}))

    selected = {}
    for name, aliases in ua_channels:
        for source_number, (index, channel_xml, programmes) in enumerate(sources):
            channel_id = next(
                (index[norm(alias)] for alias in aliases if alias and norm(alias) in index),
                None,
            )
            if channel_id and programmes.get(channel_id):
                output_id = f"s{source_number}.{channel_id}"
                selected.setdefault(output_id, (source_number, channel_id))
                break

    if not selected:
        raise SystemExit("No Ukrainian channels matched programme data; refusing to publish an empty guide.")

    with gzip.open(OUTPUT, "wt", encoding="utf-8") as output:
        output.write('<?xml version="1.0" encoding="UTF-8"?>\n')
        output.write('<tv generator-info-name="IncyZ UA EPG Automation">\n')
        for output_id, (source_number, channel_id) in selected.items():
            xml = sources[source_number][1][channel_id]
            xml = re.sub(r'\bid="' + re.escape(channel_id) + r'"', f'id="{output_id}"', xml, count=1)
            output.write(xml + "\n")
        programme_count = 0
        for output_id, (source_number, channel_id) in selected.items():
            for xml in sources[source_number][2].get(channel_id, []):
                xml = re.sub(
                    r'\bchannel="' + re.escape(channel_id) + r'"',
                    f'channel="{output_id}"',
                    xml,
                    count=1,
                )
                output.write(xml + "\n")
                programme_count += 1
        output.write("</tv>\n")

    print(f"Matched Ukrainian channels: {len(selected)}", flush=True)
    print(f"Programme entries included: {programme_count}", flush=True)
    if programme_count < 100:
        raise SystemExit("Too few programme entries; refusing to publish an incomplete guide.")


if __name__ == "__main__":
    main()
