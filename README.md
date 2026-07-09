# Flight Radar TV

A TV-sized flight radar for your living room. It shows **live aircraft** around your
airport in a glass-cockpit (EFIS) style, with **live ATC radio**, weather, approaches,
airspace, and a 3-D view. Runs in any web browser from a tiny program on your computer.

**It works out of the box for Charleston, SC.**

---

## 1. Install Python (one time)

Get it from [python.org](https://www.python.org/downloads/). During install, tick
**"Add Python to PATH."** That's the only thing to install.

## 2. Start it

Double-click **`START-RADAR`**. Your browser opens the radar. Leave the little black
window open while you watch — that's the server. Done.

## 3. Use a different airport (optional)

**From the app itself** (works on the TV too): open **CONTROLS → CHANGE AIRPORT**,
type a 4-letter code (e.g. `KLAX`), and select **LOAD**. It downloads the map,
approaches, airspace, weather, and frequencies, then loads that field automatically —
a few minutes the first time.

Prefer the computer? Double-click **`SETUP-AIRPORT`**, type the code, then reload the
browser (`Ctrl+Shift+R`). Either way, every airport you set up is **saved**, so
switching back to one you've used before is instant.

## 4. Turn on ATC audio

ATC audio is the one thing you set up by hand (LiveATC has no automatic option):

1. Open `https://www.liveatc.net/search/?icao=xxxx` for your airport.
2. Copy a feed's name — the `NAME` in its `NAME.pls` link.
3. Put it as the `mount` in **`config.js`**, save, reload the browser.

Full example and details are in **`RUNNING.md`**. Charleston's audio already works.

---

## On a TV

Point any browser on your TV at the network address the server window prints
(`http://192.168.x.x:8478`), or install the included **`FlightRadarTV.apk`** on
Android/Google TV. For a full-screen always-on display, see **`RUNNING.md`**.

## Good to know

- **Not for navigation** — it's a hobby display, not a certified aviation tool.
- **Personal use only** — don't rebroadcast the ATC audio (LiveATC's terms).
- All data is free: ADS-B traffic, FAA nav/airspace/charts, aviationweather.gov,
  OpenStreetMap, and LiveATC. See **`RUNNING.md`** for the full list and controls.

MIT license — see [LICENSE](LICENSE).
