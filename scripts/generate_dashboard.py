"""
Build the air-quality model verification dashboard: ONE self-contained html
with a Leaflet map, per-station Plotly time series and HMS fire detections.

Settings live in config.yaml. Run:  python generate_dashboard.py [config.yaml]
"""
import glob
import json
import math
import os
import re
import sys
from collections import Counter

import pandas as pd
import yaml

# =========================================================================
# 1. SETTINGS
# =========================================================================
CFG_FILE = sys.argv[1] if len(sys.argv) > 1 else "config.yaml"
with open(CFG_FILE) as f:
    cfg = yaml.safe_load(f)

CYCLE = pd.Timestamp(cfg["cycle"])
WIN_START = CYCLE - pd.Timedelta(hours=cfg["window_hours_before"])
WIN_END = CYCLE + pd.Timedelta(hours=cfg["window_hours_after"])
PLATFORMS = cfg["platforms"]
DECIMALS = cfg.get("decimals") or {}
PLOTLY_CDN = "https://cdn.plot.ly/plotly-2.30.0.min.js"


def decimals_for(var):
    """Decimal places for a variable (config 'decimals', else its 'default')."""
    return int(DECIMALS.get(var, DECIMALS.get("default", 2)))


def rnd(v, nd):
    """Round to nd decimals; NaN/None -> None (JSON null = gap in the plot)."""
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return None
    r = round(float(v), nd)
    return int(r) if r.is_integer() else r


def js_literal(obj):
    """Compact JSON that is also safe inside <script> (no '</script>' breakouts)."""
    return json.dumps(obj, separators=(",", ":"), allow_nan=False).replace("</", "<\\/")


# Discrete colour scales from config.yaml. Bound i = lower edge of bin i. A variable
# uses its own 'colors' if given, otherwise the first len(bounds) default colours.
color_scales = {}
cs = cfg.get("color_scales") or {}
default_colors = cs.get("default_colors", [])
for var, spec in (cs.get("variables") or {}).items():
    bounds = [float(b) for b in spec["bounds"]]
    if bounds != sorted(bounds):
        sys.exit(f"color_scales: bounds for '{var}' must be increasing")
    if "colors" in spec:
        colors = spec["colors"]
        if len(colors) != len(bounds):
            sys.exit(f"color_scales: '{var}' has {len(bounds)} bounds but {len(colors)} colors (need one per bound)")
    else:
        if len(bounds) > len(default_colors):
            sys.exit(f"color_scales: '{var}' has {len(bounds)} bounds but only {len(default_colors)} "
                     f"default colors; give it its own 'colors' list")
        colors = default_colors[:len(bounds)]
    color_scales[str(var)] = {"bounds": bounds, "colors": list(colors)}
print(f"Colour scales for: {', '.join(color_scales) or 'none'}")

# =========================================================================
# 2. STATION CSVs  ->  {platform: {station_id: {meta, data: {species: ...}}}}
# =========================================================================
# MELODIES-MONET writes one CSV per site:
#   <PLOT_OUTPUT_DIR>/<species>/<platform>/plot_grp1.timeseries.<species>.<start>.<end>.site[id].<site name>.csv
# columns: time, [time_local], siteid, latitude, longitude, <species> (= observation),
#          <MODEL>_<YYYYMMDD>-<HH>Z (one column per model run)
MODEL_COL = re.compile(r"^(?P<model>.+)_(?P<init>\d{8})-(?P<hh>\d{2})Z$")
SITE_NAME = re.compile(r"\.site(?:id)?\.(?P<name>.+)\.csv$")
PLAT_ALIAS = cfg.get("platform_aliases") or {}       # workflow folder name -> dashboard platform
SPEC_ALIAS = cfg.get("species_aliases") or {}        # workflow folder name -> dashboard variable

platforms_db = {p: {} for p, pc in PLATFORMS.items() if pc.get("type") != "fires"}
model_runs = {}            # column -> {"model", "init" (Timestamp), "has_data"}
skipped = Counter()

for fpath in sorted(glob.glob(cfg["paths"]["station_csvs"], recursive=True)):
    wf_species = os.path.basename(os.path.dirname(os.path.dirname(fpath)))
    wf_plat = os.path.basename(os.path.dirname(fpath))
    plat = PLAT_ALIAS.get(wf_plat, wf_plat)
    species = SPEC_ALIAS.get(wf_species, wf_species)
    if plat not in platforms_db:
        skipped[f"platform '{wf_plat}' not in config"] += 1
        continue
    df = pd.read_csv(fpath)
    if df.empty or wf_species not in df.columns or "time" not in df.columns:
        skipped["empty or without an observation column"] += 1
        continue
    m = SITE_NAME.search(os.path.basename(fpath))
    name = m.group("name") if m else os.path.basename(fpath)[:-4]
    sid = str(df["siteid"].iloc[0]) if "siteid" in df.columns else name
    lat, lon = df["latitude"].dropna(), df["longitude"].dropna()
    if lat.empty or lon.empty:
        skipped["no latitude/longitude"] += 1
        continue
    st = platforms_db[plat].setdefault(sid, {
        "name": name, "lat": round(float(lat.iloc[0]), 4), "lon": round(float(lon.iloc[0]), 4), "data": {}})
    nd = decimals_for(species)
    series = {"Observation": [rnd(x, nd) for x in df[wf_species].tolist()]}
    for c in df.columns:
        mm = MODEL_COL.match(c)
        if not mm:
            continue                                # time_local, siteid, latitude, ...
        series[c] = [rnd(x, nd) for x in df[c].tolist()]
        run = model_runs.setdefault(c, {"model": mm["model"], "has_data": False,
                                        "init": pd.Timestamp(f"{mm['init']} {mm['hh']}:00")})
        run["has_data"] |= bool(df[c].notna().any())
    st["data"][species] = {
        "time": pd.to_datetime(df["time"]).dt.strftime("%Y-%m-%d %H:%M").tolist(),
        "series": series,
    }
for why, n in skipped.items():
    print(f"  skipped {n} CSV files: {why}")
print(f"Model runs found: {len(model_runs)} ({sum(not r['has_data'] for r in model_runs.values())} without any data)")

def platform_payload(stations):
    """Compact data for one platform.

    species:  {sp: {columns: [...], time: [...]}}  -> column order + shared time axis
    stations: {id: {name, lat, lon, obs_max: {sp: max}, d: {sp: {v: [[col0], [col1], ...], t?: [...]}}}}
    A station only carries its own 't' when its time axis differs from the shared one.
    """
    species_meta = {}
    for st in stations.values():
        for sp, d in st["data"].items():
            m = species_meta.setdefault(sp, {"columns": [], "times": Counter()})
            m["columns"] += [c for c in d["series"] if c not in m["columns"]]
            m["times"][tuple(d["time"])] += 1
    for m in species_meta.values():
        if "Observation" in m["columns"]:           # Observation always first
            m["columns"].remove("Observation")
            m["columns"].insert(0, "Observation")
        m["time"] = list(m.pop("times").most_common(1)[0][0])

    out = {}
    for sid, st in stations.items():
        e = {"name": st["name"], "lat": st["lat"], "lon": st["lon"], "obs_max": {}, "d": {}}
        for sp, d in st["data"].items():
            entry = {"v": [d["series"].get(c) for c in species_meta[sp]["columns"]]}
            if d["time"] != species_meta[sp]["time"]:
                entry["t"] = d["time"]
            e["d"][sp] = entry
            obs = [x for x in d["series"].get("Observation", []) if x is not None]
            e["obs_max"][sp] = max(obs) if obs else None
        out[sid] = e
    return {"species": species_meta, "stations": out}


# =========================================================================
# 3. HMS FIRE DETECTIONS (reference only, not compared against models)
#    One entry per unique (Lon, Lat) inside the window. FRP time series only
#    for GOES fires seen more than once (geostationary = fixed grid).
# =========================================================================
HMS_COLS = ["Lon", "Lat", "YearDay", "Time", "Satellite", "Method", "Ecosystem", "FRP"]
GAP_MIN = cfg["hms"]["gap_minutes"]
FRP_DEC = decimals_for("FRP")

days = pd.date_range(WIN_START.normalize(), (WIN_END - pd.Timedelta(seconds=1)).normalize(), freq="D")
hms_files = [cfg["paths"]["hms_fires"].format(date=d) for d in days]
for f in hms_files:
    print(f"  HMS file {'found  ' if os.path.exists(f) else 'MISSING'}: {f}")
hms_list = [pd.read_csv(f, names=HMS_COLS, skiprows=1, header=None, skipinitialspace=True)
            for f in hms_files if os.path.exists(f)]

# Column arrays (index i = one fire location, sorted small -> large FRP)
fires = {"lon": [], "lat": [], "sat": [], "frp": [], "n": [], "m": [], "eco": [],
         "t": [],              # minutes after t0 of the (first) detection; null = has a series
         "methods": [],
         "t0": WIN_START.strftime("%Y-%m-%dT%H:%M:00Z"),
         "minutes": int((WIN_END - WIN_START) / pd.Timedelta(minutes=1))}
fire_series = {}               # i -> {"t": [minutes after t0 (null point = gap)], "frp": [...]}
if hms_list:
    hms = pd.concat(hms_list, ignore_index=True).drop_duplicates()
    hms["Satellite"] = hms["Satellite"].str.strip()
    hms["Method"] = hms["Method"].str.strip()
    hms["FRP"] = hms["FRP"].where(hms["FRP"] >= 0)          # -999 (e.g. ANALYSIS) -> NaN
    # YearDay (YYYYDDD) + Time (HHMM) -> UTC; a daily file holds a few next-day detections
    hms["t"] = (pd.to_datetime(hms["YearDay"].astype(str), format="%Y%j")
                + pd.to_timedelta(hms["Time"] // 100, unit="h")
                + pd.to_timedelta(hms["Time"] % 100, unit="m"))
    hms = hms[(hms["t"] >= WIN_START) & (hms["t"] < WIN_END)].sort_values("t")
    hms["tmin"] = ((hms["t"] - WIN_START) / pd.Timedelta(minutes=1)).astype(int)

    groups = [(g["FRP"].max(), lon, lat, g) for (lon, lat), g in hms.groupby(["Lon", "Lat"])]
    groups.sort(key=lambda x: (-1 if pd.isna(x[0]) else x[0]))   # biggest drawn last (on top)

    for i, (fmax, lon, lat, g) in enumerate(groups):
        sat, method, n = g["Satellite"].iloc[0], g["Method"].iloc[0], len(g)
        has_ts = sat.startswith("GOES") and n > 1
        if has_ts:
            tt, ff, prev = [], [], None
            for tm, v in zip(g["tmin"], g["FRP"]):
                if prev is not None and tm - prev > GAP_MIN:     # null point = line break
                    tt.append(int(prev) + 1)
                    ff.append(None)
                tt.append(int(tm))
                ff.append(rnd(v, FRP_DEC))
                prev = tm
            fire_series[i] = {"t": tt, "frp": ff}
        if method not in fires["methods"]:
            fires["methods"].append(method)
        fires["lon"].append(round(float(lon), 4))
        fires["lat"].append(round(float(lat), 4))
        fires["sat"].append(sat)
        fires["frp"].append(rnd(fmax, FRP_DEC))
        fires["n"].append(int(n))
        fires["m"].append(fires["methods"].index(method))
        fires["eco"].append(int(g["Ecosystem"].iloc[0]))
        fires["t"].append(None if has_ts else int(g["tmin"].iloc[0]))

print(f"HMS: {len(fires['lon'])} fire locations between {WIN_START} and {WIN_END} "
      f"({len(fire_series)} with time series)")

# =========================================================================
# 4. COLLECT ALL PLATFORMS AND WRITE THE HTML
# =========================================================================
all_data, counts = {}, []
for plat, pc in PLATFORMS.items():
    if pc.get("type") == "fires":
        all_data[plat] = {"fires": fires, "series": fire_series}
        counts.append(f"{plat}: {len(fires['lon'])} fires")
    else:
        all_data[plat] = platform_payload(platforms_db[plat])
        counts.append(f"{plat}: {len(all_data[plat]['stations'])} stations")

# Models panel: built from the model runs found in the CSVs. config.yaml 'models' sets the
# order and colour of each model and the line styles (newest run first); models not listed
# there are added at the end with fallback colours. Public names from model_display_names.
mcfg = cfg["models"]
display_names = cfg.get("model_display_names") or {}
styles = mcfg.get("line_styles") or ["solid", "dash", "dot", "dashdot"]
fallback = mcfg.get("fallback_colors") or ["#17becf", "#bcbd22", "#e377c2", "#7f7f7f", "#ff7f0e"]
known = list(mcfg.get("groups") or {})
found = sorted({r["model"] for r in model_runs.values()})
obs = mcfg.get("observation") or {}
models = [{"group": "Observation", "label": obs.get("label", "Observation"), "items": [{
    "id": "Observation", "label": obs.get("label", "Observation"), "color": obs.get("color", "#000000"),
    "style": "solid", "obs": True, "has_data": True, "every": 1}]}]
extra = [g for g in found if g not in known]
for k, g in enumerate([g for g in known if g in found] + extra):
    gcfg = (mcfg["groups"].get(g) or {}) if g in known else {}
    color = gcfg.get("color") or fallback[k % len(fallback)]
    every = gcfg.get("output_hours", mcfg.get("default_output_hours", 1))   # hours between model outputs
    runs = sorted((c for c, r in model_runs.items() if r["model"] == g),
                  key=lambda c: model_runs[c]["init"], reverse=True)       # newest first
    models.append({"group": g, "label": display_names.get(g, g), "color": color, "items": [{
        "id": c, "label": model_runs[c]["init"].strftime("%Y-%m-%d %HZ"), "color": color, "every": every,
        "style": styles[j % len(styles)], "has_data": model_runs[c]["has_data"]} for j, c in enumerate(runs)]})

# Settings the page needs (everything else stays in Python)
page_cfg = {
    "platforms": PLATFORMS,
    "variables": cfg["variables"],          # {variable: unit}, button order
    "models": models,
    "map": cfg["map"],
    "stations": cfg["stations"],
    "hms": cfg["hms"],
    "colorScales": color_scales,
    "decimals": {v: decimals_for(v) for v in cfg["variables"]},
    "cycle": CYCLE.strftime("%Y-%m-%d %H:%M UTC"),
    "cycleDate": CYCLE.strftime("%Y-%m-%d"),
    "window": [WIN_START.strftime("%Y-%m-%d %H:%M"), WIN_END.strftime("%Y-%m-%d %H:%M")],   # x-axis range
    "dateNav": cfg.get("date_navigation") or None,
}
pop = cfg["popup"]

DASHBOARD_TEMPLATE = r"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Air Quality Model Verification System</title>
    <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
    <link rel="stylesheet" href="https://unpkg.com/leaflet.markercluster@1.5.3/dist/MarkerCluster.css" />
    <link rel="stylesheet" href="https://unpkg.com/leaflet.markercluster@1.5.3/dist/MarkerCluster.Default.css" />
    <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
    <script src="https://unpkg.com/leaflet.markercluster@1.5.3/dist/leaflet.markercluster.js"></script>
    <script src="__PLOTLY__"></script>
    <style>
        /* Colours for the two themes (dark = default; body.light switches) */
        :root { --bg: __DARK_BG__; --fg: #ededed; --title: #f5f5f5; --rule: #2e2e2e; --border: #2a2a2a;
                --btn-bg: #262626; --btn-fg: #e5e5e5; --btn-border: #404040; --btn-hover: #333333;
                --hdr-fg: #f1f5f9; --row-fg: #d4d4d4; --map-bg: #111111;
                --legend-bg: rgba(23,23,23,0.88); --legend-fg: #ededed; --legend-hover: #333333; --muted: #9a9a9a; }
        body.light { --bg: __LIGHT_BG__; --fg: #1f2937; --title: #111827; --rule: #cfcfcf; --border: #d0d0d0;
                --btn-bg: #ffffff; --btn-fg: #1f2937; --btn-border: #c4c4c4; --btn-hover: #f3f4f6;
                --hdr-fg: #111827; --row-fg: #374151; --map-bg: #dddddd;
                --legend-bg: rgba(255,255,255,0.93); --legend-fg: #1f2937; --legend-hover: #e5e7eb; --muted: #6b7280; }
        * { box-sizing: border-box; margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, "Helvetica Neue", sans-serif; }
        html, body { height: 100%; width: 100%; overflow: hidden; background: var(--bg); }
        #app-container { display: flex; height: 100vh; width: 100vw; position: relative; }
        /* Left panel: platform + variables stay put, the models list scrolls on its own */
        #left-panel { width: 360px; height: 100%; background: var(--bg); color: var(--fg); z-index: 1000;
                      border-right: 1px solid var(--border); padding: 18px 16px 0; display: flex; flex-direction: column; gap: 18px; }
        #models-section { flex: 1; min-height: 0; display: flex; flex-direction: column; }
        #models-list { flex: 1; min-height: 0; overflow-y: auto; padding: 2px 6px 16px 0; }
        #map-container { flex: 1; height: 100%; position: relative; }
        #map { height: 100%; width: 100%; background: var(--map-bg); }
        .panel-title { font-size: 14px; font-weight: 700; color: var(--title); margin-bottom: 10px; display: flex; align-items: center;
                       border-bottom: 2px solid var(--rule); padding-bottom: 6px; text-transform: uppercase; letter-spacing: 0.6px; }
        #theme-btn { margin-left: auto; font-size: 11px; font-weight: 600; text-transform: none; letter-spacing: 0;
                     padding: 3px 9px; border-radius: 12px; border: 1px solid var(--btn-border); background: var(--btn-bg);
                     color: var(--btn-fg); cursor: pointer; }
        #theme-btn:hover { background: var(--btn-hover); }
        /* Cycle date picker */
        #date-section { position: relative; }
        #date-btn { margin-left: auto; font-size: 13px; font-weight: 600; text-transform: none; letter-spacing: 0;
                    padding: 4px 10px; border-radius: 6px; border: 1px solid var(--btn-border); background: var(--btn-bg);
                    color: var(--btn-fg); cursor: pointer; }
        #date-btn:hover { background: var(--btn-hover); }
        #date-pop { position: absolute; right: 0; top: 34px; z-index: 2000; width: 252px; padding: 10px;
                    background: var(--btn-bg); color: var(--btn-fg); border: 1px solid var(--btn-border);
                    border-radius: 8px; box-shadow: 0 6px 20px rgba(0,0,0,0.45); }
        #date-pop[hidden] { display: none; }
        .cal-head { display: flex; align-items: center; justify-content: space-between; font-weight: 700; font-size: 13px; margin-bottom: 6px; }
        .cal-head button { background: none; border: none; color: var(--btn-fg); font-size: 16px; cursor: pointer; padding: 0 6px; }
        .cal-head button:disabled { opacity: 0.25; cursor: default; }
        .cal-grid { display: grid; grid-template-columns: repeat(7, 1fr); gap: 2px; text-align: center; font-size: 12px; }
        .cal-grid .dow { color: var(--muted); font-size: 10.5px; padding: 2px 0; }
        .cal-day { padding: 5px 0; border-radius: 4px; cursor: pointer; border: 1px solid transparent; }
        .cal-day:hover { background: var(--btn-hover); }
        .cal-day.off { opacity: 0.25; cursor: default; background: none; }
        .cal-day.checking { opacity: 0.6; }
        .cal-day.current { background: #0284c7; color: #fff; }
        .cal-day.today { border-color: #38bdf8; }
        .cal-note { color: var(--muted); font-size: 10.5px; margin-top: 6px; }
        input[type="checkbox"] { accent-color: #0284c7; width: 15px; height: 15px; cursor: pointer; }
        .model-group { margin-bottom: 12px; }
        .model-header { display: flex; align-items: center; gap: 6px; font-size: 14px; font-weight: 700;
                        color: var(--hdr-fg); margin-bottom: 4px; user-select: none; }
        .hdr-left { display: flex; align-items: center; gap: 8px; flex: 1; cursor: pointer; }
        .caret, .caret-spacer { width: 20px; flex: none; }
        .caret { background: none; border: none; color: var(--fg); font-size: 18px; line-height: 1; cursor: pointer; padding: 0;
                 transition: transform 0.15s ease; }
        .model-group.collapsed .caret { transform: rotate(-90deg); }
        .model-group.collapsed .model-items { display: none; }
        .trace-row { display: flex; align-items: center; justify-content: space-between; font-size: 13px;
                     padding: 4px 0 4px 45px; color: var(--row-fg); }
        .no-data { opacity: 0.4; }
        .no-data input { cursor: not-allowed; }
        .trace-left { display: flex; align-items: center; gap: 8px; cursor: pointer; user-select: none; }
        .trace-controls { display: flex; align-items: center; gap: 6px; }
        input[type="color"] { border: 1px solid var(--btn-border); width: 24px; height: 22px; border-radius: 4px; cursor: pointer; padding: 0; background: none; }
        select.style-select { font-size: 12px; padding: 3px 6px; border: 1px solid var(--btn-border); border-radius: 4px;
                              background: var(--btn-bg); color: var(--btn-fg); cursor: pointer; }
        .grid-3 { display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px; margin-top: 8px; }
        .btn-toggle { padding: 10px 5px; font-size: 13px; font-weight: 600; text-align: center; background: var(--btn-bg); color: var(--btn-fg);
                      border: 1px solid var(--btn-border); border-radius: 6px; cursor: pointer; transition: all 0.15s ease; user-select: none;
                      display: flex; align-items: center; justify-content: center; line-height: 1.2; }
        .btn-toggle:hover { background: var(--btn-hover); }
        .btn-toggle.active { background: #0284c7; color: #ffffff; border-color: #38bdf8; box-shadow: 0 0 8px rgba(2, 132, 199, 0.4); }
        /* Popups: chart box of fixed size so Leaflet can place the popup before Plotly draws */
        .leaflet-popup-content-wrapper { padding: 0; border-radius: 8px; overflow: hidden; box-shadow: 0 6px 24px rgba(0,0,0,0.45); }
        .leaflet-popup-content { margin: 0; line-height: normal; }
        .popup-below .leaflet-popup-tip-container { top: -20px; transform: rotate(180deg); }   /* tip points up */
        .plot-box { width: __POP_W__; height: __POP_H__; min-width: __POP_MINW__; min-height: __POP_MINH__; background: #fff; }
        .plot-box .modebar { right: 34px !important; }                     /* clear the close (x) button */
        .plot-box .modebar-group { background: transparent !important; }
        .leaflet-container a.leaflet-popup-close-button {                   /* always visible, above the chart */
            z-index: 1100; width: 26px; height: 26px; top: 6px; right: 6px; font: 22px/24px Tahoma, Verdana, sans-serif;
            color: #444; background: rgba(255,255,255,0.9); border-radius: 50%; text-align: center; }
        .leaflet-container a.leaflet-popup-close-button:hover { color: #000; background: #e5e5e5; }
        .plot-msg { display: flex; flex-direction: column; align-items: center; justify-content: center;
                    height: 100%; color: #555; text-align: center; padding: 24px; }
        .plot-msg h3 { margin-bottom: 8px; color: #111; font-size: 16px; }
        #status { position: absolute; top: 12px; left: 50%; transform: translateX(-50%); z-index: 1000;
                  background: var(--legend-bg); color: var(--legend-fg); padding: 8px 14px; border-radius: 6px;
                  font-size: 13px; box-shadow: 0 2px 8px rgba(0,0,0,0.4); display: none; }
        /* Legends */
        .fire-legend, .color-legend { background: var(--legend-bg); color: var(--legend-fg); padding: 8px 10px; border-radius: 6px;
                       font-size: 12px; line-height: 1.5; box-shadow: 0 2px 8px rgba(0,0,0,0.4); }
        .fire-legend b, .color-legend b { display: block; margin-bottom: 3px; }
        .fire-legend .row, .color-legend .row { display: flex; align-items: center; gap: 7px; }
        .fire-legend svg { flex: none; }
        .color-legend .sw { width: 12px; height: 12px; border-radius: 50%; border: 1px solid #111; flex: none; }
        .sat-row, .bin-row { cursor: pointer; border-radius: 3px; padding: 0 4px; margin: 0 -4px; user-select: none; }
        .sat-row:hover, .bin-row:hover { background: var(--legend-hover); }
        .sat-row.off, .bin-row.off { opacity: 0.35; text-decoration: line-through; }
        .cnt { color: var(--muted); margin-left: auto; padding-left: 10px; }
        .hint { color: var(--muted); font-size: 10.5px; margin-top: 2px; }
        .show-all { color: #38bdf8; cursor: pointer; font-size: 11px; }
        .fire-card { padding: 12px 40px 12px 14px; font-size: 13px; color: #0f172a; min-width: 230px; }
        .fire-card h4 { font-size: 14px; margin-bottom: 8px; }
        .fire-card table { border-collapse: collapse; }
        .fire-card td { padding: 2px 10px 2px 0; }
        .fire-card td:first-child { color: #555; }
    </style>
</head>
<body>
    <div id="app-container">
        <div id="left-panel">
            <div id="date-section"><div class="panel-title">Cycle date<button id="date-btn" type="button"></button></div>
                 <div id="date-pop" hidden></div></div>
            <div><div class="panel-title">Observation Platform<button id="theme-btn" type="button"></button></div>
                 <div class="grid-3" id="platform-container"></div></div>
            <div><div class="panel-title">Variable</div><div class="grid-3" id="variable-container"></div></div>
            <div id="models-section"><div class="panel-title">Models & Initializations</div><div id="models-list"></div></div>
        </div>
        <div id="map-container"><div id="map"></div><div id="status"></div></div>
    </div>

    <script>
        // ---------------- written by generate_dashboard.py ----------------
        const CFG = __CFG__;              // settings from config.yaml
        const DATA = __DATA__;            // {platform: {species, stations}} / "HMS fires": {fires, series}

        const PLATFORMS = CFG.platforms, UNITS = CFG.variables, COLOR_SCALES = CFG.colorScales;
        const VARIABLES = Object.keys(UNITS), PLATFORM_NAMES = Object.keys(PLATFORMS);
        const SAT_STYLE = CFG.hms.satellites, SAT_OTHER = CFG.hms.other_satellite;
        const NO_DATA_COLOR = CFG.stations.no_data_color;
        let activePlatform = PLATFORM_NAMES[0];
        let activeVariable = PLATFORMS[activePlatform].default;

        const varBtnId = v => "btn_var_" + v.replace(/[^a-zA-Z0-9]/g, "_");
        const decOf = v => CFG.decimals[v] ?? 2;                  // decimal places per variable
        const fmtVal = (x, v) => x.toFixed(decOf(v));             // value with the variable's decimals
        const unitOf = v => (UNITS[v] && UNITS[v] !== "unitless" ? " " + UNITS[v] : "");
        const deg = (v, pos, neg) => `${Math.abs(v).toFixed(4)}°${v >= 0 ? pos : neg}`;
        const stationsOf = plat => (DATA[plat] && DATA[plat].stations) || {};
        const statusBox = document.getElementById("status");
        const showStatus = txt => { statusBox.textContent = txt; statusBox.style.display = txt ? "block" : "none"; };

        // ======================= MODELS (below the variables, scrolls) =======================
        // Observation: one row (checkbox, colour, line style). Each model: a header with a
        // collapse arrow, a checkbox for all its runs (dash = some on) and a colour that sets
        // all its runs at once; below it one row per run. Runs with no data this cycle are
        // unchecked and disabled.
        const modelsList = document.getElementById("models-list");
        const styleSelect = (id, style) => `<select class="style-select" id="sty_${id}">` +
            [["solid", "───"], ["dash", "—"], ["dot", "···"], ["dashdot", "-·-"]]
                .map(([v, t]) => `<option value="${v}" ${style === v ? "selected" : ""}>${t}</option>`).join("") + `</select>`;
        CFG.models.forEach((group, gi) => {
            const groupDiv = document.createElement("div");
            groupDiv.className = "model-group";
            if (group.items.length === 1 && group.items[0].obs) {          // Observation: single row
                const it = group.items[0];
                groupDiv.innerHTML = `<div class="model-header"><span class="caret-spacer"></span>
                    <label class="hdr-left"><input type="checkbox" id="chk_${it.id}" checked><span>${group.label}</span></label>
                    <div class="trace-controls">${styleSelect(it.id, it.style)}<input type="color" id="col_${it.id}" value="${it.color}"></div></div>`;
                modelsList.appendChild(groupDiv);
                groupDiv.querySelector(`#chk_${it.id}`).addEventListener("change", refreshCurrentPlot);
                groupDiv.querySelector(`#col_${it.id}`).addEventListener("input", refreshCurrentPlot);
                groupDiv.querySelector(`#sty_${it.id}`).addEventListener("change", refreshCurrentPlot);
                return;
            }
            const anyData = group.items.some(it => it.has_data);
            groupDiv.innerHTML = `<div class="model-header${anyData ? "" : " no-data"}"${anyData ? "" : ' title="No data for this cycle"'}>
                    <button class="caret" type="button" title="Show/hide initializations">▾</button>
                    <label class="hdr-left"><input type="checkbox" id="grp_${gi}" ${anyData ? "checked" : "disabled"}><span>${group.label}</span></label>
                    <div class="trace-controls"><input type="color" id="gcol_${gi}" value="${group.color}" title="Colour of all ${group.label} runs"></div>
                </div><div class="model-items"></div>`;
            const items = groupDiv.querySelector(".model-items");
            group.items.forEach(item => {
                const row = document.createElement("div");
                row.className = "trace-row" + (item.has_data ? "" : " no-data");
                if (!item.has_data) row.title = "No data for this cycle";
                row.innerHTML = `
                    <label class="trace-left">
                        <input type="checkbox" id="chk_${item.id}" data-group="${gi}" ${item.has_data ? "checked" : "disabled"}>
                        <span>${item.label}</span>
                    </label>
                    <div class="trace-controls">${styleSelect(item.id, item.style)}<input type="color" id="col_${item.id}" value="${item.color}"></div>`;
                items.appendChild(row);
                row.querySelector(`#chk_${item.id}`).addEventListener("change", () => { syncGroupBox(gi); refreshCurrentPlot(); });
                row.querySelector(`#col_${item.id}`).addEventListener("input", refreshCurrentPlot);
                row.querySelector(`#sty_${item.id}`).addEventListener("change", refreshCurrentPlot);
            });
            modelsList.appendChild(groupDiv);
            groupDiv.querySelector(".caret").addEventListener("click", () => groupDiv.classList.toggle("collapsed"));
            groupDiv.querySelector(`#grp_${gi}`).addEventListener("change", e => {
                group.items.forEach(item => { const b = document.getElementById(`chk_${item.id}`); if (!b.disabled) b.checked = e.target.checked; });
                syncGroupBox(gi);
                refreshCurrentPlot();
            });
            groupDiv.querySelector(`#gcol_${gi}`).addEventListener("input", e => {    // model colour -> all its runs
                group.items.forEach(item => document.getElementById(`col_${item.id}`).value = e.target.value);
                refreshCurrentPlot();
            });
        });
        function syncGroupBox(gi) {       // all on -> checked, all off -> empty, mixed -> dash
            const boxes = [...document.querySelectorAll(`input[data-group="${gi}"]:not(:disabled)`)];
            if (!boxes.length) return;
            const on = boxes.filter(b => b.checked).length, g = document.getElementById(`grp_${gi}`);
            g.checked = on === boxes.length;
            g.indeterminate = on > 0 && on < boxes.length;
        }
        function traceSettings() {        // current settings of every model run
            const out = [];
            CFG.models.forEach(group => group.items.forEach(item => out.push({
                id: item.id,
                name: item.obs ? item.label : `${group.label} ${item.label}`,
                visible: document.getElementById(`chk_${item.id}`).checked,
                color: document.getElementById(`col_${item.id}`).value,
                style: document.getElementById(`sty_${item.id}`).value,
                every: item.every || 1,
                isObs: !!item.obs
            })));
            return out;
        }

        // ======================= PLATFORM & VARIABLE BUTTONS =======================
        const platformContainer = document.getElementById("platform-container");
        PLATFORM_NAMES.forEach(plat => {
            const btn = document.createElement("button");
            btn.className = "btn-toggle" + (plat === activePlatform ? " active" : "");
            btn.textContent = plat;
            btn.onclick = () => selectPlatform(plat);
            platformContainer.appendChild(btn);
        });
        // Only the selected platform's variables are shown (order as in config.yaml 'variables')
        const variableContainer = document.getElementById("variable-container");
        function buildVariableButtons(plat) {
            variableContainer.innerHTML = "";
            VARIABLES.filter(v => PLATFORMS[plat].variables.includes(v)).forEach(v => {
                const btn = document.createElement("button");
                btn.className = "btn-toggle" + (v === activeVariable ? " active" : "");
                btn.id = varBtnId(v);
                btn.textContent = v;
                btn.onclick = () => selectVariable(v);
                variableContainer.appendChild(btn);
            });
        }

        function selectPlatform(plat) {
            activePlatform = plat;
            document.querySelectorAll("#platform-container .btn-toggle")
                .forEach(b => b.classList.toggle("active", b.textContent === plat));
            const pc = PLATFORMS[plat];
            if (!pc.variables.includes(activeVariable)) activeVariable = pc.default;
            buildVariableButtons(plat);
            clearStations();
            if (pc.type === "fires") map.addLayer(fireLayer);
            else { map.removeLayer(fireLayer); updateMarkers(); }
        }
        function setVariable(v) {
            activeVariable = v;
            document.querySelectorAll("#variable-container .btn-toggle")
                .forEach(b => b.classList.toggle("active", b.textContent === v));
        }
        function selectVariable(v) {
            setVariable(v);
            // circles <-> circles: recolour (open popup stays); circles <-> drops: rebuild
            if (!!COLOR_SCALES[v] === colorMode) recolorStations(); else updateMarkers();
            refreshCurrentPlot();
        }

        // ======================= MAP =======================
        const baseLayers = {};
        CFG.map.base_layers.forEach(b => {
            baseLayers[b.name] = L.tileLayer(b.url, { attribution: b.attribution, maxZoom: b.max_zoom || 19 });
        });
        const bnd = CFG.map.boundaries;
        const boundaries = L.tileLayer(bnd.url, { attribution: bnd.attribution, pane: "overlayPane" });
        // Panning limited to config map.bounds ([[south, west], [north, east]]); the
        // minimum zoom is set so the view can never show anything outside them.
        const mapBounds = CFG.map.bounds ? L.latLngBounds(CFG.map.bounds) : null;
        const map = L.map("map", { center: CFG.map.center, zoom: CFG.map.zoom,
                                   maxBounds: mapBounds, maxBoundsViscosity: 1.0 });
        function fitMinZoom() {
            if (!mapBounds) return;
            map.setMinZoom(map.getBoundsZoom(mapBounds, true));
            if (map.getZoom() < map.getMinZoom()) map.setZoom(map.getMinZoom());
            map.panInsideBounds(mapBounds, { animate: false });
        }
        fitMinZoom();
        map.on("resize", fitMinZoom);
        const layerControl = L.control.layers(baseLayers, { [bnd.name]: boundaries }, { position: "bottomright" }).addTo(map);

        // ---- dark / light theme: panel colours + base map (config map.themes) ----
        const THEMES = CFG.map.themes;
        const themeBtn = document.getElementById("theme-btn");
        function applyTheme(t) {
            const th = THEMES[t];
            document.body.classList.toggle("light", t === "light");
            Object.values(baseLayers).forEach(l => map.removeLayer(l));
            map.addLayer(baseLayers[th.base] || Object.values(baseLayers)[0]);
            if (th.boundaries) map.addLayer(boundaries); else map.removeLayer(boundaries);
            themeBtn.textContent = t === "light" ? "☾ Dark mode" : "☀ Light mode";
            themeBtn.dataset.theme = t;
            try { localStorage.setItem("verif-theme", t); } catch (e) {}        // remembered per browser
        }
        themeBtn.onclick = () => applyTheme(themeBtn.dataset.theme === "light" ? "dark" : "light");
        let savedTheme = "dark";
        try { savedTheme = localStorage.getItem("verif-theme") || "dark"; } catch (e) {}
        applyTheme(THEMES[savedTheme] ? savedTheme : "dark");
        const markerCluster = L.markerClusterGroup().addTo(map);

        // ---- popups that stay inside the map ----
        // Open above the marker as usual; if that would be cut off at the top (panning limit),
        // open below it instead, and slide sideways near the east/west edges. The tip keeps
        // pointing at the marker. No auto-panning (the panning limit would block it anyway).
        const SmartPopup = L.Popup.extend({
            options: { maxWidth: 2000, autoPan: false },
            _updatePosition() {
                L.Popup.prototype._updatePosition.call(this);
                if (!this._map || !this._container) return;
                const c = this._container, tip = this._tipContainer, pad = 8;
                c.classList.remove("popup-below");
                tip.style.marginLeft = "";
                const mapR = this._map.getContainer().getBoundingClientRect();
                const p = this._map.latLngToContainerPoint(this._latlng);
                let r = c.getBoundingClientRect();
                const top = r.top - mapR.top;
                if (top < pad && mapR.height - p.y > p.y) {          // no room above -> below
                    c.classList.add("popup-below");
                    const newTop = p.y + 22;                         // just under the marker
                    c.style.bottom = (parseFloat(c.style.bottom) - (newTop - top)) + "px";
                }
                r = c.getBoundingClientRect();
                const left = r.left - mapR.left;
                let dx = 0;
                if (left < pad) dx = pad - left;
                else if (left + r.width > mapR.width - pad) dx = (mapR.width - pad) - (left + r.width);
                if (dx) {
                    c.style.left = (parseFloat(c.style.left) + dx) + "px";
                    tip.style.marginLeft = (-20 - dx) + "px";        // tip stays on the marker
                }
            }
        });
        const smartPopup = content => new SmartPopup().setContent(content);

        // ======================= CHART HELPERS =======================
        // Extra toolbar button: download the plotted values as CSV
        function downloadCSV(gd) {
            const meta = gd._csv || {};
            const traces = gd.data.filter(t => t.visible !== "legendonly");
            const times = [...new Set(traces.flatMap(t => t.x))].sort();
            const lookup = traces.map(t => new Map(t.x.map((x, i) => [x, meta.blankY ? null : t.y[i]])));
            const q = s => (/[",]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s);
            const lines = (meta.header || []).map(h => "# " + h);
            lines.push(["time_utc", ...traces.map(t => q(t.name))].join(","));
            times.forEach(x => {
                const vals = lookup.map(m => { const v = m.get(x); return v === null || v === undefined ? "" : v; });
                if (meta.blankY || vals.some(v => v !== "")) lines.push([x, ...vals].join(","));
            });
            const a = document.createElement("a");
            a.href = URL.createObjectURL(new Blob([lines.join("\n") + "\n"], { type: "text/csv" }));
            a.download = (meta.filename || "data") + ".csv";
            document.body.appendChild(a); a.click(); a.remove();
            setTimeout(() => URL.revokeObjectURL(a.href), 2000);
        }
        const plotConfig = name => ({
            responsive: true, displaylogo: false, displayModeBar: true,     // toolbar always visible
            modeBarButtonsToRemove: ["lasso2d", "select2d"],
            modeBarButtonsToAdd: [{ name: "Download data as CSV", icon: Plotly.Icons.disk, click: downloadCSV }],
            toImageButtonOptions: { format: "png", height: 550, width: 850, scale: 2, filename: name }
        });
        // Line breaks: each curve keeps only its own non-empty values, and a null point is
        // inserted wherever two consecutive values are further apart than the threshold, so
        // the line breaks instead of joining across missing hours (e.g. AERONET at night).
        // Threshold = stations.gap_minutes for hourly data; a model with output_hours = N
        // gets (N - 1) * 60 + gap_minutes (e.g. 185 min for 3-hourly GEFS-Aerosols).
        const GAP_MIN = CFG.stations.gap_minutes ?? 65;
        const tms = t => Date.parse(t.replace(" ", "T") + "Z");                  // "YYYY-MM-DD HH:MM" -> ms
        const tPlus1 = t => new Date(tms(t) + 60000).toISOString().slice(0, 16).replace("T", " ");
        function curve(x0, y0, everyH) {
            const maxMs = ((everyH - 1) * 60 + GAP_MIN) * 60000, x = [], y = [];
            let prev = null;
            for (let i = 0; i < x0.length; i++) {
                if (y0[i] === null || y0[i] === undefined) continue;
                if (prev !== null && tms(x0[i]) - tms(prev) > maxMs) { x.push(tPlus1(prev)); y.push(null); }
                x.push(x0[i]); y.push(y0[i]);
                prev = x0[i];
            }
            return { x, y };
        }
        const spikeAxis = { showspikes: true, spikemode: "across", spikesnap: "cursor",
                            spikethickness: 1, spikedash: "dash", spikecolor: "#555555" };

        // ======================= STATION CHARTS =======================
        function renderStationPlot(div, sid) {
            const payload = DATA[activePlatform], st = payload && payload.stations[sid];
            if (!st) return;
            const v = activeVariable, e = st.d[v];
            if (!e) {                                       // no data for this variable
                Plotly.purge(div);
                div.innerHTML = `<div class="plot-msg"><h3>${st.name}</h3>
                    <p>No <b>${v}</b> data available for this ${activePlatform} station.</p></div>`;
                return;
            }
            if (div.querySelector(".plot-msg")) div.innerHTML = "";
            const cols = payload.species[v].columns, x0 = e.t || payload.species[v].time;
            const traces = [];
            traceSettings().forEach(it => {
                const k = cols.indexOf(it.id), y0 = k >= 0 ? e.v[k] : null;
                if (!it.visible || !y0) return;             // unchecked, or no column for this model
                const { x, y } = curve(x0, y0, it.every);
                const tr = { x, y, name: it.name, type: "scatter", mode: it.isObs ? "lines+markers" : "lines",
                             line: { color: it.color, dash: it.style, width: it.isObs ? 2.2 : 1.7 } };
                if (it.isObs) tr.marker = { size: 5, color: it.color };   // never pass marker: undefined
                traces.push(tr);
            });
            const fname = `${activePlatform}_${sid}_${v.replace(/\s+/g, "_")}`;
            const layout = {
                title: { text: `<b>${st.name}</b> (${activePlatform}) — ${v}`, font: { size: 14, color: "#0f172a" }, x: 0.02, y: 0.98 },
                xaxis: { title: "UTC Time", range: CFG.window, ...spikeAxis },      // always the full 48 h
                yaxis: { title: v + (UNITS[v] ? ` (${UNITS[v]})` : ""), hoverformat: `.${decOf(v)}f` },
                hovermode: "x unified",
                margin: { l: 55, r: 25, t: 70, b: 45 },
                legend: { orientation: "h", y: 1.14, x: 1, xanchor: "right", font: { size: 10 } },
                autosize: true
            };
            Plotly.react(div, traces, layout, plotConfig(fname));
            div._csv = { filename: fname, header: [
                `Station: ${st.name} (id ${sid}), platform ${activePlatform}`,
                `Lat ${st.lat}, Lon ${st.lon}`, `Variable: ${v} [${UNITS[v] || ""}]`, `Cycle: ${CFG.cycle}`] };
        }
        function refreshCurrentPlot() {   // re-draw the open station chart after a panel change
            if (!openStationKey) return;
            const div = document.querySelector(".leaflet-popup .plot-box[data-sid]");
            if (div) renderStationPlot(div, openStationKey);
        }

        // ======================= STATION MARKERS =======================
        // Variable with a colour scale  -> same-size circles coloured by the 48-h max observation
        // Variable without a colour scale -> default drop markers, clustered
        // ONE canvas for station circles AND fire symbols. Two separate canvases would
        // stack on top of each other and the upper one would swallow every click,
        // leaving the markers drawn on the lower one unclickable.
        const canvasRenderer = L.canvas({ padding: 0.5, tolerance: 3 });
        const stationLayer = L.layerGroup().addTo(map);
        let stationMarkers = {};          // station id -> marker (active platform)
        let colorMode = false;
        let openStationKey = null;

        function binIndex(v, scale) {     // last lower edge <= value; "no data" = colors.length
            if (v === null || v === undefined) return scale.colors.length;
            let i = 0;
            while (i + 1 < scale.bounds.length && v >= scale.bounds[i + 1]) i++;
            return i;
        }
        function scaleColor(v, scale) {
            const i = binIndex(v, scale);
            return i === scale.colors.length ? NO_DATA_COLOR : scale.colors[i];
        }
        // Legend filter per variable (last entry = "no data", hidden by default)
        const binVisible = {};
        const binVis = v => (binVisible[v] ||= [...Array(COLOR_SCALES[v].colors.length).fill(true), false]);
        const hasObs = st => st.obs_max[activeVariable] !== null && st.obs_max[activeVariable] !== undefined;
        const stationShown = st => binVis(activeVariable)[binIndex(st.obs_max[activeVariable], COLOR_SCALES[activeVariable])];

        function applyStationFilter() {   // add/remove only what changed (keeps an open popup)
            if (!colorMode) return;
            const S = stationsOf(activePlatform);
            Object.entries(stationMarkers).forEach(([k, m]) => {
                const show = stationShown(S[k]), on = stationLayer.hasLayer(m);
                if (show && !on) stationLayer.addLayer(m);
                else if (!show && on) stationLayer.removeLayer(m);
            });
        }
        function stationTooltip(st) {
            const mx = st.obs_max[activeVariable];
            const val = mx === null || mx === undefined ? "no data" : `max obs. ${fmtVal(mx, activeVariable)}${unitOf(activeVariable)}`;
            return `<b>${st.name}</b><br>${activeVariable}: ${val}`;
        }
        function clearStations() {
            map.closePopup();
            markerCluster.clearLayers();
            stationLayer.clearLayers();
            stationMarkers = {};
            colorLegend.remove();
            showStatus("");
        }
        function updateMarkers() {
            const plat = activePlatform;
            if (PLATFORMS[plat].type === "fires") return;
            const reopen = openStationKey;
            clearStations();
            const S = stationsOf(plat);
            if (!Object.keys(S).length) showStatus(`No ${plat} stations for this cycle`);
            const scale = COLOR_SCALES[activeVariable];
            colorMode = !!scale;
            Object.entries(S).forEach(([sid, st]) => {
                const marker = scale
                    ? L.circleMarker([st.lat, st.lon], {
                          renderer: canvasRenderer, radius: CFG.stations.marker_radius, color: "#111111", weight: 1,
                          fillColor: scaleColor(st.obs_max[activeVariable], scale), fillOpacity: 0.95 })
                    : L.marker([st.lat, st.lon], { title: st.name });
                marker.bindTooltip(() => stationTooltip(st));
                marker.bindPopup(smartPopup(`<div class="plot-box" data-sid="${sid}"></div>`));
                marker.on("popupopen", e => {
                    openStationKey = sid;
                    renderStationPlot(e.popup.getElement().querySelector(".plot-box"), sid);
                });
                marker.on("popupclose", e => {
                    if (openStationKey === sid) openStationKey = null;
                    const el = e.popup.getElement();
                    if (el) Plotly.purge(el.querySelector(".plot-box"));   // free the chart's memory
                });
                if (!scale) { if (hasObs(st)) markerCluster.addLayer(marker); }     // no-data stations hidden
                else if (stationShown(st)) stationLayer.addLayer(marker);
                stationMarkers[sid] = marker;
            });
            updateColorLegend();
            if (reopen && stationMarkers[reopen]) stationMarkers[reopen].openPopup();
        }
        function recolorStations() {
            const scale = COLOR_SCALES[activeVariable], S = stationsOf(activePlatform);
            Object.entries(stationMarkers).forEach(([k, m]) => {
                if (m.setStyle) m.setStyle({ fillColor: scaleColor(S[k].obs_max[activeVariable], scale) });
            });
            applyStationFilter();
            updateColorLegend();
        }

        // ---- colour legend (click a bin: show/hide; double-click: only that bin) ----
        const colorLegend = L.control({ position: "bottomleft" });
        colorLegend.onAdd = () => {
            const d = L.DomUtil.create("div", "color-legend");
            L.DomEvent.disableClickPropagation(d);
            L.DomEvent.disableScrollPropagation(d);
            const vis = () => binVis(activeVariable);
            d.addEventListener("click", e => {
                if (e.target.closest(".show-all")) vis().fill(true);
                else {
                    const row = e.target.closest(".bin-row");
                    if (!row) return;
                    vis()[+row.dataset.i] = !vis()[+row.dataset.i];
                }
                applyStationFilter(); syncLegendRows();
            });
            d.addEventListener("dblclick", e => {
                const row = e.target.closest(".bin-row");
                if (!row) return;
                const v = vis();                            // both clicks already toggled it back
                v.forEach((_, i) => v[i] = (i === +row.dataset.i));
                applyStationFilter(); syncLegendRows();
            });
            return d;
        };
        function syncLegendRows() {       // restyle in place (rebuilding would break double-click)
            const vis = binVis(activeVariable);
            document.querySelectorAll(".color-legend .bin-row").forEach(r => r.classList.toggle("off", !vis[+r.dataset.i]));
        }
        function updateColorLegend() {
            const scale = COLOR_SCALES[activeVariable];
            if (!(colorMode && scale && Object.keys(stationMarkers).length)) { colorLegend.remove(); return; }
            if (!colorLegend._map) colorLegend.addTo(map);
            const b = scale.bounds, u = unitOf(activeVariable), vis = binVis(activeVariable), S = stationsOf(activePlatform);
            const cnt = Array(scale.colors.length + 1).fill(0);
            Object.keys(stationMarkers).forEach(k => cnt[binIndex(S[k].obs_max[activeVariable], scale)]++);
            const row = (i, color, lbl) =>
                `<div class="row bin-row${vis[i] ? "" : " off"}" data-i="${i}" title="Click: show/hide · Double-click: only this one">` +
                `<span class="sw" style="background:${color}"></span>${lbl}<span class="cnt">${cnt[i]}</span></div>`;
            let h = `<b>${activeVariable} — max obs. (48 h)</b>`;
            scale.colors.forEach((c, i) => {
                // bounds shown as written in config.yaml
                const lbl = i === b.length - 1 ? `≥ ${b[i]}` : i === 0 ? `< ${b[1]}` : `${b[i]} – ${b[i + 1]}`;
                h += row(i, c, lbl + u);
            });
            h += row(scale.colors.length, NO_DATA_COLOR, "no data");
            h += `<div class="hint">click: show/hide · double-click: only · <span class="show-all">show all</span></div>`;
            colorLegend.getContainer().innerHTML = h;
        }

        // ======================= HMS FIRES (canvas) =======================
        // Leaflet's canvas only knows circles, so add squares and triangles.
        L.Canvas.include({
            _updateShape(layer) {
                if (!this._drawing || layer._empty()) return;
                const p = layer._point, ctx = this._ctx, r = Math.max(Math.round(layer._radius), 1);
                ctx.beginPath();
                if (layer.options.shape === "square") ctx.rect(p.x - r, p.y - r, 2 * r, 2 * r);
                else if (layer.options.shape === "triangle") {
                    const h = r * 1.25;
                    ctx.moveTo(p.x, p.y - h); ctx.lineTo(p.x + h, p.y + 0.8 * h); ctx.lineTo(p.x - h, p.y + 0.8 * h);
                    ctx.closePath();
                } else ctx.arc(p.x, p.y, r, 0, 2 * Math.PI);
                this._fillStroke(ctx, layer);
            }
        });
        const ShapeMarker = L.CircleMarker.extend({
            options: { shape: "circle" },
            _updatePath() { this._renderer._updateShape(this); }
        });
        const FRP_EDGES = CFG.hms.frp_classes, RADII = CFG.hms.radii;
        function fireRadius(frp) {        // marker half-size (px) from the 48-h max FRP
            if (frp === null) return RADII[0];
            let i = 0;
            while (i < FRP_EDGES.length && frp >= FRP_EDGES[i]) i++;
            return RADII[i];
        }
        const fireLayer = L.layerGroup();
        const SAT_KEYS = [...Object.keys(SAT_STYLE), "Other"];
        const satCat = sat => (sat in SAT_STYLE ? sat : "Other");
        const satVisible = Object.fromEntries(SAT_KEYS.map(k => [k, true]));
        const satCount = Object.fromEntries(SAT_KEYS.map(k => [k, 0]));
        const FIRE_P = DATA[PLATFORM_NAMES.find(p => PLATFORMS[p].type === "fires")];
        let fireMarkers = null;           // built the first time the fire layer is shown

        const fireTimeStr = (F, mins) => new Date(Date.parse(F.t0) + mins * 60000).toISOString().slice(0, 16).replace("T", " ");
        function fireCard(F, i, frpTxt, tStr) {
            const n = F.n[i];
            const rows = [
                ["Lat", deg(F.lat[i], "N", "S")], ["Lon", deg(F.lon[i], "E", "W")],
                ["Satellite", F.sat[i]], ["Method", F.methods[F.m[i]]], ["Ecosystem", F.eco[i]],
                [n > 1 ? "Max FRP" : "FRP", frpTxt], [n > 1 ? "First obs." : "Time", `${tStr} UTC`]
            ];
            return `<div class="fire-card"><h4>${n > 1 ? `HMS fire — ${n} detections` : "HMS fire — single detection"}</h4><table>` +
                   rows.map(([k, v]) => `<tr><td>${k}</td><td><b>${v}</b></td></tr>`).join("") + `</table></div>`;
        }
        function renderFirePlot(div, i) {
            const F = FIRE_P.fires, s = FIRE_P.series[i];
            const sty = SAT_STYLE[F.sat[i]] || SAT_OTHER;
            const x = s.t.map(m => fireTimeStr(F, m));
            const valid = s.frp.some(v => v !== null);
            const trace = {
                x, y: valid ? s.frp : x.map(() => 0), type: "scatter", mode: "lines+markers", name: "FRP (MW)",
                connectgaps: false, line: { color: "#444444", width: 1 },
                marker: { size: 8, color: sty.color, line: { color: "#222222", width: 1 },
                          symbol: { square: "square", circle: "circle", triangle: "triangle-up" }[sty.shape] },
                hovertemplate: valid ? `%{y:.${decOf("FRP")}f} MW<extra></extra>` : "detected (FRP n/a)<extra></extra>"
            };
            const info = [`Lat: ${deg(F.lat[i], "N", "S")}`, `Lon: ${deg(F.lon[i], "E", "W")}`, `Satellite: ${F.sat[i]}`,
                          `Method: ${F.methods[F.m[i]]}`, `Ecosystem: ${F.eco[i]}`].join("  ·  ");
            const sub = `${F.n[i]} detections · max FRP ` + (F.frp[i] === null ? "n/a" : `${F.frp[i]} MW`);
            const fname = `hms_fire_${F.lat[i].toFixed(3)}_${F.lon[i].toFixed(3)}`;
            const layout = {
                title: { text: `<b>HMS fire — Fire Radiative Power</b><br><span style="font-size:12px">${info}</span>` +
                               `<br><span style="font-size:11px;color:#555">${sub}</span>`,
                         font: { size: 14, color: "#0f172a" }, x: 0.02, xanchor: "left", y: 0.97 },
                xaxis: { title: "UTC Time", range: [fireTimeStr(F, 0), fireTimeStr(F, F.minutes)], ...spikeAxis },
                yaxis: { title: "FRP (MW)", rangemode: "tozero", showticklabels: valid },
                hovermode: "x unified", showlegend: false, margin: { l: 60, r: 25, t: 95, b: 45 }, autosize: true,
                annotations: valid ? [] : [{ text: "FRP not available for this detection method", xref: "paper", yref: "paper",
                                             x: 0.5, y: 0.5, showarrow: false, font: { size: 13, color: "#777" } }]
            };
            Plotly.newPlot(div, [trace], layout, plotConfig(fname));
            div._csv = { filename: fname, blankY: !valid, header: [
                `HMS fire: Lat ${F.lat[i]}, Lon ${F.lon[i]}`, `Satellite: ${F.sat[i]}, Method: ${F.methods[F.m[i]]}, Ecosystem: ${F.eco[i]}`,
                `FRP in MW${valid ? "" : " (not available for this detection method)"}`, `Cycle: ${CFG.cycle}`] };
        }

        function buildFires() {
            if (fireMarkers || !FIRE_P) return;
            const F = FIRE_P.fires;
            fireMarkers = [];
            for (let i = 0; i < F.lon.length; i++) {        // sorted small -> large FRP
                const sat = F.sat[i], frp = F.frp[i], sty = SAT_STYLE[sat] || SAT_OTHER;
                const m = new ShapeMarker([F.lat[i], F.lon[i]], {
                    renderer: canvasRenderer, shape: sty.shape, radius: fireRadius(frp),
                    color: "#1a1a1a", weight: 0.7, fillColor: sty.color, fillOpacity: 0.9
                });
                const frpTxt = frp === null ? "n/a" : `${frp} MW`;
                if (F.t[i] === null) {                      // GOES fire with a time series
                    m.bindTooltip(`Max FRP = ${frpTxt}, detected by ${sat} (${F.n[i]} obs.)`);
                    m.bindPopup(smartPopup(`<div class="plot-box"></div>`));
                    m.on("popupopen", e => renderFirePlot(e.popup.getElement().querySelector(".plot-box"), i));
                    m.on("popupclose", e => { const el = e.popup.getElement(); if (el) Plotly.purge(el.querySelector(".plot-box")); });
                } else {                                    // info card only
                    const tStr = fireTimeStr(F, F.t[i]);
                    m.bindTooltip(F.n[i] > 1
                        ? `Max FRP = ${frpTxt}, detected by ${sat} (${F.n[i]} obs., first ${tStr} UTC)`
                        : `FRP = ${frpTxt}, detected by ${sat} at ${tStr} UTC`);
                    m.bindPopup(smartPopup(() => fireCard(F, i, frpTxt, tStr)));
                }
                const cat = satCat(sat);
                fireMarkers.push({ m, cat });
                satCount[cat]++;
            }
            refreshFires();
        }
        function refreshFires() {         // re-add visible satellites, keeping the FRP draw order
            if (!fireMarkers) return;
            fireLayer.clearLayers();
            fireMarkers.forEach(f => { if (satVisible[f.cat]) fireLayer.addLayer(f.m); });
            document.querySelectorAll(".fire-legend .sat-row").forEach(r => r.classList.toggle("off", !satVisible[r.dataset.sat]));
        }
        layerControl.addOverlay(fireLayer, "HMS fires");    // can be overlaid on any platform

        const sym = (shape, color, r) => {
            const s = 2 * r + 4, c = s / 2;
            const g = shape === "square" ? `<rect x="${c - r}" y="${c - r}" width="${2 * r}" height="${2 * r}"/>`
                    : shape === "triangle" ? `<polygon points="${c},${c - 1.25 * r} ${c + 1.25 * r},${c + r} ${c - 1.25 * r},${c + r}"/>`
                    : `<circle cx="${c}" cy="${c}" r="${r}"/>`;
            return `<svg width="${s}" height="${s}"><g fill="${color}" stroke="#1a1a1a" stroke-width="0.7">${g}</g></svg>`;
        };
        const fireLegend = L.control({ position: "bottomleft" });
        fireLegend.onAdd = () => {
            const d = L.DomUtil.create("div", "fire-legend");
            let h = "<b>HMS fires</b>";
            SAT_KEYS.forEach(k => {
                const v = SAT_STYLE[k] || SAT_OTHER;
                h += `<div class="row sat-row${satVisible[k] ? "" : " off"}" data-sat="${k}" title="Click: show/hide · Double-click: only this one">` +
                     `${sym(v.shape, v.color, 5)}${k}<span class="cnt">${satCount[k]}</span></div>`;
            });
            h += `<div class="hint">click: show/hide · double-click: only · <span class="show-all">show all</span></div>`;
            h += "<b style='margin-top:6px'>Max FRP (48 h)</b>";
            const E = FRP_EDGES;
            [`< ${E[0]} MW`, ...E.slice(0, -1).map((e, k) => `${e}–${E[k + 1]} MW`), `> ${E[E.length - 1]} MW`]
                .forEach((t, k) => h += `<div class="row">${sym("circle", "#bbbbbb", RADII[k])}${t}</div>`);
            d.innerHTML = h;
            L.DomEvent.disableClickPropagation(d);
            L.DomEvent.disableScrollPropagation(d);
            d.addEventListener("click", e => {
                if (e.target.closest(".show-all")) { SAT_KEYS.forEach(k => satVisible[k] = true); return refreshFires(); }
                const row = e.target.closest(".sat-row");
                if (!row) return;
                satVisible[row.dataset.sat] = !satVisible[row.dataset.sat];
                refreshFires();
            });
            d.addEventListener("dblclick", e => {
                const row = e.target.closest(".sat-row");
                if (!row) return;
                SAT_KEYS.forEach(k => satVisible[k] = (k === row.dataset.sat));
                refreshFires();
            });
            return d;
        };
        // Fire layer shown (HMS platform or the overlay checkbox) -> build markers once + legend
        fireLayer.on("add", () => { buildFires(); fireLegend.addTo(map); });
        fireLayer.on("remove", () => fireLegend.remove());

        // ======================= CYCLE DATE PICKER =======================
        // config date_navigation.url with {yyyymmdd} (cycle date) and {page} (this page's
        // file name, so every model_type links to its own page). Dates before first_date
        // and in the future are greyed out; on the web server each shown day is also checked
        // with a HEAD request and greyed out when its page doesn't exist.
        (function datePicker() {
            const DN = CFG.dateNav, btn = document.getElementById("date-btn"), pop = document.getElementById("date-pop");
            btn.textContent = `📅 ${CFG.cycleDate} ▾`;
            if (!DN) { btn.disabled = true; btn.textContent = CFG.cycleDate; return; }
            const page = decodeURIComponent(location.pathname.split("/").pop() || "");
            const urlFor = d => DN.url.replace("{yyyymmdd}", d.replaceAll("-", "")).replace("{page}", page);
            const iso = dt => dt.toISOString().slice(0, 10);
            const today = iso(new Date()), first = DN.first_date || "1900-01-01";
            // Pages can only be checked when served over http(s); opened as a local file,
            // every other date stays greyed out.
            const canCheck = location.protocol.startsWith("http");
            const avail = {};                        // date -> true | false | "checking"
            let view = new Date(CFG.cycleDate + "T00:00:00Z");
            view.setUTCDate(1);

            function check(d) {
                if (!canCheck || d in avail) return;
                avail[d] = "checking";
                fetch(urlFor(d), { method: "HEAD", cache: "no-store" })
                    .then(r => { avail[d] = r.ok; })
                    .catch(() => { avail[d] = false; })       // can't confirm -> not selectable
                    .finally(() => { if (!pop.hidden) render(); });
            }
            function render() {
                const y = view.getUTCFullYear(), m = view.getUTCMonth();
                const days = new Date(Date.UTC(y, m + 1, 0)).getUTCDate(), lead = new Date(Date.UTC(y, m, 1)).getUTCDay();
                const monthName = view.toLocaleString("en-US", { month: "long", year: "numeric", timeZone: "UTC" });
                let h = `<div class="cal-head"><button type="button" data-nav="-1" ${iso(view) <= first.slice(0, 8) + "01" ? "disabled" : ""}>‹</button>` +
                        `<span>${monthName}</span><button type="button" data-nav="1" ${iso(new Date(Date.UTC(y, m + 1, 1))) > today ? "disabled" : ""}>›</button></div>` +
                        `<div class="cal-grid">` + ["Su", "Mo", "Tu", "We", "Th", "Fr", "Sa"].map(d => `<div class="dow">${d}</div>`).join("") +
                        `<div></div>`.repeat(lead);
                for (let k = 1; k <= days; k++) {
                    const d = iso(new Date(Date.UTC(y, m, k)));
                    let cls = "cal-day", title = "";
                    if (d === CFG.cycleDate) { cls += " current"; title = "This page"; }
                    else if (d < first || d > today) { cls += " off"; title = "Not available"; }
                    else if (!canCheck) { cls += " off"; title = "Only available on the web server"; }
                    else {
                        check(d);
                        if (avail[d] === true) title = "Open this date";
                        else if (avail[d] === "checking") { cls += " off checking"; title = "Checking…"; }
                        else { cls += " off"; title = "No page for this date"; }
                    }
                    if (d === today) cls += " today";
                    h += `<div class="${cls}" data-date="${d}" title="${title}">${k}</div>`;
                }
                h += `</div><div class="cal-note">${canCheck ? "Greyed out: no page for that date." : "Other dates can only be opened on the web server."}</div>`;
                pop.innerHTML = h;
            }
            btn.addEventListener("click", e => { e.stopPropagation(); pop.hidden = !pop.hidden; if (!pop.hidden) render(); });
            pop.addEventListener("click", e => {
                e.stopPropagation();
                const nav = e.target.closest("[data-nav]");
                if (nav && !nav.disabled) { view.setUTCMonth(view.getUTCMonth() + +nav.dataset.nav); render(); return; }
                const day = e.target.closest(".cal-day");
                if (!day || day.classList.contains("off") || day.classList.contains("current")) return;
                window.location.href = urlFor(day.dataset.date);
            });
            document.addEventListener("click", () => { pop.hidden = true; });
        })();

        selectPlatform(activePlatform);
    </script>
</body>
</html>
"""

html = (DASHBOARD_TEMPLATE
        .replace("__PLOTLY__", PLOTLY_CDN)
        .replace("__DARK_BG__", cfg["map"]["themes"]["dark"].get("panel_bg", "#171717"))
        .replace("__LIGHT_BG__", cfg["map"]["themes"]["light"].get("panel_bg", "#ebebeb"))
        .replace("__POP_W__", str(pop["width"])).replace("__POP_H__", str(pop["height"]))
        .replace("__POP_MINW__", str(pop["min_width"])).replace("__POP_MINH__", str(pop["min_height"]))
        .replace("__CFG__", js_literal(page_cfg))
        .replace("__DATA__", js_literal(all_data)))
os.makedirs(os.path.dirname(os.path.abspath(cfg["output_html"])), exist_ok=True)
with open(cfg["output_html"], "w") as f:
    f.write(html)
print(f"{cfg['output_html']}: {os.path.getsize(cfg['output_html']) / 1024**2:.2f} MB  (" + "; ".join(counts) + ")")