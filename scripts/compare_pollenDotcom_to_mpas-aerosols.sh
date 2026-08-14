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
today_j=`date +%j -d "${START_TIME}"`

YYYYyt=`date +%Y -d "${START_TIME} - 24 hours"`
MMyt=`date +%m -d "${START_TIME} - 24 hours"`
DDyt=`date +%d -d "${START_TIME} - 24 hours"`
HHyt=`date +%H -d "${START_TIME} - 24 hours"`
YYYYMMDDyt=${YYYYyt}${MMyt}${DDyt}
yesterday_j=`date +%j -d "${START_TIME} - 24 hours"`

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
model_file_all=${model_datadir}/aqm_MPAS-Aerosols_${YYYY}${MM}${DD}${cycleHH}.nc
model_file_yest=${model_dir}/${YYYYyt}${MMyt}${DDyt}${cycleHH}/aqm_MPAS-Aerosols_${YYYYyt}${MMyt}${DDyt}${cycleHH}
#
model_file=${model_datadir}/aqm_MPAS-Aerosols_${YYYY}${MM}${DD}${cycleHH}_pollen_average.nc
model_file_regridded=${model_datadir}/aqm_MPAS-Aerosols_${YYYY}${MM}${DD}${cycleHH}_pollen_average_regridded.nc
#

output_directory=${PLOT_OUTPUT_DIR}
mkdir -p ${output_directory}
#
#

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
module load rdhpcs-conda
conda activate /scratch4/BMC/acomp/cheMPAS-Fire/envs/melodies-monet-nrt-vx
forecast=0
python ${SCRIPTS_DIR}/plot_compare_pollenDotcom_to_rapchem.py ${forecast} ${obs_path} ${model_dir} ${YYYYyt}${MMyt}${DDyt} ${YYYY}${MM}${DD} ${YYYYt}${MMt}${DDt} ${cycleHH} ${output_directory} ${yesterday_j}
#
