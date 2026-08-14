import os
import re
import warnings
import numpy as np
import netCDF4 as nc
from datetime import datetime, timedelta
import matplotlib
import matplotlib.colors as mcolors

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.text as mtext
import cartopy.crs as ccrs
from PIL import Image, ImageChops, ImageDraw, ImageFont

# =============================================================================
# Functions
# =============================================================================

AOD_CMAP_RGB = np.array([
    [208, 225, 242],
    [152, 198, 224],
    [85, 158, 204],
    [33, 111, 177],
    [18, 123, 99],
    [60, 163, 85],
    [129, 200, 101],
    [209, 231, 141],
    [254, 213, 141],
    [250, 156, 89],
    [244, 121, 73],
    [228, 80, 56],
    [190, 23, 39],
    [164, 0, 52],
    [153, 0, 250],
], dtype=float) / 255.0

BIAS_CMAP_RGB = np.array([
    [122, 0, 112],
    [91, 50, 168],
    [29, 36, 192],
    [1, 66, 227],
    [0, 151, 255],
    [43, 238, 255],
    [254, 254, 254],
    [244, 247, 42],
    [241, 205, 1],
    [244, 147, 1],
    [247, 85, 0],
    [228, 33, 1],
    [150, 23, 0],
], dtype=float) / 255.0

FIG_TITLE_FONTSIZE = 18
CBAR_TICK_FONTSIZE = 14
CBAR_TICK_LENGTH = 6
CBAR_TICK_WIDTH = 1.1
CBAR_TICK_PAD_VERTICAL = 8
CBAR_TICK_PAD_HORIZONTAL = 3

PIL_TITLE_FONTSIZE = 32
PIL_CBAR_LABEL_FONTSIZE = 28
PIL_CBAR_TICK_FONTSIZE = 22

def fractional_hour_to_datetime(t, base_date):
    """Converts fractional hours to a datetime object."""
    if not np.isfinite(t) or t < 0:
        return datetime(1900, 1, 1)
    return base_date + timedelta(milliseconds=int(round(t * 60 * 60 * 1000)))

def viirs_file_date(filepath, fallback_time):
    """Extracts the date from the VIIRS filename or falls back to initial time."""
    filename = os.path.basename(filepath)
    match = re.search(r'_(\d{8})(?:_[^.]+)?\.nc$', filename)
    if not match:
        return fallback_time.replace(hour=0, minute=0, second=0, microsecond=0)
    return datetime.strptime(match.group(1), "%Y%m%d")

def read_model_data(filepath):
    """Reads model data from a NetCDF file."""
    with nc.Dataset(filepath, 'r') as ds:
        time_vals = ds.variables['time'][:]
        # Convert unix seconds to datetime
        times = np.array([datetime.fromtimestamp(t) for t in time_vals])
        
        return {
            'lon': ds.variables['lon'][:],
            'lat': ds.variables['lat'][:],
            'time': times,
            'aod': ds.variables['AOD550'][:]
        }

def replace_bad_viirs_aod(aod):
    """Replaces invalid or negative AOD values with NaN."""
    aod[~np.isfinite(aod) | (aod < 0)] = np.nan
    return aod

def read_viirs_netcdf(filepath, initial_time):
    """Reads VIIRS NetCDF."""
    base_date = viirs_file_date(filepath, initial_time)
    
    with nc.Dataset(filepath, 'r') as ds:
        aod = ds.variables['AOD550'][:]
        aod = replace_bad_viirs_aod(aod)
        
        # Convert fractional UTC hours manually
        overpass_time = ds.variables['overpass_time'][:]
        v_frac_to_dt = np.vectorize(lambda t: fractional_hour_to_datetime(t, base_date))
        times = v_frac_to_dt(overpass_time)
        
        return {
            'lon': ds.variables['lon'][:],
            'lat': ds.variables['lat'][:],
            'time': times,
            'aod': aod
        }

def average_aod(data1, data2):
    """Averages two AOD arrays, handling NaNs gracefully."""
    finite1 = np.isfinite(data1)
    finite2 = np.isfinite(data2)
    count = finite1.astype(np.int8) + finite2.astype(np.int8)
    total = np.where(finite1, data1, 0.0) + np.where(finite2, data2, 0.0)
    return np.divide(total, count, out=np.full(data1.shape, np.nan, dtype=float), where=count > 0)

def subset_latlon(lon, lat, *fields, extent, pad=0.0):
    """Subsets 2D (lat, lon) fields to a lon/lat extent."""
    lon_min, lon_max, lat_min, lat_max = extent
    lon_mask = (lon >= lon_min - pad) & (lon <= lon_max + pad)
    lat_mask = (lat >= lat_min - pad) & (lat <= lat_max + pad)
    
    if not np.any(lon_mask) or not np.any(lat_mask):
        raise ValueError(f"No grid cells found inside plot extent {extent}")
    
    field_subset = tuple(field[np.ix_(lat_mask, lon_mask)] for field in fields)
    return lon[lon_mask], lat[lat_mask], field_subset

def data_to_levels(data, levels):
    """Bins data into level intervals with boundary ticks labeled as data values."""
    levels = np.asarray(levels, dtype=float)
    n_intervals = len(levels) - 1
    binned = np.full(data.shape, np.nan, dtype=float)
    
    binned[data < levels[0]] = 1.0
    for i in range(n_intervals):
        mask = (data >= levels[i]) & (data < levels[i + 1])
        binned[mask] = float(i + 1)
    binned[data >= levels[-1]] = float(n_intervals)
    
    ticks = np.arange(0.5, n_intervals + 1.5, dtype=float)
    labels = [f"{level:g}" for level in levels]
    return binned, ticks, labels

def level_colormap(colors, nlevels, bad_color="0.86"):
    """Creates a discrete colormap with a gray color for missing data."""
    if len(colors) != nlevels:
        raise ValueError(f"Colormap has {len(colors)} colors but {nlevels} intervals are needed")
    cmap = mcolors.ListedColormap(colors).copy()
    cmap.set_bad(bad_color)
    return cmap

def plot_level_field(axis, lon, lat, data, levels, cmap_colors):
    """Plots a 2D field after converting values to discrete level bands."""
    binned, ticks, labels = data_to_levels(data, levels)
    n_intervals = len(levels) - 1
    cmap = level_colormap(cmap_colors, n_intervals)
    norm = mcolors.BoundaryNorm(np.arange(0.5, n_intervals + 1.5), n_intervals)
    mesh = axis.pcolormesh(
        lon,
        lat,
        np.ma.masked_invalid(binned),
        cmap=cmap,
        norm=norm,
        shading="auto",
        transform=ccrs.PlateCarree(),
    )
    return mesh, ticks, labels

def style_colorbar_ticks(cbar, orientation):
    """Keeps colorbar tick sizing consistent across Matplotlib environments."""
    tick_axis = "y" if orientation == "vertical" else "x"
    tick_pad = CBAR_TICK_PAD_VERTICAL if orientation == "vertical" else CBAR_TICK_PAD_HORIZONTAL
    cbar.ax.tick_params(
        axis=tick_axis,
        labelsize=CBAR_TICK_FONTSIZE,
        length=CBAR_TICK_LENGTH,
        width=CBAR_TICK_WIDTH,
        pad=tick_pad,
    )
    
    tick_labels = cbar.ax.get_yticklabels() if orientation == "vertical" else cbar.ax.get_xticklabels()
    for tick_label in tick_labels:
        tick_label.set_fontsize(CBAR_TICK_FONTSIZE)

def _draw_centered_text(draw, xy, text, font, fill):
    """Draws centered text using PIL versions with or without anchor support."""
    try:
        draw.text(xy, text, fill=fill, font=font, anchor="mm")
    except TypeError:
        bbox = draw.textbbox((0, 0), text, font=font)
        width = bbox[2] - bbox[0]
        height = bbox[3] - bbox[1]
        draw.text((xy[0] - width / 2, xy[1] - height / 2), text, fill=fill, font=font)

def _paste_rotated_centered_text(image, xy, text, font, fill):
    """Pastes rotated text centered on xy."""
    scratch = Image.new("RGBA", (1, 1), (255, 255, 255, 0))
    scratch_draw = ImageDraw.Draw(scratch)
    bbox = scratch_draw.textbbox((0, 0), text, font=font)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]
    
    text_image = Image.new("RGBA", (text_width + 10, text_height + 10), (255, 255, 255, 0))
    text_draw = ImageDraw.Draw(text_image)
    text_draw.text((5 - bbox[0], 5 - bbox[1]), text, fill=fill + (255,), font=font)
    rotated = text_image.rotate(90, expand=True)
    
    image.paste(
        rotated,
        (int(xy[0] - rotated.width / 2), int(xy[1] - rotated.height / 2)),
        rotated,
    )

def annotate_png_with_pil(filepath, fig, map_axes, cbar_specs):
    """Adds titles and colorbar labels without Matplotlib's FreeType renderer."""
    image = Image.open(filepath).convert("RGB")
    draw = ImageDraw.Draw(image)
    width, height = image.size
    
    title_font = ImageFont.load_default(size=PIL_TITLE_FONTSIZE)
    label_font = ImageFont.load_default(size=PIL_CBAR_LABEL_FONTSIZE)
    tick_font = ImageFont.load_default(size=PIL_CBAR_TICK_FONTSIZE)
    fill = (20, 20, 20)
    
    for axis, title in map_axes:
        bbox = axis.get_position()
        x = (bbox.x0 + bbox.width / 2) * width
        y = (1 - bbox.y1) * height - 36
        _draw_centered_text(draw, (x, y), title, title_font, fill)
    
    for cbar_axis, label, ticks, tick_labels, orientation in cbar_specs:
        bbox = cbar_axis.get_position()
        x0 = bbox.x0 * width
        x1 = bbox.x1 * width
        y0 = (1 - bbox.y1) * height
        y1 = (1 - bbox.y0) * height
        
        tick_min = min(ticks)
        tick_max = max(ticks)
        if tick_max == tick_min:
            continue
        
        if orientation == "vertical":
            if label:
                _paste_rotated_centered_text(image, (x1 + 128, (y0 + y1) / 2), label, label_font, fill)
            for tick, tick_label in zip(ticks, tick_labels):
                y = y1 - (tick - tick_min) / (tick_max - tick_min) * (y1 - y0)
                _draw_centered_text(draw, (x1 + 60, y), tick_label, tick_font, fill)
        else:
            if label:
                _draw_centered_text(draw, ((x0 + x1) / 2, y1 + 82), label, label_font, fill)
            for tick, tick_label in zip(ticks, tick_labels):
                x = x0 + (tick - tick_min) / (tick_max - tick_min) * (x1 - x0)
                _draw_centered_text(draw, (x, y1 + 40), tick_label, tick_font, fill)
    
    image.save(filepath)

def crop_png_whitespace(filepath, pad=10, tolerance=3):
    """Crops white margins around the finished PNG, similar to MATLAB exportgraphics."""
    image = Image.open(filepath).convert("RGB")
    background = Image.new("RGB", image.size, (255, 255, 255))
    diff = ImageChops.difference(image, background).convert("L")
    mask = diff.point(lambda value: 255 if value > tolerance else 0)
    bbox = mask.getbbox()
    
    if bbox is None:
        image.save(filepath)
        return
    
    left = max(bbox[0] - pad, 0)
    top = max(bbox[1] - pad, 0)
    right = min(bbox[2] + pad, image.width)
    bottom = min(bbox[3] + pad, image.height)
    image.crop((left, top, right, bottom)).save(filepath)

def save_figure_png(fig, filepath, map_axes, cbar_specs, dpi=200):
    """Saves a PNG, falling back when Matplotlib/FreeType cannot render text."""
    try:
        fig.savefig(filepath, dpi=dpi)
        crop_png_whitespace(filepath)
        return
    except RuntimeError as err:
        if "FT_Render_Glyph" not in str(err):
            raise
        print("Matplotlib text rendering failed; saving PNG with PIL annotations instead.")
    
    for text_artist in fig.findobj(match=mtext.Text):
        text_artist.set_visible(False)
    
    for axis in fig.axes:
        axis.tick_params(
            labelbottom=False,
            labelleft=False,
            labelright=False,
            labeltop=False,
        )
    
    fig.savefig(filepath, dpi=dpi)
    annotate_png_with_pil(filepath, fig, map_axes, cbar_specs)
    crop_png_whitespace(filepath)

def write_output_netcdf(filepath, lon, lat, model_mean, viirs_mean):
    """Writes the processed time-mean data to a NetCDF4 file."""
    with nc.Dataset(filepath, "w", format="NETCDF4") as ds:
        ds.createDimension("lon", len(lon))
        ds.createDimension("lat", len(lat))
        
        var_lon = ds.createVariable("lon", "f4", ("lon",))
        var_lon.long_name = "longitude"
        var_lon.units = "degrees_east"
        var_lon[:] = lon
        
        var_lat = ds.createVariable("lat", "f4", ("lat",))
        var_lat.long_name = "latitude"
        var_lat.units = "degrees_north"
        var_lat[:] = lat
        
        with warnings.catch_warnings():
            warnings.filterwarnings(
                "ignore",
                message="Setting the shape on a NumPy array has been deprecated.*",
                category=DeprecationWarning,
            )
            
            var_mod = ds.createVariable("aod_model", "f4", ("lat", "lon"), zlib=True, complevel=3, fill_value=np.nan)
            var_mod.long_name = "time-mean model aerosol optical depth"
            var_mod[:, :] = np.asarray(model_mean, dtype=np.float32)
            
            var_obs = ds.createVariable("aod_viirs", "f4", ("lat", "lon"), zlib=True, complevel=3, fill_value=np.nan)
            var_obs.long_name = "time-mean VIIRS aerosol optical depth"
            var_obs[:, :] = np.asarray(viirs_mean, dtype=np.float32)

# =============================================================================
# Main Execution
# =============================================================================

if __name__ == "__main__":
    
    # Environment Variables
    MODEL_NAME = os.environ.get("MODEL_NAME", "RRFS-SD")
    FILE_MODEL = os.environ.get("FILE_MODEL", "/scratch3/BMC/acomp/Gonzalo.Ferrada/verif/melodies-monet-verification/model_output/RRFS-SD/2026062800/aqm_RRFS-SD_2026062800.0p05.nc")
    FILE_NOAA20 = os.environ.get("FILE_NOAA20", "/public/data/sat/nesdis/viirs_level3/aod/eps/noaa20/viirs_eps_noaa20_aod_0.050_deg_20260628_nrt.nc")
    FILE_SNPP = os.environ.get("FILE_SNPP", "/public/data/sat/nesdis/viirs_level3/aod/eps/npp/viirs_eps_npp_aod_0.050_deg_20260628_nrt.nc")
    FILE_OUT = os.environ.get("FILE_OUT", "aod_mean.nc")
    FILE_FIG = os.environ.get("FILE_FIG", "aod_mean.png")
    
    init_time_str = os.environ.get("INITIAL_TIME", "2026-06-28 00:00:00")
    initial_time = datetime.strptime(init_time_str, "%Y-%m-%d %H:%M:%S")
    
    print(f"MODEL_NAME={MODEL_NAME}")
    print(f"FILE_MODEL={FILE_MODEL}")
    print(f"FILE_NOAA20={FILE_NOAA20}")
    print(f"FILE_SNPP={FILE_SNPP}")
    print(f"FILE_FIG={FILE_FIG}")
    
    opt_save_netcdf = False
    opt_make_figure = True
    
    # 1) Open model data
    print("Reading model data...")
    model = read_model_data(FILE_MODEL)
    
    # 2) Open VIIRS data
    print("Reading VIIRS data...")
    noaa20 = read_viirs_netcdf(FILE_NOAA20, initial_time)
    snpp = read_viirs_netcdf(FILE_SNPP, initial_time)
    
    # Initialize accumulators
    shape_viirs = noaa20['aod'].shape
    shape_model = model['aod'].shape[1:] # Assuming (time, lat, lon)
    
    viirs_sum = np.zeros(shape_viirs, dtype=float)
    viirs_count = np.zeros(shape_viirs, dtype=int)
    model_sum = np.zeros(shape_model, dtype=float)
    model_count = np.zeros(shape_model, dtype=int)
    
    print("Calculating hourly metrics...")
    for t in model['time']:
        t0 = t - timedelta(minutes=30)
        t1 = t + timedelta(minutes=29)
        
        idx_model = (model['time'] >= t0) & (model['time'] <= t1)
        idx_noaa20 = (noaa20['time'] >= t0) & (noaa20['time'] <= t1)
        idx_snpp = (snpp['time'] >= t0) & (snpp['time'] <= t1)
        
        # Model hour average
        with np.errstate(invalid='ignore'):
            model_aod_hour = np.nanmean(model['aod'][idx_model, :, :], axis=0)
        
        # VIIRS hour matrices
        noaa20_aod_hour = np.full(shape_viirs, np.nan, dtype=np.float32)
        snpp_aod_hour = np.full(snpp['aod'].shape, np.nan, dtype=np.float32)
        
        noaa20_aod_hour[idx_noaa20] = noaa20['aod'][idx_noaa20]
        snpp_aod_hour[idx_snpp] = snpp['aod'][idx_snpp]
        
        viirs_aod_hour = average_aod(noaa20_aod_hour, snpp_aod_hour)
        
        # Valid accumulations
        valid_viirs = np.isfinite(viirs_aod_hour)
        viirs_sum[valid_viirs] += viirs_aod_hour[valid_viirs]
        viirs_count[valid_viirs] += 1
        
        # Map valid VIIRS spaces to Model spaces
        model_aod_hour_values = np.copy(model_aod_hour)
        model_aod_hour_values[~valid_viirs] = np.nan
        
        valid_model = np.isfinite(model_aod_hour_values)
        model_sum[valid_model] += model_aod_hour_values[valid_model]
        model_count[valid_model] += 1
        
    viirs_mean = np.full(shape_viirs, np.nan)
    model_mean = np.full(shape_model, np.nan)
    
    valid_viirs_mean = viirs_count > 0
    valid_model_mean = model_count > 0
    
    print("Computing time-mean and model AOD fields...")
    viirs_mean[valid_viirs_mean] = viirs_sum[valid_viirs_mean] / viirs_count[valid_viirs_mean]
    model_mean[valid_model_mean] = model_sum[valid_model_mean] / model_count[valid_model_mean]
    bias_mean = model_mean - viirs_mean
    
    if opt_save_netcdf:
        print("Saving NetCDF output...")
        write_output_netcdf(FILE_OUT, model['lon'], model['lat'], model_mean, viirs_mean)
        print(f"Saved NetCDF output to {FILE_OUT}")
        
    if opt_make_figure:
        print("Plotting...")
        
        # Defining contour levels based on Julia arrays
        lev_aod = [0, 0.05, 0.1, 0.15] + list(np.arange(0.2, 1.05, 0.1)) + [1.2, 1.5, 2.0]
        lev_bias_pos = [0.05] + list(np.arange(0.1, 0.65, 0.1))
        lev_bias = sorted([-x for x in lev_bias_pos] + lev_bias_pos)
        
        plot_extent = [-170, -50, 15, 85]
        lon_plot, lat_plot, (model_plot, viirs_plot, bias_plot) = subset_latlon(
            model['lon'], model['lat'], model_mean, viirs_mean, bias_mean, extent=plot_extent, pad=0.25
        )
        
        fig = plt.figure(figsize=(16.4, 13.0))
        ax = [
            fig.add_axes([0.06, 0.61, 0.40, 0.29], projection=ccrs.PlateCarree()),
            fig.add_axes([0.475, 0.61, 0.40, 0.29], projection=ccrs.PlateCarree()),
            fig.add_axes([0.295, 0.285, 0.40, 0.29], projection=ccrs.PlateCarree()),
        ]
        cax_aod = fig.add_axes([0.895, 0.58, 0.025, 0.36])
        cax_bias = fig.add_axes([0.295, 0.235, 0.40, 0.035])
        
        print("Plotting model mean")
        p1, aod_ticks, aod_tick_labels = plot_level_field(ax[0], lon_plot, lat_plot, model_plot, lev_aod, AOD_CMAP_RGB)
        ax[0].set_title(f"{MODEL_NAME} AOD", fontsize=FIG_TITLE_FONTSIZE, pad=14)
        
        print("Plotting VIIRS mean")
        p2, _, _ = plot_level_field(ax[1], lon_plot, lat_plot, viirs_plot, lev_aod, AOD_CMAP_RGB)
        ax[1].set_title("VIIRS AOD (Combined NOAA-20 & S-NPP)", fontsize=FIG_TITLE_FONTSIZE, pad=14)
        
        print("Plotting bias")
        p3, bias_ticks, bias_tick_labels = plot_level_field(ax[2], lon_plot, lat_plot, bias_plot, lev_bias, BIAS_CMAP_RGB)
        ax[2].set_title(f"{MODEL_NAME} Bias", fontsize=FIG_TITLE_FONTSIZE, pad=14)
        
        for axis in ax:
            axis.set_facecolor("0.86")
            axis.coastlines()
            # Set approximate spatial bounds from the Julia script
            # NOTE: PlateCarree limits use raw lon/lat bounding boxes. Adjust as necessary.
            axis.set_extent(plot_extent, crs=ccrs.PlateCarree()) 
            
        print("Adding colorbars")
        cbar1 = fig.colorbar(p1, cax=cax_aod, orientation='vertical')
        # cbar1.set_label("AOD")
        cbar1.set_ticks(aod_ticks)
        cbar1.set_ticklabels(aod_tick_labels)
        style_colorbar_ticks(cbar1, "vertical")
        cbar1.ax.yaxis.label.set_size(30)
        cbar1.ax.yaxis.labelpad = 12
        
        cbar2 = fig.colorbar(p3, cax=cax_bias, orientation='horizontal')
        # cbar2.set_label("Model - VIIRS")
        cbar2.set_ticks(bias_ticks)
        cbar2.set_ticklabels(bias_tick_labels)
        style_colorbar_ticks(cbar2, "horizontal")
        cbar2.ax.xaxis.label.set_size(30)
        cbar2.ax.xaxis.labelpad = 10
        
        print(f"Saving PNG to {FILE_FIG}")
        save_figure_png(
            fig,
            FILE_FIG,
            map_axes=[
                (ax[0], f"{MODEL_NAME} AOD"),
                (ax[1], "VIIRS AOD (Combined NOAA-20 & S-NPP)"),
                (ax[2], f"{MODEL_NAME} Bias"),
            ],
            cbar_specs=[
                (cbar1.ax, "", aod_ticks, aod_tick_labels, "vertical"),
                (cbar2.ax, "", bias_ticks, bias_tick_labels, "horizontal"),
            ],
            dpi=200,
        )
        plt.close()
