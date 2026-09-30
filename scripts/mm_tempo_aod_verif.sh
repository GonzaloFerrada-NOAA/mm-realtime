#!/bin/bash
#### sbatch --partition=u1-service --account=gsd-fv3-test --nodes=1 --time=1:00:00 --qos=batch --mem=50G mm_viiirs_aod_verif.sh
module load cdo eccodes/2.34.0
module load nco

set -e
export PS4='+ [$(date "+%Y-%m-%d %H:%M:%S")] ${LINENO}: '
set -x

# Test: # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #
# export MODEL_TYPE=regional_smoke
# export START_TIME=20260912
# export cycleHH=00
# export MELODIES_MONET_DIR="/scratch3/BMC/acomp/Gonzalo.Ferrada/verif/realtime"
# export PATH_IN="${MELODIES_MONET_DIR}/model_output"
# export PATH_OUT="${MELODIES_MONET_DIR}/model_output"
# export PATH_TEMPO="/scratch3/BMC/acomp/Gonzalo.Ferrada/monet-rt/obs/${START_TIME}12"
# export SCRIPTS_DIR="${MELODIES_MONET_DIR}/scripts"
# export CONDA_ENV="/scratch4/BMC/acomp/cheMPAS-Fire/envs/melodies-monet-nrt-vx"
# export namelist="${SCRIPTS_DIR}/monet_namelist.${MODEL_TYPE}"
# # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #

source ${SCRIPTS_DIR}/tools/workflow_tools.sh

# env variables  to process and plot the VIIRS AOD verification
export INITIAL_TIME="$( date -d "${START_TIME}" +%F ) 00:00:00"
YMD=$( date -d "${INITIAL_TIME}" +%Y%m%d )
HH=$( date -d "${INITIAL_TIME}" +%H )

export TEMPO_FILE="${PATH_TEMPO}/tempo_aggregated_hourly_0p1deg_${START_TIME}00.nc"
export LAMBERT_CSV_FILE="${SCRIPTS_DIR}/aux/lambert_map_settings_tempo.csv"
isfile "${TEMPO_FILE}"
isfile "${LAMBERT_CSV_FILE}"

# local:
CDO_REGRID_FILE="${TEMPO_FILE}"
PYTHON="${CONDA_ENV}/bin/python"
SCRIPT="${SCRIPTS_DIR}/tempo_aod_verification.py"

# Read namelist:
mapfile -t MODEL_LIST < <(awk -F',' '!/^#/ {print $1}' "${namelist}")

export opt_save_netcdf=True
export opt_make_figure=False

# Process each model output against VIIRS data
FILES_AVAILABLE=( )
for MODEL_NAME in "${MODEL_LIST[@]}"; do

    export WORKDIR="${PATH_IN}/${MODEL_NAME}/${YMD}${HH}"
    export FILE_MODEL_IN="${WORKDIR}/aqm_${MODEL_NAME}_${YMD}${HH}.nc"
    
    if [[ -s ${FILE_MODEL_IN} ]]; then
        
        echo "Regridding ${MODEL_NAME}"
        
        export FILE_MODEL="${WORKDIR}/aod550_${MODEL_NAME}_${YMD}${HH}.0p1.nc"
        export FILE_OUT="${WORKDIR}/tempo_${MODEL_NAME}_verification_${YMD}${HH}.nc"
        FILES_AVAILABLE+=( "${FILE_OUT}" )
        
        # Regridding
        if [[ ! -s ${FILE_MODEL} ]]; then
            # Regrid each model output using bilinear interpolation to same TEMPO data resolution (0.1 deg):
            TMP_NC="${WORKDIR}/tmp_tempo_${MODEL_NAME}_${YMD}${HH}.nc"
            
            case "${MODEL_NAME}" in
            RAP-Smoke)
                ncks -O -v "AOD_550" "${FILE_MODEL_IN}" "${TMP_NC}"
                ncrename -v AOD_550,AOD550 "${TMP_NC}"
                ;;
            MPAS-Aerosols)
                ncks -O -v "AOD550,AOD550_SIMPLE" "${FILE_MODEL_IN}" "${TMP_NC}"
                ;;
            *)
                ncks -O -v "AOD550" "${FILE_MODEL_IN}" "${TMP_NC}"
                ;;
            esac
            
            # Bilinear interpolation is fine:
            cdo remapbil,"${CDO_REGRID_FILE}" ${TMP_NC} ${FILE_MODEL}
            rm -f ${TMP_NC}
        fi
        
        # Run python code:
        export MODEL_NAME
        srun --export=ALL --ntasks=1 --cpus-per-task=1 --mem=0 ${PYTHON} -u "${SCRIPT}"
        
        checkstatus
        
    else
        FILES_AVAILABLE+=( "None" )
    fi
done

# Overwrite to make figures:
export opt_save_netcdf=False
export opt_make_figure=True
export MODEL_NAMES="${MODEL_LIST[*]}"
export FILE_OUT="${FILES_AVAILABLE[*]}"
export PATH_FIG="${MELODIES_MONET_DIR}/plot_output/${YMD}12/${MODEL_TYPE}/aod_550nm/TEMPO"
ismkdir "${PATH_FIG}"

# Run python code:
srun --export=ALL --ntasks=1 --cpus-per-task=1 --mem=0 ${PYTHON} -u "${SCRIPT}"

checkstatus

exit 0


