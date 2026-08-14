#!/bin/bash


START_TIME=$1
SCRIPTS_DIR=$2
LOG_DIR=$3
MODEL_TYPE=$4

exitstatus=0

#model_type=(regional_smoke regional_chemistry global)
species=(PM25 PM10 TEMP temp dew_pt_temp wdir ws precip_1hr vsb ceiling AOD550 AOD550 AOD550)
platform=(airnow airnow airnow ish-lite ish-lite ish-lite ish-lite ish-lite ish ish aeronet MODIS_AQUA MODIS_TERRA)
plottype=(ts_regional ts_site spatial_overlay spatial_bias boxplot taylor scorecard csi)

#nmodels=$((${#model_type[@]}-1))
nspecies=$((${#species[@]}-1))
nplatforms=$((${#platform[@]}-1))
nplottypes=$((${#plottype[@]}-1))

#for i in $(seq 0 ${nmodels} )
#do
for j in $(seq 0 ${nspecies} )
do
  for k in $(seq 0 ${nplottypes} )
  do
    if [[ -e ${SCRIPTS_DIR}/task_list_files/do_${MODEL_TYPE}_${species[$j]}_${platform[$j]}_${plottype[$k]}.txt ]]; then
       if [[ ! -e ${LOG_DIR}/mm_run_${START_TIME}_${MODEL_TYPE}_${species[$j]}_${platform[$j]}_${plottype[$k]}.log ]]; then
          exitstatus=1
          break
       fi
    fi
  done
done
#done

exit ${exitstatus}
