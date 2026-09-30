#!/bin/bash
# module load hpss
module load nco
source ${SCRIPTS_DIR}/tools/workflow_tools.sh

set -e
export PS4='+ [$(date "+%Y-%m-%d %H:%M:%S")] ${LINENO}: '
set -x


YYYY=$( date -d "${START_TIME}" +%Y )
MM=$(   date -d "${START_TIME}" +%m )
DD=$(   date -d "${START_TIME}" +%d )
YYYYMMDD="${YYYY}${MM}${DD}"
model="RAP-Chem"
final_filename="aqm_${model}_${YYYYMMDD}${cycleHH}.nc"
final_filename3d="aqm3D_${model}_${YYYYMMDD}${cycleHH}.nc"

datadir="/scratch4/BMC/acomp/cheMPAS-Fire/realtime/rap-chem/homebasedir/rap-chem_databasedir/cycle_covid/${YYYYMMDD}${cycleHH}/wrfprd/output/joined"
echo "Location of data: ${datadir}"

workdir_base="${MELODIES_MONET_DIR}/model_output/${model}"

cd ${workdir_base}
workdir="${workdir_base}/${YYYYMMDD}${cycleHH}"
echo "Downloading to JET:${workdir}"
mkdir -p ${workdir}
# Create a directory to keep the surface data that's sent safe from removing

filename="*00_surface"
# Grab the files
echo "Attepting to retrieve file: ${datadir}/${filename}"
cd ${datadir}

files=$(find . -name "$filename" -type f -print)
count=$(printf '%s\n' "$files" | grep -c .)
if [ "$count" -eq 0 ]; then
    echo "Error: no files found for $filename"
    exit 1
fi

ncrcat ${files} ${workdir}/${final_filename}
cd ${workdir}
ncap2 -O -s 'WDIR10=180.+(180./3.14159)*atan2(U10,V10)' ${final_filename} ${final_filename} 
ncap2 -O -s 'PRECIP_1HR=PREC_ACC_C+PREC_ACC_NC'         ${final_filename} ${final_filename}
ncap2 -O -s 'T2=T2-273.15'                              ${final_filename} ${final_filename}
ncap2 -O -s 'AFWA_VIS=AFWA_VIS*0.621371/1000.'          ${final_filename} ${final_filename}
ncap2 -O -s 'latitude=XLAT' -s 'longitude=XLONG'        ${final_filename} ${final_filename}
ncap2 -O -s 'lat=latitude' -s 'lon=longitude'           ${final_filename} ${final_filename}

filename="*select3D*"
cd ${datadir}
files=`find . -name ${filename} | sort`
ncrcat ${files} ${workdir}/${final_filename3d}

isfile "${workdir}/${final_filename}"
exit 0
