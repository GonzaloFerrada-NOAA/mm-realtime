#!/bin/bash
#### sbatch --partition=u1-service --account=gsd-fv3-test --nodes=1 --time=1:00:00 --qos=batch --mem=50G mm_viiirs_aod_verif.sh
module load cdo eccodes/2.34.0
module load nco

set -e
export PS4='+ [$(date "+%Y-%m-%d %H:%M:%S")] ${LINENO}: '
set -x

# MODEL_TYPE=regional_smoke
# PATH_IN=model_output
# PATH_OUT=model_output
# START_TIME=20260804
# START_TIME_STR=2026-08-04
# cycleHH=00
# PATH_VIIRS_NOAA20=/public/data/sat/nesdis/viirs_level3/aod/eps/noaa20
# PATH_VIIRS_NOAA21=/public/data/sat/nesdis/viirs_level3/aod/eps/noaa21
# PATH_VIIRS_SNPP=/public/data/sat/nesdis/viirs_level3/aod/eps/npp
# SCRIPTS_DIR=/scratch3/BMC/acomp/Gonzalo.Ferrada/verif/melodies-monet-verification
# MELODIES_MONET_DIR=/scratch3/BMC/acomp/Gonzalo.Ferrada/verif/melodies-monet-verification
# CONDA_ENV=/scratch4/BMC/acomp/cheMPAS-Fire/envs/melodies-monet-nrt-vx
# namelist=/scratch4/BMC/acomp/cheMPAS-Fire/realtime/melodies-monet/scripts/monet_namelist.${MODEL_TYPE}

# env variables  to process and plot the VIIRS AOD verification
export INITIAL_TIME="${START_TIME_STR} 00:00:00"
YMD=$( date -d "${INITIAL_TIME}" +%Y%m%d )
HH=$( date -d "${INITIAL_TIME}" +%H )

# local:
CDO_REGRID_FILE="${SCRIPTS_DIR}/cdo_regrid_0p05.txt"
SCRIPT="${SCRIPTS_DIR}/viirs_l3_aod_verification.py"

# VIIRS files:
export FILE_SNPP="${PATH_VIIRS_SNPP}/viirs_eps_npp_aod_0.050_deg_${YMD}_nrt.nc"
export FILE_NOAA20="${PATH_VIIRS_NOAA20}/viirs_eps_noaa20_aod_0.050_deg_${YMD}_nrt.nc" 
export FILE_NOAA21="${PATH_VIIRS_NOAA21}/viirs_eps_noaa21_aod_0.050_deg_${YMD}_nrt.nc"

export LAMBERT_CSV_FILE="${SCRIPTS_DIR}/aux/lambert_map_settings_viirs.csv"

# Check if VIIRS files exist, if not set their value to None:
for f in FILE_NOAA20 FILE_NOAA21 FILE_SNPP; do
    [[ -s ${!f} ]] || printf -v "$f" '%s' "None"
done

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
        
        export FILE_MODEL="${WORKDIR}/aod550_${MODEL_NAME}_${YMD}${HH}.0p05.nc"
        export FILE_OUT="${WORKDIR}/viirs_${MODEL_NAME}_verification_${YMD}${HH}.nc"
        FILES_AVAILABLE+=( "${FILE_OUT}" )
        
        # Regridding
        if [[ ! -s ${FILE_MODEL} ]]; then
            # Regrid each model output using bilinear interpolation to same VIIRS' data resolution (0.05 deg):
            TMP_NC="${WORKDIR}/tmp_viirs_${MODEL_NAME}_${YMD}${HH}.nc"
            
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
            cdo remapbil,${CDO_REGRID_FILE} ${TMP_NC} ${FILE_MODEL}
            rm -f ${TMP_NC}
        fi
        
        # Run python code:
        export MODEL_NAME
        srun --export=ALL --ntasks=1 --cpus-per-task=1 --mem=0 ${CONDA_ENV}/bin/python -u "${SCRIPT}"
        
        status=$?
        if [[ $status -ne 0 ]]; then
            echo "Comparing ${MODEL_NAME} outputs against VIIRS failed with exit status $status"
            exit 1
        fi
        
    else
        FILES_AVAILABLE+=( "None" )
    fi
done

# Overwrite to make figures:
export opt_save_netcdf=False
export opt_make_figure=True
export MODEL_NAMES="${MODEL_LIST[*]}"
export FILE_OUT="${FILES_AVAILABLE[*]}"
export PATH_FIG="${MELODIES_MONET_DIR}/plot_output/${YMD}12/${MODEL_TYPE}/aod_550nm/VIIRS"
mkdir -p ${PATH_FIG}

# Run python code:
srun --export=ALL --ntasks=1 --cpus-per-task=1 --mem=0 ${CONDA_ENV}/bin/python -u "${SCRIPT}"

status=$?
if [[ $status -ne 0 ]]; then
    echo "Plotting failed with exit status $status"
    exit 1
fi

exit 0


