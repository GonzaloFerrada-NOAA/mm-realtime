#!/bin/bash -l
#SBATCH --account=acomp
#SBATCH --partition=u1-compute
#SBATCH --time=10:00:00
#SBATCH -q batch
#SBATCH -n 1 
#SBATCH --mem-per-cpu=20G

set -x

module load hpss
module load nco


YYYY=`date +%Y -d "${START_TIME}"`
MM=`date +%m -d "${START_TIME}"`
DD=`date +%d -d "${START_TIME}"`
HH=${cycleHH}
YYYYMMDD=${YYYY}${MM}${DD}
model="MPAS-Aerosols"
final_filename=aqm_${model}_${YYYYMMDD}${cycleHH}.nc
final_filename3d=aqm3D_${model}_${YYYYMMDD}${cycleHH}.nc
datadir="/home/Jordan.Schnell/mpas_aerosols_jet/${YYYY}${MM}${DD}${cycleHH}/rrfs_mpassit_${cycleHH}_v2.1.3/det/"
#datadir=/lfs5/BMC/rtwbl/rap-chem/mpas_conus3km/cycledir/stmp/${YYYY}${MM}${DD}${cycleHH}/rrfs_mpassit_${cycleHH}_v2.1.1/det/
#datadir=/lfs5/BMC/rtwbl/rap-chem/homebasedir/rap-chem_databasedir/cycle_covid/${YYYY}${MM}${DD}${cycleHH}/wrfprd/output/joined
echo "Location of data on HPSS: ${datadir}"

workdir_base=${MELODIES_MONET_DIR}/model_output/${model}/
mkdir -p ${workdir_base}
cd ${workdir_base}
workdir=${workdir_base}/${YYYYMMDD}${cycleHH}
echo "Downloading to JET:${workdir}"
mkdir -p ${workdir}
# Create a directory to keep the surface data that's sent safe from removing

filename='mpassit*.nc'
# Grab the files
echo "Attepting to retrieve file: ${datadir}/${filename}"
cd ${datadir}
files=`find . -name 'mpas*.nc' | sort`

#ncrcat -v
ncrcat ${files} ${workdir}/${final_filename}
ncks -O -d bottom_top,0,0 ${workdir}/${final_filename} ${workdir}/${final_filename}
cd ${workdir}
ncap2 -O -s 'WDIR10=180.+(180./3.14159)*atan2(U10MEAN,V10MEAN)' ${final_filename} ${final_filename} 
ncap2 -O -s 'PRECIP_1HR=PREC_ACC_C+PREC_ACC_NC' ${final_filename} ${final_filename}
ncap2 -O -s 'T2=T2-273.15' ${final_filename} ${final_filename}
ncap2 -O -s 'VIS=VIS*0.621371/1000.' ${final_filename} ${final_filename}
ncap2 -O -s 'WIND10MEAN=(U10MEAN^2+V10MEAN^2)^(0.5)' ${final_filename} ${final_filename}
ncap2 -O -s 'latitude=XLAT' -s 'longitude=XLONG' ${final_filename} ${final_filename}


if [[ -e ${workdir}/${final_filename} ]];then
        echo "Finished processing cycle ${YYYYMMDD}${cycleHH}"
        exit 0
else
        echo "Did not complete ${model} cycle ${YYYYMMDD}${cycleHH} transfer"
        exit 1
fi
