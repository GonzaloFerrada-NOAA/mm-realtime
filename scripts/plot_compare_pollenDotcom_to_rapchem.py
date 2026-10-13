from netCDF4 import Dataset
import matplotlib.image as mpimg
import xarray as xr
import numpy as np
import matplotlib as mpl
mpl.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.cm import get_cmap
import cartopy.crs as ccrs
import cartopy.feature as cfeature
from cartopy.feature import NaturalEarthFeature
import matplotlib.colors as mcolors
from matplotlib.colors import ListedColormap, BoundaryNorm, LinearSegmentedColormap
import wrf
import math
import sys
#
# ${YYYY}${MM}${DD} ${model_file} ${model_file_regridded} ${obs_data}
#



def add_common_features_nostates(ax):
    ax.set_extent([-140, -50, 20, 60], crs=ccrs.PlateCarree())
    ax.add_feature(cfeature.COASTLINE)

# Print all arguments, including the script name
print("All arguments:", sys.argv)


fcst_type            = int(sys.argv[1]) # 0 = obs, 1 = one day ahead forecast, 2 = two day ahead...
obs_path             = sys.argv[2]
mdl_path             = sys.argv[3]
yesterday            = sys.argv[4] # Current day of analysis (2 days behind real time)
today                = sys.argv[5]
tomorrow             = sys.argv[6]
cycleHH              = sys.argv[7]
outdir               = sys.argv[8]
today_j              = str(sys.argv[9])


rot_proj=wrf.getproj(map_proj='RotatedLatLon',moad_cen_lat=54.,stand_lon=106.,pole_lat=36.,pole_lon=180)

white = plt.get_cmap('Greys', 2)([0])  # Pure white
blues = plt.get_cmap('Blues', 6)(range(1, 5))  # Middle blues
green_yellow_red = plt.get_cmap('RdYlGn_r', 18)([1, 3, 5, 9, 12, 13, 14, 16, 17])  # Corrected indices
purple = np.array([mpl.colors.to_rgba('xkcd:vivid purple')])  # Specific purple color
dark_red = np.array([mpl.colors.to_rgba('darkred')]) 
# Concatenate all color segments
cbar_colors = np.concatenate((white, blues, green_yellow_red, dark_red))
# Create a custom LinearSegmentedColormap
#newcmp = mpl.colors.LinearSegmentedColormap.from_list("custom_cmap", cbar_colors, N=len(cbar_colors))
#newcmp.set_over(purple)
#lvls = np.linspace(0.,4.,num=19)
#lvls_diff = np.linspace(-2.,2.,num=19)
#lvls = [0., 10., 25., 50., 100., 250., 500., 750., 1000., 1500., 2000., 2500., 3000., 5000., 7500., 10000.] #
#lvls = [0., 10., 25., 50., 100., 250., 500., 750., 1000., 1500., 2000., 2500., 5000., 7500., 10000.] #
#lvls = [0., 10., 25., 50., 100., 250., 500., 750., 1000., 1500., 2000., 2500., 3000., 4000., 5000.] #
#lvls = np.linspace(0,1000,num=16)
lvls = [5., 50., 100., 500., 1000., 2500.];
colors = ['green', 'limegreen', 'yellow', 'orange', 'red']
newcmp = LinearSegmentedColormap.from_list('discrete_pollen', colors, N=5)
newcmp.set_over('magenta')
newcmp.set_under('white')

norm = mpl.colors.BoundaryNorm(lvls, newcmp.N)
diff_lb   = -1000.
diff_ub   = 1000.
lvls_diff = np.linspace(diff_lb,diff_ub,16)
diff_cmap = mcolors.LinearSegmentedColormap.from_list(name='red_white_blue',
                                                 colors =[(0, 0, 1),
                                                          (1, 1., 1),
                                                          (1, 0, 0)],
                                                 N=len(lvls_diff)+1,
                                                 )
diff_cmap.set_over('Red')
diff_cmap.set_under('Blue')
obs_species_list = ["POL"]
mdl_species_list = ["polp"]
titles = ['Total']
nspecies = len(obs_species_list)
#
polp_conv = 1.e9 / ( 4./3. * 3.14 * 25.**3. * 1200.)

mdl_knt=0

for ispec in obs_species_list:
   fig,axes = plt.subplots(1,2,figsize=(12, 6),subplot_kw={'projection': ccrs.PlateCarree()})
   #fig,axes = plt.subplots(1,2,figsize=(12, 6))
   fig.subplots_adjust(bottom=0.5, wspace=0.05)
   axes = axes.flatten()
   knt = 0
   print("wokring on " + ispec)
   if fcst_type == 0:
      obs_fname  = obs_path + '/' + today + '12/PollenDotCom_' + today_j + ".png"
      model_file = mdl_path + '/' + today + cycleHH + '/' + 'aqm_RAP-Chem_' + today + cycleHH + '_pollen_average.nc'
      model_file_regridded = mdl_path + '/' + today + cycleHH + '/' + 'aqm_RAP-Chem_' + today + cycleHH + '_pollen_average_regridded.nc'
      figtitle   = 'pollen.com for ' + today + ' vs. RAP-Chem 1 day-forecast '
   else:
      print("unrecognized forecast type/figure option, quitting")
      exit()

   img = mpimg.imread(obs_fname)
   print(type(img))

   img2=np.array(img)

   left_lon = -127
   right_lon = -65
   bottom_lat = 20
   top_lat = 50

   #
   mdl_fid   = Dataset(model_file)
   mdl_lons  = np.asarray(mdl_fid.variables['lon'])
   mdl_lats  = np.asarray(mdl_fid.variables['lat'])
   mdl_temp  = np.asarray(mdl_fid.variables['T']).squeeze() + 273.15
   mdl_pres  = np.asarray(mdl_fid.variables['P']).squeeze() + np.asarray(mdl_fid.variables['PB']).squeeze()
   mdl_dens = ((1./287.)*(mdl_pres[:,:]/mdl_temp[:,:]))
   mdl_pollen= polp_conv * np.asarray(mdl_fid.variables[mdl_species_list[mdl_knt]]).squeeze() * mdl_dens.squeeze() 
   mdl_pollen_log = np.log10(mdl_pollen)
   #
   # Obs 
   axes[2*knt].imshow(img2, extent=[left_lon, right_lon, bottom_lat, top_lat], origin='upper')
   axes[2*knt].set_title(" pollen.com")
#   contour1 = axes[2*knt].imshow(img)
#   axes[2*knt].axis('off')
   # Model
   contour2 = axes[2*knt+1].contourf(mdl_lons, mdl_lats, mdl_pollen, levels=lvls, norm=norm, cmap=newcmp,transform=ccrs.PlateCarree(),projection=ccrs.PlateCarree())
   axes[2*knt+1].set_xlim([-130, -60]) # Set x limits manually
   axes[2*knt+1].set_ylim([20, 65]) # Set y limits manually
   add_common_features_nostates(axes[2*knt+1])
   axes[2*knt+1].set_title("RAP-Chem (experimental)")
   # Add a shared colorbar
   cbar = fig.colorbar(plt.cm.ScalarMappable(norm=norm, cmap=newcmp), ax=axes[1], orientation='horizontal', aspect=100, pad=0.025, extend='both', spacing='uniform', ticks=lvls, location='bottom')
#   cbar.set_ticklabels(['0','','25','','100','','500','','1000','','2000','','3000','','5000'])
   cbar.set_label(titles[mdl_knt] + ' Pollen Count (grains m$^{-3}$)', fontsize=12)
   fig.suptitle(figtitle, fontsize=14)
#
   plt_name = 'plot_grp3.pollen_'+ispec+'_'+today+'_PollenDotCom_RAP-Chem_CONUS_'+str(fcst_type) + '.png'
   plt.savefig(outdir + '/' + plt_name, format='png',bbox_inches='tight')
