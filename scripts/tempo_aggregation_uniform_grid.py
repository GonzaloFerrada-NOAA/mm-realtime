import sys, os
import re
import glob
import numpy as np
import netCDF4 as nc
from datetime import datetime, timedelta

sys.path.insert(0, "/scratch3/BMC/gsd-fv3-dev/Gonzalo.Ferrada/.HOME/PYTHON/shared-packages/pyearthsciences")
import src as es

# =============================================================================
# TEMPO L2 -> uniform 0.1-deg grid, hourly aggregation.
#
# Reads one day of raw TEMPO_AODALH_L2_V*.nc granules, keeps only pixels from
# granules whose (whole-granule) granule_level_quality_flag == 0 and whose
# per-pixel dqf <= DQF_MAX, bins them into a uniform 0.1x0.1 deg lon/lat grid
# (nearest-box membership, not xESMF), and writes hourly mean/std/max for
# aod550 and alh to tempo_aggregated_0p2deg_YYYYMMDD.nc. Each hour's bin is a
# +/-30 min window: hour H = [H:00-0:30, H:00+0:30), e.g. 14z = [13:30, 14:30).
#
# Run once per day, before the model comparison script -- the comparison
# script then regrids the model onto this single fixed TEMPO grid instead of
# TEMPO being regridded separately for every model.
# =============================================================================

# TEMPO's field of regard is North America only:
LON_MIN, LON_MAX = -150.0, -40.0
LAT_MIN, LAT_MAX = 15.0, 65.0
GRID_RES = 0.1

DQF_MAX = 0  # per-pixel QC: dqf <= DQF_MAX (0=high, 1=medium quality)

TEMPO_FILENAME_TIME = re.compile(r"_(\d{8}T\d{6})Z")  # e.g. ..._20260908T163559Z_...


def list_tempo_files(tempo_dir):
    """Lists every TEMPO L2 granule in tempo_dir with its granule start time, parsed from
    the filename (e.g. TEMPO_AODALH_L2_V02_20260908T163559Z_S009G01.nc -> 2026-09-08 16:35:59).
    Granules whose filename doesn't carry a parseable timestamp are skipped."""
    files = sorted(glob.glob(os.path.join(tempo_dir, "TEMPO_AODALH_L2_V*.nc")))
    tagged = []
    for filepath in files:
        match = TEMPO_FILENAME_TIME.search(os.path.basename(filepath))
        if not match:
            es.msg(f"  [SKIP] {os.path.basename(filepath)}: no timestamp in filename")
            continue
        tagged.append((filepath, datetime.strptime(match.group(1), "%Y%m%dT%H%M%S")))
    return tagged


def files_in_hour_window(tagged_files, day_start, hour):
    """Files whose granule start time falls in the [hour-0:30, hour+0:30) window, e.g. hour=14
    covers [13:30, 14:30). Granules from the adjacent day that would fall in hour 0's or hour
    23's window are not included, since only one day's directory is scanned."""
    window_start = day_start + timedelta(hours=hour, minutes=-30)
    window_end = window_start + timedelta(hours=1)
    return [f for f, t in tagged_files if window_start <= t < window_end]


def parse_start_time(value):
    """Parses START_TIME in either 'YYYYMMDD' or '%Y-%m-%d %H:%M:%S' form."""
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y%m%d"):
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    raise ValueError(f"START_TIME={value!r} doesn't match 'YYYYMMDD' or 'YYYY-MM-DD HH:MM:SS'.")


def build_uniform_grid():
    """Builds cell-center lon/lat coordinates and bin edges for the 0.1-deg output grid.
    n_lon/n_lat computed from the bounds so edges and centers always align exactly
    (avoids np.arange floating-point drift)."""
    n_lon = round((LON_MAX - LON_MIN) / GRID_RES)
    n_lat = round((LAT_MAX - LAT_MIN) / GRID_RES)
    lon_edges = LON_MIN + GRID_RES * np.arange(n_lon + 1)
    lat_edges = LAT_MIN + GRID_RES * np.arange(n_lat + 1)
    lon = 0.5 * (lon_edges[:-1] + lon_edges[1:])
    lat = 0.5 * (lat_edges[:-1] + lat_edges[1:])
    return lon, lat, lon_edges, lat_edges


def read_tempo_granule(filepath):
    """Reads one TEMPO L2 granule's aod550/alh + lon/lat, gated by the granule-level
    quality flag (whole granule rejected unless granule_level_quality_flag == 0) and
    the per-pixel dqf (dqf <= DQF_MAX)."""
    with nc.Dataset(filepath, 'r') as ds:
        try:
            granule_flag = int(ds.variables['granule_level_quality_flag'][...])
        except (KeyError, TypeError, ValueError):
            return None
        if granule_flag != 0:
            return None

        geo = ds.groups['geolocation']
        product = ds.groups['product']
        qc = ds.groups['quality_diagnostic_flags']

        lon = np.ma.filled(geo['longitude'][:], np.nan).astype(np.float64)
        lat = np.ma.filled(geo['latitude'][:], np.nan).astype(np.float64)
        aod = np.ma.filled(product['aod550'][:], np.nan).astype(np.float64)
        alh = np.ma.filled(product['alh'][:], np.nan).astype(np.float64)
        dqf = np.ma.filled(qc['dqf'][:], 255).astype(np.int16)

        valid = (
            np.isfinite(lon) & np.isfinite(lat)
            & (np.abs(lat) <= 90.0) & (np.abs(lon) <= 180.0)
            & np.isfinite(aod) & (dqf <= DQF_MAX)
        )
        if not np.any(valid):
            return None

        return {
            'lon': lon[valid],
            'lat': lat[valid],
            'aod550': aod[valid],
            'alh': alh[valid],  # left as NaN where alh itself is missing; aod550 validity drives the pixel mask
        }


def _cell_stats(values, flat_idx, n_cells, grid_shape):
    """Per-cell mean/std/max/count of `values`, grouped by flat_idx (one entry per pixel).
    NaNs in `values` (e.g. missing alh at an otherwise-valid AOD pixel) are dropped
    from that cell's stats rather than propagated."""
    finite = np.isfinite(values)
    idx_f, val_f = flat_idx[finite], values[finite]

    count = np.bincount(idx_f, minlength=n_cells)
    vsum  = np.bincount(idx_f, weights=val_f, minlength=n_cells)
    vsum2 = np.bincount(idx_f, weights=val_f ** 2, minlength=n_cells)

    vmax = np.full(n_cells, -np.inf)
    np.maximum.at(vmax, idx_f, val_f)

    with np.errstate(invalid='ignore'):
        mean = np.where(count > 0, vsum / count, np.nan)
        var  = np.where(count > 0, vsum2 / count - mean ** 2, np.nan)
    std  = np.sqrt(np.clip(var, 0, None))
    maxv = np.where(count > 0, vmax, np.nan)

    return (mean.reshape(grid_shape).astype(np.float32),
            std.reshape(grid_shape).astype(np.float32),
            maxv.reshape(grid_shape).astype(np.float32),
            count.reshape(grid_shape).astype(np.int32))


def aggregate_hour(files, lon_edges, lat_edges, grid_shape):
    """Pools every granule for one hour and bins their valid pixels into the uniform
    grid (nearest-box membership via np.digitize), returning per-cell mean/std/max for
    aod550 and alh, plus the aod550 pixel count per cell. All-NaN/zero-count fields if
    no granule/pixel survives QC for that hour."""
    lon_parts, lat_parts, aod_parts, alh_parts = [], [], [], []
    for filepath in files:
        g = read_tempo_granule(filepath)
        if g is None:
            continue
        lon_parts.append(g['lon']); lat_parts.append(g['lat'])
        aod_parts.append(g['aod550']); alh_parts.append(g['alh'])

    n_cells = grid_shape[0] * grid_shape[1]
    empty_float = tuple(np.full(grid_shape, np.nan, dtype=np.float32) for _ in range(6))
    empty_count = np.zeros(grid_shape, dtype=np.int32)
    if not aod_parts:
        return empty_float + (empty_count,)

    lon = np.concatenate(lon_parts); lat = np.concatenate(lat_parts)
    aod = np.concatenate(aod_parts); alh = np.concatenate(alh_parts)

    ix = np.digitize(lon, lon_edges) - 1
    iy = np.digitize(lat, lat_edges) - 1
    in_grid = (ix >= 0) & (ix < grid_shape[1]) & (iy >= 0) & (iy < grid_shape[0])
    if not np.any(in_grid):
        return empty_float + (empty_count,)

    flat_idx = iy[in_grid] * grid_shape[1] + ix[in_grid]
    aod_mean, aod_std, aod_max, count = _cell_stats(aod[in_grid], flat_idx, n_cells, grid_shape)
    alh_mean, alh_std, alh_max, _     = _cell_stats(alh[in_grid], flat_idx, n_cells, grid_shape)
    return aod_mean, aod_std, aod_max, alh_mean, alh_std, alh_max, count


def write_aggregated_netcdf(filepath, lon, lat, initial_time,
                             aod_mean, aod_std, aod_max, alh_mean, alh_std, alh_max, count):
    """Writes the 24-hourly, 0.1-deg aggregated TEMPO fields to a NetCDF4 file."""
    with nc.Dataset(filepath, 'w', format='NETCDF4') as ds:
        ds.createDimension('lon', len(lon))
        ds.createDimension('lat', len(lat))
        ds.createDimension('time', 24)

        var_lon = ds.createVariable('lon', 'f4', ('lon',))
        var_lon.long_name = 'longitude'
        var_lon.units = 'degrees_east'
        var_lon[:] = lon

        var_lat = ds.createVariable('lat', 'f4', ('lat',))
        var_lat.long_name = 'latitude'
        var_lat.units = 'degrees_north'
        var_lat[:] = lat

        var_time = ds.createVariable('time', 'f8', ('time',))
        var_time.long_name = 'time'
        var_time.units = f"hours since {initial_time.strftime('%Y-%m-%d %H:%M:%S')}"
        var_time.calendar = 'standard'
        var_time[:] = np.arange(24)

        def add_var(name, data, long_name, units):
            v = ds.createVariable(name, 'f4', ('time', 'lat', 'lon'), zlib=True, complevel=3, fill_value=np.nan)
            v.long_name = long_name
            v.units = units
            v[:, :, :] = np.asarray(data, dtype=np.float32)

        add_var('aod550',     aod_mean, 'hourly-mean TEMPO AOD at 550 nm, 0.1-deg aggregated', '1')
        add_var('aod550_std', aod_std,  'hourly standard deviation of TEMPO AOD at 550 nm', '1')
        add_var('aod550_max', aod_max,  'hourly maximum TEMPO AOD at 550 nm', '1')
        add_var('alh',        alh_mean, 'hourly-mean TEMPO aerosol layer height', 'km')
        add_var('alh_std',    alh_std,  'hourly standard deviation of TEMPO aerosol layer height', 'km')
        add_var('alh_max',    alh_max,  'hourly maximum TEMPO aerosol layer height', 'km')

        var_count = ds.createVariable('count', 'i4', ('time', 'lat', 'lon'), zlib=True, complevel=3, fill_value=0)
        var_count.long_name = 'number of QC-passed TEMPO aod550 pixels aggregated into this grid cell'
        var_count.units = '1'
        var_count[:, :, :] = np.asarray(count, dtype=np.int32)


# =============================================================================
# Main Execution
# =============================================================================

if __name__ == "__main__":

    TEMPO_DIR = os.environ.get("TEMPO_DIR", "None")  # dir of raw TEMPO_AODALH_L2_V*.nc granules for this day
    FILE_OUT_AGG = os.environ.get("TEMPO_FILE_OUT", "None")

    # No silent default here on purpose -- a plausible-looking fallback date is what
    # produced two straight all-NaN "successful" runs. Fail loudly instead.
    init_time_str = os.environ.get("START_TIME")
    if not init_time_str:
        raise ValueError(
            "START_TIME is not set. Export it in the launcher, e.g. "
            "'export START_TIME=\"${START_TIME}\"' (accepts 'YYYYMMDD' or 'YYYY-MM-DD HH:MM:SS')."
        )
    day_start = parse_start_time(init_time_str)
    date_str = day_start.strftime("%Y%m%d")

    if FILE_OUT_AGG == "None":
        FILE_OUT_AGG = f"tempo_aggregated_0p2deg_{date_str}.nc"

    es.msg(f"TEMPO_DIR={TEMPO_DIR}")
    es.msg(f"date={date_str}")
    es.msg(f"FILE_OUT_AGG={FILE_OUT_AGG}")

    tagged_files = list_tempo_files(TEMPO_DIR)
    es.msg(f"Found {len(tagged_files)} granule(s) in {TEMPO_DIR}")

    lon, lat, lon_edges, lat_edges = build_uniform_grid()
    grid_shape = (len(lat), len(lon))

    aod_mean = np.full((24,) + grid_shape, np.nan, dtype=np.float32)
    aod_std  = np.full((24,) + grid_shape, np.nan, dtype=np.float32)
    aod_max  = np.full((24,) + grid_shape, np.nan, dtype=np.float32)
    alh_mean = np.full((24,) + grid_shape, np.nan, dtype=np.float32)
    alh_std  = np.full((24,) + grid_shape, np.nan, dtype=np.float32)
    alh_max  = np.full((24,) + grid_shape, np.nan, dtype=np.float32)
    count    = np.zeros((24,) + grid_shape, dtype=np.int32)

    for hour in range(24):
        files = files_in_hour_window(tagged_files, day_start, hour)
        if not files:
            es.msg(f"  {hour:02d}z: no granules found")
            continue

        (aod_mean[hour], aod_std[hour], aod_max[hour],
         alh_mean[hour], alh_std[hour], alh_max[hour], count[hour]) = aggregate_hour(files, lon_edges, lat_edges, grid_shape)
        es.msg(f"  {hour:02d}z: {len(files)} granule(s) aggregated, {int(count[hour].sum())} points gridded")

    if count.sum() == 0:
        raise RuntimeError(
            f"No TEMPO points were aggregated for {date_str} (found {len(tagged_files)} granule(s) "
            f"in {TEMPO_DIR}). Check that START_TIME matches TEMPO_DIR's date and the QC filters "
            "aren't rejecting everything."
        )

    write_aggregated_netcdf(FILE_OUT_AGG, lon, lat, day_start,
                             aod_mean, aod_std, aod_max, alh_mean, alh_std, alh_max, count)
    es.msg(f"Saved {FILE_OUT_AGG}")