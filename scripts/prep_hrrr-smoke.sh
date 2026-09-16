#!/bin/bash
#SBATCH --account=acomp
#SBATCH --partition=u1-service
#SBATCH --time=00:30:00
#SBATCH --cpus-per-task=10
#SBATCH -q debug
#SBATCH --mem=40G

module load hpss
module load wgrib2
module load nco
# module load parallel

source ${SCRIPTS_DIR}/tools/workflow_tools.sh

set -e
export PS4='+ [$(date "+%Y-%m-%d %H:%M:%S")] ${LINENO}: '
set -x

# TEST:
# source tools/workflow_tools.sh
# MELODIES_MONET_DIR="/scratch3/BMC/acomp/Gonzalo.Ferrada/verif/realtime"
# START_TIME="20260901"
# cycleHH=00


YYYY=$(date +%Y -d "${START_TIME}")
YY=$(  date +%y -d "${START_TIME}")
MM=$(  date +%m -d "${START_TIME}")
DD=$(  date +%d -d "${START_TIME}")
YYYYMMDD=${YYYY}${MM}${DD}

model="HRRR-Smoke"
final_filename=aqm_${model}_${YYYY}${MM}${DD}${cycleHH}.nc

echo "Getting ${model} operational forecast data for the ${cycleHH}z cycle on ${YYYYMMDD}"

datadir="/BMC/fdr/Permanent/${YYYY}/${MM}/${DD}/grib/hrrr_wrfsfc/7/0/83/0_1905141_30"
workdir_base="${MELODIES_MONET_DIR}/model_output/${model}"
workdir="${workdir_base}/${YYYYMMDD}${cycleHH}"
filename="${YYYY}${MM}${DD}${cycleHH}00.zip"

mkdir -p "${workdir}"
cd "${workdir}"

echo "Attempting to retrieve file: ${datadir}/${filename}"

hsi get -N "${datadir}/${filename}"

unzip "${filename}"
checkstatus

rm ${filename}

process_file() {
    file="$1"
    gribvars="AOTK|DSWRF|VIS|HGT:cloud ceiling|MASSDEN|:(UGRD|VGRD):10 m above ground:|:(DPT|TMP):2 m above ground:|APCP"
    wgrib2 -nc_nlev 1 -match "${gribvars}" -set center 7 "${file}" -netcdf "${file}.nc"

    ncrename -h -O \
        -v MASSDEN_8maboveground,PM2_5_DRY \
        -v AOTK_entireatmosphere_consideredasasinglelayer_,AOD550 \
        "${file}.nc"

    ncap2 -h -O  \
        -s 'PM2_5_DRY=float(1.0e9*PM2_5_DRY)' \
        "${file}.nc" "${file}.nc"

    ncap2 -h -O  \
        -s 'VIS_surface=float(0.000621371*VIS_surface)' \
        "${file}.nc" "${file}.nc"

    ncap2 -h -O  \
        -s 'where(VIS_surface>10.0) VIS_surface=10.0' \
        "${file}.nc" "${file}.nc"

    ncap2 -h -O  \
        -s 'WDIR_10maboveground=float(180.+(180./3.14159)*atan2(UGRD_10maboveground,VGRD_10maboveground))' \
        "${file}.nc" "${file}.nc"

    ncap2 -h -O  \
        -s 'DPT_2maboveground=float(DPT_2maboveground-273.15)' \
        -s 'TMP_2maboveground=float(TMP_2maboveground-273.15)' \
        "${file}.nc" "${file}.nc"
        
    ncks -O -h -4 -L 3 "${file}.nc" "${file}.nc"
    
    rm -f "${file}"
}

export -f process_file

parallel --jobs 12 process_file ::: ${YY}*

ncrcat -O -h --hdr_pad=16384 ${YY}*.nc ${final_filename}

echo "Getting rid of non-saved files..."
rm -f ${YY}*.nc

isfile "${final_filename}"
echo "Finished processing cycle ${YYYYMMDD}${cycleHH}"
exit 0
