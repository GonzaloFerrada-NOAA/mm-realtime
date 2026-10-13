from netCDF4 import Dataset
import rioxarray as rio
import xarray as xr
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.cm import get_cmap
import math
import sys
#
# ${YYYY}${MM}${DD} ${model_file} ${model_file_regridded} ${obs_data}
#

def add_common_features_nostates(ax):
    ax.set_extent([-140, -50, 20, 60], crs=ccrs.PlateCarree())
    ax.add_feature(cfeature.COASTLINE)

cycle = sys.argv[1]
model_file = sys.argv[2]
model_file_regridded = sys.argv[3]
obs_data = sys.argv[4]
outdir = sys.argv[5]

lvls = np.linspace(0.,4.,num=19)
lvls_diff = np.linspace(-2.,2.,num=19)
obs_species_list = ["POL","TRE","GRA","WEE"]
mdl_species_list = ["polp","polp_tree","polp_grass","polp_weed"]
nspecies = len(obs_species_list)
#
polp_conv = 1.e9 / ( 4./3. * 3.14 * 25.**3. * 1200.)
knt = 0
for ispec in obs_species_list:
   fig,axes = plt.subplots(1,3,figsize=(20, 10))
   axes = axes.flatten()
   obs_fname = obs_data + "/" + ispec + "_" + cycle + ".nc"
   obs_fid   = Dataset(obs_fname,'r')
   obs_lons  = np.asarray(obs_fid.variables['x'])
   obs_lats  = np.asarray(obs_fid.variables['y'])
   obs_pollen = np.asarray(obs_fid.variables[ispec])
   obs_pollen_log = np.log10(obs_pollen)
   obs_xs, obs_ys = np.meshgrid(obs_lons, obs_lats)
   #
   mdl_fid   = Dataset(model_file)
   mdl_lons  = np.asarray(mdl_fid.variables['lon'])
   mdl_lats  = np.asarray(mdl_fid.variables['lat'])
   mdl_temp  = np.asarray(mdl_fid.variables['T']).squeeze() + 273.15
   mdl_pres  = np.asarray(mdl_fid.variables['P']).squeeze() + np.asarray(mdl_fid.variables['PB']).squeeze()
   mdl_dens = ((1./287.)*(mdl_pres[:,:]/mdl_temp[:,:]))
   mdl_pollen= polp_conv * np.asarray(mdl_fid.variables[mdl_species_list[knt]]).squeeze() * mdl_dens.squeeze() 
   mdl_pollen_log = np.log10(mdl_pollen)
   #
   mdl_fidR   = Dataset(model_file_regridded)
   mdl_lonsR  = obs_lons #np.asarray(mdl_fid.variables['XLONG'])
   mdl_latsR  = obs_lats #np.asarray(mdl_fid.variables['XLAT'])
   mdl_tempR  = np.asarray(mdl_fidR.variables['T']).squeeze() + 273.15
   mdl_presR  = np.asarray(mdl_fidR.variables['P']).squeeze() + np.asarray(mdl_fidR.variables['PB']).squeeze()
   mdl_densR  = ((1./287.)*(mdl_presR[:,:]/mdl_tempR[:,:]))
   mdl_pollenR = polp_conv * np.asarray(mdl_fidR.variables[mdl_species_list[knt]]).squeeze() * mdl_densR.squeeze()
   mdl_pollen_logR = np.log10(mdl_pollen)
 
   ax = axes[0]
   add_common_features_nostates(ax) 
   ax.contourf(obs_xs, obs_ys, obs_pollen_log, levels=lvls, cmap=get_cmap("jet"),extent=[-140, -50, 20, 60],transform=ccrs.PlateCarree())
   
   ax = axes[1]
   add_common_features_nostates(ax) 
   ax.contourf(mdl_lons, mdl_lats, mdl_pollen_log, levels=lvls, cmap=get_cmap("jet"),extent=[-140, -50, 20, 60],transform=ccrs.PlateCarree())
   
   ax = axes[2]
   add_common_features_nostates(ax) 
   ax.contourf(obs_xs, obs_ys, mdl_pollen_logR - obs_pollen_log, levels=lvls_diff, cmap=get_cmap("jet"),extent=[-140, -50, 20, 60],transform=ccrs.PlateCarree())

#
   plt.tight_layout()
   plt.savefig(outdir + '/' + ispec + '_pollen_compare_ ' + cycle + '.png', format='png')



