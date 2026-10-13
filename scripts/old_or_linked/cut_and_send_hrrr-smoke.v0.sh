#!/bin/bash
#SBATCH --account=acomp
#SBATCH --partition=u1-service
#SBATCH --time=08:30:00
#SBATCH -q batch
#SBATCH -n 1 

set -x
module load hpss

YYYY=`date +%Y -d "${START_TIME}"`
YY=`date +%y -d "${START_TIME}"`
MM=`date +%m -d "${START_TIME}"`
DD=`date +%d -d "${START_TIME}"`
YYYYMMDD=${YYYY}${MM}${DD}

model="HRRR-Smoke"
final_filename=aqm_${model}_${YYYY}${MM}${DD}${cycleHH}.nc

echo "Getting NAQFC operational forecast data for the ${cycleHH}z cycle on ${YYYYMMDD}"

basedatadir=/BMC/fdr/Permanent/
datadir=${basedatadir}/${YYYY}/${MM}/${DD}/grib/hrrr_wrfsfc/7/0/83/0_1905141_30/
echo "Location of data on HPSS: ${datadir}"

workdir_base=${MELODIES_MONET_DIR}/model_output/${model}

meiyudir=/wrk/csd4/rahmadov/RAP-Chem/hrrr_smoke/${YYYYMMDD}${cycleHH}

cd ${workdir_base}
workdir=${workdir_base}/${YYYYMMDD}${cycleHH}
echo "Downloading to JET:${workdir}"
mkdir -p ${workdir}
cd ${workdir}

filename=${YYYY}${MM}${DD}${cycleHH}00.zip
# Grab the file
echo "Attepting to retrieve file: ${datadir}/${filename}"
hsi get -N ${datadir}/${filename}

### REST OF SCRIPT NEEDS TO BE DONE ON A COMPUTE NODE

cat << EOF >> get_${model}.${START_TIME}${cycleHH}.sh
#!/bin/bash --login
#SBATCH --account=acomp
#SBATCH --partition=u1-compute
#SBATCH --time=05:00:00
#SBATCH -n 1
#SBATCH -q batch
#SBATCH --mem-per-cpu=20G

module load wgrib2
module load nco

cd ${workdir}
# Unzip it
unzip ${filename}
# convert the files to grib2 and cut out just the smoke data and rename to PM2_5_DRY
for file in ${YY}*; do
EOF
cat << "EOF" >> get_${model}.${START_TIME}${cycleHH}.sh
wgrib2 -set center 7 ${file} -netcdf ${file}.nc
ncks -v DSWRF_surface,HGT_cloudceiling,DPT_2maboveground,UGRD_10maboveground,VGRD_10maboveground,WIND_10maboveground,VIS_surface,TMP_2maboveground,APCP_surface,MASSDEN_8maboveground,AOTK_entireatmosphere_consideredasasinglelayer_ ${file}.nc ${file}.smoke.nc
ncrename -v MASSDEN_8maboveground,PM2_5_DRY -v AOTK_entireatmosphere_consideredasasinglelayer_,AOD_550 ${file}.smoke.nc
ncap2 -O -s 'PM2_5_DRY=1.0e9*PM2_5_DRY' ${file}.smoke.nc ${file}.smoke.nc
ncap2 -O -s 'VIS_surface=0.000621371*VIS_surface' ${file}.smoke.nc ${file}.smoke.nc
ncap2 -O -s 'where(VIS_surface>10.0) VIS_surface=10.0' ${file}.smoke.nc ${file}.smoke.nc
ncap2 -O -s 'WDIR_10maboveground=180.+(180./3.14159)*atan2(UGRD_10maboveground,VGRD_10maboveground)' ${file}.smoke.nc ${file}.smoke.nc
ncap2 -O -s 'DPT_2maboveground=DPT_2maboveground-273.15' -s 'TMP_2maboveground=TMP_2maboveground-273.15' ${file}.smoke.nc ${file}.smoke.nc
rm -f ${file}
done
EOF
cat << EOF >> get_${model}.${START_TIME}${cycleHH}.sh
ncrcat *smoke.nc smoke.all.${YYYY}${MM}${DD}.nc

# Move it
mv smoke.all.${YYYY}${MM}${DD}.nc ${final_filename}

#mkdir -p ${linkdir}
#cd ${linkdir}
#ln -s ${workdir}/${final_filename} .
cd ${workdir}

echo "Getting rid non-saved files"
# Remove everything else
rm -f *.smoke.nc
rm -f ${YY}*.nc
rm -f *.zip 

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
