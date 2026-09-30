import sys, os
import csv
import numpy as np
import netCDF4 as nc
from datetime import datetime, timedelta
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap
import matplotlib.font_manager as fm

sys.path.insert(0, "/scratch3/BMC/gsd-fv3-dev/Gonzalo.Ferrada/.HOME/PYTHON/shared-packages/pyearthsciences")
import src as es
from src.ll2lamb import ll2lamb

# =============================================================================
# This is the model-comparison step of the TEMPO verification pipeline.
#
# Unlike the VIIRS script, no cropping or regridding happens here at all: the
# calling bash script already used CDO (remapbil) to put the model's AOD550
# on TEMPO's exact 0.1-deg grid (the same grid produced by
# tempo_aggregate_0p2deg.py), so model and TEMPO come in already co-located.
#
# The other real difference from VIIRS: TEMPO here carries 24 real hourly
# time steps (one per UTC hour of the day) instead of VIIRS's single overpass
# file, so the two datasets' time axes have to be matched explicitly rather
# than assumed to already correspond. The output NetCDF keeps all 24 hours
# (no daily mean at save time); the daily mean used for plotting is computed
# from that hourly stack at plot time via nanmean, same idea as MATLAB's
# nanmean across the time dimension.
# =============================================================================

font = fm.FontProperties(fname="/scratch3/BMC/acomp/Gonzalo.Ferrada/verif/realtime/sandbox/OpenSans-Regular.ttf")
for f in fm.findSystemFonts(fontpaths=["/scratch3/BMC/acomp/Gonzalo.Ferrada/verif/realtime/sandbox/Google_Sans_Code/static"]):
    fm.fontManager.addfont(f)
fmono = fm.FontProperties(family="Google Sans Code", size=5, weight="light")


# Levels:
lev_aod         = np.concatenate([[0, 0.05, 0.1, 0.15], np.arange(2, 11) / 10.0, [1.2, 1.5, 2.0]])
lev_bias_pos    = np.concatenate([[0.05], np.arange(1, 7) / 10.0])
lev_bias        = np.sort(np.concatenate([-lev_bias_pos, lev_bias_pos]))

# Colormaps
cm1 = es.hue([227,227,227], [136,183,211], 5)
cm2 = es.hue([85,180,94],[251,232,135],[252,170,95],[242,114,69],[194,27,38],[135,27,87],[255,192,203], len(lev_aod) - 1 - 5)
cmap_aod = ListedColormap(np.vstack((cm1.colors, cm2.colors)))
cmap_bias = es.hue('pan', len(lev_bias) - 1)


# =============================================================================
# Functions
# =============================================================================
def is_valid_file(filepath):
    """Returns True if filepath points to a real, usable file (i.e. not "None"/empty/missing)."""
    return bool(filepath) and filepath.lower() != "none" and os.path.isfile(filepath)

def load_map_regions(csv_path):
    """Reads a Lambert-region-specs CSV (path given via LAMBERT_CSV_FILE) into
    {region: {'ps': [cen_lat, cen_lon], 'axl': [x1, x2, y1, y2], 'mapres': str}}."""
    regions = {}
    with open(csv_path, newline='') as f:
        for row in csv.DictReader(f):
            regions[row['region']] = {
                'ps': [float(row['cen_lat']), float(row['cen_lon'])],
                'axl': [float(row['x1']), float(row['x2']), float(row['y1']), float(row['y2'])],
                'mapres': row['MapRes'],
            }
    return regions

def region_rows(region, map_regions):
    """Builds the (label, ps, axl, mapres) row list for a map figure: a single row per
    region, using that region's own Lambert specs from map_regions (LAMBERT_CSV_FILE)."""
    r = map_regions[region]
    return [(region, r['ps'], r['axl'], r['mapres'])]

def _read_times(time_var):
    """Converts a NetCDF time variable to an array of python datetimes using its own units/calendar."""
    if not hasattr(time_var, 'units'):
        raise ValueError(f"Time variable '{time_var.name}' has no 'units' attribute")
    return np.array(
        nc.num2date(
            time_var[:],
            units=time_var.units,
            calendar=getattr(time_var, 'calendar', 'standard'),
            only_use_cftime_datetimes=False,
            only_use_python_datetimes=True
        )
    )

def read_model_data(filepath):
    """Reads model AOD from a NetCDF file already bilinearly regridded (CDO remapbil) onto
    TEMPO's own 0.1-deg grid -- no cropping or spatial regridding needed here. The model's
    own native time axis is kept as-is (CDO only touches the horizontal grid)."""
    with nc.Dataset(filepath, 'r') as ds:
        if 'time' in ds.variables:
            time_var = ds.variables['time']
        elif 'XTIME' in ds.variables:
            time_var = ds.variables['XTIME']
        else:
            raise KeyError(f"Could not find either 'time' or 'XTIME' in {filepath}")

        times = _read_times(time_var)
        lon = ds.variables['lon'][:]
        lat = ds.variables['lat'][:]
        aod = ds.variables['AOD550'][:]

        # Some models report AOD as exactly zero everywhere at the first time step
        # (spin-up artifact); left as-is this biases the matched hourly mean low.
        if aod.shape[0] > 0 and np.nansum(aod[0]) == 0:
            es.msg("  First model time step has zero AOD everywhere, setting to NaN")
            aod[0] = np.nan

        result = {'lon': lon, 'lat': lat, 'time': times, 'aod': aod}

        if 'AOD550_SIMPLE' in ds.variables:
            aod_simple = ds.variables['AOD550_SIMPLE'][:]
            if aod_simple.shape[0] > 0 and np.nansum(aod_simple[0]) == 0:
                es.msg("  First model time step has zero AOD550_SIMPLE everywhere, setting to NaN")
                aod_simple[0] = np.nan
            result['aod_simple'] = aod_simple

        return result

def read_tempo_netcdf(filepath):
    """Reads the pre-aggregated, 0.1-deg TEMPO hourly file (24 real UTC-hour time steps,
    already on the CDO-regrid target grid). Unlike VIIRS's single-overpass L3 file, TEMPO's
    own time axis here must be checked and matched against the model's (see
    verify_tempo_time / match_model_to_obs_times) rather than assumed to line up."""
    with nc.Dataset(filepath, 'r') as ds:
        times = _read_times(ds.variables['time'])
        return {
            'lon': ds.variables['lon'][:],
            'lat': ds.variables['lat'][:],
            'time': times,
            'aod': ds.variables['aod550'][:],
        }

def verify_tempo_time(tempo_time, initial_time):
    """Sanity-checks TEMPO's own time axis: exactly 24 hourly steps starting at INITIAL_TIME's
    day. Catches a stale/misdated TEMPO_FILE here instead of silently mispairing hours later
    (this is exactly the class of bug that hit the aggregation step earlier in this pipeline)."""
    if len(tempo_time) != 24:
        raise ValueError(f"Expected 24 TEMPO time steps, got {len(tempo_time)}")
    day0 = initial_time.replace(hour=0, minute=0, second=0, microsecond=0)
    expected = [day0 + timedelta(hours=h) for h in range(24)]
    if list(tempo_time) != expected:
        raise ValueError(
            f"TEMPO_FILE's time axis doesn't match the expected hourly sequence for {day0.date()} "
            f"(got {tempo_time[0]} .. {tempo_time[-1]}). Check TEMPO_FILE vs INITIAL_TIME."
        )

def check_grids_match(model, tempo):
    """Verifies the model (post-CDO-regrid) and TEMPO grids actually line up -- if CDO's
    target grid wasn't really TEMPO's grid, every pixel-wise comparison below would be
    silently wrong, so this fails loudly instead."""
    if model['aod'].shape[1:] != tempo['aod'].shape[1:]:
        raise ValueError(f"Model grid {model['aod'].shape[1:]} != TEMPO grid {tempo['aod'].shape[1:]} -- CDO regrid target mismatch?")
    if not (np.allclose(model['lon'], tempo['lon'], atol=1e-3) and np.allclose(model['lat'], tempo['lat'], atol=1e-3)):
        raise ValueError("Model and TEMPO lon/lat coordinates don't match after CDO regridding.")

def match_model_to_obs_times(model_time, model_aod, obs_time, window_minutes=30):
    """For each TEMPO hourly time in obs_time, averages model_aod over every model time step
    within [-window_minutes, +window_minutes) of it (e.g. 14z TEMPO <- model steps in
    [13:30, 14:30)). Returns an array with the same leading time length as obs_time; NaN
    where no model time step falls in that window."""
    matched = np.full((len(obs_time),) + model_aod.shape[1:], np.nan, dtype=np.float32)
    for i, t in enumerate(obs_time):
        t0 = t - timedelta(minutes=window_minutes)
        t1 = t + timedelta(minutes=window_minutes - 1, seconds=59)
        idx = (model_time >= t0) & (model_time <= t1)
        if not np.any(idx):
            es.msg(f"  [WARN] no model time step within +/-{window_minutes}min of TEMPO time {t}")
            continue
        with np.errstate(invalid='ignore'):
            matched[i] = np.nanmean(model_aod[idx], axis=0)
    return matched

def write_output_netcdf(filepath, lon, lat, time_axis, model_aod, tempo_aod, model_simple_aod=None):
    """Writes the paired, still-hourly (matches TEMPO's 24 time steps) model/TEMPO AOD to a
    NetCDF4 file. The daily mean is intentionally NOT computed here, so the hourly detail
    stays available for future use -- the plotting step computes it via nanmean instead."""
    day0 = time_axis[0].replace(hour=0, minute=0, second=0, microsecond=0)

    with nc.Dataset(filepath, "w", format="NETCDF4") as ds:
        ds.createDimension("lon", len(lon))
        ds.createDimension("lat", len(lat))
        ds.createDimension("time", len(time_axis))

        var_lon = ds.createVariable("lon", "f4", ("lon",))
        var_lon.long_name = "longitude"
        var_lon.units = "degrees_east"
        var_lon[:] = lon

        var_lat = ds.createVariable("lat", "f4", ("lat",))
        var_lat.long_name = "latitude"
        var_lat.units = "degrees_north"
        var_lat[:] = lat

        var_time = ds.createVariable("time", "f8", ("time",))
        var_time.long_name = "time"
        var_time.units = f"hours since {day0.strftime('%Y-%m-%d %H:%M:%S')}"
        var_time.calendar = "standard"
        var_time[:] = [(t - day0).total_seconds() / 3600.0 for t in time_axis]

        def add_var(name, data, long_name):
            v = ds.createVariable(name, "f4", ("time", "lat", "lon"), zlib=True, complevel=3, fill_value=np.nan)
            v.long_name = long_name
            v[:, :, :] = np.asarray(data, dtype=np.float32)

        add_var("aod_model", model_aod, "hourly model aerosol optical depth, matched to TEMPO's time steps (+/-30 min)")
        add_var("aod_tempo", tempo_aod, "hourly TEMPO aerosol optical depth")
        if model_simple_aod is not None:
            add_var("aod_model_simple", model_simple_aod, "hourly model AOD550_SIMPLE, matched to TEMPO's time steps (+/-30 min)")

def read_output_netcdf(filepath):
    """Reads back a per-model hourly NetCDF file written by write_output_netcdf.
    aod_model/aod_tempo keep their full (time, lat, lon) shape here; the daily
    mean used for plotting is computed by the caller via nanmean over time."""
    with nc.Dataset(filepath, 'r') as ds:
        result = {
            'lon': ds.variables['lon'][:],
            'lat': ds.variables['lat'][:],
            'aod_model': ds.variables['aod_model'][:],
            'aod_tempo': ds.variables['aod_tempo'][:],
        }
        if 'aod_model_simple' in ds.variables:
            result['aod_model_simple'] = ds.variables['aod_model_simple'][:]
        return result


# =============================================================================
# Plotting -- same workflow/functions as the VIIRS script (no cartopy). The
# only addition versus VIIRS: fields read from NetCDF are now (time, lat, lon)
# instead of (lat, lon), so the daily mean (nanmean over time, MATLAB-style)
# is computed once up front before anything below ever sees a 3D array.
# =============================================================================
def get_metrics(lon, lat, obs, model, origin, axlims):
    """Computes metrics over the pixels actually visible in a plot panel.
    origin: Lambert projection specs for that row (the same Origin passed to es.spatial).
    axlims: [xmin, xmax, ymin, ymax] in projected km for that row (its axl)."""
    lon2d, lat2d = np.meshgrid(lon, lat)
    x, y = ll2lamb(lat2d, lon2d, origin)
    x_f, y_f, lat_f = x.ravel(), y.ravel(), lat2d.ravel()
    obs_f, model_f = obs.ravel(), model.ravel()

    mask = (x_f >= axlims[0]) & (x_f <= axlims[1]) & (y_f >= axlims[2]) & (y_f <= axlims[3])

    return es.metrics(obs_f[mask], model_f[mask], np.cos(np.radians(lat_f[mask])), metrics_to_show=["R", "MB", "cRMSE"], num_format='.3f')

def _finalize_grid(axes, axl, ncols, hasMetrics):
    """Shared axis-limit/tick cleanup and layout pass for a 2-row multi-column figure."""
    nrows = len(axes)
    for row in range(nrows):
        for ax in axes[row]:
            ax.set_xlim(axl[row][0], axl[row][1])
            ax.set_ylim(axl[row][2], axl[row][3])
            ax.set_xticks([])
            ax.set_yticks([])

    vertical_spacement = 10
    if nrows > 1 and hasMetrics:
        vertical_spacement = 35

    es.reorganizeaxes(nrows, ncols, width=300, height=None, spacing_horiz=10, spacing_vert=vertical_spacement,
                        remove_tick_labels=True, margin=120)

def _finalize_colorbar(cb, nrows, ncols, rotate_labels=False):
    """Shared colorbar repositioning/tick cleanup, stretched across the full row width."""
    cb = es.reorganizecolorbar(cb, nrows, ncols, 'bottom', proportion=0.96, extent_axes=[1, ncols])
    cb.ax.tick_params(labelsize=9.5)

    x0, y0, w, _ = cb.ax.get_position().bounds
    cb.ax.set_position([x0, y0, w, 0.02])

    cb_ticks = cb.get_ticks()[1:-1]
    cb_labels = [t.get_text() for t in cb.ax.get_xticklabels()][1:-1]
    cb.set_ticks(cb_ticks)
    cb.set_ticklabels(cb_labels)
    if rotate_labels:
        plt.setp(cb.ax.get_xticklabels(), rotation=90)
    return cb

def make_spatial_figure(columns, rows, lev_aod, cmap_aod, initial_time, end_time, obs_label):
    """Spatial AOD comparison. columns: list of (label, lon, lat, field) tuples, column 0 is TEMPO.
    rows: list of (label, ps, axl, mapres) tuples, one per map row. `field` here is already
    the daily (time-nanmean'd) 2D array -- see the daily-mean step in __main__."""
    ncols = len(columns)
    nrows = len(rows)

    axes = [[None] * ncols for _ in range(nrows)]
    ids = []
    cb = None

    for row, (row_label, row_ps, row_axl, row_mapres) in enumerate(rows):
        for col, (name, lon, lat, field) in enumerate(columns):
            es.msg(f"{row_label} {name} AOD")
            ax = plt.subplot(nrows, ncols, row * ncols + col + 1)
            axes[row][col] = ax

            if col == 0:
                es.spatial(lon, lat, field, Projection='lambert', Origin=row_ps, Levels=lev_aod,
                           MapRes=row_mapres, Colormap=cmap_aod, GeoTicks='off', Colorbar='off', MapWidth=0.3)
            elif cb is None:
                cb, _ = es.spatial(lon, lat, field, Projection='lambert', Origin=row_ps, Levels=lev_aod,
                                    MapRes=row_mapres, Colormap=cmap_aod, GeoTicks='off', MapWidth=0.3)
            else:
                es.spatial(lon, lat, field, Projection='lambert', Origin=row_ps, Levels=lev_aod,
                           MapRes=row_mapres, Colormap=cmap_aod, GeoTicks='off', Colorbar='off', MapWidth=0.3)

            if row == 0:
                ids.append(es.figid(f'{name}', ax=ax))

    _finalize_grid(axes, [r[2] for r in rows], ncols, False)
    cb = _finalize_colorbar(cb, nrows, ncols)
    plt.setp(ids, fontsize=11, fontproperties=font)

    stime1 = initial_time.strftime("%Y-%m-%d %H")
    stime2 = end_time.strftime("%Y-%m-%d %H")
    label_str = f"{obs_label} AOD 550 nm (daily mean)\n{stime1}Z to {stime2}Z"
    axes[0][0].text(0, 1.2, label_str, fontsize=9, transform=axes[0][0].transAxes, fontproperties=font, color=(0.5, 0.5, 0.5))

def make_bias_figure(columns, M, rows, lev_bias, cmap_bias, initial_time, end_time, obs_label):
    """Bias (model - TEMPO) comparison. columns: list of (label, lon, lat, field) tuples, one per model.
    rows: list of (label, ps, axl, mapres) tuples, one per map row.
    M[i][row] holds the metrics for model i over the pixels shown in that row's panel (see get_metrics)."""
    ncols = len(columns)
    nrows = len(rows)

    axes = [[None] * ncols for _ in range(nrows)]
    ids = []
    mms = []
    cb = None

    for row, (row_label, row_ps, row_axl, row_mapres) in enumerate(rows):
        for col, (name, lon, lat, field) in enumerate(columns):
            es.msg(f"{row_label} {name} Bias")
            ax = plt.subplot(nrows, ncols, row * ncols + col + 1)
            axes[row][col] = ax

            if cb is None:
                cb, _ = es.spatial(lon, lat, field, Projection='lambert', Origin=row_ps, Levels=lev_bias,
                                    MapRes=row_mapres, Colormap=cmap_bias, GeoTicks='off', MapWidth=0.3)
            else:
                es.spatial(lon, lat, field, Projection='lambert', Origin=row_ps, Levels=lev_bias,
                           MapRes=row_mapres, Colormap=cmap_bias, GeoTicks='off', Colorbar='off', MapWidth=0.3)

            if row == 0:
                ids.append(es.figid(f"{name} bias", ax=ax))

            mms.append(es.figid('\n'.join(M[col][row].Text), Location='outright'))
            ax.set_facecolor((0.8, 0.8, 0.8))

    _finalize_grid(axes, [r[2] for r in rows], ncols, True)
    cb = _finalize_colorbar(cb, nrows, ncols, rotate_labels=False)
    plt.setp(ids, fontsize=11, fontproperties=font)
    plt.setp(mms, fontsize=4, fontproperties=fmono)

    stime1 = initial_time.strftime("%Y-%m-%d %H")
    stime2 = end_time.strftime("%Y-%m-%d %H")
    label_str = f"AOD 550 nm bias against {obs_label} (daily mean)\n{stime1}Z to {stime2}Z"
    axes[0][0].text(0, 1.2, label_str, fontsize=9, transform=axes[0][0].transAxes, fontproperties=font, color=(0.5, 0.5, 0.5))


# =============================================================================
# Main Execution
# =============================================================================

if __name__ == "__main__":

    # Environment Variables
    MODEL_NAME = os.environ.get("MODEL_NAME", "None")
    FILE_MODEL = os.environ.get("FILE_MODEL", "None")   # model AOD550, already CDO-regridded onto TEMPO_FILE's grid
    TEMPO_FILE = os.environ.get("TEMPO_FILE", "None")   # tempo_aggregated_hourly_0p1deg_*.nc (24 hourly steps)
    FILE_OUT   = os.environ.get("FILE_OUT", "aod_mean.nc")
    PATH_FIG   = os.environ.get("PATH_FIG", "./")

    init_time_str = os.environ.get("INITIAL_TIME", "2026-07-12 00:00:00")
    initial_time = datetime.strptime(init_time_str, "%Y-%m-%d %H:%M:%S")
    end_time = initial_time + timedelta(hours=24)
    ymd = initial_time.strftime('%Y-%m-%d')

    es.msg(f"MODEL_NAME={MODEL_NAME}")
    es.msg(f"FILE_MODEL={FILE_MODEL}")
    es.msg(f"TEMPO_FILE={TEMPO_FILE}")
    es.msg(f"PATH_FIG={PATH_FIG}")

    opt_save_netcdf = os.getenv("opt_save_netcdf", "False").lower() == "true"
    opt_make_figure = os.getenv("opt_make_figure", "False").lower() == "true"


    if opt_save_netcdf:

        # 1) Open model data -- already regridded onto TEMPO's grid by CDO upstream
        es.msg("Reading model data...")
        model = read_model_data(FILE_MODEL)

        # 2) Open TEMPO's pre-aggregated hourly data (24 real UTC-hour time steps)
        es.msg("Reading TEMPO data...")
        tempo = read_tempo_netcdf(TEMPO_FILE)

        es.msg("Verifying TEMPO time axis and model/TEMPO grid match...")
        verify_tempo_time(tempo['time'], initial_time)
        check_grids_match(model, tempo)

        es.msg("Matching model time steps to TEMPO's hourly times (+/-30 min)...")
        model_matched = match_model_to_obs_times(model['time'], model['aod'], tempo['time'])

        model_simple_matched = None
        if 'aod_simple' in model:
            es.msg("Matching model AOD550_SIMPLE to TEMPO's hourly times...")
            model_simple_matched = match_model_to_obs_times(model['time'], model['aod_simple'], tempo['time'])

        es.msg("Saving NetCDF output (24 hourly time steps)...")
        write_output_netcdf(FILE_OUT, tempo['lon'], tempo['lat'], tempo['time'],
                             model_matched, tempo['aod'], model_simple_matched)
        es.msg(f"Saved NetCDF output to {FILE_OUT}")


    if opt_make_figure:
        es.msg("Plotting...")

        # Read the models in current model_type:
        model_names_all = os.environ["MODEL_NAMES"].split()
        model_files_all = os.environ["FILE_OUT"].split()

        # labels for output figure name
        stime1 = initial_time.strftime("%Y-%m-%d_%H")
        stime2 = end_time.strftime("%Y-%m-%d_%H")

        # Regions to plot:
        regions = ["CONUS", "R1", "R2", "R3", "R4", "R5", "R6", "R7", "R8", "R9", "R10"]
        regions_csv_file = os.environ.get("LAMBERT_CSV_FILE", "None")
        if not is_valid_file(regions_csv_file):
            raise RuntimeError(f"LAMBERT_CSV_FILE is not set to a valid file (got {regions_csv_file!r}).")
        map_regions = load_map_regions(regions_csv_file)

        if len(model_names_all) != len(model_files_all):
            raise RuntimeError(f"MODEL_NAMES ({len(model_names_all)}) and FILE_OUT ({len(model_files_all)}) counts must match.")

        # Skip models whose NetCDF output is "None" (e.g. that model wasn't run for this cycle)
        model_names, model_files = [], []
        for name, path in zip(model_names_all, model_files_all):
            if is_valid_file(path):
                model_names.append(name)
                model_files.append(path)
            else:
                es.msg(f"  {name}: no NetCDF output ({path}), skipping")

        if not model_files:
            raise RuntimeError("No valid per-model NetCDF outputs were provided (FILE_OUT).")

        obs_label = "TEMPO"

        es.msg("Reading per-model NetCDF output...")
        outputs = [read_output_netcdf(f) for f in model_files]

        # Daily mean (nanmean across the 24-hour time axis), computed here at plot time --
        # the saved NetCDF keeps the full, unmasked hourly detail for other future uses.
        # For an apples-to-apples comparison, the model is masked to TEMPO's own per-hour
        # validity before averaging: an hour/pixel where TEMPO has no data (cloud, no
        # granule, etc.) is excluded from the model's daily mean too, rather than letting
        # the model "fill in" hours TEMPO never observed.
        for o in outputs:
            tempo_valid = np.isfinite(o['aod_tempo'])
            model_masked = np.where(tempo_valid, o['aod_model'], np.nan)

            with np.errstate(invalid='ignore'):
                o['aod_tempo_daily'] = np.nanmean(o['aod_tempo'], axis=0)
                o['aod_model_daily'] = np.nanmean(model_masked, axis=0)
                if 'aod_model_simple' in o:
                    model_simple_masked = np.where(tempo_valid, o['aod_model_simple'], np.nan)
                    o['aod_model_simple_daily'] = np.nanmean(model_simple_masked, axis=0)

        model_specs = []
        for name, o in zip(model_names, outputs):
            model_specs.append((name, o, 'aod_model_daily'))
            if 'aod_model_simple_daily' in o:
                model_specs.append((f"{name} (SIMPLE)", o, 'aod_model_simple_daily'))

        spatial_columns = [(obs_label, outputs[0]['lon'], outputs[0]['lat'], outputs[0]['aod_tempo_daily'])]
        spatial_columns += [(name, o['lon'], o['lat'], o[field]) for name, o, field in model_specs]

        # Plot spatial_overlay
        for region in regions:
            rows = region_rows(region, map_regions)

            make_spatial_figure(spatial_columns, rows, lev_aod, cmap_aod, initial_time, end_time, obs_label)

            fig_out = f"{PATH_FIG}/plot_grp2.spatial_overlay.aod_500nm.{stime1}.{stime2}.{region}.TEMPO_{ymd}.png"
            plt.gcf().savefig(fig_out, bbox_inches='tight', dpi=200)
            plt.close('all')
            es.msg(f"{fig_out} saved!")

        # Plot spatial_bias
        bias_columns = [(name, o['lon'], o['lat'], o[field] - o['aod_tempo_daily'])
                         for name, o, field in model_specs]

        for region in regions:
            rows = region_rows(region, map_regions)

            M = [[get_metrics(o['lon'], o['lat'], o['aod_tempo_daily'], o[field], row_ps, row_axl)
                  for (_, row_ps, row_axl, _) in rows]
                 for _, o, field in model_specs]

            make_bias_figure(bias_columns, M, rows, lev_bias, cmap_bias, initial_time, end_time, obs_label)

            fig_out = f"{PATH_FIG}/plot_grp3.spatial_bias.aod_500nm.{stime1}.{stime2}.{region}.TEMPO_{ymd}.png"
            plt.gcf().savefig(fig_out, bbox_inches='tight', dpi=200)
            plt.close('all')
            es.msg(f"{fig_out} saved!")