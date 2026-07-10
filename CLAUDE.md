# Flight Radar TV — developer guide

A TV-sized (1920×1080) live flight radar in a glass-cockpit / EFIS style: live ADS-B
traffic, weather, approaches, airspace, a 3-D view, and live ATC audio. It's a plain
web app plus a tiny Python server — **no build step**. Edit a file, reload the browser.

## Run it
See **README.md** (install Python, double-click `START-RADAR`) and **RUNNING.md**
(controls, TV/kiosk mode, switching airports). The app lives at http://localhost:8478.

## How it's put together
- **index.html** — the entire web app: canvas rendering (2-D map + isometric 3-D view),
  traffic, approaches/airspace, weather radar, the side info panel, and the ATC audio
  player. Self-contained HTML/CSS/JS, no framework, no bundler.
- **server.py** — the local "engine": serves the app and **proxies the live feeds**
  (ADS-B, weather, LiveATC audio) so the browser never hits CORS or mixed-content;
  does FAA registry lookups; runs on-demand airport setup; **hot-reloads `config.js`**.
- **setup_region.py** — builds *all* data for an airport from free, keyless sources
  (OurAirports, FAA CIFP, FAA airspace, OpenStreetMap, OpenTopoData, FAA charts) and
  writes `config.js` + `mapdata/`. Snapshots each airport under `regions/<ICAO>/` for
  instant round-trips.
- **config.js** — single source of truth for the current region; **both** the app and
  the server read this exact file. Switching airports = rewriting this + `mapdata/`.
- **mapdata/** — baked data: `map_data.js` (coastline/water/terrain), `nav_data.js`
  (approaches/airspace/navaids/airways), `charts_data.js` (VFR/IFR chart tiles).
- **FlightRadarTV.apk** — a thin full-screen WebView for Android/Google/Fire TV that
  just points at the server. Its source is not in this repo.

## Conventions & gotchas (read before touching these areas)
- **No build step.** Edit `index.html` / `server.py` and reload. The server re-reads
  `config.js` on its own — no restart needed to switch airports.
- **`config.js` is the one knob** that moves the whole display. Keep it valid JSON
  after the `=`.
- **Water / coastline:** `MAP.water` holds real closed water polygons (open sea +
  estuaries) built by `setup_region.py`; render the sea from those. Don't assume which
  way the coast faces — a hardcoded "ocean is to the south-east" fill once flooded the
  land at west-coast airports.
- **ILS feather:** only ILS/LOC approaches get a localizer feather, drawn at a fixed
  ~4° course width (the FAA record's width field is unreliable). RNAV approaches are a
  dashed centerline, never a feather.
- **ATC discovery:** LiveATC's search page blocks scripts, but the audio mounts are
  reachable — setup **probes** common feed names (`_twr`/`_gnd`/`_app`/…) and keeps the
  ones actually streaming. Approach/Center feeds are named after the TRACON and are
  added by hand via the in-app "Add ATC channel" box.
- **Caching:** the server sends `Cache-Control: no-store` for `config.js`,
  `index.html`, and `mapdata/*` so switching airports never shows a stale field.
- **Free & keyless:** every data source is free and needs no API key. Be polite — the
  app already caches and rate-limits.
- **Not for navigation; personal use.** LiveATC audio is personal-use — don't
  rebroadcast it, and don't commit personal information.

## Data sources
ADS-B: adsb.lol / adsb.fi · Weather: aviationweather.gov, datis.clowd.io · Radar:
RainViewer · Nav / airspace / charts: FAA · Map: OpenStreetMap + OpenTopoData · Photos:
planespotters.net / airport-data.com / Wikipedia · ATC: LiveATC.
