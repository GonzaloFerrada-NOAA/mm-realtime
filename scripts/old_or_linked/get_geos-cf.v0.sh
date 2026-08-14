#!/bin/bash -l
#SBATCH --account=acomp
#SBATCH --partition=u1-service
#SBATCH --time=07:30:00
#SBATCH -q batch
#SBATCH -n 1
#SBATCH --mem-per-cpu=20G 
module load nco
#
YYYY=`date +%Y -d "${START_TIME}"`
MM=`date +%m -d "${START_TIME}"`
DD=`date +%d -d "${START_TIME}"`
YYYYMMDD=${YYYY}${MM}${DD}
model="GEOS-CF"
final_filename=aqm_${model}_${YYYYMMDD}${cycleHH}.nc
#
workdir=${MELODIES_MONET_DIR}/model_output/${model}/${YYYYMMDD}${cycleHH}
meiyudir=/wrk/csd4/rahmadov/RAP-Chem/geos-cf/${YYYYMMDD}${cycleHH}
#
mkdir -p ${workdir}
#
cd ${workdir}
#
scp -o 'ProxyJump jschnell@gate.al.noaa.gov' jschnell@meiyu:${meiyudir}/geos-cf.${YYYYMMDD}${cycleHH}.nc .
#
mv geos-cf.${YYYYMMDD}${cycleHH}.nc ${final_filename}
#
# Append the time from HRRR-Smoke (kludge)
if [[ -e ../../HRRR-Smoke/${YYYYMMDD}06/aqm_HRRR-Smoke_${YYYYMMDD}06.nc ]]; then
ncks -v time -d time,6,47 ../../HRRR-Smoke/${YYYYMMDD}06/aqm_HRRR-Smoke_${YYYYMMDD}06.nc times4geos.nc
elif [[ -e ../../HRRR-Smoke/${YYYYMMDD}00/aqm_HRRR-Smoke_${YYYYMMDD}00.nc ]]; then
ncks -v time -d time,0,41 ../../HRRR-Smoke/${YYYYMMDD}00/aqm_HRRR-Smoke_${YYYYMMDD}00.nc times4geos.nc
fi
ncks -A -v time times4geos.nc ${final_filename}
#
#
if [[ -e ${final_filename} ]];then
        echo "Finished processing cycle ${YYYYMMDD}${cycleHH}"
        exit 0
else
        echo "Did not complete ${model} cycle ${YYYYMMDD}${cycleHH} transfer"
        exit 1
fi
