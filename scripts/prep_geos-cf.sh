#!/bin/bash 
module load nco
source ${SCRIPTS_DIR}/tools/workflow_tools.sh

set -e
export PS4='+ [$(date "+%Y-%m-%d %H:%M:%S")] ${LINENO}: '
set -x

YYYY=$(date +%Y -d "${START_TIME}")
MM=$(  date +%m -d "${START_TIME}")
DD=$(  date +%d -d "${START_TIME}")
YYYYMMDD="${YYYY}${MM}${DD}"
model="GEOS-CF"
final_filename=aqm_${model}_${YYYYMMDD}${cycleHH}.nc

workdir=${MELODIES_MONET_DIR}/model_output/${model}/${YYYYMMDD}${cycleHH}
meiyudir=/wrk/csd4/rahmadov/RAP-Chem/geos-cf/${YYYYMMDD}${cycleHH}

mkdir -p ${workdir}
cd ${workdir}

scp -o 'ProxyJump jschnell@gate.al.noaa.gov' jschnell@meiyu:${meiyudir}/geos-cf.${YYYYMMDD}${cycleHH}.nc .
checkstatus

mv geos-cf.${YYYYMMDD}${cycleHH}.nc ${final_filename}

# Append the time from HRRR-Smoke (kludge)
if [[ -e ../../HRRR-Smoke/${YYYYMMDD}06/aqm_HRRR-Smoke_${YYYYMMDD}06.nc ]]; then
    ncks -v time -d time,6,47 ../../HRRR-Smoke/${YYYYMMDD}06/aqm_HRRR-Smoke_${YYYYMMDD}06.nc times4geos.nc
    checkstatus
    
elif [[ -e ../../HRRR-Smoke/${YYYYMMDD}00/aqm_HRRR-Smoke_${YYYYMMDD}00.nc ]]; then
    ncks -v time -d time,0,41 ../../HRRR-Smoke/${YYYYMMDD}00/aqm_HRRR-Smoke_${YYYYMMDD}00.nc times4geos.nc
    checkstatus
fi

ncks -A -v time times4geos.nc ${final_filename}
checkstatus

isfile "${final_filename}"

echo "Done!"
exit 0
