"""FlightRadar TV local server.

Serves the app files AND proxies the live data feeds, so the browser never
deals with CORS or a flaky upstream. Run via START-RADAR.bat (or:
`python server.py`), then open http://localhost:8478
"""
import json, os, re, time, urllib.request
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


CFG = load_config()
_C = CFG["center"]
_RAD = CFG.get("adsbRadiusNm", 100)
ADSB_URLS = [
    f"https://api.adsb.lol/v2/point/{_C['lat']}/{_C['lon']}/{_RAD}",
    f"https://opendata.adsb.fi/api/v2/lat/{_C['lat']}/lon/{_C['lon']}/dist/{_RAD}",
]
# LiveATC audio relay: lets the browser measure levels (same-origin) for the
# priority scanner. Personal listening only — do not rebroadcast.
ATC_MOUNTS = {ch["mount"] for ch in CFG.get("atcChannels", [])}
ATC_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36",
    "Referer": "https://www.liveatc.net/",
    "Accept": "*/*",
}
# a plain browser UA — some sites (FAA registry) refuse scripted user-agents
BROWSER = {"User-Agent": ATC_HEADERS["User-Agent"]}
PASSTHRU = {
    "/api/metar": "https://aviationweather.gov/api/data/metar?ids=" + ",".join(CFG["wxAirports"]) + "&format=json",
    "/api/taf":   "https://aviationweather.gov/api/data/taf?ids=" + CFG["tafStation"] + "&format=json",
    "/api/sig":   "https://aviationweather.gov/api/data/airsigmet?format=json",
    "/api/datis": "https://datis.clowd.io/api/" + CFG["atisStation"],
}
_cache = {}

def fetch(url, timeout=9):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()

class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=HERE, **kw)

    def do_GET(self):
        path = self.path.split("?")[0]
        if path == "/apk":                        # short URL for sideloading to the TV
            self.send_response(302)
            self.send_header("Location", "/FlightRadarTV.apk")
            self.end_headers()
            return
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

    def log_message(self, *a):            # keep the console quiet
        pass

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
    print("  (Ctrl+C to stop)")
    ThreadingHTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
