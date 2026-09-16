#!/bin/bash
module load wgrib2
module load nco
source ${SCRIPTS_DIR}/tools/workflow_tools.sh
# source tools/workflow_tools.sh

# local function:
extract_grib()
{
    local match="$1"
    local fin="$2"
    local outfile="$3"
    local rename_from="$4"
    local rename_to="$5"

    wgrib2 -nc_nlev 1 -match "$match" -set center 7 "$fin" -netcdf "$outfile"

    if [[ -n "$rename_from" ]]; then
        ncrename -h -v "${rename_from},${rename_to}" "$outfile"
    fi
}


set -e
export PS4='+ [$(date "+%Y-%m-%d %H:%M:%S")] ${LINENO}: '
set -x

# TEST Passed as env:
# MELODIES_MONET_DIR="/scratch3/BMC/acomp/Gonzalo.Ferrada/verif/realtime"
# START_TIME="20260825"
# cycleHH=00
# GROUP=9
# NGROUPS=10
# FCST_LENGTH_HOURS=48
# processORcat=0
# RRFS_SD_DATADIR_GRIB2="/scratch3/BMC/acomp/Sudheer/Fire-nest/Retros/RRFS_A/RT/GRIB2"

# Test:
FCST_LENGTH_HOURS=$((10#$FCST_LENGTH_HOURS))
NGROUPS=$((10#$NGROUPS))
GROUP=$((10#$GROUP))

YYYY=$( date -d "${START_TIME}" +%Y )
MM=$( date -d "${START_TIME}" +%m )
DD=$( date -d "${START_TIME}" +%d )
YYYYMMDD=${YYYY}${MM}${DD}
model="RRFS-SD"
model2="RRFS-A"
MODEL_DT=1

# Directories:
datadir="${RRFS_SD_DATADIR_GRIB2}/rrfs.${YYYY}${MM}${DD}/${cycleHH}"
workdir="${MELODIES_MONET_DIR}/model_output/${model}/${YYYYMMDD}${cycleHH}"
mkdir -p ${workdir}

final_fout="${workdir}/aqm_${model}_${YYYYMMDD}${cycleHH}.nc"
final_fout2="${workdir}/aqm_${model2}_${YYYYMMDD}${cycleHH}.nc"

# if processORcat = 1; then simply concatenate:
if [[ ${processORcat} -eq 1 ]]; then
    ncrcat -O -h --hdr_pad=16384 ${workdir}/frame_*_aqm_${model}_${YYYYMMDD}${cycleHH}.nc "${final_fout}"
    ln -sf ${final_fout} ${final_fout2}
    
    # Check if file was created and its size is not 0:
    isfile "${final_fout}"
    
    # Cleanup
    rm -f ${workdir}/frame_*_aqm_${model}_${YYYYMMDD}${cycleHH}.nc
    
    echo "${final_fout} created!"
    echo "${final_fout2} created!"
    exit 0
fi

# Determine the output hours to process:
# this function outputs LEAD_HH_START and LEAD_HH_END
get_group_leads "${FCST_LENGTH_HOURS}" "${MODEL_DT}" "${NGROUPS}" "${GROUP}"

# Process files:
for (( hh=LEAD_HH_START; hh<=LEAD_HH_END; hh+=MODEL_DT )); do

    printf -v HHH "%03d" "$hh"
    fin="${datadir}/rrfs.t${cycleHH}z.2dfld.3km.f${HHH}.na.grib2" 
    fout="${workdir}/frame_${HHH}_aqm_${model}_${YYYYMMDD}${cycleHH}.nc"
    
    # Check if file exists before proceeding:
    isfile $fin
    echo "=============================================================================="
    echo "Working on ${fout}"
    echo "Extracting GRIB2 variables..."
    
    # data extraction and conversion to netcdf:
    # AOD
    extract_grib 'AOTK'                             "$fin" "${fout%.*}_aod.nc"          'AOTK_entireatmosphere_consideredasasinglelayer_' 'AOD550'
    # Downward SW
    extract_grib 'DSWRF'                            "$fin" "${fout%.*}_dswrf.nc"        '' ''
    # Visibility
    extract_grib 'VIS'                              "$fin" "${fout%.*}_vis.nc"          '' ''
    # Ceiling
    extract_grib 'HGT:cloud ceiling'                "$fin" "${fout%.*}_ceil.nc"         '' ''
    # Fine dust
    extract_grib 'Dust dry:aerosol_size <2.5e-06'   "$fin" "${fout%.*}_dust_fine.nc"   'MASSDEN_8maboveground' 'dust_fine'
    # Coarse dust
    extract_grib 'Dust dry:aerosol_size >=2.5e-06'  "$fin" "${fout%.*}_dust_coarse.nc" 'MASSDEN_8maboveground' 'dust_coarse'
    # Smoke
    extract_grib 'organic'                          "$fin" "${fout%.*}_smoke.nc"       'MASSDEN_8maboveground' 'smoke'
    # 10-m wind
    extract_grib ':(UGRD|VGRD):10 m above ground:'  "$fin" "${fout%.*}_wind.nc"        '' ''
    # 2-m temperature/dew point
    extract_grib ':(DPT|TMP):2 m above ground:'     "$fin" "${fout%.*}_temp.nc"        '' ''
    # Precipitation
    extract_grib 'APCP'                             "$fin" "${fout%.*}_precip.nc"      '' ''
    
    # Calculations
    echo "Calculations (ncap2)..."
    ncap2 -O -h -s 'WIND_10maboveground=float(sqrt(UGRD_10maboveground^2 + VGRD_10maboveground^2))'                 "${fout%.*}_wind.nc" "${fout%.*}_wind.nc"
    ncap2 -O -h -s 'WDIR_10maboveground=float(180.+(180./3.14159)*atan2(UGRD_10maboveground,VGRD_10maboveground))'  "${fout%.*}_wind.nc" "${fout%.*}_wind.nc"
    ncap2 -O -h -s 'TMP_2maboveground=float(TMP_2maboveground-273.15)'                                  "${fout%.*}_temp.nc"            "${fout%.*}_temp.nc"
    ncap2 -O -h -s 'DPT_2maboveground=float(DPT_2maboveground-273.15)'                                  "${fout%.*}_temp.nc"            "${fout%.*}_temp.nc"
    ncap2 -O -h -s 'dust_fine=float(1.e9*dust_fine)'                                                    "${fout%.*}_dust_fine.nc"       "${fout%.*}_dust_fine.nc"
    ncap2 -O -h -s 'dust_coarse=float(1.e9*dust_coarse)'                                                "${fout%.*}_dust_coarse.nc"     "${fout%.*}_dust_coarse.nc"
    ncap2 -O -h -s 'smoke=float(1.e9*smoke)'                                                            "${fout%.*}_smoke.nc"           "${fout%.*}_smoke.nc"
    ncap2 -O -h -s 'VIS_surface=float(0.000621371*VIS_surface)'                                         "${fout%.*}_vis.nc"             "${fout%.*}_vis.nc"
    ncap2 -O -h -s 'where(VIS_surface>10.0) VIS_surface=10.0'                                           "${fout%.*}_vis.nc"             "${fout%.*}_vis.nc"
    
    # Append:
    echo "Merging to ${fout}..."
    ncks -A -h                                                  "${fout%.*}_aod.nc"             "${fout}"
    ncks -A -h -v "DSWRF_surface"                               "${fout%.*}_dswrf.nc"           "${fout}"
    ncks -A -h -v "VIS_surface"                                 "${fout%.*}_vis.nc"             "${fout}"
    ncks -A -h -v "HGT_cloudceiling"                            "${fout%.*}_ceil.nc"            "${fout}"
    ncks -A -h -v "dust_fine"                                   "${fout%.*}_dust_fine.nc"       "${fout}"
    ncks -A -h -v "dust_coarse"                                 "${fout%.*}_dust_coarse.nc"     "${fout}"
    ncks -A -h -v "smoke"                                       "${fout%.*}_smoke.nc"           "${fout}"
    ncks -A -h -v "WIND_10maboveground,WDIR_10maboveground"     "${fout%.*}_wind.nc"            "${fout}"
    ncks -A -h -v "TMP_2maboveground,DPT_2maboveground"         "${fout%.*}_temp.nc"            "${fout}"
    if [[ -f "${fout%.*}_precip.nc" ]]; then
    ncks -A -h -v "APCP_surface"                                "${fout%.*}_precip.nc"          "${fout}"
    fi
    
    # Delete files:
    echo "Deleting intermediate files..."
    rm -f ${fout%.*}_*.nc
    
    # Final calculations:
    echo "Final calculations..."
    ncap2 -h -O -s 'pm25=float(dust_fine+smoke)'       "${fout}" "${fout}"
    ncap2 -h -O -s 'pm10=float(pm25+dust_coarse)'      "${fout}" "${fout}"
    ncap2 -h -O -s 'lat=latitude' -s 'lon=longitude'   "${fout}" "${fout}"
    # ncwa  -h -O -a    hlevel                           "${fout}" "${fout}"
    ncks  -h -O -x -v hlevel                           "${fout}" "${fout}"
    
    # Compress:
    echo "Compressing..."
    ncks -O -h -4 -L 3 "${fout}" "${fout}"
    
    isfile "${fout}" # Check if file was created and its size is not 0
    
    echo "${fout} created!"
    
done

echo "prep_rrfs-sd completed for current group ${GROUP}"

exit 0