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
YYYYMMDD=${YYYY}${MM}${DD}
model="RAP-Chem"
final_filename=aqm_${model}_${YYYYMMDD}${cycleHH}.nc
final_filename3d=aqm3D_${model}_${YYYYMMDD}${cycleHH}.nc

#basedatadir=/5year/BMC/wrf-chem/rap-chem/realtime/covid/wrfout/
#datadir=${basedatadir}/${YYYY}/${MM}/${DD}/${cycleHH}
datadir=/scratch4/BMC/acomp/cheMPAS-Fire/realtime/rap-chem/homebasedir/rap-chem_databasedir/cycle_covid/${YYYY}${MM}${DD}${cycleHH}/wrfprd/output/joined
echo "Location of data on HPSS: ${datadir}"

workdir_base=${MELODIES_MONET_DIR}/model_output/${model}/

cd ${workdir_base}
workdir=${workdir_base}/${YYYYMMDD}${cycleHH}
echo "Downloading to JET:${workdir}"
mkdir -p ${workdir}
# Create a directory to keep the surface data that's sent safe from removing

filename="*00_surface"
# Grab the files
echo "Attepting to retrieve file: ${datadir}/${filename}"
cd ${datadir}
files=`find . -name ${filename} | sort`

ncrcat ${files} ${workdir}/${final_filename}
cd ${workdir}
ncap2 -O -s 'WDIR10=180.+(180./3.14159)*atan2(U10,V10)' ${final_filename} ${final_filename} 
ncap2 -O -s 'PRECIP_1HR=PREC_ACC_C+PREC_ACC_NC' ${final_filename} ${final_filename}
ncap2 -O -s 'T2=T2-273.15' ${final_filename} ${final_filename}
ncap2 -O -s 'AFWA_VIS=AFWA_VIS*0.621371/1000.' ${final_filename} ${final_filename}
ncap2 -O -s 'latitude=XLAT' -s 'longitude=XLONG' ${final_filename} ${final_filename}
ncap2 -O -s 'lat=latitude' -s 'lon=longitude'  ${final_filename} ${final_filename}

filename="*select3D*"
cd ${datadir}
files=`find . -name ${filename} | sort`
ncrcat ${files} ${workdir}/${final_filename3d}

if [[ -e ${workdir}/${final_filename} ]];then
        echo "Finished processing cycle ${YYYYMMDD}${cycleHH}"
        exit 0
else
        echo "Did not complete ${model} cycle ${YYYYMMDD}${cycleHH} transfer"
        exit 1
fi
