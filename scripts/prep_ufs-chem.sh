#!/bin/bash

module load wgrib2
module load nco 
module load cdo eccodes/2.34.0
source ${SCRIPTS_DIR}/tools/workflow_tools.sh

extract_grib()
{
    # Args: fin outfile rename_from rename_to  <one or more -match patterns>
    local fin="$1"
    local outfile="$2"
    local rename_from="$3"
    local rename_to="$4"
    shift 4                       # remaining args = however many -match patterns you need

    local match_flags=()
    for pat in "$@"; do
        match_flags+=(-match "$pat")   # each becomes its own -match; wgrib2 ANDs them
    done
    
    wgrib2 "${match_flags[@]}" -set center 7  "$fin" -netcdf tmp.nc

    if [[ -n "$rename_from" ]]; then
        ncrename -h -v "${rename_from},${rename_to}" tmp.nc
    fi
    ncks -h -A -v "${rename_to}" tmp.nc "${outfile}"
    rm -f tmp.nc
}

set -e
export PS4='+ [$(date "+%Y-%m-%d %H:%M:%S")] ${LINENO}: '
set -x

# TEST:
# START_TIME="2026-10-26"
# cycleHH="00"
# MELODIES_MONET_DIR="/scratch3/BMC/acomp/Gonzalo.Ferrada/verif/mm-realtime"
# SCRIPTS_DIR="${MELODIES_MONET_DIR}/scripts"
# UFSCHEM_DIR="/scratch3/BMC/gsd-fv3/rtruns/UFS-Chem/FV3GFSrun/rt_hr3-chem/gfs.20261026/00/model_data/atmos/master"
# MODEL="UFS-Chem"
# source ${SCRIPTS_DIR}/tools/workflow_tools.sh


DATE1=$( date -d "${START_TIME} ${cycleHH}:00:00" "+%F %T" )
YYYYMMDDHH=$( date -d "${DATE1}" "+%Y%m%d%H" )
MODEL_DT_HOURS=6
PATH_OUT="${MELODIES_MONET_DIR}/model_output/UFS-Chem/${YYYYMMDDHH}"
FINAL_OUTPUT="${PATH_OUT}/aqm_UFS-Chem_${YYYYMMDDHH}.nc"

mkdir -p ${PATH_OUT}
cd ${PATH_OUT}

# sequence of hours to be read:
lead_times=( $(seq 0 "${MODEL_DT_HOURS}" "96") )

WAVELENGTH="aerosol_wavelength >=5.5e-07,<=5.5e-07"
REF_DATE_STR=$(date -d "$DATE1" +"%Y-%m-%d %H:%M:%S")   # e.g. "2016-08-01 00:00:00"


for H in "${lead_times[@]}"; do
    
    printf -v HHH "%03d" "$H"
    master="${UFSCHEM_DIR}/gfs.t${cycleHH}z.master.grb2f${HHH}"
    frame="${PATH_OUT}/ufschem_${YYYYMMDDHH}_f${HHH}.nc"
    isfile "${master}"
    
    echo "=================================================================================================="
    rm -f ${frame} > /dev/null 2>&1
    
    # Extract variables:
    extract_grib "${master}" "${frame}" "AOTK_entireatmosphere" "aod550"    ":AOTK:" "aerosol_size <2e-05"  "${WAVELENGTH}" "Total aerosol" 
    extract_grib "${master}" "${frame}" "PMTF_surface"          "pm25"      ":PMTF:" "aerosol_size <2.5e-06" "surface" "Total aerosol"
    extract_grib "${master}" "${frame}" "PMTC_surface"          "pm10"      ":PMTC:" "aerosol_size <1e-05" "surface" "Total aerosol"
    
    # Overwrite time's value with the plain lead-time integer, and its
    # units so it's expressed relative to DATE1 instead of the wgrib2 default:
    ncap2 -h -O -s "time[\$time]=int(${H})" "${frame}" "${frame}"
    ncatted -h -O   -a long_name,time,o,c,"time" \
                    -a units,time,o,c,"hours since ${REF_DATE_STR}" \
                    -a reference_date,time,d,, \
                    -a reference_time,time,d,, \
                    -a reference_time_description,time,d,, \
                    -a reference_time_type,time,d,, \
                    -a time_step,time,d,, \
                    -a time_step_setting,time,d,, \
                    "${frame}"
done

# We have all frames, now concatenate in time:
echo "Concatenating into ${FINAL_OUTPUT} ..."
ncrcat -O -h ${PATH_OUT}/ufschem_${YYYYMMDDHH}_f*.nc "${FINAL_OUTPUT}"

isfile "${FINAL_OUTPUT}"
rm -f ${PATH_OUT}/ufschem_${YYYYMMDDHH}_f*.nc

echo "Renaming lat and lon..."
ncrename -h -d latitude,lat  "${FINAL_OUTPUT}"
ncrename -h -d longitude,lon "${FINAL_OUTPUT}"
ncrename -h -v latitude,lat  "${FINAL_OUTPUT}"
ncrename -h -v longitude,lon "${FINAL_OUTPUT}"

echo "Changing longitude: -180 to +180..."
cdo sellonlatbox,-180.0,180.0,-90.0,90.0 ${FINAL_OUTPUT} tmp.nc
mv tmp.nc ${FINAL_OUTPUT}

ncks -O -d lon,-180.,0. -d lat,0.,90. ${FINAL_OUTPUT} ${FINAL_OUTPUT}


echo "done!"