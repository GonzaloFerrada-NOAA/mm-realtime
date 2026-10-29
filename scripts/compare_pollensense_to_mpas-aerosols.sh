#!/bin/bash

module load netcdf
module load nco
module load rdhpcs-conda
conda activate /scratch4/BMC/acomp/cheMPAS-Fire/envs/melodies-monet-nrt-vx

# set -x
# Test:
START_TIME="20261026"
WORKDIR="/scratch3/BMC/acomp/Gonzalo.Ferrada/verif/tmp"
MELODIES_MONET_DIR="/scratch4/BMC/acomp/cheMPAS-Fire/realtime/melodies-monet"
OBS_DIR="/scratch4/BMC/acomp/cheMPAS-Fire/realtime/melodies-monet/obs"
PLOT_OUTPUT_DIR="${WORKDIR}/plot_output"
SCRIPTS_DIR="${MELODIES_MONET_DIR}/scripts"

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
YYYYMMDDyt="${YYYYyt}${MMyt}${DDyt}"

YYYYt=`date +%Y -d "${START_TIME} + 24 hours"`
MMt=`date +%m -d "${START_TIME} + 24 hours"`
DDt=`date +%d -d "${START_TIME} + 24 hours"`
HHt=`date +%H -d "${START_TIME} + 24 hours"`
YYYYMMDDt="${YYYYt}${MMt}${DDt}"

# Set the working directory
cd ${WORKDIR}

model_dir="${MELODIES_MONET_DIR}/model_output/MPAS-Aerosols"
model_datadir_today="${model_dir}/${YYYYMMDD}${cycleHH}"
model_datadir_tomorrow="${model_dir}/${YYYYMMDDt}${cycleHH}"
model_datadir_yesterday="${model_dir}/${YYYYMMDDyt}${cycleHH}"
model_file_today="${model_datadir_today}/aqm_MPAS-Aerosols_${YYYYMMDD}${cycleHH}.nc"
model_file_tomorrow="${model_datadir_tomorrow}/aqm_MPAS-Aerosols_${YYYYMMDDt}${cycleHH}.nc"
model_file_yesterday="${model_datadir_yesterday}/aqm_MPAS-Aerosols_${YYYYMMDDyt}${cycleHH}.nc"

pollen_file="${model_datadir_today}/aqm_MPAS-Aerosols_${YYYY}${MM}${DD}${cycleHH}_pollen_average.nc"
pollen_file_regridded="${model_datadir_today}/aqm_MPAS-Aerosols_${YYYY}${MM}${DD}${cycleHH}_pollen_average_regridded.nc"

pollen_file_tomorrow="${model_datadir_tomorrow}/aqm_MPAS-Aerosols_${YYYYt}${MMt}${DDt}${cycleHH}_pollen_average.nc"
pollen_file_regridded_tomorrow="${model_datadir_tomorrow}/aqm_MPAS-Aerosols_${YYYYt}${MMt}${DDt}${cycleHH}_pollen_average_regridded.nc"


mkdir -p ${PLOT_OUTPUT_DIR}

# Cut out and average the day
rm -f "${pollen_file}" "${pollen_file_regridded}" "${pollen_file_tomorrow}" "${pollen_file_regridded_tomorrow}"

# ncrename -v POLP_TREE,polp_tree -v POLP_WEED,polp_weed -v POLP_GRASS,polp_grass ${model_file_today}
ncra -d time,1,24 -v T,P,PB,polp_tree,polp_grass,polp_weed "${model_file_today}" "${pollen_file}"
ncap2 -O -s 'polp=polp_tree+polp_grass+polp_weed' "${pollen_file}" "${pollen_file}"
ncks -O -6  "${pollen_file}" "${pollen_file}"
ncwa -O -a time "${pollen_file}" "${pollen_file}"
# ncwa -O -a bottom_top "${pollen_file}" "${pollen_file}"
# ncap2 -O -s 'lat=XLAT' -s 'lon=XLONG' ${pollen_file} ${pollen_file}
# ncrename -d .west_east,lon -d .south_north,lat ${pollen_file}


# ncrename -v POLP_TREE,polp_tree -v POLP_WEED,polp_weed -v POLP_GRASS,polp_grass "${model_file_tomorrow}"
ncra -d Time,1,24 -v T,P,PB,polp_tree,polp_grass,polp_weed "${model_file_tomorrow}" "${pollen_file_tomorrow}"
ncap2 -O -s 'polp=polp_tree+polp_grass+polp_weed' "${pollen_file_tomorrow}" "${pollen_file_tomorrow}"
ncks -O -6  "${pollen_file_tomorrow}" "${pollen_file_tomorrow}"
ncwa -O -a Time "${pollen_file_tomorrow}" "${pollen_file_tomorrow}"
# ncwa -O -a bottom_top "${pollen_file_tomorrow}" "${pollen_file_tomorrow}"
# ncap2 -O -s 'lat=XLAT' -s 'lon=XLONG' "${pollen_file_tomorrow}" "${pollen_file_tomorrow}"
# ncrename -d .west_east,lon -d .south_north,lat "${pollen_file_tomorrow}"



if [[ ! -r ${pollen_file} ]]; then
   echo "${pollen_file} does not exist, exiting"
   exit 1
fi
if [[ ! -r ${pollen_file_regridded} ]]; then
# Regrid model file to PollenSense domain
python ${SCRIPTS_DIR}/regrid_mpas_to_pollensense.py ${pollen_file} ${pollen_file_regridded}
fi
if [[ ! -r ${pollen_file_regridded_tomorrow} ]]; then
# Regrid model file to PollenSense domain
python ${SCRIPTS_DIR}/regrid_mpas_to_pollensense.py ${pollen_file_tomorrow} ${pollen_file_regridded_tomorrow}
fi
if [[ ! -r ${pollen_file_regridded} ]]; then
   echo "failed to create ${pollen_file_regridded}, exiting"
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
if [[ ! -r ${pollen_file_regridded_tomorrow} ]]; then
   echo "failed to create ${pollen_file_regridded_tomorrow}, exiting"
   exit 1
fi
forecast=1
python ${SCRIPTS_DIR}/plot_compare_pollensense_to_mpas.py ${forecast} ${obs_path} ${model_dir} ${YYYYyt}${MMyt}${DDyt} ${YYYY}${MM}${DD} ${YYYYt}${MMt}${DDt} ${cycleHH} ${output_directory}
#
