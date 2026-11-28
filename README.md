# IncyZ TV Guide

Automated XMLTV guides for Ireland, Ukraine, Australia, New Zealand, Canada and the USA.

## TiviMate: one combined EPG source

Use this single address in TiviMate:

```text
https://raw.githubusercontent.com/IncyZ/tv-guide/main/combined.xml.gz
```

## Separate country feeds

The country feeds remain available independently:

| Country | Feed |
|---|---|
| Ireland | https://raw.githubusercontent.com/IncyZ/tv-guide/main/ie.xml |
| Ukraine | https://raw.githubusercontent.com/IncyZ/tv-guide/main/ua.xml.gz |
| Australia | https://raw.githubusercontent.com/IncyZ/tv-guide/main/au.xml.gz |
| New Zealand | https://raw.githubusercontent.com/IncyZ/tv-guide/main/nz.xml.gz |
| Canada | https://raw.githubusercontent.com/IncyZ/tv-guide/main/ca.xml.gz |
| USA | https://raw.githubusercontent.com/IncyZ/tv-guide/main/us.xml.gz |

## Build schedule

- Ireland: daily at 00:00 UTC.
- Ukraine: daily at 00:30 UTC.
- Australian source EPG (including the Eurotrasz 7plus/9Now/10Play FAST supplement) and combined guide: refreshed every 6 hours.
- New Zealand, Canada and USA source guides: daily at 02:00 UTC (with the combined guide refreshed again after each country build).
- All workflows can also be started manually from the repository's Actions tab.

The international workflow uses the pinned `iptv-org/epg` generator and the selected TV Passport channel lists in `channels-north-america.xml` and `channels-north-america-extra.xml`. Australian listings are supplemented with the separately maintained Eurotrasz XMLTV guide, which adds FAST listings from 7plus, 9Now and 10Play. All country data is merged into the single `combined.xml.gz` feed shown above. Canada and the USA are split using their XMLTV country suffixes, retaining the separate regional IDs.

## Validation and safety

The international build checks that each country feed contains channels and programme listings and applies minimum coverage thresholds to the North American feeds before publishing. It also validates the combined output. If a build fails, the workflow stops before committing the new guides, leaving the previously published files in place.

Programme coverage depends on the upstream listings providers. A channel being in a channel list does not guarantee that its provider currently supplies schedule data. TiviMate may still require manual EPG assignment where an IPTV playlist uses different channel IDs.
