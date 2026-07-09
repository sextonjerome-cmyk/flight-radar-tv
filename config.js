/* Flight Radar TV -- REGION CONFIG.
   This is the one file you edit to move the whole display to another airport.
   Change "center" to your field, adjust the weather airports and ATC channels,
   then restart the server. To also regenerate the map, charts and nav data for
   a faraway region (e.g. California), run:  python setup_region.py KXXX
   Both the web app and server.py read this exact file. Keep it valid JSON
   after the "=" (double quotes, no trailing commas, no braces in comments). */
window.CONFIG = {
  "center":      {"id": "KCHS", "name": "CHARLESTON", "lat": 32.743691, "lon": -80.107315},
  "arrivalRef":  {"lat": 32.89865, "lon": -80.04051},
  "adsbRadiusNm": 100,
  "overscan": 1.0,

  "atisStation": "KCHS",
  "tafStation":  "KCHS",
  "runways": {"15": 154, "33": 334, "03": 31, "21": 211},
  "wxAirports": ["KCHS","KJZI","KLRO","KDYB","KMKS","KSAV","KCAE","KMYR","KHXD","KNBC","KARW","KGGE","KFLO","KCRE","KSVN","KOGB"],
  "sigmetBox": {"latMin": 30.5, "latMax": 35.5, "lonMin": -83.5, "lonMax": -76.5},
  "atcChannels": [
    {"mount": "kchs",      "label": "CHS",     "sub": "TWR·APP·GND", "priority": 1},
    {"mount": "ksav1_app", "label": "SAV APP", "sub": "120.40",               "priority": 2},
    {"mount": "ksav1_zjx", "label": "ZJX CTR", "sub": "HI SECTORS",           "priority": 3}
  ]
};
