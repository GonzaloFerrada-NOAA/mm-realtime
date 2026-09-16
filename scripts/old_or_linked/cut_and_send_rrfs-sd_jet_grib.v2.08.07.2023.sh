#!/bin/bash
module load wgrib2
module load nco

set -e
export PS4='+ [$(date "+%Y-%m-%d %H:%M:%S")] ${LINENO}: '
set -x

YYYY=$( date -d "${START_TIME}" +%Y )
MM=$( date -d "${START_TIME}" +%m )
DD=$( date -d "${START_TIME}" +%d )
frame=0${fcsthour} # Needs to be passed as env
YYYYMMDD=${YYYY}${MM}${DD}
model_name="FWx-nest"
frame_filename="frame_${frame}_aqm_${model_name}_${YYYYMMDD}${cycleHH}.nc"

h_thishour=$((10#${frame}))
h_lasthour=$((${h_thishour}-1))

final_filename="aqm_${model_name}_${YYYYMMDD}${cycleHH}.nc"
datadir="/scratch3/BMC/wrfruc/mpas/fire/fwx1.25km/com/rrfs/v2.1.3/rrfs.${YYYY}${MM}${DD}/${cycleHH}/upp"
workdir_base="${MELODIES_MONET_DIR}/model_output/${model_name}"

cd ${workdir_base}
workdir=${workdir_base}/${YYYYMMDD}${cycleHH}
mkdir -p ${workdir}
cd ${workdir}

# Create a directory to keep the surface data that's sent safe from removing


file_natlev=${datadir}/
filename=rrfs.t${cycleHH}z.2dfld.3km.f${frame}.na.grib2


# AOD
wgrib2 -match 'AOTK' -set center 7 ${datadir}/${file_natlev} -netcdf ./${file_natlev}.nc
ncrename -v AOTK_entireatmosphere_consideredasasinglelayer_,AOD550 ./${file_natlev}.nc
# Downward SW
wgrib2 -match 'DSWRF' -set center 7 ${datadir}/${file_natlev} -netcdf ./${file_natlev}_dswrf.nc
# Visibility
wgrib2 -match 'VIS' -set center 7 ${datadir}/${file_natlev} -netcdf ./${file_natlev}_vis.nc
# Ceiling
#wgrib2 -match 'CEIL' -set center 7 ${datadir}/${file_natlev} -netcdf ./${file_natlev}_ceil.nc
wgrib2 -match 'HGT:cloud ceiling' -set center 7 ${datadir}/${file_natlev} -netcdf ./${file_natlev}_ceil.nc
#if [[ -r ${datadir}/${filename2} ]]; then
#   wgrib2 -match 'hour ave fcst:aerosol=Missing:aerosol_size <2.5e-06' -set center 7 ${datadir}/${filename2} -netcdf ./${file_natlev}_pm25.nc
#   ncrename -v MASSDEN_8maboveground,pm25 ./${file_natlev}_pm25.nc
#   ncap2 -O -s 'pm25=1.e9*pm25' ./${file_natlev}_pm25.nc ./${file_natlev}_pm25.nc
#   wgrib2 -match 'hour ave fcst:aerosol=Missing:aerosol_size <1e-05' -set center 7 ${datadir}/${filename2} -netcdf ./${file_natlev}_pm10.nc
#   ncrename -v MASSDEN_8maboveground,pm10 ./${file_natlev}_pm10.nc
#   ncap2 -O -s 'pm10=1.e9*pm10' ./${file_natlev}_pm10.nc ./${file_natlev}_pm10.nc
#else
# fine dust
wgrib2 -nc_nlev 1 -match 'Dust dry:aerosol_size <2.5e-06' -set center 7 ${datadir}/${file_natlev} -netcdf ./${file_natlev}_dust_fine.nc
ncrename -v MASSDEN_8maboveground,dust_fine ${file_natlev}_dust_fine.nc
# coarse dust
wgrib2 -nc_nlev 1 -match 'Dust dry:aerosol_size >=2.5e-06' -set center 7 ${datadir}/${file_natlev} -netcdf ./${file_natlev}_dust_coarse.nc
ncrename -v MASSDEN_8maboveground,dust_coarse ${file_natlev}_dust_coarse.nc
# smoke (fine)
wgrib2 -nc_nlev 1 -match 'organic' -set center 7 ${datadir}/${file_natlev} -netcdf ./${file_natlev}_smoke.nc
ncrename -v MASSDEN_8maboveground,smoke ${file_natlev}_smoke.nc
#fi

# Weather vars
wgrib2 -match ":(UGRD|VGRD):10 m above ground:" -set center 7 ${datadir}/${file_natlev} -netcdf ./${file_natlev}_wind.nc
ncap2 -O -s 'WIND_10maboveground=(UGRD_10maboveground^2.0 + VGRD_10maboveground^2.0)^(0.5)' ./${file_natlev}_wind.nc ./${file_natlev}_wind.nc
wgrib2 -match ":(DPT|TMP):2 m above ground:" -set center 7 ${datadir}/${file_natlev} -netcdf ./${file_natlev}_temp.nc
wgrib2 -match "APCP" -set center 7 ${datadir}/${file_natlev} -netcdf ./${file_natlev}_precip.nc
# Append
ncks -A -v DSWRF_surface ./${file_natlev}_rad.nc ${file_natlev}.nc
ncks -A -v APCP_surface ./${file_natlev}_precip.nc ${file_natlev}.nc
ncks -A -v TMP_2maboveground,DPT_2maboveground ${file_natlev}_temp.nc ${file_natlev}.nc
ncks -A -v UGRD_10maboveground,VGRD_10maboveground,WIND_10maboveground ${file_natlev}_wind.nc ${file_natlev}.nc
ncks -A -v VIS_surface ./${file_natlev}_vis.nc ${file_natlev}.nc
ncks -A -v HGT_cloudceiling ./${file_natlev}_ceil.nc ${file_natlev}.nc
# Append dust vars to smoke file and calculate pm25/pm10
#if [[ -r ${datadir}/${filename2} ]]; then
#   ncks -A -v pm25 ./${file_natlev}_pm25.nc ${file_natlev}.nc
#   ncks -A -v pm10 ./${file_natlev}_pm10.nc ${file_natlev}.nc
#else
ncks -A -v dust_fine ${file_natlev}_dust_fine.nc ${file_natlev}.nc
ncks -A -v dust_coarse ${file_natlev}_dust_coarse.nc ${file_natlev}.nc
ncks -A -v smoke ${file_natlev}_smoke.nc ${file_natlev}.nc
ncap2 -O -s 'dust_fine=1.e9*dust_fine' -s 'dust_coarse=1.e9*dust_coarse' -s 'smoke=1.e9*smoke' ${file_natlev}.nc ${file_natlev}.nc
ncap2 -O -s 'pm25=dust_fine+smoke' ${file_natlev}.nc ${file_natlev}.nc
ncap2 -O -s 'pm10=pm25+dust_coarse' ${file_natlev}.nc ${file_natlev}.nc
#fi
ncap2 -O -s 'VIS_surface=0.000621371*VIS_surface' ${file_natlev}.nc ${file_natlev}.nc
ncap2 -O -s 'where(VIS_surface>10.0) VIS_surface=10.0' ${file_natlev}.nc ${file_natlev}.nc
# Cacluate direction
ncap2 -O -s 'WDIR_10maboveground=180.+(180./3.14159)*atan2(UGRD_10maboveground,VGRD_10maboveground)' ${file_natlev}.nc ${file_natlev}.nc
# Add/(avg and remove) dimensions
ncap2 -O -s 'lat=latitude' -s 'lon=longitude' ${file_natlev}.nc ${file_natlev}.nc
ncwa -O -a hlevel ${file_natlev}.nc ${file_natlev}.nc
ncks -O -x -v hlevel ${file_natlev}.nc ${file_natlev}.nc
ncks -O -x -v AEMFLX_surface,COLMD_entireatmosphere_consideredasasinglelayer_ ${file_natlev}.nc ${file_natlev}.nc
#ncks -O -x -v dust_fine,dust_coarse ${file_natlev}.nc ${file_natlev}.nc
ncap2 -O -s 'TMP_2maboveground=TMP_2maboveground-273.15' -s 'DPT_2maboveground=DPT_2maboveground-273.15' ${file_natlev}.nc ${file_natlev}.nc

rm -f *.grib2
rm -f ${file_natlev}_dust_coarse.nc
rm -f ${file_natlev}_dust_fine.nc
rm -f ${file_natlev}_smoke.nc
rm -f ${file_natlev}_wind.nc
rm -f ${file_natlev}_temp.nc
rm -f ${file_natlev}_precip.nc
rm -f ${file_natlev}_vis.nc
rm -f ${file_natlev}_ceil.nc

mv ${file_natlev}.nc ${frame_filename}



if [[ ${processORcat} -eq 1 ]];then
#if [[ `ls frame* | wc -l` -eq 24 ]]; then
   ncrcat frame_0*nc ${final_filename}
   ln -s ${final_filename} ${final_filename2}
#fi

if [[ -e ${final_filename} ]];then
        echo "Finished processing cycle ${YYYYMMDD}${cycleHH}"
	rm -f frame* rrfs*
        exit 0
else
        echo "Did not complete ${model_name} cycle ${YYYYMMDD}${cycleHH} transfer"
        exit 1
fi

fi
