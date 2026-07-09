#!/usr/bin/env python3
"""setup_region.py  KLAX   — move the whole Flight Radar TV display to any US airport.

Downloads and rebuilds everything for the chosen field:
  * approaches, runways, navaids, waypoints, airways   (FAA CIFP)
  * airspace: Class B/C/D polygons + MOA/Restricted/Warning (FAA)
  * live weather airports (nearest METAR/TAF stations)
  * tower / CTAF frequencies                            (OurAirports)
  * live ATC audio channels                             (LiveATC, best effort)
  * the map: coastline, rivers, lakes, terrain          (OpenStreetMap + NED)
  * charts: VFR sectional + IFR-low + satellite tiles

Usage:   python setup_region.py KLAX
         python setup_region.py KJFK --no-charts     (skip the slow chart bake)
         python setup_region.py KLAX --rebuild       (force a fresh re-download)

Each airport you set up is saved under regions/<ICAO>/, so switching BACK to an
airport you've used before is instant and identical (no re-download, and any
hand-edits to config.js are preserved). Use --rebuild to refetch from scratch.

Everything it writes goes through config.js, so after it runs you can still
hand-edit config.js (e.g. to fix an ATC channel) and just restart the server.
"""
import sys, os, io, re, csv, json, math, time, zipfile, pathlib, shutil
import urllib.request, urllib.parse

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")   # Windows console
except Exception:
    pass

HERE = pathlib.Path(__file__).parent
MAPDATA = HERE / "mapdata"
BROWSER = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
           "(KHTML, like Gecko) Chrome/126.0 Safari/537.36")

# ---- saved regions: switch airports without re-downloading or losing edits -----
# The full set of files a single airport owns. Snapshotted per airport under
# regions/<ICAO>/ so returning to an airport restores it EXACTLY (incl. hand edits).
REGION_FILES = ["config.js",
                "mapdata/nav_data.js", "mapdata/nav_data.json",
                "mapdata/map_data.js", "mapdata/map_data.json",
                "mapdata/charts_data.js", "mapdata/charts_data.json"]

def _active_id():
    try:
        t = (pathlib.Path(__file__).parent / "config.js").read_text(encoding="utf8")
        return json.loads(t[t.index("{"): t.rindex("}") + 1])["center"]["id"].strip().upper()
    except Exception:
        return None

def save_active_region():
    """Snapshot whatever airport is loaded right now into regions/<ID>/."""
    rid = _active_id()
    if not rid:
        return
    for rel in REGION_FILES:
        src = HERE / rel
        if src.exists():
            dst = HERE / "regions" / rid / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)

def restore_region(icao):
    """If this airport was set up before, copy its saved files back. Returns True."""
    d = HERE / "regions" / icao
    if not (d / "config.js").exists():
        return False
    for rel in REGION_FILES:
        src = d / rel
        if src.exists():
            dst = HERE / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
            os.utime(dst, None)          # bump mtime to NOW so browsers don't serve a
                                         # stale cached copy of the previous airport
    return True

def http(url, data=None, timeout=60, ua="FlightRadarTV-setup/1.0 (personal project)",
         headers=None):
    h = {"User-Agent": ua}
    if headers: h.update(headers)
    req = urllib.request.Request(url, data=data, headers=h)
    return urllib.request.urlopen(req, timeout=timeout).read()

def nm_between(a, b):
    dlat = (a[0]-b[0])*60
    dlon = (a[1]-b[1])*60*math.cos(math.radians((a[0]+b[0])/2))
    return math.hypot(dlat, dlon)

# ---------------------------------------------------------------- airports ---
_AIRPORTS = None
def airports_csv():
    global _AIRPORTS
    if _AIRPORTS is None:
        print("  downloading airport database (OurAirports)…", flush=True)
        txt = http("https://davidmegginson.github.io/ourairports-data/airports.csv",
                   ua="Mozilla/5.0").decode("utf8", "replace")
        _AIRPORTS = list(csv.DictReader(io.StringIO(txt)))
    return _AIRPORTS

def find_airport(icao):
    icao = icao.upper()
    for r in airports_csv():
        if r["ident"].upper() == icao:
            return r
    raise SystemExit(f"airport {icao} not found in database")

def runways_for(icao):
    """{'06L':64, '24R':244, ...} magnetic-ish headings from OurAirports runways.csv."""
    txt = http("https://davidmegginson.github.io/ourairports-data/runways.csv",
               ua="Mozilla/5.0").decode("utf8", "replace")
    out = {}
    for r in csv.DictReader(io.StringIO(txt)):
        if r["airport_ident"].upper() != icao.upper():
            continue
        for lbl, hdg in ((r["le_ident"], r["le_heading_degT"]),
                         (r["he_ident"], r["he_heading_degT"])):
            lbl = (lbl or "").strip()
            if not lbl:
                continue
            try:
                h = round(float(hdg))
            except (ValueError, TypeError):
                m = re.match(r"(\d{1,2})", lbl)          # fall back to the number*10
                h = (int(m.group(1)) % 36) * 10 if m else 0
            out[lbl] = h
    return out

def nearest_wx(center, icao, limit=16, max_nm=95):
    """Nearest airports likely to have a METAR (4-letter ICAO, real service)."""
    cand = []
    for r in airports_csv():
        ident = r["ident"].upper()
        if len(ident) != 4 or not ident[0].isalpha():
            continue
        if r["type"] in ("closed", "heliport", "seaplane_base"):
            continue
        try:
            p = (float(r["latitude_deg"]), float(r["longitude_deg"]))
        except ValueError:
            continue
        d = nm_between(center, p)
        if d > max_nm:
            continue
        # prefer real fields: scheduled service or larger types sort first
        rank = 0 if r["scheduled_service"] == "yes" else (1 if r["type"] != "small_airport" else 2)
        cand.append((rank, d, ident))
    cand.sort(key=lambda t: (t[0], t[1]))
    out, seen = [], set()
    for _, _, ident in cand:
        if ident in seen:
            continue
        seen.add(ident); out.append(ident)
        if len(out) >= limit:
            break
    if icao.upper() in out:                              # keep home field first
        out.remove(icao.upper())
    return [icao.upper()] + out

# --------------------------------------------------------------- live ATC ---
def scrape_liveatc(icao):
    """Best-effort: read LiveATC's page for this ICAO and pull feed mounts + labels.
    LiveATC has no API and may block scripted requests; returns [] on failure so the
    tool falls back to a manual note (edit config.js by hand)."""
    icao = icao.lower()
    try:
        html = http("https://www.liveatc.net/search/?icao=" + icao, timeout=30,
                    ua=BROWSER, headers={"Referer": "https://www.liveatc.net/",
                                         "Accept": "text/html"}).decode("utf8", "replace")
    except Exception as e:
        print(f"  LiveATC lookup blocked ({e}); add channels by hand in config.js")
        return []
    mounts = list(dict.fromkeys(re.findall(r"(?:play|hear)/([A-Za-z0-9_]+)\.pls", html)))
    if not mounts:
        mounts = list(dict.fromkeys(re.findall(r"([A-Za-z0-9_]{3,})\.pls", html)))
    out = []
    for i, m in enumerate(mounts[:4]):
        out.append({"mount": m, "label": m.upper().replace("_", " "),
                    "sub": "", "priority": i + 1})
    return out

# --------------------------------------------------------------- config.js ---
def write_config(icao, args):
    ap = find_airport(icao)
    center = (float(ap["latitude_deg"]), float(ap["longitude_deg"]))
    override = next((a.split("=", 1)[1] for a in args if a.startswith("--center=")), None)
    if override:                                     # frame the view on a custom point
        lat, lon = (float(x) for x in override.split(","))
        center = (lat, lon)
        print(f"  using custom center {lat:.5f}, {lon:.5f}")
    name = ap["name"].upper().replace(" INTERNATIONAL", "").replace(" AIRPORT", "")
    print(f"  {icao} = {name}  ({center[0]:.5f}, {center[1]:.5f})")
    print("  runways…", flush=True)
    rwys = runways_for(icao)
    print("  nearest weather stations…", flush=True)
    wx = nearest_wx(center, icao)
    print("  live ATC channels (LiveATC)…", flush=True)
    atc = scrape_liveatc(icao)
    coslat = math.cos(math.radians(center[0]))
    cfg = {
        "center":      {"id": icao.upper(), "name": name,
                        "lat": round(center[0], 6), "lon": round(center[1], 6)},
        "arrivalRef":  {"lat": round(center[0], 5), "lon": round(center[1], 5)},
        "adsbRadiusNm": 100,
        "overscan": 1.0,
        "atisStation": icao.upper(),
        "tafStation":  icao.upper(),
        "runways": rwys,
        "wxAirports": wx,
        "sigmetBox": {"latMin": round(center[0]-2.6, 3), "latMax": round(center[0]+2.6, 3),
                      "lonMin": round(center[1]-2.6/coslat, 3), "lonMax": round(center[1]+2.6/coslat, 3)},
        "atcChannels": atc or [{"mount": "REPLACE_ME", "label": icao.upper(),
                                "sub": "add from liveatc.net", "priority": 1}],
    }
    banner = ("/* Flight Radar TV -- REGION CONFIG (generated by setup_region.py).\n"
              "   Edit any value and restart the server. To fix ATC audio, find the\n"
              f"   feed name at https://www.liveatc.net/search/?icao={icao.lower()}\n"
              "   and set it as the \"mount\" below. Keep this valid JSON after \"=\". */\n"
              "window.CONFIG = ")
    (HERE / "config.js").write_text(banner + json.dumps(cfg, indent=2) + ";\n",
                                    encoding="utf8")
    print(f"  wrote config.js  (weather: {', '.join(wx[:6])}… ; "
          f"ATC: {', '.join(c['mount'] for c in cfg['atcChannels'])})")
    return cfg


# ------------------------------------------------------------------ CIFP ---
def cifp_file():
    """Download the current FAA CIFP (national nav database) once, cache the
    extracted FAACIFP18 in mapdata/cifp/, and return its path."""
    dst = MAPDATA / "cifp" / "FAACIFP18"
    if dst.exists():
        return dst
    dst.parent.mkdir(parents=True, exist_ok=True)
    print("  finding current CIFP cycle…", flush=True)
    page = http("https://www.faa.gov/air_traffic/flight_info/aeronav/digital_products/cifp/download/").decode("utf8", "replace")
    zips = re.findall(r'href="(https://[^"]*cifp/CIFP_(\d{6})\.zip)"', page)
    today = time.strftime("%y%m%d")
    eff = [(d, u) for (u, d) in zips if d <= today] or [(d, u) for (u, d) in zips]
    url = sorted(eff)[-1][1]
    print(f"  downloading {url.split('/')[-1]} (~50 MB, one time)…", flush=True)
    raw = http(url, timeout=240, ua="Mozilla/5.0")
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        name = next(n for n in z.namelist() if n.upper().endswith("FAACIFP18"))
        dst.write_bytes(z.read(name))
    print(f"  CIFP ready ({dst.stat().st_size//1_000_000} MB)")
    return dst

_LL = re.compile(r"([NS]\d{8})([EW]\d{9})")
def _lat(s): return (1 if s[0]=="N" else -1)*(int(s[1:3])+int(s[3:5])/60+int(s[5:9])/360000)
def _lon(s): return (1 if s[0]=="E" else -1)*(int(s[1:4])+int(s[4:6])/60+int(s[6:10])/360000)

def parse_cifp(center, bbox):
    """Charleston parse_cifp.py logic, generalised: nav data within bbox, approaches
    for airports within ~55 nm of center."""
    S, W, N, E = bbox
    r5 = lambda x: round(x, 5)
    inb = lambda la, lo, pad=0.0: S-pad <= la <= N+pad and W-pad <= lo <= E+pad
    F = cifp_file()
    vors, ndbs, wpts, apts = [], [], [], {}
    vor_ix, ndb_ix, ea_ix, pc_ix, rw_ix, ils_ix = {}, {}, {}, {}, {}, {}
    awy_raw, appr_raw = {}, {}
    appr_apts = set()
    for l in open(F, encoding="latin-1"):
        if not l.startswith("SUSA"): continue
        sec2 = l[4:6]
        if sec2 == "D ":
            m = _LL.search(l)
            if not m: continue
            la, lo = _lat(m[1]), _lon(m[2]); ident = l[13:17].strip()
            rec = {"id": ident, "lat": r5(la), "lon": r5(lo),
                   "f": round(int(l[22:27])/100, 2), "cls": l[27:30].strip(),
                   "name": l[93:123].strip().title()}
            vor_ix[ident] = rec
            if inb(la, lo, 0.3): vors.append(rec)
        elif sec2 == "DB":
            m = _LL.search(l)
            if not m: continue
            la, lo = _lat(m[1]), _lon(m[2]); ident = l[13:17].strip()
            rec = {"id": ident, "lat": r5(la), "lon": r5(lo),
                   "f": round(int(l[22:27])/10, 1), "name": l[93:123].strip().title()}
            ndb_ix[ident] = rec
            if inb(la, lo): ndbs.append(rec)
        elif sec2 == "EA":
            m = _LL.search(l)
            if not m: continue
            la, lo = _lat(m[1]), _lon(m[2]); ident = l[13:18].strip()
            ea_ix[ident] = (r5(la), r5(lo))
            if inb(la, lo): wpts.append({"id": ident, "lat": r5(la), "lon": r5(lo)})
        elif sec2 == "ER":
            rid = l[13:18].strip()
            awy_raw.setdefault(rid, []).append((l[25:29], l[29:34].strip(), l[34:38]))
        elif l[4] == "P" and l[5] == " ":
            icao, sub = l[6:10], l[12]
            if sub == "A":
                m = _LL.search(l)
                if not m: continue
                la, lo = _lat(m[1]), _lon(m[2]); name = l[93:123].strip().title()
                if inb(la, lo) and "Heli" not in name and l[80] == "C":
                    apts[icao] = {"id": icao, "lat": r5(la), "lon": r5(lo),
                                  "name": name, "rwys": []}
                    if nm_between(center, (la, lo)) <= 55:
                        appr_apts.add(icao)
            elif sub == "G":
                m = _LL.search(l)
                if not m: continue
                g = re.search(r"(\d{6})(\d{4})\s*[NS]", l)
                rw_ix[(icao, l[13:18].strip())] = {"lat": r5(_lat(m[1])), "lon": r5(_lon(m[2])),
                    "len": int(g[1]) if g else 0, "brg": (int(g[2])/10) if g else None}
            elif sub == "C":
                m = _LL.search(l)
                if not m: continue
                pc_ix[(icao, l[13:18].strip())] = (r5(_lat(m[1])), r5(_lon(m[2])))
            elif sub == "I" and icao in appr_apts:
                m = _LL.search(l)
                if not m: continue
                after = l[m.end():]
                crs = int(after[:4])/10 if after[:4].isdigit() else None
                g = None
                for g in re.finditer(r"(\d{3})(\d{4})W\d{5}", l): pass
                gs = (int(g[2])/100) if g else 3.0
                if not 2.0 <= gs <= 4.5: gs = 3.0
                ils_ix[(icao, l[27:32].strip())] = {"ident": l[13:18].strip().rstrip("0123456789"),
                    "f": round(int(l[22:27])/100, 2), "crs": crs,
                    # real localizer course is ~700 ft wide at threshold → a few degrees.
                    # The exact value isn't reliably in this record, so use a fixed 4.0°
                    # for the chart-style feather instead of mis-parsing a stray number.
                    "width": 4.0, "gs": gs}
            elif sub == "F" and icao in appr_apts:
                proc, trans = l[13:19].strip(), l[19:25].strip()
                appr_raw.setdefault((icao, proc), {}).setdefault(trans, []).append(
                    (l[26:29], l[29:34].strip(), l[34:38], l[39:43]))

    def mate(rw):
        num = (int(rw[2:4]) + 18 - 1) % 36 + 1
        sfx = {"L": "R", "R": "L", "C": "C", "": ""}.get(rw[4:].strip(), "")
        return f"RW{num:02d}{sfx}"
    for (icao, rw), v in rw_ix.items():
        if icao in apts and rw < mate(rw) and (icao, mate(rw)) in rw_ix:
            o = rw_ix[(icao, mate(rw))]
            apts[icao]["rwys"].append({"a": [v["lat"], v["lon"]], "b": [o["lat"], o["lon"]]})

    def resolve(fix, fsec, icao=None):
        t = fsec[2:4]
        if t == "EA": return ea_ix.get(fix)
        if t[0] == "D":
            r = (vor_ix if t != "DB" else ndb_ix).get(fix)
            return (r["lat"], r["lon"]) if r else None
        if t == "PC": return pc_ix.get((icao, fix)) or ea_ix.get(fix)
        if t == "PG":
            r = rw_ix.get((icao, fix)); return (r["lat"], r["lon"]) if r else None
        if t == "PA":
            r = apts.get(fix); return (r["lat"], r["lon"]) if r else None
        return ea_ix.get(fix)

    awys = []
    for rid, legs in awy_raw.items():
        if rid[0] not in "VT": continue
        legs.sort()
        pts = [(f, resolve(f, s)) for _, f, s in legs]
        chain = []
        for i, (f, p) in enumerate(pts):
            if p is None: continue
            near = inb(*p, 0.02) or (i > 0 and pts[i-1][1] and inb(*pts[i-1][1], 0.02)) \
                   or (i+1 < len(pts) and pts[i+1][1] and inb(*pts[i+1][1], 0.02))
            if near: chain.append([p[0], p[1]])
            elif len(chain) > 1: awys.append({"id": rid, "pts": chain}); chain = []
            else: chain = []
        if len(chain) > 1: awys.append({"id": rid, "pts": chain})

    TYPE = {"I": "ILS OR LOC", "R": "RNAV (GPS)", "V": "VOR", "D": "VOR/DME",
            "L": "LOC", "N": "NDB", "T": "TACAN", "S": "VOR", "X": "LDA", "J": "GLS"}
    best = {}
    rank = lambda p: {"": 0, "Y": 1, "Z": 2}.get(p[5:6].strip() or p[3:4].strip(), 3)
    for (icao, proc) in appr_raw:
        if proc[0] not in "IR": continue
        k = (icao, proc[0], proc[1:3])
        if k not in best or rank(proc) < rank(best[k]): best[k] = proc
    appr = []
    for (icao, proc), groups in sorted(appr_raw.items()):
        kind, rwy = proc[0], proc[1:3]
        if best.get((icao, kind, rwy)) != proc: continue
        out = {"apt": icao, "rwy": rwy,
               "title": f"{TYPE.get(kind, kind)} RWY {rwy.lstrip('0')}", "final": [], "trans": []}
        # attach a localizer (→ ILS feather) ONLY to actual ILS/LOC approaches, never
        # to the RNAV approach that happens to serve the same runway
        ils = None
        if kind in ("I", "L", "X"):
            ils = ils_ix.get((icao, "RW"+rwy)) or next(
                  (v for (a, r), v in ils_ix.items() if a == icao and r.startswith("RW"+rwy)), None)
        if ils: out["ils"] = ils
        fin_key = None
        for tk, legs in groups.items():
            if any(d[3:4] == "M" for _, _, _, d in legs): fin_key = tk; break
        for tk, legs in groups.items():
            legs.sort(); chain = []
            for _, fix, fsec, desc in legs:
                p = resolve(fix, fsec, icao)
                if not p: continue
                role = "faf" if desc[3:4] == "F" else "map" if desc[3:4] == "M" else ""
                if chain and chain[-1]["id"] == fix: continue
                chain.append({"id": fix, "lat": p[0], "lon": p[1], "role": role})
                if role == "map" and tk == fin_key: break
            if not chain: continue
            if tk == fin_key: out["final"] = chain
            else: out["trans"].append(chain)
        if out["final"]: appr.append(out)

    return {"apts": sorted(apts.values(), key=lambda a: a["id"]),
            "vors": vors, "ndbs": ndbs, "wpts": wpts, "awys": awys, "appr": appr}

def parse_sua(bbox):
    """MOA / Restricted / Warning / Alert / Prohibited polygons from CIFP UR records."""
    S, W, N, E = bbox
    F = cifp_file()
    TYPES = {"M": "MOA", "R": "RESTRICTED", "W": "WARNING", "A": "ALERT", "P": "PROHIBITED"}
    areas = {}
    for l in open(F, encoding="latin-1"):
        if not l.startswith("SUSAUR"): continue
        typ = l[8]
        if typ not in TYPES: continue
        a = areas.setdefault((typ, l[9:19].strip()), {"pts": [], "alts": None, "name": None})
        m = _LL.search(l)
        if m: a["pts"].append((round(_lat(m[1]), 5), round(_lon(m[2]), 5)))
        am = re.search(r"([0G][\dND]{4}|FL\d{3})\s*A\s*(\d{5}|FL\d{3}|UNLTD)", l)
        if am and not a["alts"]:
            def alt(x):
                if x.startswith("FL"): return int(x[2:])*100
                if x.strip() == "GND": return 0
                return int(x) if x.isdigit() else 0
            a["alts"] = (alt(am[1]), alt(am[2]))
        nm = l[93:118].strip()
        if nm and not a["name"] and not nm.startswith("FAA"): a["name"] = nm.title()
    sua = []
    for (typ, ident), a in areas.items():
        pts = a["pts"]
        if len(pts) < 3: continue
        if not any(S <= p[0] <= N and W <= p[1] <= E for p in pts): continue
        fl, ce = (a["alts"] or (0, 18000))
        sua.append({"t": TYPES[typ], "id": ident, "name": a["name"] or ident,
                    "fl": fl, "ce": min(ce, 60000), "pts": pts})
    return sua

def fetch_class_airspace(bbox):
    """Class B/C/D control-zone polygons (with floor/ceiling) from the FAA."""
    S, W, N, E = bbox
    url = "https://services6.arcgis.com/ssFJjBXIUyZDrSYZ/arcgis/rest/services/Class_Airspace/FeatureServer/0/query"
    params = urllib.parse.urlencode({
        "where": "CLASS IN ('B','C','D')", "geometry": f"{W},{S},{E},{N}",
        "geometryType": "esriGeometryEnvelope", "inSR": "4326",
        "spatialRel": "esriSpatialRelIntersects",
        "outFields": "NAME,ICAO_ID,CLASS,UPPER_VAL,LOWER_VAL,UPPER_UOM,LOWER_UOM",
        "returnGeometry": "true", "outSR": "4326", "f": "json"})
    # the FAA server sometimes throttles by returning an empty result (no error) — retry
    # a few times so a brief hiccup doesn't permanently drop an airport's Class B/C/D
    j = {"features": []}
    for attempt in range(3):
        try:
            r = json.loads(http(url + "?" + params, timeout=45, ua="Mozilla/5.0"))
            j = r
            if r.get("features"): break               # got airspace — done
        except Exception as e:
            print(f"  Class airspace attempt {attempt+1}/3 failed ({e})")
        if attempt < 2:                               # empty/error → FAA server likely busy
            print(f"  FAA airspace server busy, retrying in {6*(attempt+1)}s…", flush=True)
            time.sleep(6*(attempt+1))
    if not j.get("features"):
        print("  (no Class B/C/D returned — none nearby, or re-run --rebuild later to retry)")
    def ft(v, uom):
        if v is None: return None
        return int(v) if (uom or "FT") == "FT" else int(v) * 100
    out = []
    for f in j.get("features", []):
        a = f["attributes"]; g = f.get("geometry", {})
        cls = a.get("CLASS")
        for ring in g.get("rings", []):
            pts = [[round(y, 5), round(x, 5)] for x, y in ring]     # esri x=lon,y=lat
            if len(pts) < 3: continue
            pts = simplify_ring(pts, 0.0012)                        # ~130 m — FAA rings
            if len(pts) < 3: continue                               # are absurdly dense
            out.append({"cls": cls, "name": (a.get("NAME") or "").title(),
                        "fl": ft(a.get("LOWER_VAL"), a.get("LOWER_UOM")) or 0,
                        "ce": ft(a.get("UPPER_VAL"), a.get("UPPER_UOM")) or 10000,
                        "pts": pts})
    return out

def add_comm(nav):
    """Tower / CTAF frequency per airport from OurAirports."""
    def get(u): return http(u, ua="Mozilla/5.0").decode("utf8", "replace")
    apid = {r["id"]: r["ident"] for r in
            csv.DictReader(io.StringIO(get("https://davidmegginson.github.io/ourairports-data/airports.csv")))}
    freqs = {}
    for row in csv.DictReader(io.StringIO(get("https://davidmegginson.github.io/ourairports-data/airport-frequencies.csv"))):
        ident = apid.get(row["airport_ref"])
        if ident: freqs.setdefault(ident, {})[row["type"].upper()] = row["frequency_mhz"]
    def pick(f):
        for t, v in f.items():
            if "TWR" in t: return ("TWR", v)
        for t in ("CTAF", "CTAF/UNICOM", "UNIC", "UNICOM", "MULTICOM"):
            if t in f: return ("CTAF", f[t])
        for t, v in f.items():
            if "CTAF" in t or "UNIC" in t: return ("CTAF", v)
        return None
    n = 0
    for ap in nav["apts"]:
        p = pick(freqs.get(ap["id"].strip(), {}))
        if not p: continue
        try:
            mhz = ("%.3f" % float(p[1])).rstrip("0")
            if mhz.endswith("."): mhz += "0"
        except ValueError:
            mhz = p[1]
        ap["comm"] = f"{p[0]} {mhz}"; n += 1
    return n

def build_nav(icao, cfg):
    center = (cfg["center"]["lat"], cfg["center"]["lon"])
    bbox = region_bbox(center)
    nav = parse_cifp(center, bbox)
    print(f"  airports {len(nav['apts'])}, vors {len(nav['vors'])}, "
          f"wpts {len(nav['wpts'])}, airways {len(nav['awys'])}, approaches {len(nav['appr'])}")
    nav["sua"] = parse_sua(bbox)
    print(f"  SUA (MOA/restricted/…): {len(nav['sua'])}")
    nav["airspace"] = fetch_class_airspace(bbox)
    ncls = {}
    for a in nav["airspace"]: ncls[a["cls"]] = ncls.get(a["cls"], 0) + 1
    print(f"  Class B/C/D polygons: {sum(ncls.values())} ({ncls})")
    print("  frequencies (OurAirports)…", flush=True)
    print(f"  comm freq on {add_comm(nav)}/{len(nav['apts'])} airports")
    (MAPDATA / "nav_data.json").write_text(json.dumps(nav, separators=(",", ":")), encoding="utf8")
    write_js("nav_data", "NAV", nav)
    return nav

# ------------------------------------------------------------------- map ---
_last_overpass = [0.0]
def overpass(query, timeout=180, cache=None):
    """Query Overpass with polite spacing + retries. If `cache` is given, a
    successful (non-empty) response is saved to mapdata/osm_cache/<cache>.json and
    reused on later runs — so a flaky Overpass doesn't force you to refetch what
    already worked."""
    cf = (MAPDATA / "osm_cache" / f"{cache}.json") if cache else None
    if cf and cf.exists():
        try:
            j = json.loads(cf.read_text(encoding="utf8"))
            if j.get("elements"):
                print(f"    (cached {cache}: {len(j['elements'])} elements)")
                return j
        except Exception:
            pass
    hosts = ("https://overpass-api.de/api/interpreter",
             "https://overpass.kumi.systems/api/interpreter",
             "https://maps.mail.ru/osm/tools/overpass/api/interpreter")
    body = urllib.parse.urlencode({"data": query}).encode()
    per_try = min(timeout, 35)                                   # don't let one slow
    for attempt in range(6):                                     # mirror hang for minutes
        gap = time.time() - _last_overpass[0]                    # be polite: space calls
        if gap < 5: time.sleep(5 - gap)
        host = hosts[attempt % len(hosts)]
        name = host.split("/")[2]
        print(f"    trying {name} (attempt {attempt+1}/6)…", flush=True)
        try:
            d = http(host, data=body, timeout=per_try)
            _last_overpass[0] = time.time()
            j = json.loads(d)
            if cf and j.get("elements"):
                cf.parent.mkdir(parents=True, exist_ok=True)
                cf.write_text(json.dumps(j), encoding="utf8")
            return j
        except Exception as e:
            _last_overpass[0] = time.time()
            reason = "rate-limited/busy" if "429" in str(e) else str(e)
            wait = 6 * (attempt + 1)
            print(f"      {name}: {reason}. waiting {wait}s…", flush=True)
            time.sleep(wait)
    print("    OpenStreetMap is busy right now — skipping this layer for now.")
    print("    Everything else is built; re-run later to add it (it will be quick).")
    return {"elements": []}

def simplify_ring(pts, tol):
    """DP-simplify a polygon ring, handling the closed-ring degeneracy (a ring whose
    first point == last point collapses to 2 pts under plain DP)."""
    if len(pts) > 4 and pts[0] == pts[-1]:
        m = len(pts)//2
        return _dp(pts[:m+1], tol)[:-1] + _dp(pts[m:], tol)
    return _dp(pts, tol)

def _dp(pts, tol):
    if len(pts) < 3: return pts
    keep = [False]*len(pts); keep[0] = keep[-1] = True
    stack = [(0, len(pts)-1)]
    while stack:
        a, b = stack.pop()
        if b <= a+1: continue
        (y1, x1), (y2, x2) = pts[a], pts[b]
        dx, dy = x2-x1, y2-y1; L = math.hypot(dx, dy) or 1e-12
        dmax, imax = -1, -1
        for i in range(a+1, b):
            d = abs(dy*(pts[i][1]-x1) - dx*(pts[i][0]-y1))/L
            if d > dmax: dmax, imax = d, i
        if dmax > tol:
            keep[imax] = True; stack += [(a, imax), (imax, b)]
    return [p for p, k in zip(pts, keep) if k]

def build_map(cfg, args):
    center = (cfg["center"]["lat"], cfg["center"]["lon"])
    S, W, N, E = region_bbox(center)
    TOL = 0.00025
    key = lambda p: (round(p[0], 7), round(p[1], 7))
    inside = lambda p: S <= p[0] <= N and W <= p[1] <= E
    rnd = lambda p: [round(p[0], 5), round(p[1], 5)]

    tag = f"{center[0]:.2f}_{center[1]:.2f}"
    print("  coastline (OpenStreetMap)…", flush=True)
    craw = overpass(f'[out:json][timeout:180];way["natural"="coastline"]({S},{W},{N},{E});out geom;',
                    cache=tag+"_coast")
    ways = [[(p["lat"], p["lon"]) for p in el["geometry"]]
            for el in craw["elements"] if el["type"] == "way" and "geometry" in el]
    # stitch end->start
    polys = [list(w) for w in ways]; changed = True
    while changed:
        changed = False
        starts = {}
        for i, p in enumerate(polys):
            if p: starts.setdefault(key(p[0]), i)
        for i, p in enumerate(polys):
            if not p: continue
            j = starts.get(key(p[-1]))
            if j is not None and j != i and polys[j]:
                polys[i] = p + polys[j][1:]; polys[j] = []; changed = True; break
    polys = [p for p in polys if p]
    closed = [p for p in polys if key(p[0]) == key(p[-1]) and len(p) > 3]
    open_ = [p for p in polys if key(p[0]) != key(p[-1])]

    def cross(a, b):                               # segment × bbox-edge intersections
        hits = []; (y1, x1), (y2, x2) = a, b
        for c, is_lat in ((S, 1), (N, 1), (W, 0), (E, 0)):
            if is_lat and (y1-c)*(y2-c) < 0:
                t = (c-y1)/(y2-y1); x = x1+t*(x2-x1)
                if W <= x <= E: hits.append((t, (c, x)))
            elif not is_lat and (x1-c)*(x2-c) < 0:
                t = (c-x1)/(x2-x1); y = y1+t*(y2-y1)
                if S <= y <= N: hits.append((t, (y, c)))
        return [p for _, p in sorted(hits)]
    def clip(poly):                                # inside pieces, ending exactly on bbox
        out, cur = [], []
        for i in range(len(poly)):
            p = poly[i]
            if i:
                for h in cross(poly[i-1], p):
                    if cur: cur.append(h); out.append(cur); cur = []
                    else:   cur = [h]
            if inside(p): cur.append(p)
            elif cur: out.append(cur); cur = []
        if cur: out.append(cur)
        return [c for c in out if len(c) > 1]
    coasts = []
    for p in open_: coasts += clip(p)
    rings_in = []
    for p in closed:
        if all(inside(q) for q in p): rings_in.append(p)
        else: coasts += clip(p)

    def area(p):
        return sum(p[i][1]*p[i+1][0] - p[i+1][1]*p[i][0] for i in range(len(p)-1))/2

    # boundary walk: chain shoreline pieces along the bbox edge into closed water
    # polygons — THIS is what fills the tidal estuaries (Cooper/Wando/Ashley), not
    # just the open ocean. (OSM coastline keeps water on the right of travel.)
    pieces = coasts
    def t_of(p):                                   # clockwise boundary param 0..4 from NW
        y, x = p
        if abs(y-N) < 1e-6: return (x-W)/(E-W)
        if abs(x-E) < 1e-6: return 1+(N-y)/(N-S)
        if abs(y-S) < 1e-6: return 2+(E-x)/(E-W)
        if abs(x-W) < 1e-6: return 3+(y-S)/(N-S)
        return None
    CORNERS = {1.0: (N, E), 2.0: (S, E), 3.0: (S, W), 4.0: (N, W)}
    info = [(t_of(p[0]), t_of(p[-1])) for p in pieces]
    unused = [i for i in range(len(pieces)) if info[i][0] is not None and info[i][1] is not None]
    water = []
    while unused:
        i0 = unused.pop(0)
        poly = list(pieces[i0]); start_t = info[i0][0]; cur_t = info[i0][1]
        for _ in range(4000):
            cands = [(((info[j][0]-cur_t) % 4), j) for j in unused]
            cands.append((((start_t-cur_t) % 4), -1))
            d, j = min(cands)
            for k in range(1, 5):                  # add bbox corners swept while walking
                ct = math.ceil(cur_t)+k-1
                if 0 < (ct-cur_t) % 4 < d: poly.append(CORNERS[(ct-1) % 4 + 1.0])
            if j == -1:
                water.append(poly); break
            poly += pieces[j]; unused.remove(j); cur_t = info[j][1]

    islands = [p for p in rings_in if area(p) > 0]
    lake_rings = [p for p in rings_in if area(p) <= 0]

    def simp(pts, tol):
        # DP is degenerate on a closed ring (start==end → zero-length baseline
        # collapses it to 2 pts) — split the ring in half and simplify each part
        if len(pts) > 4 and key(pts[0]) == key(pts[-1]):
            m = len(pts)//2
            return _dp(pts[:m+1], tol)[:-1] + _dp(pts[m:], tol)
        return _dp(pts, tol)
    def prep(ps, tol, minp):
        out = []
        for p in ps:
            s = simp(p, tol)
            if len(s) >= minp: out.append([rnd(q) for q in s])
        return out
    coasts_s = prep(coasts, TOL, 2)
    islands_s = prep(islands, TOL, 4)
    water_s = prep(water, TOL, 4)                  # filled water polygons (ocean + estuaries)
    print(f"    {len(coasts_s)} shoreline lines, {len(islands_s)} islands, {len(water_s)} water polys")

    print("  rivers + lakes (OpenStreetMap)…", flush=True)
    coslat = math.cos(math.radians(center[0]))
    rb = (round(center[0]-1.3, 3), round(center[1]-1.3/coslat, 3),
          round(center[0]+1.3, 3), round(center[1]+1.3/coslat, 3))
    rraw = overpass(f'[out:json][timeout:120];way["waterway"="river"]({rb[0]},{rb[1]},{rb[2]},{rb[3]});out geom;',
                    150, cache=tag+"_rivers")
    rivers_s = []
    for el in rraw["elements"]:
        if el["type"] != "way" or "geometry" not in el: continue
        if not (el.get("tags") or {}).get("name"): continue   # named rivers only — the
        w = [(p["lat"], p["lon"]) for p in el["geometry"]]     # ~300 unnamed tidal creeks
        s = _dp(w, TOL)                                        # are handled by the water fill
        if len(s) >= 2 and sum(math.hypot(s[i+1][0]-s[i][0], s[i+1][1]-s[i][1]) for i in range(len(s)-1)) > 0.02:
            rivers_s.append([rnd(q) for q in s])
    # only true lakes / reservoirs / ponds — NOT tidal rivers, estuaries or marsh
    # (those are natural=water water=river / wetland and fill as bogus blobs on land)
    lraw = overpass(
        f'[out:json][timeout:120];('
        f'way["natural"="water"]["water"~"^(lake|reservoir|pond)$"]({rb[0]},{rb[1]},{rb[2]},{rb[3]});'
        f'relation["natural"="water"]["water"~"^(lake|reservoir|pond)$"]({rb[0]},{rb[1]},{rb[2]},{rb[3]});'
        f');out geom;', 150, cache=tag+"_lakes")
    def stitch_rings(segs):                          # merge split outer ways → rings
        polys = [list(s) for s in segs]; changed = True
        while changed:
            changed = False
            for i, p in enumerate(polys):
                if not p: continue
                for j, q in enumerate(polys):
                    if i == j or not q: continue
                    if   key(p[-1]) == key(q[0]):  polys[i] = p + q[1:]
                    elif key(p[-1]) == key(q[-1]): polys[i] = p + q[-2::-1]
                    elif key(p[0])  == key(q[-1]): polys[i] = q + p[1:]
                    elif key(p[0])  == key(q[0]):  polys[i] = q[::-1] + p[1:]
                    else: continue
                    polys[j] = []; changed = True; break
                if changed: break
        return [p for p in polys if p and key(p[0]) == key(p[-1]) and len(p) > 8]

    lakes_raw = []                                    # (name, closed ring)
    for el in lraw["elements"]:
        nm = (el.get("tags") or {}).get("name", "")
        if el["type"] == "way" and "geometry" in el:
            p = [(q["lat"], q["lon"]) for q in el["geometry"]]
            if len(p) > 3 and key(p[0]) == key(p[-1]): lakes_raw.append((nm, p))
        elif el["type"] == "relation":                # outer ring may be split in pieces
            segs = [[(q["lat"], q["lon"]) for q in m["geometry"]]
                    for m in el.get("members", []) if m.get("role") == "outer" and "geometry" in m]
            for r in stitch_rings(segs): lakes_raw.append((nm, r))
    lk = []
    for nm, p in lakes_raw:
        a = abs(area(p))
        # real lakes ≳3 sq mi (Moultrie/Marion); anonymous water only if huge — skips
        # tiny ponds and the coastal impoundments/marsh that read as bogus blobs
        if a < 8e-4: continue
        if not nm and a < 3e-3: continue
        s = simp(p, 0.001)
        if len(s) >= 8: lk.append((a, [rnd(q) for q in s]))
    lk.sort(key=lambda t: -t[0])
    lakes_s = [p for _, p in lk[:15]]
    print(f"    {len(rivers_s)} rivers, {len(lakes_s)} lakes")

    print("  terrain elevation (OpenTopoData NED)…", flush=True)
    elev = fetch_elev(S, W, N, E)
    out = {"bbox": [S, W, N, E], "water": water_s, "islands": islands_s,
           "coasts": coasts_s, "rivers": rivers_s, "lakes": lakes_s, "elev": elev}
    (MAPDATA / "map_data.json").write_text(json.dumps(out, separators=(",", ":")), encoding="utf8")
    write_js("map_data", "MAP", out)
    print(f"  wrote map_data.js ({(MAPDATA/'map_data.js').stat().st_size//1024} KB)")

def fetch_elev(S, W, N, E, ROWS=64, COLS=80):
    pts = [(S+(N-S)*r/(ROWS-1), W+(E-W)*c/(COLS-1)) for r in range(ROWS) for c in range(COLS)]
    grid = []
    for i in range(0, len(pts), 100):
        locs = "|".join(f"{a:.5f},{b:.5f}" for a, b in pts[i:i+100])
        body = json.dumps({"locations": locs}).encode()
        for attempt in range(4):
            try:
                j = json.loads(http("https://api.opentopodata.org/v1/ned10m", data=body, timeout=60,
                                    headers={"Content-Type": "application/json"}))
                grid += [(res["elevation"] or 0) for res in j["results"]]
                break
            except Exception:
                time.sleep(2 + attempt*2)
        else:
            grid += [0]*len(pts[i:i+100])           # gaps → sea level (e.g. offshore)
        time.sleep(1.1)
    return {"s": S, "w": W, "n": N, "e": E, "rows": ROWS, "cols": COLS,
            "m": [round(max(0, e), 1) for e in grid]}

# ---------------------------------------------------------------- charts ---
def bake_charts(cfg):
    try:
        from PIL import Image, ImageFilter
    except ImportError:
        print("  installing Pillow (image library, one time)…", flush=True)
        import subprocess
        subprocess.run([sys.executable, "-m", "pip", "install", "--quiet", "pillow"])
        from PIL import Image, ImageFilter
    import base64
    ctr = (cfg["center"]["lat"], cfg["center"]["lon"])
    COS = math.cos(math.radians(ctr[0])); W_OUT, H_OUT = 3120, 2160
    BASES = {
     "sec": ("https://tiles.arcgis.com/tiles/ssFJjBXIUyZDrSYZ/arcgis/rest/services/VFR_Sectional/MapServer/tile/{z}/{y}/{x}",
             80, True, {"close": 12, "near": 12, "far": 10}),
     "ifr": ("https://tiles.arcgis.com/tiles/ssFJjBXIUyZDrSYZ/arcgis/rest/services/IFR_AreaLow/MapServer/tile/{z}/{y}/{x}",
             78, True, {"close": 11, "near": 11, "far": 10}),
     "sat": ("https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
             62, False, {"close": 13, "near": 12, "far": 10}),
     "dark": ("https://a.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}.png",
              70, False, {"close": 13, "near": 12, "far": 10}),
    }
    TIERS = {"close": (26.0, 18.0), "near": (42.0, 29.0), "far": (90.0, 62.0)}
    mx = lambda lon: (lon+180)/360
    my = lambda lat: (1-math.asinh(math.tan(math.radians(lat)))/math.pi)/2
    out = {}
    for bn, (tpl, q, sharp, zooms) in BASES.items():
        out[bn] = {}
        for tn, (hw, hh) in TIERS.items():
            z = zooms[tn]
            Sx = ctr[0]-hh/60; Nx = ctr[0]+hh/60
            Wl = ctr[1]-hw/(60*COS); El = ctr[1]+hw/(60*COS)
            wp = 256*2**z
            tx0 = int(mx(Wl)*wp)//256; tx1 = int(mx(El)*wp)//256
            ty0 = int(my(Nx)*wp)//256; ty1 = int(my(Sx)*wp)//256
            big = Image.new("RGB", ((tx1-tx0+1)*256, (ty1-ty0+1)*256), (0, 0, 0))
            ok = 0
            for ty in range(ty0, ty1+1):
                for tx in range(tx0, tx1+1):
                    try:
                        t = Image.open(io.BytesIO(http(tpl.format(z=z, x=tx, y=ty), timeout=40,
                            ua="Mozilla/5.0 (FlightRadarTV chart prep)"))).convert("RGB")
                        big.paste(t, ((tx-tx0)*256, (ty-ty0)*256)); ok += 1
                    except Exception: pass
                    time.sleep(0.02)
            sx0 = mx(Wl)*wp - tx0*256; sx1 = mx(El)*wp - tx0*256
            im = Image.new("RGB", (W_OUT, H_OUT))
            for y in range(H_OUT):
                lat = Nx-(y+0.5)/H_OUT*(Nx-Sx); sy = my(lat)*wp - ty0*256
                im.paste(big.crop((int(sx0), int(sy), int(sx1), int(sy)+1)).resize((W_OUT, 1), Image.LANCZOS), (0, y))
            if sharp: im = im.filter(ImageFilter.UnsharpMask(radius=1.4, percent=80, threshold=2))
            buf = io.BytesIO(); im.save(buf, "WEBP", quality=q, method=5)
            out[bn][tn] = {"S": round(Sx, 5), "W": round(Wl, 5), "N": round(Nx, 5), "E": round(El, 5),
                           "img": "data:image/webp;base64,"+base64.b64encode(buf.getvalue()).decode()}
            print(f"    {bn}/{tn} z{z}: {ok} tiles, {buf.getbuffer().nbytes//1024} KB", flush=True)
    (MAPDATA / "charts_data.json").write_text(json.dumps(out, separators=(",", ":")), encoding="utf8")
    write_js("charts_data", "CHARTS", out)
    print(f"  wrote charts_data.js ({(MAPDATA/'charts_data.js').stat().st_size//1024} KB)")

def region_bbox(center):
    coslat = math.cos(math.radians(center[0]))
    return (round(center[0]-2.4, 3), round(center[1]-2.4/coslat, 3),
            round(center[0]+2.4, 3), round(center[1]+2.4/coslat, 3))

def write_js(stem, varname, obj):
    js = f"const {varname}=" + json.dumps(obj, separators=(",", ":")) + ";\n"
    (MAPDATA / f"{stem}.js").write_text(js, encoding="utf8")


if __name__ == "__main__":
    argv = [a for a in sys.argv[1:] if not a.startswith("--")]
    args = set(a for a in sys.argv[1:] if a.startswith("--"))
    if not argv:
        raise SystemExit(__doc__)
    icao = argv[0].upper()
    if not re.fullmatch(r"[A-Z]{3,4}\d?", icao):
        raise SystemExit(f"'{icao}' doesn't look like an ICAO id (e.g. KLAX)")
    if "--map-only" in args:                          # fast iteration: rebuild map only
        t = (HERE / "config.js").read_text(encoding="utf8")
        cfg = json.loads(t[t.index("{"): t.rindex("}")+1])
        print(f"=== rebuilding map only for {cfg['center']['id']} ===")
        build_map(cfg, args)
        raise SystemExit(0)
    MAPDATA.mkdir(parents=True, exist_ok=True)        # fresh clone may not have it yet
    # remember the airport that's loaded now, so you can return to it exactly later
    save_active_region()
    if "--rebuild" not in args and restore_region(icao):
        print(f"\n✔ Restored your saved {icao} setup instantly (no download needed).")
        print("  Restart the server (START-RADAR) and reload the app.")
        print(f"  (To rebuild it from fresh data instead: python setup_region.py {icao} --rebuild)")
        raise SystemExit(0)
    print(f"\n=== Flight Radar TV — setting up {icao} ===")
    print("[1/4] airport + config.js")
    cfg = write_config(icao, args)
    print("[2/4] nav: approaches, navaids, airways, airspace, frequencies")
    build_nav(icao, cfg)
    print("[3/4] map: coastline, rivers, lakes, terrain")
    build_map(cfg, args)
    if "--no-charts" in args:
        print("[4/4] charts: skipped (--no-charts)")
    else:
        print("[4/4] charts: VFR sectional + IFR-low + satellite (slow, ~a few min)")
        try:
            bake_charts(cfg)
        except Exception as e:                        # map/nav already done — don't lose them
            print(f"  charts failed ({e}); the app still works, just without the paper")
            print(f"  charts. Re-run later to add them: python setup_region.py {icao}")
    save_active_region()                               # snapshot the freshly-built airport
    print(f"\n✔ {icao} is ready. Restart the server (START-RADAR) and reload the app.")
