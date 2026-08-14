#!/bin/bash

#model_type=(regional_smoke)
#species=(PM25 PM10 PM25 PM10 temp dew_pt_temp wdir ws precip_1hr vsb ceiling AOD550 AOD550 AOD550)
#platform=(airnow airnow openaq openaq ish-lite ish-lite ish-lite ish-lite ish-lite ish ish aeronet MODIS_AQUA MODIS_TERRA)
model_type=(regional_smoke regional_chemistry global)
species=(PM2.5 PM2.5)
platform=(airnow openaq)
#plottype=(ts_regional ts_site spatial_overlay spatial_bias boxplot taylor)
plottype=(stats)


nmodels=$((${#model_type[@]}-1))
nspecies=$((${#species[@]}-1))
#nplatforms=$((${#platform[@]}-1))
nplottypes=$((${#plottype[@]}-1))

for i in $(seq 0 ${nmodels} )
do
  for j in $(seq 0 ${nspecies} )
  do
    for k in $(seq 0 ${nplottypes} )
    do
      touch do_${model_type[$i]}_${species[$j]}_${platform[$j]}_${plottype[$k]}.txt
    done
  done
done

