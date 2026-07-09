"""FlightRadar TV local server.

Serves the app files AND proxies the live data feeds, so the browser never
deals with CORS or a flaky upstream. Run via START-RADAR.bat (or:
`python server.py`), then open http://localhost:8478
"""
import json, os, re, sys, time, subprocess, threading, urllib.request
from urllib.parse import urlparse, parse_qs
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler

PORT = 8478
HERE = os.path.dirname(os.path.abspath(__file__))
UA = {"User-Agent": "FlightRadarTV/1.0 (personal hobby wall display)"}


def load_config():
    """Read config.js (the single source of truth shared with the web app).
    It's `window.CONFIG = { ...valid JSON... };` -- we grab the object literal."""
    path = os.path.join(HERE, "config.js")
    if not os.path.exists(path):
        raise SystemExit("\n  No airport is set up yet.\n"
                         "  Run SETUP-AIRPORT (or: python setup_region.py KXXX) first.\n")
    txt = open(path, encoding="utf-8").read()
    return json.loads(txt[txt.index("{"): txt.rindex("}") + 1])


ATC_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36",
    "Referer": "https://www.liveatc.net/",
    "Accept": "*/*",
}
# a plain browser UA — some sites (FAA registry) refuse scripted user-agents
BROWSER = {"User-Agent": ATC_HEADERS["User-Agent"]}

# ---- live region state, reloaded from config.js whenever the file changes -------
# This means switching airports (SETUP-AIRPORT) takes effect WITHOUT restarting the
# server — otherwise the server keeps serving the old airport's traffic/weather/ATC.
CFG = {}; _C = {}; _RAD = 100
ADSB_URLS = []; ATC_MOUNTS = set(); PASSTHRU = {}
_cache = {}
_cfg_mtime = [0.0]

def refresh_cfg():
    global CFG, _C, _RAD, ADSB_URLS, ATC_MOUNTS, PASSTHRU, _cache
    try:
        m = os.path.getmtime(os.path.join(HERE, "config.js"))
    except OSError:
        return
    if m == _cfg_mtime[0]:
        return
    try:
        new = load_config()                # may fail if setup_region is mid-write
    except (ValueError, OSError):
        return                             # keep the current config until it's valid
    _cfg_mtime[0] = m
    CFG = new
    _C = CFG["center"]; _RAD = CFG.get("adsbRadiusNm", 100)
    ADSB_URLS = [
        f"https://api.adsb.lol/v2/point/{_C['lat']}/{_C['lon']}/{_RAD}",
        f"https://opendata.adsb.fi/api/v2/lat/{_C['lat']}/lon/{_C['lon']}/dist/{_RAD}",
    ]
    ATC_MOUNTS = {ch["mount"] for ch in CFG.get("atcChannels", [])}
    PASSTHRU = {
        "/api/metar": "https://aviationweather.gov/api/data/metar?ids=" + ",".join(CFG["wxAirports"]) + "&format=json",
        "/api/taf":   "https://aviationweather.gov/api/data/taf?ids=" + CFG["tafStation"] + "&format=json",
        "/api/sig":   "https://aviationweather.gov/api/data/airsigmet?format=json",
        "/api/datis": "https://datis.clowd.io/api/" + CFG["atisStation"],
    }
    _cache = {}                        # drop the previous airport's cached responses

refresh_cfg()

# ---- on-demand airport setup, triggered from the app ("Change airport" box) -----
# Runs setup_region.py in the background and streams its progress so the TV can show
# a "downloading…" screen, then reloads itself when the new airport is ready.
_setup = {"running": False, "icao": None, "lines": [], "done": False, "ok": False}
_setup_lock = threading.Lock()

def run_setup(icao):
    _setup.update(running=True, icao=icao, lines=[], done=False, ok=False)
    try:
        proc = subprocess.Popen(
            [sys.executable, os.path.join(HERE, "setup_region.py"), icao],
            cwd=HERE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, bufsize=1, encoding="utf-8", errors="replace")
        for line in proc.stdout:
            line = line.rstrip()
            if line:
                _setup["lines"].append(line)
                del _setup["lines"][:-200]          # keep the tail only
        _setup["ok"] = (proc.wait() == 0)
    except Exception as e:
        _setup["lines"].append(f"error: {e}")
        _setup["ok"] = False
    finally:
        _setup["running"] = False
        _setup["done"] = True
        _cfg_mtime[0] = 0                            # force a config reload next request

def fetch(url, timeout=9):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()

# ---- add/remove ATC channels from the app (for Approach/Center feeds the auto-finder
# can't guess). A live LiveATC mount redirects to a 200 audio stream; a dead name 404s.
def probe_mount(mount):
    try:
        req = urllib.request.Request("http://d.liveatc.net/" + mount,
              headers={"User-Agent": ATC_HEADERS["User-Agent"],
                       "Referer": "https://www.liveatc.net/", "Range": "bytes=0-2000"})
        with urllib.request.urlopen(req, timeout=8) as r:
            return getattr(r, "status", 200) == 200 and "audio" in r.headers.get("Content-Type", "")
    except Exception:
        return False

def write_config_obj(cfg):
    path = os.path.join(HERE, "config.js")
    txt = open(path, encoding="utf-8").read()
    i, j = txt.index("{"), txt.rindex("}") + 1
    open(path, "w", encoding="utf-8").write(txt[:i] + json.dumps(cfg, indent=2) + txt[j:])
    _cfg_mtime[0] = 0                                 # force a reload on the next request

class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=HERE, **kw)

    def do_GET(self):
        refresh_cfg()                             # pick up an airport switch live
        path = self.path.split("?")[0]
        if path == "/apk":                        # short URL for sideloading to the TV
            self.send_response(302)
            self.send_header("Location", "/FlightRadarTV.apk")
            self.end_headers()
            return
        if path == "/api/atc/add":
            return self.atc_add()
        if path == "/api/atc/remove":
            return self.atc_remove()
        if path == "/api/setup":
            return self.start_setup()
        if path == "/api/setup/status":
            return self.send_json(json.dumps({
                "running": _setup["running"], "icao": _setup["icao"],
                "done": _setup["done"], "ok": _setup["ok"],
                "lines": _setup["lines"][-30:],
            }).encode())
        if path == "/api/adsb":
            return self.cached("adsb", 4, self.get_adsb)
        if path == "/api/reg":
            n = (parse_qs(urlparse(self.path).query).get("n") or [""])[0]
            n = re.sub(r"[^A-Za-z0-9]", "", n).upper()
            if not n:
                return self.send_error(400, "no n-number")
            return self.cached("reg:" + n, 86400, lambda: self.get_reg(n))
        if path in PASSTHRU:
            ttl = 60 if path == "/api/adsb" else 240
            return self.cached(path, ttl, lambda: fetch(PASSTHRU[path], 15))
        if path.startswith("/atc/"):
            return self.stream_atc(path[5:])
        return super().do_GET()

    def stream_atc(self, mount):
        if mount not in ATC_MOUNTS:
            return self.send_error(404, "unknown mount")
        try:
            req = urllib.request.Request("http://d.liveatc.net/" + mount,
                                         headers=ATC_HEADERS)
            up = urllib.request.urlopen(req, timeout=15)
        except Exception as e:
            return self.send_error(502, str(e))
        self.send_response(200)
        self.send_header("Content-Type", up.headers.get("Content-Type", "audio/mpeg"))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        try:
            while True:
                chunk = up.read(4096)
                if not chunk:
                    break
                self.wfile.write(chunk)
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError, OSError):
            pass
        finally:
            try: up.close()
            except Exception: pass

    def atc_add(self):
        q = parse_qs(urlparse(self.path).query)
        mount = re.sub(r"[^a-z0-9_]", "", (q.get("mount") or [""])[0].lower())
        label = re.sub(r"[^A-Za-z0-9 ·/+.-]", "", (q.get("label") or [""])[0]).strip()[:16]
        if not mount:
            return self.send_error(400, "no mount")
        if not probe_mount(mount):                    # only add feeds that actually stream
            return self.send_json(json.dumps({"ok": False, "reason": "not_live", "mount": mount}).encode())
        cfg = load_config()
        chans = [c for c in cfg.get("atcChannels", []) if c.get("mount") not in ("REPLACE_ME", mount)]
        chans.append({"mount": mount, "label": label or mount.upper().replace("_", " "),
                      "sub": "added", "priority": len(chans) + 1})
        cfg["atcChannels"] = chans
        write_config_obj(cfg)
        return self.send_json(json.dumps({"ok": True, "mount": mount, "channels": chans}).encode())

    def atc_remove(self):
        mount = re.sub(r"[^a-z0-9_]", "",
                       (parse_qs(urlparse(self.path).query).get("mount") or [""])[0].lower())
        cfg = load_config()
        chans = [c for c in cfg.get("atcChannels", []) if c.get("mount") != mount]
        for i, c in enumerate(chans):
            c["priority"] = i + 1
        cfg["atcChannels"] = chans or [{"mount": "REPLACE_ME", "label": cfg["center"]["id"],
                                        "sub": "add from liveatc.net", "priority": 1}]
        write_config_obj(cfg)
        return self.send_json(json.dumps({"ok": True, "channels": cfg["atcChannels"]}).encode())

    def start_setup(self):
        icao = (parse_qs(urlparse(self.path).query).get("icao") or [""])[0]
        icao = re.sub(r"[^A-Za-z0-9]", "", icao).upper()
        if not re.fullmatch(r"[A-Z]{3,4}\d?", icao or ""):
            return self.send_error(400, "bad airport code")
        with _setup_lock:
            if _setup["running"]:
                return self.send_json(json.dumps(
                    {"running": True, "icao": _setup["icao"], "already": True}).encode())
            threading.Thread(target=run_setup, args=(icao,), daemon=True).start()
        return self.send_json(json.dumps({"running": True, "icao": icao, "started": True}).encode())

    def cached(self, key, ttl, fn):
        now = time.time()
        hit = _cache.get(key)
        if hit and now - hit[0] < ttl:
            return self.send_json(hit[1])
        try:
            data = fn()
            _cache[key] = (now, data)
            return self.send_json(data)
        except Exception as e:
            if hit:                       # stale beats nothing
                return self.send_json(hit[1])
            self.send_error(502, str(e))

    def get_reg(self, n):
        # FAA aircraft registry lookup by N-number → make / model (covers
        # experimentals & anything the ADS-B feed doesn't tag with a type).
        url = "https://registry.faa.gov/aircraftinquiry/Search/NNumberResult?NNumbertxt=" + n
        req = urllib.request.Request(url, headers=BROWSER)
        with urllib.request.urlopen(req, timeout=15) as r:
            html = r.read().decode("utf-8", "replace")
        def field(lbl):
            m = re.search(r'data-label="' + re.escape(lbl) + r'">\s*([^<]*?)\s*</td>', html)
            return m.group(1).strip() if m else ""
        return json.dumps({"n": n,
                           "mfr": field("Manufacturer Name"),
                           "model": field("Model")}).encode()

    def get_adsb(self):
        err = None
        for u in ADSB_URLS:
            try:
                return fetch(u, 8)
            except Exception as e:
                err = e
        raise err

    def send_json(self, data):
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def end_headers(self):
        # never let the browser cache the region files — otherwise switching airports
        # can show the previous field's map/nav from a stale cache (esp. on TV WebViews)
        p = self.path.split("?")[0]
        if p in ("/config.js", "/index.html", "/") or p.startswith("/mapdata/"):
            self.send_header("Cache-Control", "no-store, must-revalidate")
        super().end_headers()

    def log_message(self, *a):            # keep the console quiet
        pass


class QuietServer(ThreadingHTTPServer):
    # False so a second server on Windows can't silently share the port (which made
    # requests hit random old/new instances); START-RADAR frees the port first instead
    allow_reuse_address = False
    def handle_error(self, request, client_address):
        # a browser tab closing / reloading mid-response aborts the connection —
        # that's normal, so don't spew a traceback for it
        import sys
        if isinstance(sys.exc_info()[1],
                      (ConnectionResetError, ConnectionAbortedError, BrokenPipeError)):
            return
        super().handle_error(request, client_address)

if __name__ == "__main__":
    import socket
    print(f"Flight Radar TV  --  {_C['id']} {_C['name']}")
    print(f"  this computer:  http://localhost:{PORT}")
    try:
        for ip in socket.gethostbyname_ex(socket.gethostname())[2]:
            if not ip.startswith("127."):
                print(f"  TV / other devices on your wifi:  http://{ip}:{PORT}")
    except Exception:
        pass
    print(f"  switch airports anytime with SETUP-AIRPORT — no restart needed")
    print("  (Ctrl+C to stop)")
    try:
        QuietServer(("0.0.0.0", PORT), Handler).serve_forever()
    except OSError as e:
        print(f"\n  Could not start: port {PORT} is already in use.")
        print("  Another Flight Radar TV server is probably still running —")
        print("  close its window (or reboot) and run START-RADAR again.\n")
