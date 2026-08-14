#!/bin/bash -l
#SBATCH --account=acomp
#SBATCH --partition=u1-compute
#SBATCH --time=07:30:00
#SBATCH -q batch
#SBATCH -n 1
#SBATCH --mem-per-cpu=20G 
module load nco
#
YYYY=`date +%Y -d "${START_TIME}"`
MM=`date +%m -d "${START_TIME}"`
DD=`date +%d -d "${START_TIME}"`
YYYY1=`date +%Y -d "${START_TIME} + 1 day"`
MM1=`date +%m -d "${START_TIME} + 1 day"`
DD1=`date +%d -d "${START_TIME} + 1 day"`
YYYYMMDD=${YYYY}${MM}${DD}
model="RAQMS"
final_filename=aqm_${model}_${YYYYMMDD}${cycleHH}.nc
#
jetdir=/public/data/grids/ssec/raqms/${YYYYMMDD}/
workdir=${MELODIES_MONET_DIR}/model_output/${model}/${YYYYMMDD}${cycleHH}
#
mkdir -p ${workdir}
#
cd ${workdir}
rm -f *
#
cp ${jetdir}/uwhyb_${MM}_${DD}_${YYYY}*.chem.assim.nc .
cp ${jetdir}/uwhyb_${MM1}_${DD1}_${YYYY1}*.chem.assim.nc .
for file in *; do 
ncks -O -d lev,34,34 -v o3vmr,ico,ino2,iso2,aod,ibc1,ibc2,idu1,idu2,idu3,idu4,idu5,inh4aer,ino3aer,ioc1,ioc2,iso4aer,iss1,iss2,iss3,iss4,iss5,thsfc,psfc,Times ${file} ${file}
ncap2 -O -s 'tsfc=thsfc/((1000./psfc)^(2./7.))' ${file} ${file}
ncap2 -O -s 'rho=(1./287.)*psfc/tsfc' ${file} ${file}
ncap2 -O -s 'pm25=rho*1.e9*(ibc1+ibc2+idu1+idu2+inh4aer+ino3aer+ioc1+ioc2+iso4aer+iss1+iss2)' ${file} ${file}
ncap2 -O -s 'pm10=pm25+rho*1.e9*(idu3+idu3+idu5+iss3+iss4+iss5)' ${file} ${file}
ncap2 -O -s 'ino2=1000.0*ino2' -s 'ico=1000.0*ico' -s 'o3vmr=1000.*o3vmr' ${file} ${file}
ncks -O --mk_rec_dmn time ${file} ${file}
done
ncrcat * ${final_filename}
#
if [[ -e ${final_filename} ]];then
        echo "Finished processing cycle ${YYYYMMDD}${cycleHH}"
        exit 0
else
        echo "Did not complete ${model} cycle ${YYYYMMDD}${cycleHH} transfer"
        exit 1
fi
