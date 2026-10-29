#!/bin/bash -l

module purge
module load imagemagick

# Helpers:
isempty() {
    [[ -z $(find "$1" -mindepth 1 -maxdepth 1 -print -quit) ]]
}
get_figs() (
    shopt -s nullglob
    local files=( "$1"/*"$2"."$3".*"$4"*.png )
    ((${#files[@]})) && printf '%s\n' "${files[@]}"
)
# set -e
# export PS4='+ [$(date "+%Y-%m-%d %H:%M:%S")] ${LINENO}: '
set -x

# TEST
# model_type=regional_smoke
# START_TIME=20261019
# BASEDIR=/scratch3/BMC/acomp/Gonzalo.Ferrada/verif/mm-realtime/toweb
# PLOTDIR=/scratch3/BMC/acomp/Gonzalo.Ferrada/verif/mm-realtime/plot_output/${START_TIME}12
# WORKDIR=/scratch3/BMC/acomp/Gonzalo.Ferrada/verif/mm-realtime/toweb/${START_TIME}12/all

# First check if we actually have anything in PLOTDIR:
if isempty "${PLOTDIR}/${model_type}"; then 
    echo "ERROR: directory ${PLOTDIR}/${model_type} is empty"; exit 1
fi

# Predefined:
PLATFORMS=( "aeronet" "airnow" "openaq" "metar" "TEMPO" "VIIRS")
SPECIES=( "aod_550nm" "PM2.5"  "PM10"  "OZONE"  "NO2"  "CO"  "TEMP"  "vsb"  "ceiling")
PLOT_TYPES=( "ts_regional" "spatial_overlay" "spatial_bias" "boxplot" "taylor" "None" "7.csi" "8.csi" "9.csi" "stats" )
REGIONIN=(  "CONUS" "R1" "R2" "R3" "R4" "R5" "R6" "R7" "R8" "R9" "R10" )
REGIONOUT=( "full" "r01" "r02" "r03" "r04" "r05" "r06" "r07" "r08" "r09" "r10" )

# Construct some dates
YYYY=$( date +%Y -d "${START_TIME}" )
MM=$(   date +%m -d "${START_TIME}" )
DD=$(   date +%d -d "${START_TIME}" )

YYYYMMDD=$(     date +"%Y%m%d" -d "${YYYY}${MM}${DD}" )
YESTERDAY=$(    date +"%Y%m%d" -d "${YYYY}${MM}${DD} -1 day" )      # Start of analysis 
TWODAYSAGO=$(   date +"%Y%m%d" -d "${YYYY}${MM}${DD} -2 days" )
TOMORROW=$(     date +"%Y%m%d" -d "${YYYY}${MM}${DD} +1 day" )

# Directories
echo "Building the MELODIES-MONET plots from the analysis performed on ${YYYYMMDD} for ${YESTERDAY} with forecast run on ${TWODAYSAGO}"

# Begin
for R in "${!REGIONIN[@]}"; do

    RIN="${REGIONIN[R]}"
    ROUT="${REGIONOUT[R]}"
    PATHOUT="${WORKDIR}/${ROUT}"
    mkdir -p "${PATHOUT}"
    
    for P in "${PLATFORMS[@]}"; do
        echo "================================================================================="
        echo "Processing $RIN ${P}"
        
        PATHIN="${PLOTDIR}/${model_type}/${P}"
        isempty "${PATHIN}" && continue
        
        for S in "${SPECIES[@]}"; do
        for T in "${!PLOT_TYPES[@]}"; do
            
            TYPE="${PLOT_TYPES[T]}"
            printf -v TT "%02d" "$((T + 1))"
            
            [[ "${TYPE}" == "ts_regional" && "${RIN}" == "CONUS" ]] && TYPE="timeseries"
            
            # echo "Processing ${P} ${RIN}: ${S} - ($TT) ${TYPE}"
            
            mapfile -t FIGS < <(get_figs "${PATHIN}" "${TYPE}" "${S}" "${RIN}")
            NFIGS=${#FIGS[@]}
            # echo "NFIGS = ${NFIGS}"
            
            (( NFIGS == 0 )) && continue
            FOUT="${PATHOUT}/${model_type}_${S}_${P}_f${TT}.png"
            echo ${FOUT}
            
            if [[ "${TYPE}" == "stats" || "${P}" == "VIIRS" || "${P}" == "TEMPO" ]]; then
                # (( NFIGS == 1 )) || { echo "ERROR: expected one figure, found ${NFIGS}: ${FIGS[@]}"; echo "skipping"; continue; }
                # cp "${FIGS[@]}" "${FOUT}"
                magick montage -geometry +0+0 -tile 1x "${FIGS[@]}" "${FOUT}"
            else
                magick montage -geometry 900x400+0+0 -tile 1x${NFIGS} "${FIGS[@]}" "${FOUT}"
            fi
            
        done # T PLOT_TYPES
        done # S SPECIES
    done # P PLATFORMS
    
    # Copy html files
    [[ "${RIN}" == "CONUS" ]] && cp ${PLOTDIR}/sites/html/*.html ${PATHOUT}
    
    zip -j ${PATHOUT}/files.zip ${PATHOUT}/*
    
done # R REGIONS


exit





exit 0
