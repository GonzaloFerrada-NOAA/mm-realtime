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
cycleHH="06"

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
model_dir=${MELODIES_MONET_DIR}/model_output/RAP-Chem/
model_datadir=${MELODIES_MONET_DIR}/model_output/RAP-Chem/${YYYY}${MM}${DD}${cycleHH}/
model_file_all=${model_datadir}/aqm_RAP-Chem_${YYYY}${MM}${DD}${cycleHH}.nc
model_file_yest=${model_dir}/${YYYYyt}${MMyt}${DDyt}${cycleHH}/aqm_RAP-Chem_${YYYYyt}${MMyt}${DDyt}${cycleHH}.nc
#
model_file=${model_datadir}/aqm_RAP-Chem_${YYYY}${MM}${DD}${cycleHH}_pollen_average.nc
model_file_regridded=${model_datadir}/aqm_RAP-Chem_${YYYY}${MM}${DD}${cycleHH}_pollen_average_regridded.nc
#
model_file_2=${model_datadir}/aqm_RAP-Chem_${YYYYt}${MMt}${DDt}${cycleHH}_pollen_average.nc
model_file_regridded_2=${model_datadir}/aqm_RAP-Chem_${YYYYt}${MMt}${DDt}${cycleHH}_pollen_average_regridded.nc

output_directory=${PLOT_OUTPUT_DIR}
mkdir -p ${output_directory}
#
#
# Cut out and average the day
rm -f ${model_file} ${model_file_regridded} ${model_file_2} ${model_file_regridded_2} ${model_datadir}/subset_1.nc ${model_datadir}/subset_2.nc ${model_datadir}/combined_${YYYY}${MM}${DD}${cycleHH}.nc ${model_datadir}/*.tmp

ncks -d Time,19,24 -v T,P,PB,pols,polp,polp_tree,polp_grass,polp_weed ${model_file_yest} ${model_datadir}/subset_1.nc
ncks -d Time,0,18 -v T,P,PB,pols,polp,polp_tree,polp_grass,polp_weed ${model_file_all} ${model_datadir}/subset_2.nc
ncrcat  ${model_datadir}/subset_1.nc  ${model_datadir}/subset_2.nc  ${model_datadir}/combined_${YYYY}${MM}${DD}${cycleHH}.nc
#
ncra -v T,P,PB,pols,polp,polp_tree,polp_grass,polp_weed ${model_datadir}/combined_${YYYY}${MM}${DD}${cycleHH}.nc ${model_file} 
#ncra -d Time,0,23 -v T,P,PB,pols,polp,polp_tree,polp_grass,polp_weed ${model_file_all} ${model_file}
ncwa -O -a Time ${model_file} ${model_file}
ncwa -O -a bottom_top ${model_file} ${model_file}
ncrename -v XLAT,lat -v XLONG,lon ${model_file}
ncrename -d west_east,lon -d south_north,lat ${model_file}

ncra -d Time,18,41 -v T,P,PB,pols,polp,polp_tree,polp_grass,polp_weed ${model_file_all} ${model_file_2}
ncwa -O -a Time ${model_file_2} ${model_file_2}
ncwa -O -a bottom_top ${model_file_2} ${model_file_2}
ncrename -v XLAT,lat -v XLONG,lon ${model_file_2}
ncrename -d west_east,lon -d south_north,lat ${model_file_2}
#

module load rdhpcs-conda
conda activate /scratch4/BMC/acomp/cheMPAS-Fire/envs/melodies-monet-nrt-vx
#
if [[ ! -r ${model_file} ]]; then
   echo "${model_file} does not exist, exiting"
   exit 1
fi
if [[ ! -r ${model_file_regridded} ]]; then
# Regrid model file to PollenSense domain
python ${SCRIPTS_DIR}/regrid_rapchem_to_pollensense.py ${model_file} ${model_file_regridded}
python ${SCRIPTS_DIR}/regrid_rapchem_to_pollensense.py ${model_file_2} ${model_file_regridded_2}
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
python ${SCRIPTS_DIR}/plot_compare_pollensense_to_rapchem.py ${forecast} ${obs_path} ${model_dir} ${YYYYyt}${MMyt}${DDyt} ${YYYY}${MM}${DD} ${YYYYt}${MMt}${DDt} ${cycleHH} ${output_directory}
#
forecast=1
python ${SCRIPTS_DIR}/plot_compare_pollensense_to_rapchem.py ${forecast} ${obs_path} ${model_dir} ${YYYYyt}${MMyt}${DDyt} ${YYYY}${MM}${DD} ${YYYYt}${MMt}${DDt} ${cycleHH} ${output_directory}
#
forecast=2
python ${SCRIPTS_DIR}/plot_compare_pollensense_to_rapchem.py ${forecast} ${obs_path} ${model_dir} ${YYYYyt}${MMyt}${DDyt} ${YYYY}${MM}${DD} ${YYYYt}${MMt}${DDt} ${cycleHH} ${output_directory}
#
