#!/bin/bash

module load netcdf
module load nco

set -x

# Define some dates/constants
YYYY=`date +%Y -d "${START_TIME}"`
MM=`date +%m -d "${START_TIME}"`
DD=`date +%d -d "${START_TIME}"`
HH=`date +%H -d "${START_TIME}"`
YYYYMMDD=${YYYY}${MM}${DD}
cycleHH="00"

YYYYyt=`date +%Y -d "${START_TIME} - 24 hours"`
MMyt=`date +%m -d "${START_TIME} - 24 hours"`
DDyt=`date +%d -d "${START_TIME} - 24 hours"`
HHyt=`date +%H -d "${START_TIME} - 24 hours"`
YYYYMMDDyt=${YYYYyt}${MMyt}${DDyt}

YYYYt=`date +%Y -d "${START_TIME} + 24 hours"`
MMt=`date +%m -d "${START_TIME} + 24 hours"`
DDt=`date +%d -d "${START_TIME} + 24 hours"`
HHt=`date +%H -d "${START_TIME} + 24 hours"`
YYYYMMDDt=${YYYYt}${MMt}${DDt}

# Set the working directory
workdir=${WORKDIR}
mkdir -p ${workdir}
cd ${workdir}
#
model_dir=${MELODIES_MONET_DIR}/model_output/MPAS-Aerosols/
model_datadir=${MELODIES_MONET_DIR}/model_output/MPAS-Aerosols/${YYYY}${MM}${DD}${cycleHH}/
model_datadir_2=${MELODIES_MONET_DIR}/model_output/MPAS-Aerosols/${YYYYt}${MMt}${DDt}${cycleHH}/
model_file_all=${model_datadir}/aqm_MPAS-Aerosols_${YYYY}${MM}${DD}${cycleHH}.nc
model_file_all_2=${model_datadir_2}/aqm_MPAS-Aerosols_${YYYYt}${MMt}${DDt}${cycleHH}.nc
model_file_yest=${model_dir}/${YYYYyt}${MMyt}${DDyt}${cycleHH}/aqm_MPAS-Aerosols_${YYYYyt}${MMyt}${DDyt}${cycleHH}.nc
#
model_file=${model_datadir}/aqm_MPAS-Aerosols_${YYYY}${MM}${DD}${cycleHH}_pollen_average.nc
model_file_regridded=${model_datadir}/aqm_MPAS-Aerosols_${YYYY}${MM}${DD}${cycleHH}_pollen_average_regridded.nc
#
model_file_2=${model_datadir_2}/aqm_MPAS-Aerosols_${YYYYt}${MMt}${DDt}${cycleHH}_pollen_average.nc
model_file_regridded_2=${model_datadir_2}/aqm_MPAS-Aerosols_${YYYYt}${MMt}${DDt}${cycleHH}_pollen_average_regridded.nc
#
output_directory=${PLOT_OUTPUT_DIR}
mkdir -p ${output_directory}
#
#
# Cut out and average the day
rm -f ${model_file} ${model_file_regridded} ${model_file_2} ${model_file_regridded_2}
#
ncrename -v POLP_TREE,polp_tree -v POLP_WEED,polp_weed -v POLP_GRASS,polp_grass ${model_file_all}
ncra -d Time,1,24 -v T,P,PB,polp_tree,polp_grass,polp_weed ${model_file_all} ${model_file}
ncap2 -O -s 'polp=polp_tree+polp_grass+polp_weed' ${model_file} ${model_file}
ncks -O -6  ${model_file}  ${model_file}
ncwa -O -a Time ${model_file} ${model_file}
ncwa -O -a bottom_top ${model_file} ${model_file}
ncap2 -O -s 'lat=XLAT' -s 'lon=XLONG' ${model_file} ${model_file}
ncrename -d .west_east,lon -d .south_north,lat ${model_file}


ncrename -v POLP_TREE,polp_tree -v POLP_WEED,polp_weed -v POLP_GRASS,polp_grass ${model_file_all_2}
ncra -d Time,1,24 -v T,P,PB,polp_tree,polp_grass,polp_weed ${model_file_all_2} ${model_file_2}
ncap2 -O -s 'polp=polp_tree+polp_grass+polp_weed' ${model_file_2} ${model_file_2} 
ncks -O -6  ${model_file_2} ${model_file_2}
ncwa -O -a Time ${model_file_2} ${model_file_2}
ncwa -O -a bottom_top ${model_file_2} ${model_file_2}
ncap2 -O -s 'lat=XLAT' -s 'lon=XLONG' ${model_file_2} ${model_file_2}
ncrename -d .west_east,lon -d .south_north,lat ${model_file_2}

module load rdhpcs-conda
conda activate /scratch4/BMC/acomp/cheMPAS-Fire/envs/melodies-monet-nrt-vx
#
if [[ ! -r ${model_file} ]]; then
   echo "${model_file} does not exist, exiting"
   exit 1
fi
if [[ ! -r ${model_file_regridded} ]]; then
# Regrid model file to PollenSense domain
python ${SCRIPTS_DIR}/regrid_mpas_to_pollensense.py ${model_file} ${model_file_regridded}
fi
if [[ ! -r ${model_file_regridded_2} ]]; then
# Regrid model file to PollenSense domain
python ${SCRIPTS_DIR}/regrid_mpas_to_pollensense.py ${model_file_2} ${model_file_regridded_2}
fi
if [[ ! -r ${model_file_regridded} ]]; then
   echo "failed to create ${model_file_regridded}, exiting"
   exit 1
fi

obs_path=${OBS_DIR}
#fcst_type            = sys.argv[1] # 0 = obs, 1 = one day ahead forecast, 2 = two day ahead...
#obs_path             = sys.argv[2]
#mdl_path             = sys.argv[3]
#yesterday            = sys.argv[4] # Current day of analysis (2 days behind real time)
#today                = sys.argv[5]
#tomorrow             = sys.argv[6]
#cycleHH              = sys.argv[7]
#outdir               = sys.argv[8]
# Now plot it
forecast=0
python ${SCRIPTS_DIR}/plot_compare_pollensense_to_mpas.py ${forecast} ${obs_path} ${model_dir} ${YYYYyt}${MMyt}${DDyt} ${YYYY}${MM}${DD} ${YYYYt}${MMt}${DDt} ${cycleHH} ${output_directory}
#
if [[ ! -r ${model_file_regridded_2} ]]; then
   echo "failed to create ${model_file_regridded_2}, exiting"
   exit 1
fi
forecast=1
python ${SCRIPTS_DIR}/plot_compare_pollensense_to_mpas.py ${forecast} ${obs_path} ${model_dir} ${YYYYyt}${MMyt}${DDyt} ${YYYY}${MM}${DD} ${YYYYt}${MMt}${DDt} ${cycleHH} ${output_directory}
#
