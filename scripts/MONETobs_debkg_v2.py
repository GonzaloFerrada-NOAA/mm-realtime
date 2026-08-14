#!/usr/bin/env python3
# Remove baseline v2 from airnow obs file from MONET
# Author: Huiying Luo, last modified Sept 2025, v2.1

import netCDF4 as nc
import numpy as np
import pandas as pd
from math import radians, cos, sin, asin, sqrt
from datetime import datetime
import calendar
import warnings
import sys
import shutil

# Input
#locsetpath='airnow_sites_epalist_20240716.csv' # Synced with jcsda/ioda, ['UNKNOWN', 'RURAL', 'SUBURBAN', 'URBAN AND CENTER CITY'] or blank   
#basepath='IODA_hourlyPM25baseline_v2r1.nc'  
#inpath='test/AIRNOW_20240720_20240731_MONET.nc' # Prepared by JS_reformat_airnow.py from Johana, tested
#inpath='test/test5.airnow.20240724-20240725.nc' # Prepared by workflow from Jordan, not tested
inpath = sys.argv[1]
locsetpath = sys.argv[2]
basepath = sys.argv[3]

# Settings
SearchDist_km=[100,30,30] # Max searching distances for both (baseline and obs) non-urban, one urban one non urban, and both urban; ORDER MATTERS
KeepNoncalib=0 # Keep(1) or discart(0, default) sites w no matching baseline nearby
SaveOri=1 # Save(1, default) copy or change file directly

if SaveOri==0:
    outpath=inpath
    print('NOTE: Obs file will be modified!')
else:
    outpath=inpath[:-3]+'_PM25blremoved_.nc'
    shutil.copyfile(inpath, outpath)
print()
print('####### Start of Baseline Removal for AirNow PM2.5 Observations #######')
print("Input: "+locsetpath+" "+basepath+" "+inpath+" ")
print("Output: "+outpath)
print("Searching distance for non-urban/non-urban, urban/non-urban, urban/urban pairs (km): "+str(SearchDist_km))
print("Keep raw PM2.5 obs when baseline not available: "+str(KeepNoncalib))
print("Keep original copy: "+str(SaveOri))
print('----- End of Settings -----')

def haversine(lat1, lon1, lat2, lon2):
    """
    Calculate the great circle distance in kilometers between two points
    on the earth (specified in decimal degrees)
    """
    # Convert decimal degrees to radians
    lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])

    # Haversine formula
    dlon = lon2 - lon1
    dlat = lat2 - lat1
    a = sin(dlat / 2)**2 + cos(lat1) * cos(lat2) * sin(dlon / 2)**2
    c = 2 * asin(sqrt(a))
    km = 6371 * c  # Radius of earth in kilometers.
    return km

def find_nearest_within_threshold(reference_lat, reference_lon, reference_isurban,lat,lon,isurban):
    """
    Finds the index of the nearest location from a baseline dataset to a reference point.
    In: lat lon is_urban for obs site, lat lon is_urban array for baseline data
    Out: index of matched site from baseline
    """
    min_distance=[100000,100000,100000]
    nearest_location=[np.nan,np.nan,np.nan]
    for s in range(len(lat)):
        distance = haversine(reference_lat, reference_lon, lat[s], lon[s])
        match_setting=int(reference_isurban+isurban[s]) # index of SearchDist_km
        if distance < min_distance[match_setting]:
            min_distance[match_setting] = distance
            nearest_location[match_setting] = s
    #print(min_distance)
    #print(nearest_location)
    for i in range(3):
        if min_distance[i]>SearchDist_km[i]:
            nearest_location[i]=np.nan
    #print(min_distance)
    #print(nearest_location)

    # return prefernce: both urban/non-urban, then mismatched land setting
    for index in [0,2,1]:
        if ~np.isnan(nearest_location[index]):
            #print(nearest_location[index])
            return nearest_location[index]
    return np.nan

def smooth_BLm2m(DS_aqsioda,dst,DS_aqs):
    """
    Produce month-to-month smoothed baseline in obs time space 
    In: obs, obs time, monthly baseline
    Out: baseline at the times of obs 
    """
    # Temp ref BL to deal with Jan and Dec
    BLL=np.concatenate((DS_aqs,DS_aqs,DS_aqs),axis=1) # site*36*24
         
    BLsmooth=np.zeros((DS_aqsioda.shape[0],DS_aqs.shape[0]))
    for i in range(len(dst)):
        if dst[i].day>(calendar.monthrange(dst[i].year, dst[i].month)[1]-7): # smooth m2m transition for last
            y1=BLL[:,dst[i].month+12-1,dst[i].hour]
            y2=BLL[:,dst[i].month+12,dst[i].hour]
            x1=calendar.monthrange(dst[i].year, dst[i].month)[1]-7 
            x2=calendar.monthrange(dst[i].year, dst[i].month)[1]+8
            BLsmooth[i,:]=y1+(dst[i].day-x1)* ((y2 - y1) / (x2 - x1))
        elif dst[i].day<8: # smooth m2m transition for first week
            y1=BLL[:,dst[i].month+12-1-1,dst[i].hour]
            y2=BLL[:,dst[i].month+12-1,dst[i].hour]
            x1=-7 
            x2=8
            BLsmooth[i,:]=y1+(dst[i].day-x1)* ((y2 - y1) / (x2 - x1))
        else:  # center of month use monthly BL directly 
            BLsmooth[i,:]=BLL[:,dst[i].month+12-1,dst[i].hour]
    return BLsmooth

## Read input files
# Read aqs land use data
lu_read = pd.read_csv(locsetpath)
lu_id = lu_read['stat_id']
lu_loc = lu_read['loc_setting']
lu_isurban = [1 if loc == 'URBAN AND CENTER CITY' else 0 for loc in lu_loc]

# Read bkg
dss = nc.Dataset(basepath)
site_id_aqs = dss.variables['site_id_aqs'][:]
site_lat_aqs = dss.variables['site_lat'][:]
site_lon_aqs = dss.variables['site_lon'][:]
DS_aqs = dss.variables['PM25baseline'][:]
dss.close()
aqs_isurban = np.zeros(len(site_id_aqs))
counter=0
for i in range(len(site_id_aqs)):
    try:
        #print(np.where(site_id_aqs[i]==lu_id)[0][0])
        aqs_isurban[i]=lu_isurban[np.where(site_id_aqs[i]==lu_id)[0][0]]
    except:# no info as not urban
        counter=counter+1
        #print('Baseline site location setting not found at '+site_id_aqs[i])
#print('Total urban baseline site: ' +str(int(sum(aqs_isurban))))
print(str(counter)+' out of '+str(len(site_id_aqs)) +' baseline location settings not found, used non-urban as default.')


# Read obs for update
ds = nc.Dataset(outpath,'r+')
site_time_aqsioda = ds['time'][:] #(time) int min since 2024-07-20 00:00:00
dst=nc.num2date(site_time_aqsioda, units=ds['time'].units, calendar='standard')
site_id_aqsioda = ds['siteid'] #[0,:] #longitude(y, x)
site_lat_aqsioda = ds['latitude'] #[0,:]
site_lon_aqsioda = ds['longitude'] #[0,:] 

# For MONET workflow obs that has improper FillValue
variable = ds.variables['PM2.5']
data = variable[:]
old_fill_value = variable._FillValue
#print(old_fill_value)
#print(data[0:10,0,0:10])  
data[data == old_fill_value] = np.nan
#print(data[0:10,0,0:10])

DS_aqsioda = data[:,0,:] #(time, y, x), time*site

## Calculate new baseline removed PM25 value
DS_aqsfinal=np.zeros([len(site_time_aqsioda),1,len(site_id_aqsioda)])
DS_aqsfinal[:]=np.nan
DS_aqscali=np.zeros([len(site_id_aqsioda)])

# Step 1: Temporal interpolate baseline to obs time space with month to month smoothing 
DS_blsmooth=smooth_BLm2m(DS_aqsioda,dst,DS_aqs) # baseline in obs time space

# Step 2: Spatial matching and baseline removal
counter=0
print('When obs site location setting not found to match with nearby sites, used non-urban as default.')
for s in range(len(site_id_aqsioda)):
    if len(np.where(site_id_aqs==site_id_aqsioda[s])[0])==0:
        # find matching nearby
        
        # obs site location settings
        try:
            #print('Obs site location setting found')
            obs_isurban=lu_isurban[np.where(site_id_aqsioda[s]==lu_id)[0][0]]
        except:# no info as not urban
            obs_isurban=0
        
        nearest = find_nearest_within_threshold(site_lat_aqsioda[s], site_lon_aqsioda[s], obs_isurban,site_lat_aqs,site_lon_aqs,aqs_isurban)
        if np.isnan(nearest):
            #print('No matching site found..................')
            counter=counter+1
            if KeepNoncalib==0:
                DS_aqsfinal[:,0,s]=np.nan
            else:
                DS_aqsfinal[:,0,s]=DS_aqsioda[:,s]
        else:
            #print('Matching site found..................')
            DS_aqsfinal[:,0,s]=DS_aqsioda[:,s]-DS_blsmooth[:,nearest]
            DS_aqscali[s]=1
    else: # direct match id
        #print('Direct match found..............')
        DS_aqsfinal[:,0,s]=DS_aqsioda[:,s]-DS_blsmooth[:,np.where(site_id_aqs==site_id_aqsioda[s])[0]].flatten()
        DS_aqscali[s]=1
DS_aqsfinal[DS_aqsfinal<0]=0.0
DS_aqsfinal=np.round(DS_aqsfinal,2)
#print(DS_aqsfinal[0:10,0,0:10])

if KeepNoncalib==0:
    print(str(counter)+' out of '+str(len(site_id_aqsioda))+' observation sites discarded. Change KeepNoncalib to 1 to keep raw observation at these locations.')
else:
    print(str(counter)+' out of '+str(len(site_id_aqsioda))+' observation sites not calibrated. Change KeepNoncalib to 0 to discard raw observation sites.')

with warnings.catch_warnings():
    warnings.simplefilter("ignore", category=RuntimeWarning)
    ds.variables['PM2.5'][:] = DS_aqsfinal.astype('double')
ds.close()

print('####### End of Baseline Removal for AirNow PM2.5 Observations #######')
print()
