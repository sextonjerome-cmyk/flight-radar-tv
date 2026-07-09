# Running Flight Radar TV

## Everyday use (this computer)
Double-click **START-RADAR.bat**. It starts the little local server and opens
the radar at http://localhost:8478 in your browser. Leave the black console
window running (that's the server); close it to stop.

## Install it as an app (computer, TV, phone)
It's a web app, so it installs everywhere from the same server — no app store.
- **Computer (Chrome/Edge):** open http://localhost:8478, click the install icon
  in the address bar (or ⋮ menu → "Install Flight Radar TV"). It gets its own
  window and Start-menu/desktop icon.
- **TV / phone / tablet on your wifi:** make sure the computer running
  START-RADAR.bat stays on, then on the other device open the **network address**
  the server prints in its console window (looks like `http://192.168.x.x:8478`).
  On a phone/tablet use the browser's "Add to Home Screen." On an Android/Fire TV
  browser, same thing — or just leave it fullscreen.
- The window title, icon, and app name are all **Flight Radar TV**.

## Move to another airport (great for sharing with a friend)
**Easiest — double-click `SETUP-AIRPORT`.** It asks for your airport's 4-letter
code (e.g. `KLAX`), then downloads and builds the whole display for it. When it
finishes, double-click `START-RADAR`. That's the entire process — no editing files.

Prefer the command line? Same thing:
```
python setup_region.py KLAX          (or any ICAO id — KJFK, KDEN, KSEA…)
python setup_region.py KLAX --no-charts   (skip the slow chart download)
python setup_region.py KCHS --center=32.7437,-80.1073   (custom map framing)
```

(One-time requirement: **Python** installed — python.org, tick "Add to PATH".
The tool auto-installs its only other dependency.)

**Switching back is instant.** Every airport you set up is saved under
`regions/<ICAO>/`, so returning to one you've used before restores it exactly —
same map, charts, and ATC channels, no re-download. Add `--rebuild` to refetch
from fresh data.

It downloads and rebuilds **everything** for that field and takes a few minutes
(it fetches the national nav database the first time):

- approaches, runways, navaids, waypoints, airways  (FAA CIFP)
- airspace: Class B/C/D + MOA/Restricted/Warning       (FAA)
- nearest weather stations for METAR/TAF
- tower / CTAF frequencies                             (OurAirports)
- live ATC audio channels                              (LiveATC, best effort)
- the map: coastline, rivers, lakes, terrain           (OpenStreetMap + NED)
- charts: VFR sectional + IFR-low + satellite

When it finishes, **restart the server** and reload. Everything it decides is
written into **config.js**, so you can still hand-edit that file afterward — the
most likely tweak is an **ATC channel**: if the live audio is silent, open
`https://www.liveatc.net/search/?icao=xxxx`, copy the feed name, and set it as
the `mount` in config.js.

### Just fine-tuning (no rebuild)
For small changes near your current field, edit **config.js** directly — `center`,
`wxAirports`, `atisStation`/`tafStation`, home `runways`, `sigmetBox`,
`atcChannels` — save, restart the server. No download needed.

## ATC audio
Click a channel chip once (CHS ALL / SAV APP / ZJX CTR) — browsers require one
click before audio can start. Volume slider is under the channels.

**SCAN mode** (the SCAN button next to LIVEATC): monitors all three channels at
once, like an audio panel — whoever is transmitting on the highest-priority
channel plays, everyone else is muted. Priority: 1 CHS · 2 SAV APP · 3 ZJX CTR
(numbers appear on the chips). When CHS goes quiet you hear Savannah; when both
are quiet, Center. Click a chip while scanning to drop/add that channel.
Note: the CHS feed is LiveATC's own combined Tower+Approach+Ground scanner, so
within Charleston the "whoever talks" behavior is already built in.

Streams come from LiveATC.net via the local relay — personal listening only,
don't rebroadcast.

## On the TV (kiosk mode)
For an always-on display where audio starts without clicking:

```
"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe" --kiosk http://localhost:8478 --edge-kiosk-type=fullscreen --autoplay-policy=no-user-gesture-required
```

(or Chrome: `chrome --kiosk --autoplay-policy=no-user-gesture-required http://localhost:8478`)

## Controls
- **MAP** EFIS / SAT HYB / DARK · **SEC/IFR sliders** blend the FAA charts over it
- **SHOW** airspace (Class C solid / Class D dashed), special-use, **ILS** and
  **RNAV** approaches (separate buttons), waypoints, navaids, airways
- **WX** live NEXRAD radar + live SIGMETs/AIRMETs
- **RANGE** 10/15/25/50 NM · **AUTO** follows inbound traffic · **≤180** hides high overflights
- **VIEW 2D/3D** — Tacview-style isometric with glidepaths and airspace volumes ·
  **WAVES** animates the water on the EFIS map
- **CONTROLS** header (top-left of the panel) collapses/expands the whole control box
- No photo of the exact plane? It shows a **same-type / same-airline-livery**
  example seen earlier in the session, labeled "SIMILAR AIRCRAFT."
- **ATC** on/off · **SCAN** priority audio panel · click a channel to listen
- Click a plane → photo, route, data.
- **Click an airport** → recenters the map on it and shows its **CTAF/tower
  frequency** + METAR. Click Charleston (or the **⌂ KCHS** button, top-left) to
  return home. Works for any field within chart range (Johns Island, Mt Pleasant…).
- **WAVES** puts a shimmering sun-glint (tiny twinkling triangles) on the water.
- No photo of a GA plane? It shows a stock photo of that **type** (via Wikipedia).
  If the ADS-B feed didn't even send a type (common on **experimentals** and some
  GA), the app looks the tail number up in the **FAA registry** to find the
  make/model, then shows a photo of that type.

## Aircraft colors
- **Royal blue** = general aviation (N-number) · Airliners are colored by altitude:
  **green** below 10,000 ft · **cyan** 10–25,000 ft · **magenta** above 25,000 ft
- **Amber** = the selected aircraft.

## Nav colors (Garmin GTN / G1000 convention)
- **Mint green** = ILS / LOC approaches (VLOC)
- **Violet** = RNAV / GPS approaches and T-routes (GPS course)
- **Blue** = VORs and Victor (V) airways
- **Cyan** = intersections / waypoints
- **Tan** = NDBs
(Shades kept distinct from the traffic green/magenta so approaches don't blend
with aircraft.)

## Data sources (all free)
ADS-B: adsb.lol → adsb.fi (proxied by server.py) · Weather: aviationweather.gov ·
D-ATIS: datis.clowd.io · Radar: RainViewer · Photos: planespotters.net /
airport-data.com · Routes: adsbdb.com · Nav data: FAA CIFP (cycle 2606, in
mapdata/ — re-run mapdata/parse_cifp.py with a fresh CIFP zip each 28-day cycle
if you want current procedures) · Charts: FAA VFR sectional & IFR low.

NOT FOR NAVIGATION — hobby display.
