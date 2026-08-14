from pathlib import Path
import numpy as np
import xarray as xr
import sys
import xesmf as xe


source_file = sys.argv[1]
outfile     = sys.argv[2]
source_fid  = xr.open_dataset(source_file)

dest_file = "/home/Jordan.Schnell/melodies-monet-verification/pollensense_30km_latlon.nc"
#dest_file = "/mnt/lfs5/BMC/rtwbl/rap-chem/homebasedir/static/WRF_INPUT/pollensense_30km_latlon.nc"
dest_fid  = xr.open_dataset(dest_file)

regridder = xe.Regridder(source_fid,dest_fid,'bilinear')

#print(regridder)
regridded_data = regridder(source_fid[['polp','polp_tree','polp_weed','polp_grass','T','P','PB']])
regridded_data.to_netcdf(outfile)
