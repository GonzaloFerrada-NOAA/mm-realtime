#!/usr/bin/env python3

import os
for _name in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
    os.environ.setdefault(_name, "1")

import glob
import re
import gc
import time
import subprocess
import traceback
from multiprocessing import Pool
from pathlib import Path

import cartopy.crs as ccrs
import cartopy.feature as cfeature
import matplotlib.colors as mcolors
import matplotlib.pyplot as plt
import netCDF4
import numpy as np
from scipy.spatial import cKDTree


# =============================================================================
# UDATE THE FOLLOWING LINES
# =============================================================================

CURRDIR = os.getcwd()
PLOT_DIR = os.path.join(CURRDIR, "TEMPO_vs_RRFS_AOD_MM_bilinear_t3")

TEMPO_PATH = Path(
    "/scratch3/BMC/acomp/Johana.R/"
    "RRFS_v1.analysis/TEMPO/TEMPO_AOD/data/"
)

RRFS_BASE_DIR = (
    "/scratch3/BMC/acomp/Johana.R/"
    "ICS_LBCS_Feb2026_retro/2026_aug/"
)

DATES_TO_PROCESS = ["20260803"]
HOURS_TO_PROCESS = list(range(24))

WGRIB2 = "wgrib2"
WGRIB2_MATCH = ":AOTK:"

# Hourly model output: intentionally pair TEMPO filename hour H with RRFS H.
RRFS_HOUR_OFFSET = 0

# Spatial interpolation method.
#
# "nearest"
#     Fast --> cKDTree source-to-destination nearest neighbor.
#     xarray/xESMF/ESMF are not imported or used. 
#
# xESMF methods
#     "bilinear", "conservative", "conservative_normed",
#     "conservative_2nd", or "patch".
#
# Here the MODEL is regridded to each TEMPO granule, then paired
# model/observation values are binned to the regular 0.05-degree statistics grid.
# Conservative methods generate grid-cell corners using the same cf_xarray
# approach used by the MELODIES-MONET TEMPO utility.

REGRID_METHOD = "bilinear"  # "nearest"

# Crop the RRFS source grid to each TEMPO
# granule footprint before weight generation. This preserves model->TEMPO
# pairing while avoiding ESMF work over the full RRFS domain.
XESMF_CROP_MODEL_TO_GRANULE = True #Enables cropping of the RRFS grid around each TEMPO granule before xESMF regridding
XESMF_MODEL_CROP_MARGIN_DEG = 1.0 #Expands the TEMPO footprint by 1° in all directions before cropping RRFS
XESMF_MODEL_CROP_PAD_CELLS = 2 #Adds two additional RRFS grid cells around the cropped subdomain. This is an extra safety buffer in grid-index space (based on RRFS preprocessing experience)
PRINT_XESMF_TIMING = True #Prints the processing time for each TEMPO granule

#DO NOT CHANGE FROM HERE:

REQUESTED_WORKERS = int(os.environ.get("SLURM_CPUS_PER_TASK", 16))

if REGRID_METHOD.startswith("conservative"):
    N_WORKERS = 1
elif REGRID_METHOD in ("bilinear", "patch"):
    N_WORKERS = min(4, REQUESTED_WORKERS)
else:
    N_WORKERS = REQUESTED_WORKERS

ALLOW_XESMF_TO_KDTREE_FALLBACK = False #if interpolation fails, the script reports the error and does not silently replace that interpolation with nearest neighbor. If True --> failed xESMF granule is rescued using cKDTree nearest-neighbor interpolation

# Script-1 maximum center-to-center distances in lon/lat degrees.
# These are used only by the KDTree nearest path (and optional xESMF fallback).
TEMPO_MAX_DISTANCE_DEG = 0.07
RRFS_MAX_DISTANCE_DEG = 0.05

XESMF_METHODS = {
    "bilinear",
    "conservative",
    "conservative_normed",
    "conservative_2nd",
    "patch",
}
# ------------------------------------------------------------------------------------------
# UPDATE FROM HERE

#AOD limits.
MIN_VALID_AOD = 0.0
AOD_CEILING = 10.0

# MELODIES-MONET-style filters: isin, isnotin, ==, !=, >, <, >=, <=
#
# Examples:
# TEMPO_FILTER_DICT = {
#     "dqf": {"oper": "<=", "value": 1},
#     "other_flag": {"oper": "==", "value": 0},
# }
TEMPO_FILTER_DICT = {
    "dqf": {"oper": "<=", "value": 1},
}
# ---------------------------------------------------------------------------------------

# If a requested filter variable is absent, reject that granule instead of
# silently assuming good quality.
REJECT_IF_FILTER_VARIABLE_MISSING = True

EXTREME_PLACEHOLDER_LIMIT = 1.0e10

LON_MIN, LON_MAX = -168.0, -48.0
LAT_MIN, LAT_MAX = 15.0, 80.0
GRID_SPACING = 0.05

# Plot temporal output:
#   "hourly" -> one paired TEMPO/RRFS plot for every successful hour
#   "daily"  -> one daily-mean paired TEMPO/RRFS plot per date
#   "both"   -> hourly and daily plots
#   "none"   -> no TEMPO/RRFS side-by-side temporal plots
#
# Daily means are calculated from the already-collocated hourly 0.05-degree
# pairs, so TEMPO and RRFS always use the same sampling and each successful
# hour contributes equal weight at a given grid cell.
PLOT_MODE = "daily"

if PLOT_MODE not in ("hourly", "daily", "both", "none"):
    raise ValueError("PLOT_MODE must be 'hourly', 'daily', 'both', or 'none'.")

MAKE_HOURLY_PLOTS = PLOT_MODE in ("hourly", "both")
MAKE_DAILY_PLOTS = PLOT_MODE in ("daily", "both")

# Number of valid paired hourly means required at a grid cell before that cell
# is shown in the daily-mean plot. Use 1 to show the union of daily coverage.
MIN_DAILY_HOURS_PER_CELL = 1

PRINT_QC_SUMMARY = True

# Pearson correlation. Overall r is always computed from running scalar sums.
# The spatial r map needs five additional 1-D float64 accumulator arrays
# (~125 MB for the default 0.05-degree full-domain grid). Set False if the
# lowest possible memory footprint is more important than a spatial r map.
MAKE_SPATIAL_CORRELATION_MAP = True
MIN_CORRELATION_PAIRS = 2

os.makedirs(PLOT_DIR, exist_ok=True)


# GRID / PLOT CONFIGURATION

STATES_PROVINCES = cfeature.NaturalEarthFeature(
    category="cultural",
    name="admin_1_states_provinces_lakes",
    scale="50m",
    facecolor="none",
)

LEVELS_AOD = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0, 1.5, 2.0]


def smoke_colors():
    white = plt.get_cmap("Greys", 2)([0])
    blues = plt.get_cmap("Blues", 6)(range(1, 5))
    gyr = plt.get_cmap("RdYlGn_r", 18)([1, 3, 5, 9, 12, 13, 14, 16, 18])
    purple = np.array([mcolors.to_rgba("xkcd:vivid purple")])
    return np.concatenate((white, blues, gyr, purple))


CBAR_COLORS = smoke_colors()

lon_grid = np.arange(LON_MIN, LON_MAX, GRID_SPACING)
lat_grid = np.arange(LAT_MIN, LAT_MAX, GRID_SPACING)

LON_DST, LAT_DST = np.meshgrid(lon_grid, lat_grid)
DST_POINTS = np.column_stack((LON_DST.ravel(), LAT_DST.ravel()))
GRID_SHAPE = LON_DST.shape
N_GRID_CELLS = int(np.prod(GRID_SHAPE))


# REGRID_METHOD="nearest" mode these remain unused,
# keeping the fast Script-1 path independent of ESMF initialization.
_XR = None
_XE = None


def using_kdtree_nearest():
    return REGRID_METHOD.lower() == "nearest"


def validate_regrid_method():
    method = REGRID_METHOD.lower()
    if method == "nearest":
        return
    if method not in XESMF_METHODS:
        raise ValueError(
            f"Unsupported REGRID_METHOD={REGRID_METHOD!r}. "
            f"Use 'nearest' or one of {sorted(XESMF_METHODS)}."
        )


def _load_xesmf_stack():
    """Import xarray/xESMF only when an xESMF method is actually selected."""
    global _XR, _XE
    if _XR is None or _XE is None:
        try:
            import xarray as xr
            import xesmf as xe
        except ImportError as exc:
            raise ImportError(
                f"REGRID_METHOD={REGRID_METHOD!r} requires xarray and xESMF. "
                "Use REGRID_METHOD='nearest' for the dependency-light KDTree path."
            ) from exc
        _XR = xr
        _XE = xe
    return _XR, _XE


def _needs_corners():
    return REGRID_METHOD.lower().startswith("conservative")


def _add_grid_corners(ds, lat="lat", lon="lon"):
    """MELODIES-MONET-style approximate bounds for conservative xESMF."""
    try:
        import cf_xarray as cfxr
    except ImportError as exc:
        raise ImportError(
            "Conservative xESMF methods require cf_xarray to construct grid-cell bounds."
        ) from exc

    corners = ds[[lat, lon]].cf.add_bounds([lat, lon])
    ds["lat_b"] = cfxr.bounds_to_vertices(
        corners[f"{lat}_bounds"], "bounds", order=None
    )
    ds["lon_b"] = cfxr.bounds_to_vertices(
        corners[f"{lon}_bounds"], "bounds", order=None
    )
    return ds


# FILTERS

def _normalize_filter_specs(spec):
    if isinstance(spec, dict):
        return [spec]
    if isinstance(spec, (list, tuple)):
        return list(spec)
    raise TypeError("Filter specification must be a dict or list of dicts.")


def _apply_operator(values, oper, target):
    if oper == "isin":
        return np.isin(values, target)
    if oper == "isnotin":
        return ~np.isin(values, target)
    if oper == "==":
        return values == target
    if oper == "!=":
        return values != target
    if oper == ">":
        return values > target
    if oper == "<":
        return values < target
    if oper == ">=":
        return values >= target
    if oper == "<=":
        return values <= target
    raise ValueError(f"Unsupported filter operation {oper!r}")


def _find_nc_variable(dataset, variable_name):
    """Find a variable in the root or one of the immediate TEMPO groups."""
    if variable_name in dataset.variables:
        return dataset.variables[variable_name]

    for group in dataset.groups.values():
        if variable_name in group.variables:
            return group.variables[variable_name]

    return None


def _read_nc_filter_variable(dataset, variable_name):
    variable = _find_nc_variable(dataset, variable_name)
    if variable is None:
        return None

    raw = variable[:]
    if np.issubdtype(raw.dtype, np.number):
        return np.ma.filled(raw.astype(np.float64), np.nan)

    return np.ma.filled(raw, "")



def apply_tempo_user_filters(dataset, base_mask):
    """Apply MELODIES-MONET-like filter_dict logic to a TEMPO granule."""
    keep = np.asarray(base_mask, dtype=bool).copy()

    for variable_name, spec in TEMPO_FILTER_DICT.items():
        values = _read_nc_filter_variable(dataset, variable_name)

        if values is None:
            message = f"Requested TEMPO filter variable {variable_name!r} is missing."
            if REJECT_IF_FILTER_VARIABLE_MISSING:
                raise KeyError(message)
            print(f"[TEMPO FILTER WARNING] {message} Filter skipped.")
            continue

        values = np.squeeze(np.asarray(values))

        if values.shape == ():
            values = np.full(keep.shape, values.item())

        if values.shape != keep.shape:
            try:
                values = np.broadcast_to(values, keep.shape)
            except ValueError as exc:
                raise ValueError(
                    f"Filter variable {variable_name!r} has shape {values.shape}, "
                    f"but AOD has shape {keep.shape}."
                ) from exc

        if np.issubdtype(values.dtype, np.number):
            keep &= np.isfinite(values)

        for condition in _normalize_filter_specs(spec):
            keep &= _apply_operator(values, condition["oper"], condition["value"])

    return keep


# TEMPO READER / REGRIDDER

def read_tempo_granule(filename):
    """Read one TEMPO AOD granule and apply mandatory + quality controls."""
    try:
        with netCDF4.Dataset(filename, "r") as ds:
            if not ds.groups:
                return None

            geo = ds.groups["geolocation"]
            product = ds.groups["product"]

            lat = np.squeeze(
                np.ma.filled(geo["latitude"][:], np.nan).astype(np.float64)
            )
            lon = np.squeeze(
                np.ma.filled(geo["longitude"][:], np.nan).astype(np.float64)
            )
            aod = np.squeeze(
                np.ma.filled(product["aod550"][:], np.nan).astype(np.float64)
            )

            if lat.ndim != 2 or lon.ndim != 2 or aod.ndim != 2:
                raise ValueError(
                    f"Expected 2-D arrays; lat={lat.shape}, lon={lon.shape}, aod={aod.shape}"
                )

            if lat.shape != lon.shape or lat.shape != aod.shape:
                raise ValueError(
                    f"TEMPO shape mismatch: lat={lat.shape}, lon={lon.shape}, aod={aod.shape}"
                )

            lon = np.where(lon > 180.0, lon - 360.0, lon)

            valid_geo = (
                np.isfinite(lat)
                & np.isfinite(lon)
                & (np.abs(lat) <= 90.0)
                & (np.abs(lon) <= 180.0)
            )

            valid = (
                valid_geo
                & np.isfinite(aod)
                & (aod >= MIN_VALID_AOD)
                & (aod <= AOD_CEILING)
            )

            valid = apply_tempo_user_filters(ds, valid)

            n_valid = int(np.count_nonzero(valid))
            if n_valid == 0:
                return None

            return {
                "lat": lat,
                "lon": lon,
                "aod": np.where(valid, aod, np.nan).astype(np.float32),
                "valid": valid,
                "valid_count": n_valid,
                "total_count": int(aod.size),
                "source_file": str(filename),
            }

    except Exception as exc:
        print(f"[TEMPO ERROR] {Path(filename).name}: {exc}")
        return None


def kdtree_regrid(source_lon, source_lat, source_data, max_distance_deg):
    """
    Script-1 nearest-source-to-destination mapping.

    Distances are Euclidean in (longitude, latitude). Each destination cell receives the
    value of the single closest valid source point, then the explicit distance
    cutoff is applied.
    """
    lon = np.asarray(source_lon, dtype=np.float64).ravel()
    lat = np.asarray(source_lat, dtype=np.float64).ravel()
    data = np.asarray(source_data, dtype=np.float32).ravel()

    valid = (
        np.isfinite(lon)
        & np.isfinite(lat)
        & np.isfinite(data)
        & (np.abs(lat) <= 90.0)
        & (np.abs(lon) <= 180.0)
    )
    if np.count_nonzero(valid) < 2:
        return None

    points = np.column_stack((lon[valid], lat[valid]))
    values = data[valid]

    tree = cKDTree(points)
    distance, index = tree.query(DST_POINTS, k=1, workers=1)

    output = values[index].astype(np.float32, copy=False)
    output[distance > max_distance_deg] = np.nan
    return output.reshape(GRID_SHAPE)


def _tempo_to_xarray(granule):
    """Build the TEMPO granule grid used as the xESMF destination."""
    xr, _ = _load_xesmf_stack()

    lat = np.asarray(granule["lat"], dtype=np.float64)
    lon = np.asarray(granule["lon"], dtype=np.float64)
    valid_geo = (
        np.isfinite(lat)
        & np.isfinite(lon)
        & (np.abs(lat) <= 90.0)
        & (np.abs(lon) <= 180.0)
    )

    if not np.all(valid_geo):
        # ESMF cannot ingest NaN coordinates. In normal TEMPO AOD granules the
        # geolocation mesh is finite even when AOD is masked. If geometry itself
        # is missing, use finite placeholders only at destination points that are
        # also masked out; they are excluded from the final paired values.
        lon_for_grid = np.where(valid_geo, lon, 0.0)
        lat_for_grid = np.where(valid_geo, lat, 0.0)
    else:
        lon_for_grid = lon
        lat_for_grid = lat

    destination_mask = (
        valid_geo
        & granule["valid"]
        & np.isfinite(granule["aod"])
    ).astype(np.int32)

    ds = xr.Dataset(
        data_vars={
            "mask": (("y", "x"), destination_mask),
        },
        coords={
            "lon": (("y", "x"), lon_for_grid, {"units": "degrees_east"}),
            "lat": (("y", "x"), lat_for_grid, {"units": "degrees_north"}),
        },
    )

    if _needs_corners():
        ds = _add_grid_corners(ds, lat="lat", lon="lon")

    return ds


def read_tempo_hour(files):
    """Read and QC all TEMPO granules belonging to one filename hour."""
    granules = []
    total_valid = 0
    total_pixels = 0

    for filename in files:
        granule = read_tempo_granule(filename)
        if granule is None:
            continue
        granules.append(granule)
        total_valid += granule["valid_count"]
        total_pixels += granule["total_count"]

    if not granules:
        return None

    if PRINT_QC_SUMMARY:
        print(
            f"[TEMPO QC] method={REGRID_METHOD}; files={len(granules)}, "
            f"valid_pixels={total_valid}/{total_pixels}"
        )

    return granules


def tempo_granules_to_kdtree_grid(granules):
    """all valid hourly TEMPO pixels -> common 0.05° grid."""
    lon_parts = []
    lat_parts = []
    aod_parts = []

    for granule in granules:
        valid = granule["valid"] & np.isfinite(granule["aod"])
        if not np.any(valid):
            continue
        lon_parts.append(granule["lon"][valid].ravel())
        lat_parts.append(granule["lat"][valid].ravel())
        aod_parts.append(granule["aod"][valid].ravel())

    if not aod_parts:
        return None

    return kdtree_regrid(
        np.concatenate(lon_parts),
        np.concatenate(lat_parts),
        np.concatenate(aod_parts),
        TEMPO_MAX_DISTANCE_DEG,
    )


# RRFS READER / REGRIDDER

def read_rrfs_aotk(gribfile, file_date, forecast_hour):
    """Extract RRFS AOTK using wgrib2 and clean masked/fill/spurious values."""
    fhr = f"{forecast_hour:03d}"
    tmp_nc = os.path.join(
        PLOT_DIR,
        f".tmp_rrfs_aotk_{file_date}_f{fhr}_pid{os.getpid()}.nc",
    )

    if os.path.exists(tmp_nc):
        os.remove(tmp_nc)

    command = [WGRIB2, gribfile, "-match", WGRIB2_MATCH, "-netcdf", tmp_nc]
    result = subprocess.run(
        command,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        text=True,
    )

    if result.returncode != 0 or not os.path.exists(tmp_nc):
        print(f"[WGRIB2 ERROR] {result.stderr[-1000:]}")
        return None, None, None

    try:
        with netCDF4.Dataset(tmp_nc, "r") as ds:
            candidates = [
                name
                for name, var in ds.variables.items()
                if "AOTK" in name.upper() and var.ndim >= 2
            ]
            if not candidates:
                return None, None, None

            preferred = [n for n in candidates if "ENTIREATMOSPHERE" in n.upper()]
            var_name = preferred[0] if preferred else candidates[0]

            aod = np.squeeze(
                np.ma.filled(ds.variables[var_name][:], np.nan).astype(np.float32)
            )
            lat = np.squeeze(
                np.ma.filled(ds.variables["latitude"][:], np.nan).astype(np.float64)
            )
            lon = np.squeeze(
                np.ma.filled(ds.variables["longitude"][:], np.nan).astype(np.float64)
            )

            aod[~np.isfinite(aod)] = np.nan
            aod[np.abs(aod) >= EXTREME_PLACEHOLDER_LIMIT] = np.nan
            aod[aod < MIN_VALID_AOD] = np.nan
            aod[aod > AOD_CEILING] = np.nan

            lon = np.where(lon > 180.0, lon - 360.0, lon)
            return aod, lon, lat

    finally:
        if os.path.exists(tmp_nc):
            os.remove(tmp_nc)


def _rrfs_grid_to_xarray(lon, lat, aod):
    """Build an xarray RRFS source grid for xESMF."""
    xr, _ = _load_xesmf_stack()

    lon = np.asarray(lon, dtype=np.float64)
    lat = np.asarray(lat, dtype=np.float64)
    aod = np.asarray(aod, dtype=np.float32)

    valid_geo = (
        np.isfinite(lon)
        & np.isfinite(lat)
        & (np.abs(lat) <= 90.0)
        & (np.abs(lon) <= 180.0)
    )
    source_mask = (valid_geo & np.isfinite(aod)).astype(np.int32)

    ds = xr.Dataset(
        data_vars={
            "aod": (("y", "x"), aod),
            "mask": (("y", "x"), source_mask),
        },
        coords={
            "lon": (("y", "x"), np.where(valid_geo, lon, 0.0), {"units": "degrees_east"}),
            "lat": (("y", "x"), np.where(valid_geo, lat, 0.0), {"units": "degrees_north"}),
        },
    )

    if _needs_corners():
        ds = _add_grid_corners(ds, lat="lat", lon="lon")

    return ds


def crop_rrfs_to_granule(aod, lon, lat, granule):
    """
    Crop the structured RRFS grid to the TEMPO granule bounding box.

    speed optimization beyond the basic MELODIES-MONET:
    source remains RRFS and destination remains the TEMPO granule, but ESMF
    sees only the RRFS rows/columns that can contribute to this granule.
    """
    if not XESMF_CROP_MODEL_TO_GRANULE:
        return aod, lon, lat

    gvalid = (
        granule["valid"]
        & np.isfinite(granule["lat"])
        & np.isfinite(granule["lon"])
    )
    if not np.any(gvalid):
        return None

    glon = granule["lon"][gvalid]
    glat = granule["lat"][gvalid]

    lon_min = float(np.nanmin(glon) - XESMF_MODEL_CROP_MARGIN_DEG)
    lon_max = float(np.nanmax(glon) + XESMF_MODEL_CROP_MARGIN_DEG)
    lat_min = float(np.nanmin(glat) - XESMF_MODEL_CROP_MARGIN_DEG)
    lat_max = float(np.nanmax(glat) + XESMF_MODEL_CROP_MARGIN_DEG)

    valid_geo = np.isfinite(lon) & np.isfinite(lat)
    inside = (
        valid_geo
        & (lon >= lon_min)
        & (lon <= lon_max)
        & (lat >= lat_min)
        & (lat <= lat_max)
    )

    rows, cols = np.where(inside)
    if rows.size == 0:
        return None

    pad = int(max(0, XESMF_MODEL_CROP_PAD_CELLS))
    y0 = max(int(rows.min()) - pad, 0)
    y1 = min(int(rows.max()) + pad + 1, aod.shape[0])
    x0 = max(int(cols.min()) - pad, 0)
    x1 = min(int(cols.max()) + pad + 1, aod.shape[1])

    return (
        aod[y0:y1, x0:x1],
        lon[y0:y1, x0:x1],
        lat[y0:y1, x0:x1],
    )


def kdtree_rrfs_to_tempo_granule(rrfs_aod, rrfs_lon, rrfs_lat, granule):
    """The optional rescue nearest RRFS source point -> valid TEMPO pixels."""
    cropped = crop_rrfs_to_granule(
        rrfs_aod,
        rrfs_lon,
        rrfs_lat,
        granule,
    )
    if cropped is None:
        return None

    aod_src, lon_src, lat_src = cropped
    source_valid = (
        np.isfinite(aod_src)
        & np.isfinite(lon_src)
        & np.isfinite(lat_src)
    )
    dest_valid = (
        granule["valid"]
        & np.isfinite(granule["aod"])
        & np.isfinite(granule["lon"])
        & np.isfinite(granule["lat"])
    )
    if np.count_nonzero(source_valid) < 2 or not np.any(dest_valid):
        return None

    tree = cKDTree(
        np.column_stack((lon_src[source_valid], lat_src[source_valid]))
    )
    dest_points = np.column_stack(
        (granule["lon"][dest_valid], granule["lat"][dest_valid])
    )
    distance, index = tree.query(dest_points, k=1, workers=1)
    source_values = aod_src[source_valid]
    model_values = source_values[index].astype(np.float32, copy=False)

    keep = distance <= RRFS_MAX_DISTANCE_DEG
    if not np.any(keep):
        return None

    return (
        granule["lon"][dest_valid][keep].astype(np.float64, copy=False),
        granule["lat"][dest_valid][keep].astype(np.float64, copy=False),
        granule["aod"][dest_valid][keep].astype(np.float32, copy=False),
        model_values[keep].astype(np.float32, copy=False),
    )


def regrid_rrfs_to_tempo_granule(rrfs_aod, rrfs_lon, rrfs_lat, granule):
    """xESMF: RRFS/model -> one TEMPO granule, then return collocated pixels."""
    _, xe = _load_xesmf_stack()

    cropped = crop_rrfs_to_granule(
        rrfs_aod,
        rrfs_lon,
        rrfs_lat,
        granule,
    )
    if cropped is None:
        return None

    aod_src, lon_src, lat_src = cropped
    ds_model = _rrfs_grid_to_xarray(lon_src, lat_src, aod_src)
    ds_tempo = _tempo_to_xarray(granule)

    t0 = time.perf_counter()
    regridder = None
    try:
        regridder = xe.Regridder(
            ds_model,
            ds_tempo,
            REGRID_METHOD,
            ignore_degenerate=True,
            unmapped_to_nan=True,
        )

        model_on_tempo = np.asarray(
            regridder(ds_model["aod"]).values,
            dtype=np.float32,
        )
        model_on_tempo[~np.isfinite(model_on_tempo)] = np.nan
        model_on_tempo[model_on_tempo < MIN_VALID_AOD] = np.nan
        model_on_tempo[model_on_tempo > AOD_CEILING] = np.nan

        valid = (
            granule["valid"]
            & np.isfinite(granule["aod"])
            & np.isfinite(model_on_tempo)
            & np.isfinite(granule["lon"])
            & np.isfinite(granule["lat"])
        )

        if not np.any(valid):
            return None


        result = (
            granule["lon"][valid].astype(np.float64, copy=False),
            granule["lat"][valid].astype(np.float64, copy=False),
            granule["aod"][valid].astype(np.float32, copy=False),
            model_on_tempo[valid].astype(np.float32, copy=False),
        )

        if PRINT_XESMF_TIMING:
            elapsed = time.perf_counter() - t0
            print(
                f"[xESMF] {REGRID_METHOD}; "
                f"RRFS crop={aod_src.shape}; TEMPO={granule['aod'].shape}; "
                f"paired_pixels={int(np.count_nonzero(valid))}; "
                f"elapsed={elapsed/60.0:.2f} min; "
                f"file={Path(granule['source_file']).name}"
            )

        return result

    except Exception as exc:
        if not ALLOW_XESMF_TO_KDTREE_FALLBACK:
            raise
        print(
            f"[RRFS->TEMPO xESMF -> KDTree FALLBACK] "
            f"{Path(granule['source_file']).name}: {exc}"
        )
        return kdtree_rrfs_to_tempo_granule(
            rrfs_aod, rrfs_lon, rrfs_lat, granule
        )

    finally:
        if regridder is not None:
            del regridder
        del ds_model
        del ds_tempo
        gc.collect()


def _accumulate_pairs_into_regular_grid(sum_obs, sum_mod, pair_count, lon, lat, obs, mod):
    """Bin collocated TEMPO-grid pairs to the nearest 0.05° statistics-grid point."""
    lon = np.asarray(lon, dtype=np.float64).ravel()
    lat = np.asarray(lat, dtype=np.float64).ravel()
    obs = np.asarray(obs, dtype=np.float32).ravel()
    mod = np.asarray(mod, dtype=np.float32).ravel()

    valid = (
        np.isfinite(lon)
        & np.isfinite(lat)
        & np.isfinite(obs)
        & np.isfinite(mod)
    )
    if not np.any(valid):
        return 0

    lon = lon[valid]
    lat = lat[valid]
    obs = obs[valid]
    mod = mod[valid]

    # The regular grid coordinates are point locations beginning at LON_MIN and
    # LAT_MIN, so round to the closest grid point rather than using cell edges.
    col = np.rint((lon - LON_MIN) / GRID_SPACING).astype(np.int64)
    row = np.rint((lat - LAT_MIN) / GRID_SPACING).astype(np.int64)

    inside = (
        (row >= 0)
        & (row < GRID_SHAPE[0])
        & (col >= 0)
        & (col < GRID_SHAPE[1])
    )
    if not np.any(inside):
        return 0

    row = row[inside]
    col = col[inside]
    obs = obs[inside].astype(np.float64, copy=False)
    mod = mod[inside].astype(np.float64, copy=False)
    flat = row * GRID_SHAPE[1] + col

    # Compress each granule to unique target cells before touching the full
    # hourly accumulators. This avoids a 3.12-million-element bincount per granule.
    unique, inverse = np.unique(flat, return_inverse=True)
    local_count = np.bincount(inverse).astype(np.uint32)
    local_obs = np.bincount(inverse, weights=obs)
    local_mod = np.bincount(inverse, weights=mod)

    sum_obs[unique] += local_obs
    sum_mod[unique] += local_mod
    pair_count[unique] += local_count
    return int(obs.size)


def pair_xesmf_hour_to_regular_grid(granules, rrfs_aod, rrfs_lon, rrfs_lat):
    """
    MELODIES-MONET-style xESMF branch.

    For every TEMPO granule:
      RRFS -> TEMPO grid -> pair valid model/obs pixels.
    Then all collocated pixels in the filename hour are binned to the common
    0.05° grid, producing one hourly mean obs/model pair per occupied grid cell.
    """
    sum_obs = np.zeros(N_GRID_CELLS, dtype=np.float64)
    sum_mod = np.zeros(N_GRID_CELLS, dtype=np.float64)
    pair_count = np.zeros(N_GRID_CELLS, dtype=np.uint32)

    total_paired_pixels = 0
    successful_granules = 0

    for granule in granules:
        paired = regrid_rrfs_to_tempo_granule(
            rrfs_aod,
            rrfs_lon,
            rrfs_lat,
            granule,
        )
        if paired is None:
            continue

        lon, lat, obs, mod = paired
        n_added = _accumulate_pairs_into_regular_grid(
            sum_obs,
            sum_mod,
            pair_count,
            lon,
            lat,
            obs,
            mod,
        )
        total_paired_pixels += n_added
        successful_granules += 1

        del paired
        gc.collect()

    occupied = pair_count > 0
    if not np.any(occupied):
        return None

    indices = np.flatnonzero(occupied).astype(np.int32)
    obs_mean = (sum_obs[indices] / pair_count[indices]).astype(np.float32)
    mod_mean = (sum_mod[indices] / pair_count[indices]).astype(np.float32)

    print(
        f"[xESMF HOUR] granules={successful_granules}/{len(granules)}; "
        f"paired TEMPO pixels={total_paired_pixels}; "
        f"occupied 0.05-deg cells={indices.size}"
    )

    del sum_obs
    del sum_mod
    del pair_count
    gc.collect()

    return indices, obs_mean, mod_mean


# STATISTICS

def pearson_r_from_sums(n, sum_x, sum_y, sum_x2, sum_y2, sum_xy):
    """Pearson r from sufficient statistics without storing all pairs."""
    if n < MIN_CORRELATION_PAIRS:
        return np.nan

    numerator = n * sum_xy - sum_x * sum_y
    var_x_term = n * sum_x2 - sum_x * sum_x
    var_y_term = n * sum_y2 - sum_y * sum_y
    denominator_sq = var_x_term * var_y_term

    if denominator_sq <= 0.0 or not np.isfinite(denominator_sq):
        return np.nan

    r = numerator / np.sqrt(denominator_sq)
    return float(np.clip(r, -1.0, 1.0))


# PLOTTING

def plot_side_by_side(tempo_data, rrfs_data, tempo_title, rrfs_title, output_file):
    data_crs = ccrs.PlateCarree()
    plot_crs = ccrs.LambertConformal(
        central_longitude=-100.0,
        central_latitude=50.0,
    )

    fig, axes = plt.subplots(
        1,
        2,
        figsize=(11, 5),
        subplot_kw={"projection": plot_crs},
        constrained_layout=True,

   )

    cmap = mcolors.ListedColormap(CBAR_COLORS)
    cmap.set_bad((0.0, 0.0, 0.0, 0.0))
    norm = mcolors.BoundaryNorm(LEVELS_AOD, len(CBAR_COLORS))

    graph = None
    for axis, data, title in (
        (axes[0], tempo_data, tempo_title),
        (axes[1], rrfs_data, rrfs_title),
    ):
        axis.set_extent([-145.0, -55.0, 20.0, 74.0], crs=data_crs)
        axis.set_title(title, fontsize=8, loc="left")
        axis.add_feature(cfeature.LAND, facecolor="whitesmoke", zorder=0)
        axis.add_feature(cfeature.OCEAN, facecolor="lightcyan", zorder=0)

        graph = axis.pcolormesh(
            LON_DST,
            LAT_DST,
            np.ma.masked_invalid(data),
            transform=data_crs,
            cmap=cmap,
            norm=norm,
            shading="auto",
            zorder=1,
        )

        axis.add_feature(STATES_PROVINCES, edgecolor="black", linewidth=0.25, zorder=2)
        axis.add_feature(
            cfeature.COASTLINE.with_scale("50m"),
            edgecolor="black",
            linewidth=0.3,
            zorder=2,
        )
        axis.add_feature(
            cfeature.BORDERS.with_scale("50m"),
            edgecolor="dimgray",
            linewidth=0.5,
            linestyle=":",
            zorder=2,
        )

        gl = axis.gridlines(
            draw_labels=True,
            rotate_labels=False,
            linewidth=0.2,
            color="gray",
            alpha=0.15,
            linestyle="--",
        )
        gl.top_labels = False
        gl.bottom_labels = False
        gl.right_labels = False
        gl.left_labels = True
        gl.xlabel_style = {"size": 7}
        gl.ylabel_style = {"size": 7}

    cbar = fig.colorbar(
        graph,
        ax=axes,
        orientation="horizontal",
        pad=0.04,
        shrink=0.5,
        aspect=40,
        ticks=LEVELS_AOD,
        extend="both",
    )
    cbar.set_label("Aerosol Optical Depth at 550 nm")
    cbar.ax.tick_params(labelsize=8)

    plt.savefig(output_file, bbox_inches="tight", dpi=150)
    plt.close(fig)


def plot_spatial_metric(
    metric,
    title,
    cbar_label,
    cmap,
    vmin,
    vmax,
    output_file,
):
    data_crs = ccrs.PlateCarree()
    plot_crs = ccrs.LambertConformal(
        central_longitude=-100.0,
        central_latitude=50.0,
    )

    fig, ax = plt.subplots(
        figsize=(9, 7),
        subplot_kw={"projection": plot_crs},
        constrained_layout=True,
    )

    ax.set_extent([-145.0, -55.0, 20.0, 74.0], crs=data_crs)
    ax.add_feature(cfeature.LAND, facecolor="whitesmoke", zorder=0)
    ax.add_feature(cfeature.OCEAN, facecolor="lightcyan", zorder=0)

    mesh = ax.pcolormesh(
        LON_DST,
        LAT_DST,
        np.ma.masked_invalid(metric),
        transform=data_crs,
        cmap=cmap,
        vmin=vmin,
        vmax=vmax,
        shading="auto",
        zorder=1,
    )

    ax.add_feature(STATES_PROVINCES, edgecolor="black", linewidth=0.25, zorder=2)
    ax.add_feature(
        cfeature.COASTLINE.with_scale("50m"),
        edgecolor="black",
        linewidth=0.3,
        zorder=2,
    )


    gl = ax.gridlines(
        draw_labels=True,
        rotate_labels=False,
        linewidth=0.2,
        color="gray",
        alpha=0.2,
        linestyle="--",
    )
    gl.top_labels = False
    gl.bottom_labels = False
    gl.right_labels = False
    gl.left_labels = True

    cbar = fig.colorbar(
        mesh,
        ax=ax,
        orientation="horizontal",
        pad=0.04,
        shrink=0.65,
        aspect=40,
    )
    cbar.set_label(f"AOD Spatial {cbar_label}", fontsize=9)
    ax.set_title(title, fontsize=9, loc="left")

    plt.savefig(output_file, bbox_inches="tight", dpi=200)
    plt.close(fig)


# WORKER

def tempo_filename_time_label(files, fallback_hour):

    pattern = re.compile(r"(\d{8}T\d{6}Z?)")
    found = []

    for filename in (files[0], files[-1]):
        match = pattern.search(Path(filename).name)
        if match:
            found.append(match.group(1))

    if len(found) == 2:
        return f"{found[0]}-{found[1]}"

    return f"{fallback_hour:02d}z group"


def process_hour(task):
    """
    Process one hourly TEMPO group and same-hour RRFS field.

    nearest:
        Script-1 TEMPO and RRFS KDTree -> common 0.05° grid -> pair.

    xESMF methods:
        RRFS/model -> each TEMPO granule -> pair on satellite grid -> bin the
        paired hourly means to the common 0.05° statistics grid.

    Returns compact paired indices/differences only; full 2-D arrays are not
    serialized back to the parent process.
    """
    target_date, tempo_hour, target_dir, dir_str = task
    hour_str = f"{tempo_hour:02d}"

    try:
        tempo_glob = os.path.join(
            target_dir,
            f"TEMPO_AODALH_L2_V*_{dir_str}T{hour_str}*.nc",
        )
        tempo_files = sorted(glob.glob(tempo_glob))
        if not tempo_files:
            return None

        granules = read_tempo_hour(tempo_files)
        if not granules:
            return None

        rrfs_hour = tempo_hour + RRFS_HOUR_OFFSET
        gribfile = os.path.join(
            RRFS_BASE_DIR,
            f"rrfs.{target_date}",
            "00",
            f"rrfs.t00z.2dfld.3km.f{rrfs_hour:03d}.na.grib2",
        )

        if not os.path.exists(gribfile):
            print(f"[MISSING RRFS] {gribfile}")
            return None

        rrfs_aod, rrfs_lon, rrfs_lat = read_rrfs_aotk(
            gribfile,
            target_date,
            rrfs_hour,
        )
        if rrfs_aod is None or not np.any(np.isfinite(rrfs_aod)):
            return None

        if using_kdtree_nearest():
            tempo_grid = tempo_granules_to_kdtree_grid(granules)
            if tempo_grid is None or not np.any(np.isfinite(tempo_grid)):
                return None

            rrfs_grid = kdtree_regrid(
                rrfs_lon,
                rrfs_lat,
                rrfs_aod,
                RRFS_MAX_DISTANCE_DEG,
            )
            if rrfs_grid is None or not np.any(np.isfinite(rrfs_grid)):
                return None

            valid = np.isfinite(tempo_grid) & np.isfinite(rrfs_grid)
            if not np.any(valid):
                print(f"[NO PAIRS] {target_date} {hour_str}z")
                return None

            indices = np.flatnonzero(valid.ravel()).astype(np.int32)
            obs = tempo_grid.ravel()[indices].astype(np.float32, copy=False)
            mod = rrfs_grid.ravel()[indices].astype(np.float32, copy=False)

            # For plotting, show only the cells actually entering the paired
            # evaluation. This makes nearest directly comparable with xESMF.
            if MAKE_HOURLY_PLOTS:
                tempo_flat = np.full(N_GRID_CELLS, np.nan, dtype=np.float32)
                rrfs_flat = np.full(N_GRID_CELLS, np.nan, dtype=np.float32)
                tempo_flat[indices] = obs
                rrfs_flat[indices] = mod
                tempo_grid = tempo_flat.reshape(GRID_SHAPE)
                rrfs_grid = rrfs_flat.reshape(GRID_SHAPE)

        else:
            paired = pair_xesmf_hour_to_regular_grid(
                granules,
                rrfs_aod,
                rrfs_lon,
                rrfs_lat,
            )
            if paired is None:
                print(f"[NO PAIRS] {target_date} {hour_str}z")
                return None

            indices, obs, mod = paired

            # Only reconstruct full grids when an hourly plot is requested.
            tempo_grid = None
            rrfs_grid = None
            if MAKE_HOURLY_PLOTS:
                tempo_flat = np.full(N_GRID_CELLS, np.nan, dtype=np.float32)
                rrfs_flat = np.full(N_GRID_CELLS, np.nan, dtype=np.float32)
                tempo_flat[indices] = obs
                rrfs_flat[indices] = mod
                tempo_grid = tempo_flat.reshape(GRID_SHAPE)
                rrfs_grid = rrfs_flat.reshape(GRID_SHAPE)

        diff = (mod - obs).astype(np.float32, copy=False)

        if MAKE_HOURLY_PLOTS:
            if using_kdtree_nearest():
                method_note = "Script-1 KDTree -> 0.05-deg grid"
            else:
                method_note = f"RRFS -> TEMPO ({REGRID_METHOD}); paired -> 0.05-deg bins"

            tempo_title = (
                f"TEMPO AOD: {tempo_filename_time_label(tempo_files, tempo_hour)}\n"
                f"user QC; AOD <= {AOD_CEILING}; {method_note}"
            )
            rrfs_title = (
                f"RRFS_A 3 km f{rrfs_hour:03d}\n"
                f"same-hour pairing; {method_note}"
            )
            output_file = os.path.join(
                PLOT_DIR,
                f"RRFS_vs_TEMPO_AOD_{target_date}_{hour_str}z.png",
            )
            plot_side_by_side(
                tempo_grid,
                rrfs_grid,
                tempo_title,
                rrfs_title,
                output_file,
            )

        print(
            f"[SUCCESS] {target_date} {hour_str}z -> "
            f"f{rrfs_hour:03d}; paired 0.05-deg cells={diff.size}"
        )

        obs64 = obs.astype(np.float64)
        mod64 = mod.astype(np.float64)
        diff64 = diff.astype(np.float64)

        result = {
            "date": target_date,
            "hour": tempo_hour,
            "indices": indices,
            "difference": diff,
            "sum_diff": float(np.sum(diff64)),
            "sum_sq_diff": float(np.sum(diff64 ** 2)),
            "sum_obs": float(np.sum(obs64)),
            "sum_mod": float(np.sum(mod64)),
            "sum_obs2": float(np.sum(obs64 * obs64)),
            "sum_mod2": float(np.sum(mod64 * mod64)),
            "sum_obs_mod": float(np.sum(obs64 * mod64)),
            "count": int(diff.size),
        }

        # Daily means and the spatial-r map both need the paired observation
        if MAKE_SPATIAL_CORRELATION_MAP or MAKE_DAILY_PLOTS:
            result["observation"] = obs

        return result

    except Exception as exc:
        print(f"[ERROR] date={target_date} hour={hour_str}z error={exc}")
        traceback.print_exc()
        return None


# MAIN

if __name__ == "__main__":
    validate_regrid_method()
    print("--- Initializing TEMPO/RRFS AOD pipeline ---")
    if using_kdtree_nearest():
        print(
            f"--- Regridding: Script-1 KDTree nearest "
            f"(TEMPO <= {TEMPO_MAX_DISTANCE_DEG} deg; "
            f"RRFS <= {RRFS_MAX_DISTANCE_DEG} deg) ---"
        )
    else:
        print(
            f"--- Regridding: xESMF {REGRID_METHOD}; "
            "RRFS/model -> each TEMPO granule -> paired 0.05-deg hourly bins ---"
        )

    base_tasks = []

    for target_date in DATES_TO_PROCESS:
        matching_dirs = [
            path
            for path in TEMPO_PATH.glob(f"*{target_date}*")
            if path.is_dir()
        ]

        if not matching_dirs:
            print(f"[MISSING TEMPO DIRECTORY] {target_date}")
            continue

        for target_dir in matching_dirs:
            for hour in HOURS_TO_PROCESS:
                base_tasks.append(
                    (target_date, hour, str(target_dir), target_dir.name)
                )

    if not base_tasks:
        raise RuntimeError("No TEMPO tasks were built.")

    # In xESMF mode the destination is each moving TEMPO granule, so there is
    # intentionally no single reusable RRFS->destination weight file.
    tasks = list(base_tasks)

    print(f"--- Built {len(tasks)} tasks total ---")
    print(
        f"--- Plot mode: {PLOT_MODE}; "
        f"daily minimum hours/cell={MIN_DAILY_HOURS_PER_CELL} ---"
    )

    # Global spatial statistics across every successfully paired hour/date.
    sum_bias = np.zeros(N_GRID_CELLS, dtype=np.float64)
    sum_sq_error = np.zeros(N_GRID_CELLS, dtype=np.float64)
    count = np.zeros(N_GRID_CELLS, dtype=np.uint32)

    # Sufficient statistics for Pearson r at each target-grid cell.
    if MAKE_SPATIAL_CORRELATION_MAP:
        spatial_sum_obs = np.zeros(N_GRID_CELLS, dtype=np.float64)
        spatial_sum_mod = np.zeros(N_GRID_CELLS, dtype=np.float64)
        spatial_sum_obs2 = np.zeros(N_GRID_CELLS, dtype=np.float64)
        spatial_sum_mod2 = np.zeros(N_GRID_CELLS, dtype=np.float64)
        spatial_sum_obs_mod = np.zeros(N_GRID_CELLS, dtype=np.float64)

    # Scalar sufficient statistics for overall paired MB/NMB/RMSE/Pearson r.
    total_sum_diff = 0.0
    total_sum_sq_diff = 0.0
    total_sum_obs = 0.0
    total_sum_mod = 0.0
    total_sum_obs2 = 0.0
    total_sum_mod2 = 0.0
    total_sum_obs_mod = 0.0
    total_pairs = 0
    successful_hours = 0

    # Process one date at a time. This lets us make a daily mean and immediately
    # release its daily accumulators instead of storing a full-domain set for
    # every date in a long retrospective.
    for target_date in DATES_TO_PROCESS:
        date_tasks = [task for task in tasks if task[0] == target_date]
        if not date_tasks:
            continue

        n_workers = max(1, min(N_WORKERS, len(date_tasks)))
        print(
            f"--- {target_date}: {len(date_tasks)} hourly tasks; "
            f"using {n_workers} workers ---"
        )

        if MAKE_DAILY_PLOTS:
            # These accumulate *hourly paired means*. Therefore every successful
            # hour has equal temporal weight at a given 0.05-degree cell.
            daily_sum_obs = np.zeros(N_GRID_CELLS, dtype=np.float64)
            daily_sum_mod = np.zeros(N_GRID_CELLS, dtype=np.float64)
            daily_hour_count = np.zeros(N_GRID_CELLS, dtype=np.uint16)
            daily_successful_hours = 0

        with Pool(
            processes=n_workers,
            maxtasksperchild=1,
        ) as pool:
            for result in pool.imap_unordered(
                process_hour,
                date_tasks,
                chunksize=1,
            ):
                if result is None:
                    continue

                indices = result["indices"]
                diff = result["difference"].astype(np.float64, copy=False)

                # indices are unique within one target grid/hour.
                sum_bias[indices] += diff
                sum_sq_error[indices] += diff ** 2
                count[indices] += 1

                # Observation/model vectors are returned only when needed by
                # daily plotting and/or the spatial correlation calculation.
                if MAKE_SPATIAL_CORRELATION_MAP or MAKE_DAILY_PLOTS:
                    obs = result["observation"].astype(np.float64, copy=False)
                    mod = obs + diff

                if MAKE_SPATIAL_CORRELATION_MAP:
                    spatial_sum_obs[indices] += obs
                    spatial_sum_mod[indices] += mod
                    spatial_sum_obs2[indices] += obs * obs
                    spatial_sum_mod2[indices] += mod * mod
                    spatial_sum_obs_mod[indices] += obs * mod

                if MAKE_DAILY_PLOTS:
                    daily_sum_obs[indices] += obs
                    daily_sum_mod[indices] += mod
                    daily_hour_count[indices] += 1
                    daily_successful_hours += 1

                total_sum_diff += result["sum_diff"]
                total_sum_sq_diff += result["sum_sq_diff"]
                total_sum_obs += result["sum_obs"]
                total_sum_mod += result["sum_mod"]
                total_sum_obs2 += result["sum_obs2"]
                total_sum_mod2 += result["sum_mod2"]
                total_sum_obs_mod += result["sum_obs_mod"]
                total_pairs += result["count"]
                successful_hours += 1

        # Create the daily side-by-side plot after every hourly task for this
        if MAKE_DAILY_PLOTS and daily_successful_hours > 0:
            daily_valid = daily_hour_count >= MIN_DAILY_HOURS_PER_CELL

            tempo_daily_flat = np.full(
                N_GRID_CELLS,
                np.nan,
                dtype=np.float32,
            )
            rrfs_daily_flat = np.full(
                N_GRID_CELLS,
                np.nan,
                dtype=np.float32,
            )

            tempo_daily_flat[daily_valid] = (
                daily_sum_obs[daily_valid] / daily_hour_count[daily_valid]
            ).astype(np.float32)

            rrfs_daily_flat[daily_valid] = (
                daily_sum_mod[daily_valid] / daily_hour_count[daily_valid]
            ).astype(np.float32)

            tempo_daily = tempo_daily_flat.reshape(GRID_SHAPE)
            rrfs_daily = rrfs_daily_flat.reshape(GRID_SHAPE)

            if using_kdtree_nearest():
                daily_method_note = (
                    "KDTree -> paired 0.05-deg hourly fields"
                )
            else:
                daily_method_note = (
                    f"RRFS -> TEMPO ({REGRID_METHOD}); "
                    "paired -> 0.05-deg hourly bins"
                )

            tempo_title = (
                f"TEMPO AOD daily mean: {target_date}\n"
                f"{daily_successful_hours} paired hours; "
                f"minimum {MIN_DAILY_HOURS_PER_CELL} hour(s)/cell; "
                f"{daily_method_note}"
            )
            rrfs_title = (
                f"RRFS_A daily mean over TEMPO sampling: {target_date}\n"
                f"same paired hours/cells; {daily_method_note}"
            )

            daily_output = os.path.join(
                PLOT_DIR,
                f"RRFS_vs_TEMPO_AOD_DAILY_MEAN_{target_date}.png",
            )

            plot_side_by_side(
                tempo_daily,
                rrfs_daily,
                tempo_title,
                rrfs_title,
                daily_output,
            )

            print(
                f"[DAILY PLOT] {target_date}: "
                f"{daily_successful_hours} successful paired hours -> "
                f"{daily_output}"
            )

            del daily_sum_obs
            del daily_sum_mod
            del daily_hour_count
            del tempo_daily_flat
            del rrfs_daily_flat
            del tempo_daily
            del rrfs_daily
            gc.collect()

    if successful_hours == 0 or total_pairs == 0:
        raise RuntimeError("No valid TEMPO/RRFS paired hours were produced.")

    valid = count > 0

    mean_bias_flat = np.full(N_GRID_CELLS, np.nan, dtype=np.float64)
    rmse_flat = np.full(N_GRID_CELLS, np.nan, dtype=np.float64)

    mean_bias_flat[valid] = sum_bias[valid] / count[valid]
    rmse_flat[valid] = np.sqrt(sum_sq_error[valid] / count[valid])

    mean_bias = mean_bias_flat.reshape(GRID_SHAPE)
    rmse = rmse_flat.reshape(GRID_SHAPE)

    # Pearson r at each grid cell across the available hourly pairs.
    spatial_r = None
    if MAKE_SPATIAL_CORRELATION_MAP:
        n = count.astype(np.float64)
        numerator = n * spatial_sum_obs_mod - spatial_sum_obs * spatial_sum_mod
        obs_var_term = n * spatial_sum_obs2 - spatial_sum_obs * spatial_sum_obs
        mod_var_term = n * spatial_sum_mod2 - spatial_sum_mod * spatial_sum_mod
        denominator_sq = obs_var_term * mod_var_term

        r_flat = np.full(N_GRID_CELLS, np.nan, dtype=np.float64)
        r_valid = (count >= MIN_CORRELATION_PAIRS) & (denominator_sq > 0.0)
        r_flat[r_valid] = numerator[r_valid] / np.sqrt(denominator_sq[r_valid])
        r_flat[r_valid] = np.clip(r_flat[r_valid], -1.0, 1.0)
        spatial_r = r_flat.reshape(GRID_SHAPE)

    # Pair-weighted scalar statistics.
    overall_mb = total_sum_diff / total_pairs
    overall_rmse = np.sqrt(total_sum_sq_diff / total_pairs)
    overall_nmb = (
        100.0 * total_sum_diff / total_sum_obs
        if total_sum_obs != 0.0
        else np.nan
    )
    overall_r = pearson_r_from_sums(
        total_pairs,
        total_sum_obs,
        total_sum_mod,
        total_sum_obs2,
        total_sum_mod2,
        total_sum_obs_mod,
    )

    print("\n--- OVERALL PAIRED STATISTICS ---")
    print(f"Successful hourly pairs: {successful_hours}")
    print(f"Total paired grid cells: {total_pairs}")
    print(f"Mean Bias (RRFS - TEMPO): {overall_mb:.4f}")
    print(f"NMB: {overall_nmb:.2f}%")
    print(f"RMSE: {overall_rmse:.4f}")
    print(f"Pearson r: {overall_r:.4f}")


    title = (
        "RRFS Evaluation over TEMPO Sampling Domain\n"
        f"Range: {DATES_TO_PROCESS[0]}-{DATES_TO_PROCESS[-1]}; "
        f"successful hours: {successful_hours}"
    )

    plot_spatial_metric(
        mean_bias,
        title,
        "Model Bias (RRFS - TEMPO)",
        "bwr",
        -0.4,
        0.4,
        os.path.join(
            PLOT_DIR,
            "TEMPO_vs_RRFS_Spatial_Mean_Bias_FullDomain.png",
        ),
    )

    plot_spatial_metric(
        rmse,
        title,
        "Error Magnitude (RMSE)",
        "viridis",
        0.0,
        0.8,
        os.path.join(
            PLOT_DIR,
            "TEMPO_vs_RRFS_Spatial_RMSE_FullDomain.png",
        ),
    )

    if MAKE_SPATIAL_CORRELATION_MAP and spatial_r is not None:
        plot_spatial_metric(
            spatial_r,
            title,
            f"Pearson Correlation r (minimum {MIN_CORRELATION_PAIRS} pairs)",
            "RdBu_r",
            -1.0,
            1.0,
            os.path.join(
                PLOT_DIR,
                "TEMPO_vs_RRFS_Spatial_Pearson_r_FullDomain.png",
            ),
        )

    print(f"All tasks completed successfully 🙂. Outputs saved to: {PLOT_DIR}")
