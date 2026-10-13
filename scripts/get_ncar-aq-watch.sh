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
model="NCAR-AQ-WATCH"
final_filename=aqm_${model}_${YYYYMMDD}${cycleHH}.nc
#
workdir=${MELODIES_MONET_DIR}/model_output/${model}/${YYYYMMDD}${cycleHH}
meiyudir=/wrk/csd4/rahmadov/RAP-Chem/ncar_aqwatch/${YYYYMMDD}${cycleHH}
#
mkdir -p ${workdir}
#
cd ${workdir}
#
scp -o 'ProxyJump jschnell@gate.al.noaa.gov' jschnell@meiyu:${meiyudir}/wrfout\* .
#
cat << EOF >> get_${model}.${START_TIME}${cycleHH}.sh
#!/bin/bash --login
#SBATCH --account=acomp
#SBATCH --partition=u1-compute
#SBATCH --time=03:00:00
#SBATCH -n 1
#SBATCH -q batch
#SBATCH --mem-per-cpu=20G

cd ${workdir}

ncrcat wrfout* ${final_filename}
#
ncap2 -O -s 'T2=T2-273.15' ${final_filename} ${final_filename}
ncap2 -O -s 'lattitude=XLAT' -s 'longitude=XLONG' ${final_filename} ${final_filename}
#
rm -f wrfout*
#
if [[ -e ${final_filename} ]];then
        echo "Finished processing cycle ${YYYYMMDD}${cycleHH}"
        exit 0
else
        echo "Did not complete ${model} cycle ${YYYYMMDD}${cycleHH} transfer"
        exit 1
fi
EOF

sbatch get_${model}.${START_TIME}${cycleHH}.sh

exit 0
