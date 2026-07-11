# Flight Radar TV

A flight radar for your living room. It shows **live aircraft** around your airport in
a glass-cockpit (EFIS) style, with **live ATC radio**, weather, approaches, airspace,
and a 3-D view.

**Watch it on your computer *or* on your TV** — both run from one tiny program on your
computer. **It works out of the box for Charleston, SC.**

---

## 1. Install Python (one time)

Get it from [python.org](https://www.python.org/downloads/). During install, tick
**"Add Python to PATH."** That's the only thing to install.

## 2. Start it

Double-click **`START-RADAR`**. Leave the little black window open while you watch —
that's the server. Now open the radar on either screen (or both at once):

- **On the computer:** it opens in your browser automatically. Done.
- **On the TV:** keep the computer on, then on the TV open the network address the
  server window prints (looks like `http://192.168.x.x:8478`) — in any TV browser, or
  in the included **`FlightRadarTV.apk`** for Android/Google TV. (See "Watch it on a
  TV" below.)

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

## Watch it on a TV — step by step

The TV is just a screen showing what your computer serves, so a little prep first:

**On the computer (once):**
1. Double-click **`START-RADAR`** and leave its black window open.
2. It prints a **network address** that looks like `http://192.168.1.50:8478` — write
   down your exact numbers (yours will differ). This is what the TV connects to.
3. Make sure the **TV is on the same Wi-Fi** as the computer.

Then pick whichever fits your TV:

### Option 1 — Any TV with a web browser (easiest)
Open the TV's web browser and go to the `http://192.168.x.x:8478` address from step 2.
That's it. (Bookmark it so it's one click next time.)

### Option 2 — The app on Android TV / Google TV / Fire TV (Fire Stick)
This installs a clean full-screen app. It takes a few minutes the first time:

1. **Install "Downloader."** On the TV, open its app store, search **Downloader**
   (orange icon, by AFTVnews), and install it. *(This is the tool that fetches the app.)*
2. **Let Downloader install apps.** Go to the TV's **Settings → Apps → Security &
   restrictions → Unknown sources** and turn it **ON for Downloader**. *(Some TVs skip
   this and just ask you to "Allow" during step 4 instead.)*
3. **Open Downloader** and, in its address box, type this **exactly**, using your own
   numbers from step 2:
   ```
   http://192.168.x.x:8478/FlightRadarTV.apk
   ```
   Press **Go**. *(Use this full link — the app file is tiny and downloads in a second.)*
4. When it finishes, choose **Install**, then **Open**. *(Downloader will offer to
   delete the downloaded file afterward — say yes, you don't need it.)*
5. On first launch it shows a **"Radar server address"** box, already filled in with
   `http://192.168.x.x:8478`. Press **Back once** on the remote to hide the keyboard,
   then select **Connect**. The radar fills the screen. 🎉

**Handy to know:**
- The **computer must stay on and awake** whenever you watch — it feeds the TV.
- **Black screen?** Press **Back** on the remote to bring up the address box and
  re-enter `http://192.168.x.x:8478`. Press **MENU** anytime to change the address.
- **Switch airports from the couch:** open **CONTROLS → CHANGE AIRPORT** and type a
  4-letter code.

For a full-screen, always-on kiosk display, see **`RUNNING.md`**.

## Using it without your own computer (optional)

The app — on a computer, TV, Fire Stick, or Google TV — is only the **screen**.
The `START-RADAR` program is the **engine** that pulls the live planes, weather, and
ATC and feeds it to the screen. So a computer running that engine has to be **on and
awake** whenever you watch, and the TV has to reach it over the network.

To watch on **any TV, on any network, with no computer of yours running**, put that
same engine on an **always-on machine** and point the app at it instead:

- **A small cloud server** (~$5/month) — works from anywhere, nothing needed at home.
- **A mini-PC or Raspberry Pi** left on at home — free-ish, works on your home wifi.

Then in the TV app just enter that machine's address (instead of your computer's).
Everything keeps working — including **CHANGE AIRPORT** — because the engine still does
the heavy lifting; only its location moves. No app changes are needed; the app already
lets you type in whatever address the engine is at.

**Keep it private.** LiveATC audio is licensed for personal listening, so if the engine
is reachable from the internet, don't share the address publicly — put it behind a
password. (That password gate isn't built in yet; add it when you host it online.)

## Controls — what every button does

The buttons live in the **CONTROLS** box (top-left of the screen) and the **info panel**
(right side). Click the **CONTROLS** header to collapse or expand the box.

### MAP — base map style
- **EFIS** — the glass-cockpit look: dark map, terrain shading, water. *(default)*
- **SAT HYB** — satellite imagery with labels.
- **DARK** — a plain dark map.

### SHOW — map overlays (each toggles on/off)
- **ASP** — controlled airspace outlines (Class B / C / D).
- **SUA** — Special Use Airspace (military zones, restricted / prohibited areas).
- **ILS** — ILS / localizer approaches (the "feather" + glidepath into the runway).
- **RNAV** — RNAV / GPS approaches.
- **WPT** — waypoints / intersections.
- **NAV** — navaids (VORs and NDBs).
- **AWY** — airways (the "highways in the sky").

### WX — weather
- **DOPPLER** — live weather radar (NEXRAD) painted on the map.
- **SIG/AIRMET** — live SIGMETs & AIRMETs (hazard advisory areas).

### RANGE — how far the map reaches
- **10 / 15 / 25 / 50** — map radius in nautical miles.
- **AUTO** — auto-zooms to follow inbound traffic.
- **≤180** — show only traffic at/below 18,000 ft (hides high jets passing overhead).

### CHART — fade FAA paper charts over the map
- **SECTIONAL** — the VFR sectional chart; **–/+** step its opacity by 10%.
- **IFR LOW** — the IFR low-altitude enroute chart; **–/+** step its opacity.

### VIEW — 2-D or 3-D
- **2D** — flat top-down radar.
- **3D** — tilted, Tacview-style view: aircraft float at altitude, with glidepaths and
  3-D airspace volumes.
- **WAVES** — animate a shimmering sun-glint on the water (EFIS map).

### TRAIL — breadcrumb tails behind each plane
- **– / +** — set how many **minutes** of fading tail each aircraft leaves behind it (0 =
  off). Longer trails show more of where planes have been — turns, holding, the whole
  approach. The selected plane's trail is drawn brightest.

### FIELD
- **CHANGE AIRPORT** — type a 4-letter code to download and switch to a new airport.

### Top-left
- **⌂ (home)** — recenter on your home airport (appears once you've clicked another one).

### LIVE ATC (info panel)
- **ATC** — turn the radio on / off.
- **SCAN** — monitor all channels at once; whoever is transmitting on the highest-priority
  channel plays, the rest stay muted (like a real cockpit audio panel).
- **Channel buttons** (e.g. `CHS`, `SAV APP`) — tap one to listen to that feed.
- **＋ ADD ATC CHANNEL** — add an Approach/Center feed by name (checked live before adding).
- **VOL** — volume slider.

### HUD VIEW — fly along inside the plane (info panel)
- **▣ HUD VIEW** — with a plane selected, drops you into a full-screen **first-person cockpit
  view**, flying along the aircraft's track and flight path, with an F/A-18-style green HUD:
  heading tape, pitch ladder, velocity vector, bank scale, and boxed **ground speed / altitude**
  (with height above ground), plus **Mach** and **G**. The world outside is drawn in true
  perspective — **elevation-shaded terrain**, other **traffic** (with each one's height above/below
  you and distance), scattered **airport identifiers**, and your home field's **runway highlighted
  in yellow** with an extended centerline and a target box. Attitude is *derived* from the ADS-B
  track and climb rate (there's no real attitude in the data) and speed is **ground** speed, so
  it's a realistic-looking cockpit view — not an instrument. Press **CLOSE** or **Esc** to exit.

### Clicking around
- **Click a plane** — selects it: its photo, type, route, altitude, speed, and heading fill
  the panel, and the **HUD VIEW** button lights up.
- **Click an airport** — recenters on it and shows its tower/CTAF frequency + weather.

### What the colors mean
- **Aircraft:** royal blue = general aviation (N-number); airliners by altitude —
  **green** below 10,000 ft, **cyan** 10–25,000 ft, **magenta** above 25,000 ft;
  **amber = the plane you selected**.
- **Navigation** (Garmin convention): mint green = ILS/LOC, violet = RNAV/GPS & T-routes,
  blue = VORs & Victor airways, cyan = waypoints, tan = NDBs.

## Good to know

- **Terrain follows the airport** — the land is shaded by real elevation, so flat fields
  (like Charleston) look low and green while mountain fields (like Salt Lake City) show
  light-brown, hill-shaded relief. It downloads automatically with each airport.
- **Not for navigation** — it's a hobby display, not a certified aviation tool.
- **Personal use only** — don't rebroadcast the ATC audio (LiveATC's terms).
- All data is free: ADS-B traffic, FAA nav/airspace/charts, aviationweather.gov,
  OpenStreetMap, and LiveATC. See **`RUNNING.md`** for the full list and controls.

MIT license — see [LICENSE](LICENSE).
