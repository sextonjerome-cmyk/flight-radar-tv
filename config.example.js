/* Flight Radar TV -- REGION CONFIG (EXAMPLE ONLY).

   You normally do NOT write this by hand. Run SETUP-AIRPORT (or
   `python setup_region.py KXXX`) and it generates your real config.js for you,
   filled in for whatever airport you choose.

   This example just shows the format -- handy if you ever want to hand-fix one
   value, most commonly an ATC audio channel (find the feed name at
   https://www.liveatc.net/search/?icao=xxxx and set it as "mount"). */

window.CONFIG = {
  "center":      {"id": "KJFK", "name": "NEW YORK", "lat": 40.63975, "lon": -73.77893},
  "arrivalRef":  {"lat": 40.63975, "lon": -73.77893},
  "adsbRadiusNm": 100,
  "overscan": 1.0,

  "atisStation": "KJFK",
  "tafStation":  "KJFK",
  "runways": {"4L": 43, "22R": 223, "13L": 133, "31R": 313, "13R": 133, "31L": 313},
  "wxAirports": ["KJFK", "KLGA", "KEWR", "KTEB", "KHPN", "KISP"],
  "sigmetBox": {"latMin": 38.0, "latMax": 43.2, "lonMin": -77.2, "lonMax": -70.4},
  "atcChannels": [
    {"mount": "kjfk_twr", "label": "JFK TWR", "sub": "119.10", "priority": 1}
  ]
};
