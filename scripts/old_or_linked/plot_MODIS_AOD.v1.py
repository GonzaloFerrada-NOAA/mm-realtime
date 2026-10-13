# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import matplotlib.pyplot as plt
import matplotlib as mpl
mpl.use('Agg')
import os
import sys
import cartopy.crs as ccrs
import cartopy.feature as cfeature
import xarray as xr
import matplotlib.colors as mcolors
from matplotlib.colors import ListedColormap, BoundaryNorm, LinearSegmentedColormap
import numpy as np
import subprocess

print("printing all args")
print(sys.argv[1:])

nmdls     = int(sys.argv[1])
outdir    = str(sys.argv[2])
obs_name  = sys.argv[3]
mdl_names = sys.argv[4:4+nmdls]
mdl_paths = sys.argv[4+nmdls:4+nmdls+nmdls]
print("model names = ")
print(mdl_names)
print("mdl_paths = ")
print(mdl_paths)

#Observation
ds_obs = xr.open_dataset(obs_name + '_interpolated.nc')
if obs_name == "MODIS_AQUA":
  data  = ds_obs.MODIS_AQUA_AOD_550_Dark_Target_Deep_Blue_Combined_data
  count = ds_obs.MODIS_AQUA_AOD_550_Dark_Target_Deep_Blue_Combined_count
  data  = data / count 
  masked_zeroes = ds_obs.MODIS_AQUA_AOD_550_Dark_Target_Deep_Blue_Combined_data.where(data != 0)
else:
  data  = ds_obs.MODIS_TERRA_AOD_550_Dark_Target_Deep_Blue_Combined_data
  count = ds_obs.MODIS_TERRA_AOD_550_Dark_Target_Deep_Blue_Combined_count
  data  = data / count 
  masked_zeroes = ds_obs.MODIS_TERRA_AOD_550_Dark_Target_Deep_Blue_Combined_data.where(data != 0)
#Calculate the average, ignoring zeros
AOD_obs=masked_zeroes.mean(dim='time')
#AOD_obs=data.mean(dim='time')


# Get longitude and latitude
lons_obs = ds_obs.lon
lats_obs = ds_obs.lat

# Common settings for all subplots
def add_common_features(ax):
    ax.set_extent([-140, -50, 20, 60], crs=ccrs.PlateCarree())
    ax.add_feature(cfeature.COASTLINE)
    ax.add_feature(cfeature.LAND, facecolor='white')
    ax.add_feature(cfeature.OCEAN, facecolor='white')

def add_common_features_nostates(ax):
    ax.set_extent([-140, -50, 20, 60], crs=ccrs.PlateCarree())
    ax.add_feature(cfeature.COASTLINE)
    #ax.add_feature(cfeature.BORDERS, linestyle=':')
    #ax.add_feature(cfeature.LAND, facecolor='white')
    #ax.add_feature(cfeature.OCEAN, facecolor='white')

white = plt.get_cmap('Greys', 2)([0])  # Pure white
blues = plt.get_cmap('Blues', 6)(range(1, 5))  # Middle blues
green_yellow_red = plt.get_cmap('RdYlGn_r', 18)([1, 3, 5, 9, 12, 13, 14, 16, 17])  # Corrected indices
purple = np.array([mpl.colors.to_rgba('xkcd:vivid purple')])  # Specific purple color
dark_red = np.array([mpl.colors.to_rgba('darkred')]) 
# Concatenate all color segments
cbar_colors = np.concatenate((white, blues, green_yellow_red, dark_red))
# Create a custom LinearSegmentedColormap
newcmp = mpl.colors.LinearSegmentedColormap.from_list("custom_cmap", cbar_colors, N=len(cbar_colors))
newcmp.set_over(purple)

# Define levels for the colorbar
levels = [0, 0.01, 0.05, 0.075, 0.1, 0.15, 0.2, 0.25, 0.3, 0.4, 0.5, 0.75, 0.9, 1.2, 1.5]
norm = mpl.colors.BoundaryNorm(levels, newcmp.N)
diff_levels = [-1.0, -0.8, -0.6, -0.4, -0.3, -0.2, -0.1, 0.0, 0.1, 0.2, 0.3, 0.4, 0.6, 0.8, 1.0]
diff_cmap = mcolors.LinearSegmentedColormap.from_list(name='red_white_blue',
                                                 colors =[(0, 0, 1),
                                                          (1, 1., 1),
                                                          (1, 0, 0)],
                                                 N=len(diff_levels)+1,
                                                 )

# Function to add a colorbar for diff plots
def add_colorbar_diff(fig, ax1, cmap, levels, label, orientation='horizontal', location='bottom',  aspect=50, pad=0.025):
    cbar = fig.colorbar(plt.cm.ScalarMappable(norm=norm, cmap=cmap), orientation=orientation, extend='both', spacing='uniform', ticks=levels, location=location, ax=ax1)
    cbar.set_label(label, fontsize=12)
    cbar.ax.tick_params(labelsize=12)

#Model
for imdl in range(nmdls):
   #rrfs_sd=xr.open_dataset(obs_name + '_interpolated.nc')
   #AOD_rrfs_sd = rrfs_sd.MODIS_AQUA_AOD_550_Dark_Target_Deep_Blue_Combined.mean(dim='time') + np.random.rand(360,180)
   rrfs_sd = xr.open_dataset(mdl_paths[imdl])
   rrfs_sd_interp = xr.open_dataset(mdl_names[imdl]+"_interpolated.nc")
   if 'HRRR' in mdl_paths[imdl]:
      AOD_rrfs_sd = rrfs_sd.AOD_550.mean(dim='time')
      AOD_rrfs_sd_interpolated = rrfs_sd_interp.AOD_550.mean(dim='time')
      lats_rrfs_sd = rrfs_sd.latitude #rrfs_sd.latitude
      lons_rrfs_sd = rrfs_sd.longitude #rrfs_sd.longitude
   elif 'RAP-Smoke' in mdl_paths[imdl]:
      AOD_rrfs_sd = rrfs_sd.AOD_550.mean(dim='time')
      AOD_rrfs_sd_interpolated = rrfs_sd_interp.AOD_550.mean(dim='time')
      lats_rrfs_sd = rrfs_sd.gridlat_0 #rrfs_sd.latitude
      lons_rrfs_sd = rrfs_sd.gridlon_0 #rrfs_sd.longitude
   elif 'RRFS' in mdl_paths[imdl]:
      AOD_rrfs_sd = rrfs_sd.AOD550.mean(dim='time')
      AOD_rrfs_sd_interpolated = rrfs_sd_interp.AOD550.mean(dim='time')
      lats_rrfs_sd = rrfs_sd.latitude #rrfs_sd.latitude
      lons_rrfs_sd = rrfs_sd.longitude #rrfs_sd.longitude
   AOD_rrfs_sd=AOD_rrfs_sd.fillna(0)

   #------------------------------------------------------------
   mdl_minus_obs = AOD_rrfs_sd_interpolated - AOD_obs.T
   
   # Plotting
   fig1, axs1 = plt.subplots(1, 2, figsize=(15, 10), subplot_kw={'projection': ccrs.PlateCarree()})
   fig1.subplots_adjust(bottom=0.5, wspace=0.05)
   
   # Plot AQUA data
   ax = axs1[0]
   if 'RAP-Smoke' in mdl_paths[imdl]:
     add_common_features_nostates(ax)
   else:
     add_common_features_nostates(ax)
 
   plot_aqua = ax.pcolormesh(lons_obs, lats_obs, AOD_obs.T, cmap=newcmp, norm=norm, transform=ccrs.PlateCarree())
   ax.set_title(obs_name)
   
   ## Plot RRFS-SD model data
   ax = axs1[1]
   if 'RAP-Smoke' in mdl_paths[imdl]:
     add_common_features_nostates(ax)
   else:
     add_common_features_nostates(ax)
   plot_rrfs_sd = ax.contourf(lons_rrfs_sd, lats_rrfs_sd, AOD_rrfs_sd, cmap=newcmp, norm=norm, levels=levels,transform=ccrs.PlateCarree())
   ax.set_title(mdl_names[imdl], fontsize=14)
   
   # Add a shared colorbar
   cbar = fig1.colorbar(plt.cm.ScalarMappable(norm=norm, cmap=newcmp), ax=axs1[:2], orientation='horizontal', aspect=100, pad=0.025, extend='both', spacing='uniform', ticks=levels, location='bottom')
   cbar.set_label('Aerosol Optical Depth (AOD)', fontsize=12)
   cbar.ax.tick_params(labelsize=12)
   cbar.ax.set_xticklabels(['{:.2g}'.format(t) for t in levels])  # Format tick labels to remove unnecessary zeros 
  
   
   #plt.tight_layout()
   plt_name = 'plot_grp2.aod_550nm_'+obs_name+'_'+mdl_names[imdl]+'_CONUS.png'
   print("plot_name is " + plt_name)
   plt.savefig(plt_name, bbox_inches='tight')
   subprocess.run(['mv',plt_name,outdir])
   

   fig2, axs2 = plt.subplots(1,1, figsize=(10, 10), subplot_kw={'projection': ccrs.PlateCarree()})
   fig2.subplots_adjust(bottom=0.5, wspace=0.05)
   # Difference plot
   ax = axs2
   add_common_features(ax)
   plot_diff = ax.contourf(lons_obs, lats_obs, mdl_minus_obs, cmap=diff_cmap, levels=diff_levels,transform=ccrs.PlateCarree())
   diff_norm = mpl.colors.BoundaryNorm(diff_levels,diff_cmap.N, extend='both')
   fig1.colorbar(mpl.cm.ScalarMappable(norm=diff_norm,cmap=diff_cmap),ax=ax,orientation='horizontal',label='AOD Bias (Model - Obs)',ticks=diff_levels,aspect=50, pad=0.025,location='bottom',extend='both')
   ax.set_title(mdl_names[imdl] + " minus " + obs_name)
   plt_name = 'plot_grp3.aod_550nm_'+obs_name+'_'+mdl_names[imdl]+'_CONUS.png'
   print("plot_name is " + plt_name)
   plt.savefig(plt_name, bbox_inches='tight')
   subprocess.run(['mv',plt_name,outdir])
