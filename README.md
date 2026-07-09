# Flight Radar TV

A big-screen, TV-sized flight radar for your living room. It shows **live aircraft**
around your home airport in a clean glass-cockpit (EFIS) style, with **live ATC radio
audio**, weather (Doppler/NEXRAD), approaches, airspace, and a 3-D view.

It runs in any web browser (mini-PC, Raspberry Pi, or the included Android TV app),
served by a tiny local program on your computer.

> **It works out of the box for Charleston, SC (KCHS)** — just start it (below). To
> point it at *your* airport instead, run [Set up your airport](#set-up-your-airport)
> and it downloads the map, approaches, airspace, weather, and frequencies for whatever
> field you choose.

---

## What you need (one time)

- **[Python](https://www.python.org/downloads/)** — during install, tick
  *"Add Python to PATH"*. (Needed to run the server and to set up other airports; the
  setup tool installs its own image library automatically.)

---

## Set up your airport (optional — it defaults to Charleston)

To switch from the default (Charleston) to your field, **double-click `SETUP-AIRPORT`**
and type your airport's 4-letter ICAO code (e.g. `KLAX`, `KDEN`, `KJFK`, `KSEA`). It
downloads and builds everything for that field — this takes a few minutes the first time.

Prefer a terminal? Same thing:

```
python setup_region.py KLAX
```

Handy options:

| Command | Does |
|---|---|
| `python setup_region.py KDEN` | Full setup for Denver |
| `python setup_region.py KDEN --no-charts` | Skip the slow paper-chart download |
| `python setup_region.py KCHS --rebuild` | Re-download an airport from scratch |

Each airport you set up is **saved**, so switching back to one you've used before is
instant (no re-download) and keeps any edits you made.

## Watch it

**Double-click `START-RADAR`** (or run `python server.py` and open
`http://localhost:8478`). Leave the server window open while you watch.

For a TV: run Chrome/Chromium in kiosk mode —
`chrome --kiosk --autoplay-policy=no-user-gesture-required http://localhost:8478`.

## On an Android TV / Google TV

Install **`FlightRadarTV.apk`** (sideload via the "Downloader" app or `adb install`).
It's a full-screen browser that points at your computer. On first run (or via the
Back button) it asks for your computer's address — enter the
`http://192.168.x.x:8478` that the server window prints.

---

## Fine-tuning

Everything the tool decides is written to **`config.js`** (it ships set up for
Charleston, SC; SETUP-AIRPORT rewrites it for your field). You can hand-edit it and
restart the server. The most common tweak is **live ATC audio**: the tool tries to
find your field's feeds automatically, but if audio is silent, open
`https://www.liveatc.net/search/?icao=xxxx`, copy the feed name, and set it as the
`mount` in `config.js`.

See **`RUNNING.md`** for the full controls reference.

---

## How it works / data sources

All data is free and keyless:

- **Live traffic:** [adsb.lol](https://adsb.lol) / [adsb.fi](https://adsb.fi) (ADS-B)
- **Aircraft photos:** planespotters.net, airport-data.com, Wikipedia
- **Nav data** (approaches, navaids, airways): FAA CIFP
- **Airspace:** FAA (Class B/C/D + special-use)
- **Weather:** aviationweather.gov (METAR/TAF/SIGMET), RainViewer (NEXRAD)
- **Map:** OpenStreetMap (coastline/rivers/lakes) + OpenTopoData (terrain)
- **Charts:** FAA VFR sectional & IFR-low, Esri imagery
- **Live ATC audio:** LiveATC.net

## Please note

- **Not for navigation.** This is a hobby display, not a certified aviation tool.
- **Personal use only.** LiveATC's terms don't permit rebroadcasting audio, so run
  your own copy — don't put a public stream online.
- Be polite to the free data providers (the app already caches and rate-limits).

## License

MIT — see [LICENSE](LICENSE).
