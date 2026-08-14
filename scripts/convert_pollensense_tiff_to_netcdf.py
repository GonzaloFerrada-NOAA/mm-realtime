import rioxarray as rio
import xarray as xr
import numpy as np
import sys
import subprocess
#
#
yesterday = sys.argv[1]
today     = sys.argv[2]
tomorrow  = sys.argv[3]
obs_path  = sys.argv[4]
obs_species_list = ["POL","TRE","GRA","WEE"]
day_list = [yesterday, today, tomorrow]

for i in obs_species_list:
   for j in day_list
   print("working on " + i + "for day " + j)
   tiff_path  = obs_path + "/" + i + "_" + j + ".tiff"
   # Open the file and convert to an xarray dataset
   geotiff_da = rio.open_rasterio(tiff_path)
   geotiff_ds = geotiff_da.to_dataset(dim="band")
   geotiff_ds  = geotiff_ds.rename({1:i})
   pollen      = geotiff_ds[i]
   outfile     = obs_path + "/" + i + "_"+str(j)+".nc"
   pollen.to_netcdf(outfile)
