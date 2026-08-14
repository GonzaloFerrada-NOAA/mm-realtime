#!/bin/bash -l
#SBATCH --account=acomp
#SBATCH --partition=u1-service
#SBATCH --time=01:30:00
#SBATCH -q batch
#SBATCH -n 1
##SBATCH --mem-per-cpu=20G 
module load nco
#
YYYY=`date +%Y -d "${START_TIME}"`
MM=`date +%m -d "${START_TIME}"`
DD=`date +%d -d "${START_TIME}"`
YYYYMMDD=${YYYY}${MM}${DD}
model="NAAPS"
final_filename=aqm_${model}_${YYYYMMDD}${cycleHH}.nc
#
workdir=${MELODIES_MONET_DIR}/model_output/${model}/${YYYYMMDD}${cycleHH}
meiyudir=/wrk/csd4/rahmadov/RAP-Chem/NAAPS/${YYYYMMDD}${cycleHH}
#
echo "Creating directory ${workdir}"
mkdir -p ${workdir}
#
cd ${workdir}
#
scp -o 'ProxyJump jschnell@gate.al.noaa.gov' jschnell@meiyu:${meiyudir}/${final_filename} .
ncks -O -3 ${final_filename} ${final_filename}
#
exit 0
