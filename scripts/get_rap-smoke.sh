#!/bin/bash -l
#SBATCH --account=acomp
#SBATCH --partition=u1-service
#SBATCH --time=07:59:00
#SBATCH -q batch
#SBATCH -n 1 

module load hpss

YYYY=`date +%Y -d "${START_TIME}"`
YY=`date +%y -d "${START_TIME}"`
MM=`date +%m -d "${START_TIME}"`
DD=`date +%d -d "${START_TIME}"`
YYYYMMDD=${YYYY}${MM}${DD}
model="RAP-Smoke"
final_filename=aqm_${model}_${YYYY}${MM}${DD}${cycleHH}.nc

echo "Getting RAP-Smoke operational forecast data for the ${cycleHH}z cycle on ${YYYYMMDD}"
basedatadir=/BMC/fdr/Permanent/
datadir=${basedatadir}/${YYYY}/${MM}/${DD}/grib/ftp_rap_hyb/7/0/105/0_794802_32769 #0_151987_30
echo "Location of data on HPSS: ${datadir}"

workdir_base=${MELODIES_MONET_DIR}/model_output/${model}
meiyudir=/wrk/csd4/rahmadov/RAP-Chem/rap_smoke/${YYYYMMDD}${cycleHH}

cd ${workdir_base}
workdir=${workdir_base}/${YYYYMMDD}${cycleHH}
echo "Downloading to JET:${workdir}"
mkdir -p ${workdir}
cd ${workdir}
# Create a directory to keep the surface data that's sent safe from removing

filename=${YYYY}${MM}${DD}${cycleHH}00.zip
# Grab the file
echo "Attepting to retrieve file: ${datadir}/${filename}"
hsi get -N ${datadir}/${filename}

exit 0

