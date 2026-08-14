#!/bin/bash -l
#SBATCH --account=acomp
#SBATCH --partition=u1-compute
#SBATCH --time=00:59:00
#SBATCH -q batch
#SBATCH -n 1 

module load wgrib2
module load nco
module load ncl

YYYY=`date +%Y -d "${START_TIME}"`
YY=`date +%y -d "${START_TIME}"`
MM=`date +%m -d "${START_TIME}"`
DD=`date +%d -d "${START_TIME}"`
JJ=`date +%j -d "${START_TIME}"`
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
mkdir -p ${workdir}
cd ${workdir}

filename=${YYYY}${MM}${DD}${cycleHH}00.zip
unzip ${filename}
rm -f ${filename}
knt=0
for file in ${YY}*
do
# Cut out a single variable to get the time dimensions
wgrib2 -match ':(AOTK):' -set center 7 ${file} -netcdf ${file}_time.nc
# Convert to nc likes grib2 extensions
mv ${file} ${file}.grib2
ncl_convert2nc ${file}.grib2 -L -ftime -u forecast_time0 -U time
if [[ ${knt} -le 1 ]]; then

ncks -v HGT_P0_L215_GRLL0,DPT_P0_L103_GRLL0,MASSDEN_P0_L103_GRLL0,UGRD_P0_L103_GRLL0,VGRD_P0_L103_GRLL0,APCP_P8_L1_GRLL0_acc,ACPCP_P8_L1_GRLL0_acc,TMP_P0_L103_GRLL0,AOTK_P0_L200_GRLL0,VIS_P0_L1_GRLL0,time ${file}.nc ${file}.smoke.nc
ncrename -v HGT_P0_L215_GRLL0,HGT_cloudceiling -v DPT_P0_L103_GRLL0,DPT_2maboveground -v MASSDEN_P0_L103_GRLL0,PM2_5_DRY -v UGRD_P0_L103_GRLL0,UGRD_10maboveground -v VGRD_P0_L103_GRLL0,VGRD_10maboveground -v APCP_P8_L1_GRLL0_acc,APCP_surface -v ACPCP_P8_L1_GRLL0_acc,ACPCP_surface -v TMP_P0_L103_GRLL0,T2 -v AOTK_P0_L200_GRLL0,AOD_550 -v VIS_P0_L1_GRLL0,VIS_surface ${file}.smoke.nc

else

ncks -v HGT_P0_L215_GRLL0,DPT_P0_L103_GRLL0,MASSDEN_P0_L103_GRLL0,UGRD_P0_L103_GRLL0,VGRD_P0_L103_GRLL0,APCP_P8_L1_GRLL0_acc1h,ACPCP_P8_L1_GRLL0_acc1h,TMP_P0_L103_GRLL0,AOTK_P0_L200_GRLL0,VIS_P0_L1_GRLL0,time ${file}.nc ${file}.smoke.nc
ncrename -v HGT_P0_L215_GRLL0,HGT_cloudceiling -v DPT_P0_L103_GRLL0,DPT_2maboveground -v MASSDEN_P0_L103_GRLL0,PM2_5_DRY -v UGRD_P0_L103_GRLL0,UGRD_10maboveground -v VGRD_P0_L103_GRLL0,VGRD_10maboveground -v APCP_P8_L1_GRLL0_acc1h,APCP_surface -v ACPCP_P8_L1_GRLL0_acc1h,ACPCP_surface -v TMP_P0_L103_GRLL0,T2 -v AOTK_P0_L200_GRLL0,AOD_550 -v VIS_P0_L1_GRLL0,VIS_surface ${file}.smoke.nc

fi
knt=$(($knt+1))

ncap2 -O -s 'time=double(time)' ${file}.smoke.nc ${file}.smoke.nc
ncks -A -v time ${file}_time.nc ${file}.smoke.nc
ncap2 -O -s 'PRECIP=APCP_surface+ACPCP_surface' ${file}.smoke.nc ${file}.smoke.nc
ncap2 -O -s 'VIS_surface=0.000621371*VIS_surface' ${file}.smoke.nc ${file}.smoke.nc
ncap2 -O -s 'where(VIS_surface>10.0) VIS_surface=10.0' ${file}.smoke.nc ${file}.smoke.nc
ncap2 -O -s 'PM2_5_DRY=1.0e9*PM2_5_DRY' ${file}.smoke.nc ${file}.smoke.nc
ncap2 -O -s 'WIND_10maboveground=(UGRD_10maboveground^2+VGRD_10maboveground^2)^0.5' ${file}.smoke.nc ${file}.smoke.nc
ncap2 -O -s 'T2=T2-273.15' ${file}.smoke.nc ${file}.smoke.nc
ncap2 -O -s 'DPT_2maboveground=DPT_2maboveground-273.15' ${file}.smoke.nc ${file}.smoke.nc
ncap2 -O -s 'WDIR_10maboveground=180.+(180./3.14159)*atan2(UGRD_10maboveground,VGRD_10maboveground)' ${file}.smoke.nc ${file}.smoke.nc
rm -f ${file}.nc
rm -f ${file}.grib2
rm -f ${file}_time.nc

done

ncrcat *smoke.nc smoke.all.${YYYY}${MM}${DD}.nc

mv smoke.all.${YYYY}${MM}${DD}.nc ${final_filename}
ncrename -d ygrid_0,y -d xgrid_0,x ${final_filename}
ncks -A -v x,y ../rap-smoke.xy.nc ${final_filename}
ncap2 -O -s 'longitude=gridlon_0' -s 'latitude=gridlat_0' ${final_filename} ${final_filename}

echo "Getting rid non-saved files"
# Remove everything else
rm -f *smoke.nc
#rm -f *.zip

if [[ -e ${final_filename} ]];then
        echo "Finished processing cycle ${YYYYMMDD}${cycleHH}"
        exit 0
else
        echo "Did not complete ${model} cycle ${YYYYMMDD}${cycleHH} transfer"
        exit 1
fi

exit 0
