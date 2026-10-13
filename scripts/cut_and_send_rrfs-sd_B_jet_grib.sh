#!/bin/bash --login
#SBATCH --account=acomp
#SBATCH --partition=u1-compute
#SBATCH --time=2:00:00
#SBATCH -q batch
#SBATCH -n 1 
#SBATCH --mem-per-cpu=20G

module load wgrib2
module load nco

set -x
YYYY=`date +%Y -d "${START_TIME} + 24 hours"`
MM=`date +%m -d "${START_TIME} + 24 hours"`
DD=`date +%d -d "${START_TIME} + 24 hours"`
frame=0${fcsthour}
YYYYMMDD=${YYYY}${MM}${DD}
model="RRFS-SD_B"
model2="RRFS-B"
frame_filename=frame_${frame}_aqm_${model}_${YYYYMMDD}${cycleHH}.nc


h_thishour=$((10#${frame}))
h_lasthour=$((${h_thishour}-1))

final_filename=aqm_${model}_${YYYYMMDD}${cycleHH}.nc
final_filename2=aqm_${model2}_${YYYYMMDD}${cycleHH}.nc
echo "Getting RRFS-SD_B forecast data for the ${cycleHH}z cycle on ${YYYYMMDD}"
basedatadir=/mnt/lfs5/BMC/nrtrr/NCO_dirs/v0.9.5/stmp/
datadir=${basedatadir}/${YYYY}${MM}${DD}${cycleHH}/postprd
echo "Location of data on JET: ${datadir}"

workdir_base=${MELODIES_MONET_DIR}/model_output/RRFS-SD_B

cd ${workdir_base}
workdir=${workdir_base}/${YYYYMMDD}${cycleHH}
mkdir -p ${workdir}
cd ${workdir}
# Create a directory to keep the surface data that's sent safe from removing

if [[ ${processORcat} -eq 0 ]];then

filename=rrfs.t${cycleHH}z.prslev.f${frame}.grib2

# AOD
wgrib2 -match 'AOTK' -set center 7 ${datadir}/${filename} -netcdf ./${filename}.nc
ncrename -v AOTK_entireatmosphere_consideredasasinglelayer_,AOD550 ./${filename}.nc
# Visibility
wgrib2 -match 'VIS' -set center 7 ${datadir}/${filename} -netcdf ./${filename}_vis.nc
# Ceiling
#wgrib2 -match 'CEIL' -set center 7 ${datadir}/${filename} -netcdf ./${filename}_ceil.nc
wgrib2 -match 'HGT:cloud ceiling' -set center 7 ${datadir}/${filename} -netcdf ./${filename}_ceil.nc
# fine dust
wgrib2 -nc_nlev 1 -match 'Dust dry:aerosol_size <2.5e-06' -set center 7 ${datadir}/${filename} -netcdf ./${filename}_dust_fine.nc
ncrename -v MASSDEN_8maboveground,dust_fine ${filename}_dust_fine.nc
# coarse dust
wgrib2 -nc_nlev 1 -match 'Dust dry:aerosol_size >=2.5e-06' -set center 7 ${datadir}/${filename} -netcdf ./${filename}_dust_coarse.nc
ncrename -v MASSDEN_8maboveground,dust_coarse ${filename}_dust_coarse.nc
# smoke (fine)
wgrib2 -nc_nlev 1 -match 'organic' -set center 7 ${datadir}/${filename} -netcdf ./${filename}_smoke.nc
ncrename -v MASSDEN_8maboveground,smoke ${filename}_smoke.nc
# Weather vars
wgrib2 -match ":(UGRD|VGRD):10 m above ground:" -set center 7 ${datadir}/${filename} -netcdf ./${filename}_wind.nc
ncap2 -O -s 'WIND_10maboveground=(UGRD_10maboveground^2.0 + VGRD_10maboveground^2.0)^(0.5)' ./${filename}_wind.nc ./${filename}_wind.nc
wgrib2 -match ":(DPT|TMP):2 m above ground:" -set center 7 ${datadir}/${filename} -netcdf ./${filename}_temp.nc
wgrib2 -match ":(APCP):surface:${h_lasthour}-${h_thishour}" -set center 7 ${datadir}/${filename} -netcdf ./${filename}_precip.nc
# Append
ncks -A -v APCP_surface ./${filename}_precip.nc ${filename}.nc
ncks -A -v TMP_2maboveground,DPT_2maboveground ${filename}_temp.nc ${filename}.nc
ncks -A -v UGRD_10maboveground,VGRD_10maboveground,WIND_10maboveground ${filename}_wind.nc ${filename}.nc
ncks -A -v VIS_surface ./${filename}_vis.nc ${filename}.nc
ncks -A -v HGT_cloudceiling ./${filename}_ceil.nc ${filename}.nc
# Append dust vars to smoke file and calculate pm25/pm10
ncks -A -v dust_fine ${filename}_dust_fine.nc ${filename}.nc
ncks -A -v dust_coarse ${filename}_dust_coarse.nc ${filename}.nc
ncks -A -v smoke ${filename}_smoke.nc ${filename}.nc
ncap2 -O -s 'dust_fine=1.e9*dust_fine' -s 'dust_coarse=1.e9*dust_coarse' -s 'smoke=1.e9*smoke' ${filename}.nc ${filename}.nc
ncap2 -O -s 'pm25=dust_fine+smoke' ${filename}.nc ${filename}.nc
ncap2 -O -s 'pm10=pm25+dust_coarse' ${filename}.nc ${filename}.nc
ncap2 -O -s 'VIS_surface=0.000621371*VIS_surface' ${filename}.nc ${filename}.nc
ncap2 -O -s 'where(VIS_surface>10.0) VIS_surface=10.0' ${filename}.nc ${filename}.nc
# Cacluate direction
ncap2 -O -s 'WDIR_10maboveground=180.+(180./3.14159)*atan2(UGRD_10maboveground,VGRD_10maboveground)' ${filename}.nc ${filename}.nc
# Add/(avg and remove) dimensions
ncap2 -O -s 'lat=latitude' -s 'lon=longitude' ${filename}.nc ${filename}.nc
ncwa -O -a hlevel ${filename}.nc ${filename}.nc
ncks -O -x -v hlevel ${filename}.nc ${filename}.nc
ncks -O -x -v AEMFLX_surface,COLMD_entireatmosphere_consideredasasinglelayer_ ${filename}.nc ${filename}.nc
#ncks -O -x -v dust_fine,dust_coarse ${filename}.nc ${filename}.nc
ncap2 -O -s 'TMP_2maboveground=TMP_2maboveground-273.15' -s 'DPT_2maboveground=DPT_2maboveground-273.15' ${filename}.nc ${filename}.nc

echo "Sending only the surface files to ${meiyudir} and saving to ${workdir}/save"

rm -f *.grib2
rm -f ${filename}_dust_coarse.nc
rm -f ${filename}_dust_fine.nc
rm -f ${filename}_smoke.nc
rm -f ${filename}_wind.nc
rm -f ${filename}_temp.nc
rm -f ${filename}_precip.nc
rm -f ${filename}_vis.nc
rm -f ${filename}_ceil.nc

mv ${filename}.nc ${frame_filename}

fi

if [[ ${processORcat} -eq 1 ]];then
#if [[ `ls frame* | wc -l` -eq 24 ]]; then
   ncrcat frame_0{01..24}* ${final_filename}
   ln -s  ${final_filename}  ${final_filename2}
#fi

if [[ -e ${final_filename} ]];then
        echo "Finished processing cycle ${YYYYMMDD}${cycleHH}"
	rm -f frame* rrfs*
        exit 0
else
        echo "Did not complete ${model} cycle ${YYYYMMDD}${cycleHH} transfer"
        exit 1
fi

fi
