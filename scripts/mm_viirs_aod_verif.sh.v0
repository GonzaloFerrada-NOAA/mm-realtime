#!/bin/bash
#### sbatch --partition=u1-service --account=gsd-fv3-test --nodes=1 --time=1:00:00 --qos=batch --mem=50G mm_viiirs_aod_verif.sh
module load cdo eccodes/2.34.0
module load nco

set -e
export PS4='+ [$(date "+%Y-%m-%d %H:%M:%S")] ${LINENO}: '
set -x

# env variables used by the julia code to process and plot the VIIRS AOD verification
export INITIAL_TIME="${START_TIME_STR} 00:00:00"
YMD=$( date -d "${INITIAL_TIME}" +%Y%m%d )
HH=$( date -d "${INITIAL_TIME}" +%H )

export FILE_MODEL_IN="${PATH_IN}/${MODEL_NAME}/${YMD}${HH}/aqm_${MODEL_NAME}_${YMD}${HH}.nc"
export FILE_MODEL="${WORKDIR}/aod550_${MODEL_NAME}_${YMD}${HH}.0p05.nc"
export FILE_NOAA20="${PATH_VIIRS_NOAA20}/viirs_eps_noaa20_aod_0.050_deg_${YMD}_nrt.nc" 
export FILE_SNPP="${PATH_VIIRS_SNPP}/viirs_eps_npp_aod_0.050_deg_${YMD}_nrt.nc"
export FILE_OUT="${WORKDIR}/VIIRS_${MODEL_NAME}_verification_${YMD}${HH}.nc"
PATH_FIG="${MELODIES_MONET_DIR}/plot_output/${YMD}12/regional_smoke/aod_550nm/VIIRS"
mkdir -p ${PATH_FIG}
export FILE_FIG="${PATH_FIG}/plot_grp3.VIIRS_${MODEL_NAME}_CONUS_${YMD}${HH}.png"

CDO_REGRID_FILE="${SCRIPTS_DIR}/cdo_regrid_0p05.txt"

mkdir -p ${WORKDIR}

# Regrid model output using bilinear interpolation to same VIIRS' data resolution (0.05 deg):
TMP_NC="${WORKDIR}/tmp_${MODEL_NAME}_${YMD}${HH}.nc"
ncks -O -v AOD550 ${FILE_MODEL_IN} ${TMP_NC}
# Bilinear interpolation is fine:
cdo remapbil,${CDO_REGRID_FILE} ${TMP_NC} ${FILE_MODEL}
rm -f ${TMP_NC}

# Run python code:
SCRIPT="${SCRIPTS_DIR}/viirs_l3_aod_verification.py"
srun --ntasks=1 --cpus-per-task=1 --mem=0 ${CONDA_ENV}/bin/python -u "${SCRIPT}"


# Check if output figure was created:
if [[ ! -s "${FILE_FIG}" ]]
then
    echo "ERROR: The figure was not created. ${SCRIPT} must have failed."
    echo "Aborting."
    exit 1
fi

# Clean up the workdir:
rm -rf ${WORKDIR}

