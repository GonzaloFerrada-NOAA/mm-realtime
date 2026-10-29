#!/bin/bash
module load wgrib2
module load nco
module load cdo eccodes/2.34.0
source ${SCRIPTS_DIR}/tools/workflow_tools.sh

# Test:
# source tools/workflow_tools.sh
# START_TIME="20260926"
# cycleHH="00"
# MELODIES_MONET_DIR="/scratch3/BMC/acomp/Gonzalo.Ferrada/verif/tmp"


# local function:
extract_grib()
{
    # Args: fin outfile rename_from rename_to  <one or more -match patterns>
    local fin="$1"
    local outfile="$2"
    local rename_from="$3"
    local rename_to="$4"
    shift 4                       # remaining args = however many -match patterns you need

    # Temp file unique per frame (was a shared tmp.nc -> would collide in parallel)
    local tmp="${outfile%.nc}.tmp.nc"

    local match_flags=()
    for pat in "$@"; do
        match_flags+=(-match "$pat")   # each becomes its own -match; wgrib2 ANDs them
    done

    wgrib2 "${match_flags[@]}" -set center 7 "$fin" -netcdf "$tmp" > /dev/null

    if [[ -n "$rename_from" ]]; then
        ncrename -h -v "${rename_from},${rename_to}" "$tmp"
    fi
    ncks -h -A -v "${rename_to}" "$tmp" "${outfile}"
    rm -f "$tmp"
}

set -e
export PS4='+ [$(date "+%Y-%m-%d %H:%M:%S")] ${LINENO}: '
set -x

YYYY=$( date -d "${START_TIME}" +%Y )
YY=$(   date -d "${START_TIME}" +%y )
MM=$(   date -d "${START_TIME}" +%m )
DD=$(   date -d "${START_TIME}" +%d )
YYYYMMDD="${YYYY}${MM}${DD}"
model="GEFS-Aerosols"
MODEL_DT_HOURS=3
FINAL_OUTPUT="aqm_${model}_${YYYY}${MM}${DD}${cycleHH}.nc"
REF_DATE_STR="${YYYY}-${MM}-${DD} ${cycleHH}:00:00"

# Directories:
workdir="${MELODIES_MONET_DIR}/model_output/${model}/${YYYYMMDD}${cycleHH}"
mkdir -p ${workdir}
cd ${workdir}
rm -f gefs.chem*

# Download AWS files:
AWSLINK="https://noaa-gefs-pds.s3.amazonaws.com/gefs.${YYYYMMDD}/${cycleHH}/chem/pgrb2ap25"
lead_times=( $(seq 0 "${MODEL_DT_HOURS}" "96") )

for H in "${lead_times[@]}"; do
    
    printf -v HHH "%03d" "$H"
    file="gefs.chem.t${cycleHH}z.a2d_0p25.f${HHH}.grib2"
    
    # Download the file:
    wget ${AWSLINK}/${file}
    
    # Extract data and convert to netcdf:
    frame="${file}.nc"; rm -f ${frame}
    
    extract_grib "${file}" "${frame}" "AOTK_entireatmosphere"   "aod550"  ":AOTK:" "Total aerosol:aerosol_size <2e-05:aerosol_wavelength >=5.45e-07,<=5.65e-07"
    extract_grib "${file}" "${frame}" "PMTF_surface"            "pm25"    ":PMTF:" "Total aerosol:aerosol_size <2.5e-06"
    extract_grib "${file}" "${frame}" "PMTC_surface"            "pm10"    ":PMTC:" "Total aerosol:aerosol_size <1e-05"
    
    # Overwrite time with the lead-time integer, relative to START_DATE:
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
    
    rm -f ${file}
    
done

echo "Concatenating into ${FINAL_OUTPUT} ..."
ncrcat -O -h *.nc combined.nc
cdo -s sellonlatbox,-180.0,180.0,-90.0,90.0 combined.nc ${FINAL_OUTPUT}

echo "Renaming lat and lon..."
ncrename -h -d latitude,lat  "${FINAL_OUTPUT}"
ncrename -h -d longitude,lon "${FINAL_OUTPUT}"
ncrename -h -v latitude,lat  "${FINAL_OUTPUT}"
ncrename -h -v longitude,lon "${FINAL_OUTPUT}"

echo "Subsetting to second quadrant..."
ncks -O -d lon,-180.,0. -d lat,0.,90. ${FINAL_OUTPUT} ${FINAL_OUTPUT}

# Remove everything else
rm -f *.grib2 *.grib2.nc combined.nc

isfile ${FINAL_OUTPUT}

exit 0
