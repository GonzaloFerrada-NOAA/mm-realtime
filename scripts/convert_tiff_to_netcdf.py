import rioxarray as rio
import xarray as xr
import numpy as np
import sys
import subprocess
#
#
obs_path  = sys.argv[1]
ispec     = sys.argv[2]
cycle     = sys.argv[3]
f = obs_path + '/' + ispec + '_' + cycle + '.tiff'
# Open the file and convert to an xarray dataset
geotiff_da = rio.open_rasterio(f)
geotiff_ds = geotiff_da.to_dataset(dim="band")
geotiff_ds  = geotiff_ds.rename({1:ispec})
pollen      = geotiff_ds[ispec]
outfile     = obs_path + "/" + ispec+ "_"+str(cycle)+".nc"
pollen.to_netcdf(outfile)
