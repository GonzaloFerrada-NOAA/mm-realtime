#!/bin/bash
#SBATCH --account=acomp
#SBATCH --partition=u1-service
#SBATCH --time=03:30:00
#SBATCH -q batch
#SBATCH -n 1 

module load hpss
#module load wgrib2

YYYY=`date +%Y -d "${START_TIME}"`
YY=`date +%y -d "${START_TIME}"`
MM=`date +%m -d "${START_TIME}"`
DD=`date +%d -d "${START_TIME}"`
YYYYMMDD=${YYYY}${MM}${DD}
model="GEFS-Aerosols"
final_filename=aqm_${model}_${YYYY}${MM}${DD}${cycleHH}.nc

echo "Getting GEFS-Aerosols forecast data for the ${cycleHH}z cycle on ${YYYYMMDD}"

basedatadir=/NCEPPROD/hpssprod/runhistory/
datadir=${basedatadir}/rh${YYYY}/${YYYY}${MM}/${YYYY}${MM}${DD}/
echo "Location of data on HPSS: ${datadir}"

workdir_base=${MELODIES_MONET_DIR}/model_output/${model}
meiyudir=/wrk/csd4/rahmadov/RAP-Chem/gefs_aero/${YYYYMMDD}${cycleHH}

cd ${workdir_base}
workdir=${workdir_base}/${YYYYMMDD}${cycleHH}
echo "Downloading to JET:${workdir}"
mkdir -p ${workdir}
cd ${workdir}

filename=com_gefs_v12.3_gefs.${YYYY}${MM}${DD}_${cycleHH}.chem_pgrb2ap25.tar 
echo "Attepting to retrieve file: ${datadir}/${filename}"
htar -xf ${datadir}/${filename}

cat << EOF >> get_${model}.${START_TIME}${cycleHH}.sh
#!/bin/bash --login
#SBATCH --account=acomp
#SBATCH --partition=u1-compute
#SBATCH --time=03:00:00
#SBATCH -n 1
#SBATCH -q batch
#SBATCH --mem-per-cpu=20G

module load wgrib2
module load nco

cd ${workdir}
YYYY=${YYYY}
MM=${MM}
DD=${DD}
cycleHH=${cycleHH}

mv chem/pgrb2ap25/* .
rm -f *.idx
for file in *.grib2; do
EOF
cat << "EOF" >> get_${model}.${START_TIME}${cycleHH}.sh
wgrib2 -set center 7 ${file} -netcdf ${file}.nc
ncrename -v PMTF_surface,PM2_5_DRY -v PMTC_surface,PM10 -v AOTK_entireatmosphere,AOD550 ${file}.nc
ncks -O -d latitude,450,600 -d longitude,900,1250 ${file}.nc ${file}.nc
rm -f ${file}
done
ncrcat *.nc combined.${YYYY}${MM}${DD}.nc
#
timelength=`ncap2 -v -O -s 'print(time.size(),"%ld\n");' combined.${YYYY}${MM}${DD}.nc foo.nc`
rm -f foo.nc
nhours=$(((${timelength}-1)*3))
EOF
cat << EOF >> get_${model}.${START_TIME}${cycleHH}.sh
# Move it
mv combined.${YYYY}${MM}${DD}.nc ${final_filename}

echo "Getting rid non-saved files"
# Remove everything else
EOF
cat << "EOF" >> get_${model}.${START_TIME}${cycleHH}.sh
rm -f ${file}.nc *.grib2 *.grib2.nc *.tar
EOF
cat << EOF >> get_${model}.${START_TIME}${cycleHH}.sh
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
