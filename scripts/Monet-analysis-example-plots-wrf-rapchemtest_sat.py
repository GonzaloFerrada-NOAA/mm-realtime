#!/usr/bin/env python
# coding: utf-8

#This is needed to tell matplotlib to use a non-interactive backend and avoid display errors.
import matplotlib
matplotlib.use('Agg')
import sys; sys.path.append("../../")
from melodies_monet import driver
import os
import dask
import netCDF4
import xarray

do_stats=sys.argv[1]
obs_label=sys.argv[2]
mdl_labels=sys.argv[3:]
nmdls=len(mdl_labels)

print("starting MM for satellites")
print("Arguments:")
print("do_stats = " + str(do_stats))
print("obs_label = " + str(obs_label))
print("mdl_labels = " + str(mdl_labels))
print("number of models = " + str(nmdls))

an = driver.analysis()
an.control = 'control.yaml'        # 'control.yaml.rapchemtest'
an.read_control() # control='control.yaml')

an.setup_obs_grid()

an.setup_regridders()

dask.config.set(**{'array.slicing.split_large_chunks': True})

an.open_models()

for time_interval in an.time_intervals:
  print(type(time_interval))
  an.open_obs(time_interval=time_interval)
  an.update_obs_gridded_data()

an.normalize_obs_gridded_data()

param = obs_label + '_AOD_550_Dark_Target_Deep_Blue_Combined'
param_data = an.obs_gridded_dataset[param + '_data'].values
param_count = an.obs_gridded_dataset[param + '_count'].values
mask = (param_count > 0)
param_data[mask] = param_data[mask] / param_count[mask]
an.obs_gridded_dataset[param + '_data'].values = param_data
an.obs_gridded_dataset.to_netcdf(obs_label + "_interpolated.nc")

knt = 0
for imdl in an.models:
   print(an.models[imdl].obj)
   regridder = an.model_regridders[imdl]
   print(regridder)
   ds_model_regrid = regridder(an.models[imdl].obj)
   ds_model_regrid.to_netcdf(mdl_labels[knt] + "_interpolated.nc")
   knt = knt + 1
#
# For later, when plot types are in place
#if(do_stats=='1'):
#  an.stats()
#an.plotting()

