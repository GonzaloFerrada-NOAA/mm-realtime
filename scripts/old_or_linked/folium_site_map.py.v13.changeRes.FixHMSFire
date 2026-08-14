#!/usr/bin/env python
# coding: utf-8
import folium
import base64
from folium import IFrame
from PIL import Image
import numpy as np
import pandas as pd
import xarray as xr
import sys
import glob
import os.path
from folium import plugins
import subprocess
import pprint
#
#
# Initialize some arrays
popups    = list()
ipopup    = 0
mkr1      = list() # list of the individual markers
fmap_dict = dict()
fmaps     = []
fmaps_names = list()
#
# Styles for the AQI contours
style_mod = {'fillColor': '#FFFF00', 'lineColor': '#FFFF00', 'color' : '#FFFF00'}
style_uns = {'fillColor': '#ff7e00', 'lineColor': '#ff7e00', 'color' : '#ff7e00'}
style_unh = {'fillColor': '#FF0000', 'lineColor': '#FF0000', 'color' : '#FF0000'}
style_vuh = {'fillColor': '#8f3f97', 'lineColor': '#8f3f97', 'color' : '#8f3f97'}
style_haz = {'fillColor': '#7e0023', 'lineColor': '#7e0023', 'color' : '#7e0023'}
style_hms_light = {'fillColor': '#D3D3D3', 'lineColor': '#D3D3D3', 'color' : '#D3D3D3'}
style_hms_medium = {'fillColor': '#A9A9A9', 'lineColor': '#A9A9A9', 'color' : '#A9A9A9'}
style_hms_heavy = {'fillColor': '#6A6A6A', 'lineColor': '#6A6A6A', 'color' : '#6A6A6A'}
#
#
markerClusterOptions = {'chunkedLoading': True}
#
# Defining the resolution, width, and height of the popup
#
resolution, width, height = 45, 11, 6 
marker_radius=8
#
#defining plot type
#
plot_type = "grp1.timeseries"
#
# import variables from the bash file
#
start_date=sys.argv[1]
end_date=sys.argv[2]
todays_date=sys.argv[3]
model_type=sys.argv[4]
plot_output_path=sys.argv[5]
obs_path=sys.argv[6]
#
# This should probably move to a dictionary
if model_type ==  "regional_smoke":
    species_list  = ['PM2.5', 'PM2.5', 'PM10', 'PM10', 'aod_550nm','vsb', 'HMS']
    platform_list = ['airnow', 'openaq', 'airnow', 'openaq', 'aeronet','ish', 'NOAA HMS']
    platform_nice = ['EPA AirNOW', 'OpenAQ', 'EPA AirNOW', 'OpenAQ', 'AERONET', 'NOAA ISD', 'NOAA HMS']
    color_list    = ['purple', 'blue', 'red', 'green' , 'yellow', 'orange', 'black']
elif model_type == "regional_chemistry":
    species_list  = ['PM2.5', 'PM2.5', 'PM10', 'PM10', 'aod_550nm', 'OZONE', 'HMS']
    platform_list = ['airnow', 'openaq', 'airnow', 'openaq', 'aeronet','airnow', 'NOAA HMS']
    platform_nice = ['EPA AirNOW', 'OpenAQ', 'EPA AirNOW', 'OpenAQ', 'AERONET', 'EPA AirNOW', 'NOAA HMS']
    color_list    = ['purple', 'blue', 'red', 'green' , 'yellow', 'orange', 'black']
elif model_type == "global":
    species_list  = ['PM2.5', 'PM2.5', 'PM10', 'PM10', 'aod_550nm', 'OZONE', 'HMS']
    platform_list = ['airnow', 'openaq', 'airnow', 'openaq', 'aeronet', 'ish', 'NOAA HMS']
    platform_nice = ['EPA AirNOW', 'OpenAQ', 'EPA AirNOW', 'OpenAQ', 'AERONET', 'NOAA ISD', 'NOAA HMS']
    color_list    = ['purple', 'blue', 'red', 'green' , 'yellow', 'orange', 'black']
#
#
nmaps = 0
#
# First create the BASE folium map centered over the US
fmap = folium.Map(location=[40, -95],zoom_start=4,min_zoom=3,control=False,chunkedLoading=True,control_scale=True)
# Add it to the dictionary
#fmaps['Base'] = fmap
#fmaps_names.append('Base')
#nmaps = nmaps + 1
# Now create the marker cluster group (not a feature group or featuregroupsubgroup) that will hold the markers
fmap_marker_cluster = folium.plugins.MarkerCluster(name='Station Clusters',control=False,show=True,overlay=True,options=markerClusterOptions) #disableClusterAtZoom=16
#fmaps['Station Clusters'] = fmap_marker_cluster
#fmaps_names.append('Station Clusters')
#nmaps = nmaps + 1
# If minimally plotting PM2.5 or Ozone 
if (('PM2.5' in species_list or 'OZONE' in species_list) and ('airnow' in platform_list)): 
    # Create an additional top level feature group for AQI shape files and add to the map
    fmap_airnow_aqi   = folium.FeatureGroup(name='EPA AirNOW AQI',overlay=True,control=True,show=True)
    fmaps.append(fmap_airnow_aqi)
    fmap.add_child(fmap_airnow_aqi)
    #fmaps['airnow_aqi'] = fmap_airnow_aqi
    nmaps = nmaps + 1
    if 'PM2.5' in species_list:
        fmap_pm25_aqi = folium.plugins.FeatureGroupSubGroup(fmap_airnow_aqi,name='PM2.5 AQI',overlay=True,control=True,show=True)
        #fmaps['PM2.5 AQI'] = fmap_pm25_aqi
        fmaps.append(fmap_pm25_aqi)
        fmaps_names.append('PM2.5 AQI')
        nmaps = nmaps + 1
        if 'EPA AirNOW' in fmap_dict:
            fmap_dict['EPA AirNOW'].add(fmap_pm25_aqi)
        else:
            fmap_dict['EPA AirNOW'] = {fmap_pm25_aqi}
        for filename in glob.glob(obs_path + 'Moderate.pm25*json'):
            fmap_pm25_aqi.add_child(folium.GeoJson(data=(open(filename,"r",encoding="utf-8-sig")).read(),style_function=lambda x:style_mod))
        for filename in glob.glob(obs_path + 'UnhealthySG.pm25*json'):
           fmap_pm25_aqi.add_child(folium.GeoJson(data=(open(filename,"r",encoding="utf-8-sig")).read(),style_function=lambda x:style_uns))
        for filename in glob.glob(obs_path + 'Unhealthy.pm25*json'):
            fmap_pm25_aqi.add_child(folium.GeoJson(data=(open(filename,"r",encoding="utf-8-sig")).read(),style_function=lambda x:style_unh))
        for filename in glob.glob(obs_path + 'VeryUnhealthy.pm25*json'):
            fmap_pm25_aqi.add_child(folium.GeoJson(data=(open(filename,"r",encoding="utf-8-sig")).read(),style_function=lambda x:style_vuh))
        for filename in glob.glob(obs_path + 'Hazardous.pm25*json'):
            fmap_pm25_aqi.add_child(folium.GeoJson(data=(open(filename,"r",encoding="utf-8-sig")).read(),style_function=lambda x:style_haz))
    if 'OZONE' in species_list:
        fmap_ozone_aqi = folium.plugins.FeatureGroupSubGroup(fmap_airnow_aqi,name='Ozone AQI',overlay=True,control=True,show=True)
        #fmaps['Ozone AQI'] = fmap_ozone_aqi
        fmaps.append(fmap_ozone_aqi)
        fmaps_names.append('Ozone AQI')
        nmaps = nmaps + 1
        if 'EPA AirNOW' in fmap_dict:
            fmap_dict['EPA AirNOW'].add(fmap_ozone_aqi)
        else:
            fmap_dict['EPA AirNOW'] = {fmap_ozone_aqi}
        for filename in glob.glob(obs_path + 'Moderate.ozone*json'):
            fmap_ozone_aqi.add_child(folium.GeoJson(data=(open(filename,"r",encoding="utf-8-sig")).read(),style_function=lambda x:style_mod))
        for filename in glob.glob(obs_path + 'UnhealthySG.ozone*json'):
            fmap_ozone_aqi.add_child(folium.GeoJson(data=(open(filename,"r",encoding="utf-8-sig")).read(),style_function=lambda x:style_uns))
        for filename in glob.glob(obs_path + 'Unhealthy.ozone*json'):
            fmap_ozone_aqi.add_child(folium.GeoJson(data=(open(filename,"r",encoding="utf-8-sig")).read(),style_function=lambda x:style_unh))
        for filename in glob.glob(obs_path + 'VeryUnhealthy.ozone*json'):
            fmap_ozone_aqi.add_child(folium.GeoJson(data=(open(filename,"r",encoding="utf-8-sig")).read(),style_function=lambda x:style_vuh))
        for filename in glob.glob(obs_path + 'Hazardous.ozone*json'):
            fmap_ozone_aqi.add_child(folium.GeoJson(data=(open(filename,"r",encoding="utf-8-sig")).read(),style_function=lambda x:style_haz))
    if 'OZONE' in species_list and 'PM25' in species_list:
        fmap_combined_aqi = folium.plugins.FeatureGroupSubGroup(fmap_airnow_aqi,name='Ozone + PM2.5 AQI',overlay=True,control=True,show=True)
        #fmaps['Ozone + PM2.5 AQI'] = fmap_combined_aqi
        fmaps.append(fmap_combined_aqi)
        fmaps_names.append('Ozone + PM2.5 AQI')
        nmaps = nmaps + 1
        if 'EPA AirNOW' in fmap_dict:
            fmap_dict['EPA AirNOW'].add(fmap_combined_aqi)
        else:
            fmap_dict['EPA AirNOW'] = {fmap_ozone_aqi}
        for filename in glob.glob(obs_path + 'Moderate.combined*json'):
            fmap_combined_aqi.add_child(folium.GeoJson(data=(open(filename,"r",encoding="utf-8-sig")).read(),style_function=lambda x:style_mod))
        for filename in glob.glob(obs_path + 'UnhealthySG.combined*json'):
            fmap_combined_aqi.add_child(folium.GeoJson(data=(open(filename,"r",encoding="utf-8-sig")).read(),style_function=lambda x:style_uns))
        for filename in glob.glob(obs_path + 'Unhealthy.combined*json'):
            fmap_combined_aqi.add_child(folium.GeoJson(data=(open(filename,"r",encoding="utf-8-sig")).read(),style_function=lambda x:style_unh))
        for filename in glob.glob(obs_path + 'VeryUnhealthy.combined*json'):
            fmap_combined_aqi.add_child(folium.GeoJson(data=(open(filename,"r",encoding="utf-8-sig")).read(),style_function=lambda x:style_vuh))
        for filename in glob.glob(obs_path + 'Hazardous.combined*json'):
            fmap_combined_aqi.add_child(folium.GeoJson(data=(open(filename,"r",encoding="utf-8-sig")).read(),style_function=lambda x:style_haz))

if 'PM2.5' in species_list and os.path.exists(obs_path + "hms_smoke_"+todays_date+".kml"):
        fmap_hms = folium.FeatureGroup(name='NOAA HMS',overlay=True,control=True,show=True) 
        fmap.add_child(fmap_hms)
        fmap_hms_smoke = folium.plugins.FeatureGroupSubGroup(fmap_hms,name='HMS Smoke Polygons',overlay=True,control=True,show=False)
        #fmaps['HMS Smoke Polygons'] = fmap_hms_smoke
        fmaps.append(fmap_hms_smoke)
        fmaps_names.append('HMS Smoke Polygons')
        nmaps = nmaps + 1
        if 'NOAA HMS' in fmap_dict:
            fmap_dict['NOAA HMS'].add(fmap_hms_smoke)
        else:
            fmap_dict['NOAA HMS'] = {fmap_hms_smoke}
        for filename in glob.glob(obs_path + 'Light.hms*json'):
            fmap_hms_smoke.add_child(folium.GeoJson(data=(open(filename,"r",encoding="utf-8-sig")).read(),style_function=lambda x:style_hms_light))
        for filename in glob.glob(obs_path + 'Medium.hms*json'):
            fmap_hms_smoke.add_child(folium.GeoJson(data=(open(filename,"r",encoding="utf-8-sig")).read(),style_function=lambda x:style_hms_medium))
        for filename in glob.glob(obs_path + 'Heavy.hms*json'):
            fmap_hms_smoke.add_child(folium.GeoJson(data=(open(filename,"r",encoding="utf-8-sig")).read(),style_function=lambda x:style_hms_heavy))


for s in range(len(species_list)):
        species  = species_list[s]
        platform = platform_list[s]
        platform_label = platform_nice[s]
        color    = color_list[s]
        # path to plots (folium, files are linked here)
        path = plot_output_path + '/' + species + '/' + platform + '/' 
        print("now working on "+ species + " for platform " + platform)
        #
        # Create feature groups for each species
        if species != 'HMS' and len(glob.glob(path + '/plot_grp1.timeseries.'+species+'*')) < 12:
            print("Not enough files for species " + species + " to attach to folium plots, skipping")
            continue
        elif species == 'HMS' and not os.path.exists(obs_path + "hms_fire_"+todays_date+".txt"):
            print("HMS Fire locations not downloaded, skipping")
            continue
        else:
            key = species
            if species == 'HMS':
               value = folium.plugins.FeatureGroupSubGroup(fmap_hms,name='HMS Fire',overlay=True,control=True,show=False)
            else:
               value = folium.plugins.FeatureGroupSubGroup(fmap_marker_cluster,name=species,overlay=True,control=True,show=True)
            fmaps.append(value)
            fmaps_names.append(key)
            #value.add_to(fmap)
            if platform_label in fmap_dict:
                fmap_dict[platform_label].add(value)
            else:
                fmap_dict[platform_label] = {value}
            nmaps = nmaps + 1
            print(nmaps)

        if species != 'HMS':
                #get the site names from the txt file
                fileObj = open(obs_path + "sitefile.txt."+species+"."+platform+"."+todays_date, "r") #opens the file in read mode
                site_name_list = fileObj.read().splitlines() #puts the file into an array
                fileObj.close()
                ##remove the extra characters from either end
                site_name_list = [site[1:-1] for site in site_name_list]
                ##replace the spaces in the site names with underscores
                site_name = [site.replace(' ','_') for site in site_name_list]
        #have to change the PM variable name
        if species == 'PM25':
                species = 'PM2.5'
        if species == 'AOD550':
                species = 'aod_550nm'

        if species == "HMS":
                columns = ['Lon','Lat','YearDay','Time','Satellite','Method','Ecosystem','FRP']
                data = pd.read_csv(obs_path + "hms_fire_"+todays_date+".txt",names=columns,skiprows=1,header=None)
                latitude = data['Lat'].values
                longitude = data['Lon'].values
                frp = data['FRP'].values
                sat = data['Satellite'].values
                for i in range(len(latitude)):
                        tooltip = folium.Tooltip("FRP = "+str(frp[i]) + " MW, detected by "+str(sat[i]))
                        x = folium.CircleMarker(location=[latitude[i], longitude[i]], tooltip=tooltip, radius=4,color = 'red', fill_color="red", fill_opacity=0.5)
                        fmaps[nmaps-1].add_child(x)
        else:
                data = xr.open_dataset(obs_path + "test5."+platform+"."+todays_date+".nc")
                if platform == 'airnow':
                    latitude = data['latitude'].values
                    longitude = data['longitude'].values
                    site = data['site'].values[0]
                else:
                    latitude = data['latitude'].values
                    longitude = data['longitude'].values
                    site = data['siteid'].values
                for i in range(len(site_name)):
                        sitename_bool = site == site_name_list[i]
                        site_lat = latitude[sitename_bool]
                        site_lon = longitude[sitename_bool]
                        if len(site_lat) == 1:
                            if model_type == "regional_smoke" and ( site_lon >=-50 or site_lat <= 0 ):
                              continue
                            else:
                                if platform == "airnow":
                                        plot_name="plot_" + plot_type + "." + species + "." + start_date + "_00." + end_date + "_00.site." + site_name_list[i]
                                else:
                                        plot_name="plot_" + plot_type + "." + species + "." + start_date + "_00." + end_date + "_00.siteid." + site_name_list[i]
                                        #print(path+plot_name)
                                if os.path.isfile(path + plot_name + ".png") and os.path.getsize(path+plot_name + ".png") != 0:
                                        png = path + plot_name + ".png"
                                        png2= plot_name + "_resized.png"
                                        webp= plot_name + ".webp"
                                        if not os.path.isfile(png2):
                                                if species == "PM2.5": 
                                                    subprocess.run(['convert',png,'-resize','495x270',png2])
                                                else:
                                                    subprocess.run(['convert',png,'-resize','495x270',png2]) #'297x162',png2])
                                        if not os.path.isfile(webp):
                                            print("converting to webp")
                                            #subprocess.run(['convert',png2,'-quality','100',webp])
                                            img = Image.open(png2)
                                            img.save(webp, format="WEBP", quality=100)
                                        encoded = base64.b64encode(open(webp, 'rb').read())
                                        html = '<img src="data:image/webp;base64,{}">'.format
                                        iframe = IFrame(html(encoded.decode('UTF-8')), width=(width*resolution)+20, height=(height*resolution)+20)
                                        #creating a popup of the iframe
                                        popup = folium.Popup(iframe,sticky=True)
                                        popups.append(popup)
                                        ipopup = ipopup + 1
                                        tooltip = folium.Tooltip(str(site_name[i]))
                                        x = folium.CircleMarker(location=[site_lat[-1], site_lon[-1]], popup=popup, tooltip=tooltip, radius=marker_radius,color=color, fill_color=color, fill_opacity=0.5)
                                        fmaps[nmaps-1].add_child(x)
                                        mkr1.append(x)

#
fmap.add_child(fmap_marker_cluster)
for imap in range(0,nmaps,1):
    print("adding child " + str(fmaps[imap]) )
    fmap.add_child(fmaps[imap])
    fmap.keep_in_front(fmaps[imap])
fmap.keep_in_front(fmap_marker_cluster)
# Add the layer controls
folium.plugins.GroupedLayerControl(groups=fmap_dict, exclusive_groups=False).add_to(fmap)
folium.LayerControl().add_to(fmap)

# Add interactive measurement tool
folium.plugins.MeasureControl(position='bottomleft', primary_length_unit='kilometers', secondary_length_unit='miles').add_to(fmap)

#saving the map to an html file
output_name = "fullhtml_sfc_"+model_type+".html"
#fmap.gpd.simplify(tolerance=0.001)
fmap.save(output_name)
