#!/bin/bash -l

source ${SCRIPTS_DIR}/tools/workflow_tools.sh
module load nco

set -e
export PS4='+ [$(date "+%Y-%m-%d %H:%M:%S")] ${LINENO}: '
set -x

YYYY=$(date +%Y -d "${START_TIME}")
MM=$(  date +%m -d "${START_TIME}")
DD=$(  date +%d -d "${START_TIME}")
YYYYMMDD="${YYYY}${MM}${DD}"
model="NAAPS"
final_filename="aqm_${model}_${YYYYMMDD}${cycleHH}.nc"

workdir="${MELODIES_MONET_DIR}/model_output/${model}/${YYYYMMDD}${cycleHH}"
meiyudir="/wrk/csd4/rahmadov/RAP-Chem/NAAPS/${YYYYMMDD}${cycleHH}"

echo "Creating directory ${workdir}"
mkdir -p ${workdir}

cd ${workdir}

scp -o 'ProxyJump jschnell@gate.al.noaa.gov' jschnell@meiyu:${meiyudir}/${final_filename} .
checkstatus

ncks -O -3 ${final_filename} ${final_filename}
isfile "${final_filename}"

exit 0
