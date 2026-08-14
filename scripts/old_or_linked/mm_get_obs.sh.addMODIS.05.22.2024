#!/bin/bash
#
module load rdhpcs-conda
conda activate /scratch4/BMC/acomp/cheMPAS-Fire/envs/melodies-monet-nrt-vx
module load nco
module load ncl 
set -x
#
DATE=/bin/date
#
#Set up the date strings
todays_date=`${DATE} +%Y%m%d -d ${START_TIME}`
jtoday=`${DATE} +%j -d ${START_TIME}`
YYtoday=`${DATE} +%y -d ${START_TIME}`

# Tomorrow variables 
YYYY_tomorrow=`${DATE} +%Y -d "${todays_date} + 24 hours"` # with activation_offset = -24, this brings us to the current time
MM_tomorrow=`${DATE} +%m -d "${todays_date} + 24 hours"`
DD_tomorrow=`${DATE} +%d -d "${todays_date} + 24 hours"`
HH_tomorrow=`${DATE} +%H -d "${todays_date} + 24 hours"`

# Two-day variables 
YYYY_twodays=`${DATE} +%Y -d "${todays_date} + 48 hours"` # with activation_offset = -24, this brings us to the current time
MM_twodays=`${DATE} +%m -d "${todays_date} + 48 hours"`
DD_twodays=`${DATE} +%d -d "${todays_date} + 48 hours"`
HH_twodays=`${DATE} +%H -d "${todays_date} + 48 hours"`

# Three-day variables 
YYYY_threedays=`${DATE} +%Y -d "${todays_date} + 72 hours"` # with activation_offset = -24, this brings us to the current time
MM_threedays=`${DATE} +%m -d "${todays_date} + 72 hours"`
DD_threedays=`${DATE} +%d -d "${todays_date} + 72 hours"`
HH_threedays=`${DATE} +%H -d "${todays_date} + 72 hours"`

# Four-day variables 
YYYY_fourdays=`${DATE} +%Y -d "${todays_date} + 96 hours"` # with activation_offset = -24, this brings us to the current time
MM_fourdays=`${DATE} +%m -d "${todays_date} + 96 hours"`
DD_fourdays=`${DATE} +%d -d "${todays_date} + 96 hours"`
HH_fourdays=`${DATE} +%H -d "${todays_date} + 96 hours"`

# Today variables 
YYYY_today=`${DATE} +%Y -d "${todays_date}"` # with activation_offset = -24, this brings us to the current time
MM_today=`${DATE} +%m -d "${todays_date}"`
DD_today=`${DATE} +%d -d "${todays_date}"`
HH_today=`${DATE} +%H -d "${todays_date}"`

# Yesterday Variables
YYYY_ytday=`${DATE} +%Y -d "${todays_date} - 24 hours"` # with activation_offset = -24, this is 48 hours before the current time 
MM_ytday=`${DATE} +%m -d "${todays_date} - 24 hours"`
DD_ytday=`${DATE} +%d -d "${todays_date} - 24 hours"`

# Dates also need to be for yesterday
start_time_reformat=`${DATE} -d "${YYYY_ytday}${MM_ytday}${DD_ytday}" +%Y-%m-%d`
start_time_reformat2=`${DATE} -d "${YYYY_today}${MM_today}${DD_today}" +%Y-%m-%d`
end_time_reformat=`${DATE} -d "${YYYY_tomorrow}${MM_tomorrow}${DD_tomorrow}" +%Y-%m-%d`
end_time_reformat_openaq=`${DATE} -d "${YYYY_today}${MM_today}${DD_today} + 23 hours" "+%Y-%m-%d %H:00"`
end_time_reformat_openaq2=`${DATE} -d "${YYYY_ytday}${MM_ytday}${DD_ytday} + 23 hours" "+%Y-%m-%d %H:00"`

scriptsdir=${SCRIPTS_DIR}
workdir=${WORKDIR}
mkdir -p ${workdir}
cd ${workdir}

#--------------------------------------------------
# --------------  SURFRAD  --------------------------
#--------------------------------------------------
if [[ "${OBSTYPE}" == "surfrad" ]]; then
baseurl=https://gml.noaa.gov/aftp/data/radiation/surfrad/realtime/
declare -a sites=("bon" "dra" "fpk" "gwn" "psu" "red" "rut" "slv" "sxf" "tbl" "was")
for isite in "${sites[@]}"
do
#https://gml.noaa.gov/aftp/data/radiation/surfrad/realtime/bon/bon25192.dat
subdir=${isite}
filename=${isite}${YYtoday}${jtoday}.dat
rm -f ${filename}*
wget ${baseurl}/${subdir}/${filename}
done
fi

#--------------------------------------------------
# --------------  AERONET  --------------------------
#--------------------------------------------------
if [[ "${OBSTYPE}" == "aeronet" ]]; then
todays_file="AERONET_L15_${YYYY_ytday}${MM_ytday}${DD_ytday}_${YYYY_tomorrow}${MM_tomorrow}${DD_tomorrow}.nc"
rm -f ${todays_file}
melodies-monet get-aeronet -s ${start_time_reformat} -e ${end_time_reformat} -n 12 --interp-to 0.55 --debug --verbose --no-compress
if [[ -r ${todays_file} ]]; then
  mv ${todays_file} test5.aeronet.${todays_date}.nc
  cp ${scriptsdir}/make_westoreastof97_aeronet.ncl .
  ncl make_westoreastof97_aeronet.ncl
else
  echo "test5.nc is missing for aeronet!"
  exit 1
fi
exit 0
fi

#--------------------------------------------------
# --------------  AIRNOW  --------------------------
#--------------------------------------------------
if [[ "${OBSTYPE}" == "airnow" ]]; then
todays_file="AirNow_${YYYY_ytday}${MM_ytday}${DD_ytday}_${YYYY_tomorrow}${MM_tomorrow}${DD_tomorrow}.nc"
rm -f ${todays_file}
melodies-monet get-airnow -s ${start_time_reformat} -e ${end_time_reformat} -n 12 --debug --verbose --no-compress
if [[ -r ${todays_file} ]]; then
  mv ${todays_file} test5.airnow.${todays_date}.nc   #moving the test5.nc generated from reformat to test5.nc.{todays_date}
  cp ${scriptsdir}/make_westoreastof97_airnow.ncl .
  ncl make_westoreastof97_airnow.ncl
# Create baseline removal file
  baselinesrcpath=${MELODIES_MONET_DIR}/src/MM_Huiying_BaselineRemoval/
  locsetpath=${baselinesrcpath}/airnow_sites_epalist_20240716.csv
  basefname=${baselinesrcpath}/IODA_hourlyPM25baseline_v2r1.nc
  python ${scriptsdir}/MONETobs_debkg_v2.py ${workdir}/test5.airnow.${todays_date}.nc ${locsetpath} ${basefname}
  module load nco
#  ncrename -v PM2.5,PM2.5_BLremoved test5.airnow.${todays_date}_PM25blremoved_.nc
#  ncks -A -v PM2.5_BLremoved test5.airnow.${todays_date}_PM25blremoved_.nc ${workdir}/test5.airnow.${todays_date}.nc 
else
  echo "test5.nc is missing for airnow!"
  exit 1
fi
#
if [[ -e cur_aqi_ozone.kml ]]; then
   mv cur_aqi_ozone.kml cur_aqi_ozone.${todays_date}.kml
   source ${scriptsdir}/mm_split_aqi_files.sh ${todays_date} ${workdir} ozone
else
  echo "Did not download ozone AQI data!"
fi
if [[ -e cur_aqi_pm25.kml ]]; then
   mv cur_aqi_pm25.kml cur_aqi_pm25.${todays_date}.kml
   source ${scriptsdir}/mm_split_aqi_files.sh ${todays_date} ${workdir} pm25
else
  echo "Did not download PM.25 AQI data!"
fi
if [[ -e cur_aqi_combined.kml ]]; then
   mv cur_aqi_combined.kml cur_aqi_combined.${todays_date}.kml
   source ${scriptsdir}/mm_split_aqi_files.sh ${todays_date} ${workdir} combined
else
  echo "Did not download combined AQI data!"
fi
#
exit 0
fi

#--------------------------------------------------
# -------------ISH-LITE --------------------------
#--------------------------------------------------
if [[ "${OBSTYPE}" == "ish-lite" ]]; then
rm -f test5.ish-lite*.nc
melodies-monet get-ish-lite -s ${start_time_reformat} -e ${end_time_reformat} -n 12 --box 0 -179 90 -50 --debug --verbose --no-compress
if [[ -e ISH-Lite_${YYYY_ytday}${MM_ytday}${DD_ytday}_${YYYY_tomorrow}${MM_tomorrow}${DD_tomorrow}.nc ]]; then
   echo "obs file created for ISH-Lite"
   echo "moving ISH-Lite_${YYYY_ytday}${MM_ytday}${DD_ytday}_${YYYY_tomorrow}${MM_tomorrow}${DD_tomorrow}.nc to test5.ish.${todays_date}.nc"
   mv ISH-Lite_${YYYY_ytday}${MM_ytday}${DD_ytday}_${YYYY_tomorrow}${MM_tomorrow}${DD_tomorrow}.nc test5.ish-lite.${todays_date}.nc
   cp ${scriptsdir}/make_westoreastof97_ish-lite.ncl .
   ncl make_westoreastof97_ish-lite.ncl
else
   echo "test5 is missing for ISH-Lite!"
   exit 1
fi
exit 0
fi
#
#
#--------------------------------------------------
# --------------  ISH (visibility, cloud ceilin)  -
#--------------------------------------------------
if [[ "${OBSTYPE}" == "ish" ]]; then
rm -f test5.ish.*.nc
melodies-monet get-ish -s ${start_time_reformat} -e ${end_time_reformat} --box 0 -179 90 -50 -n 12 --no-compress --verbose --debug
if [[ -e ISH_${YYYY_ytday}${MM_ytday}${DD_ytday}_${YYYY_tomorrow}${MM_tomorrow}${DD_tomorrow}.nc ]]; then
   echo "obs file created for ISH/ISD"
   echo "moving ISH_${YYYY_ytday}${MM_ytday}${DD_ytday}_${YYYY_tomorrow}${MM_tomorrow}${DD_tomorrow}.nc to test5.ish.${todays_date}.nc"
   mv ISH_${YYYY_ytday}${MM_ytday}${DD_ytday}_${YYYY_tomorrow}${MM_tomorrow}${DD_tomorrow}.nc test5.ish.${todays_date}.nc
   cp ${scriptsdir}/make_westoreastof97_ish.ncl .
   ncl make_westoreastof97_ish.ncl
else
   echo "test5 is missing for ISH!"
   exit 1
fi
exit 0
fi

#--------------------------------------------------V
# --------------  OPEN-AQ --------------------------
#--------------------------------------------------
if [[ "${OBSTYPE}" == "openaq" ]]; then
  rm -f test5.openaq.*.nc
  export MM_LOGGING_LEVEL=debug
#  export OPENAQ_API_KEY=dff4aa0d178fdb763b65d72ed81f21da28de5907a9a2f74bd7bbf85d2cbeb98d   # noaa
  export OPENAQ_API_KEY=2ddf96ae51ef9ba9ce53832092be4a171cdc9f9c43877e82ed3a613acf1d44d7    # gmail
  #melodies-monet get-openaq -s "'${start_time_reformat}'" -e "'${end_time_reformat_openaq}'"  --params o3 --params pm25 --params pm10 --params co --params no2 --verbose --debug -n 4 --low-cost --no-reference-grade
#  melodies-monet get-openaq -s "'${start_time_reformat}'" -e "'${end_time_reformat_openaq}'"  --params o3 --params pm25 --params pm10 --params co --params no2 --verbose --debug -n 4 --params bbox=-140.0,-45.0.0,0,89.0
   melodies-monet get-openaq -s ${start_time_reformat} -e ${start_time_reformat2}  --params pm25 -c US --low-cost --verbose --debug

  if [[ -e OpenAQ_${YYYY_ytday}${MM_ytday}${DD_ytday}_${YYYY_today}${MM_today}${DD_today}.nc ]]; then
     echo "obs file created for OPEN-AQ"
     mv OpenAQ_${YYYY_ytday}${MM_ytday}${DD_ytday}_${YYYY_today}${MM_today}${DD_today}.nc test5.openaq.${todays_date}.nc
     cp ${scriptsdir}/make_westoreastof97_openaq.ncl .
     ncl make_westoreastof97_openaq.ncl
#     ncrename -v o3,OZONE -v pm25,PM2.5 -v no2,NO2 -v co,CO -v pm10,PM10 test5.openaq.${todays_date}.nc 
     ncrename -v pm25,PM2.5 test5.openaq.${todays_date}.nc 
  else
     echo "test5 is missing for openaq"
     exit 1
  fi
exit 0
fi

#--------------------------------------------------
# --------------  HMS FIRE/SMOKE  ----------------
#--------------------------------------------------
if [[ "${OBSTYPE}" == "hms" ]]; then
## Get the HMS smoke polygons and fire locations
if [[ -e ${HMS_DATADIR}/hms_fire/text/hms_fire${YYYY_today}${MM_today}${DD_today}.txt ]] ;then
   echo "Found HMS fire locations"
   cp ${HMS_DATADIR}/hms_fire/text/hms_fire${YYYY_today}${MM_today}${DD_today}.txt hms_fire_${todays_date}.txt
else
   echo "HMS Fire locations are unavailable"
fi
if [[ -e ${HMS_DATADIR}/hms_smoke/kml/hms_smoke${YYYY_today}${MM_today}${DD_today}.kml ]]; then
   echo "Found HMS smoke shapefiles"
   cp ${HMS_DATADIR}/hms_smoke/kml/hms_smoke${YYYY_today}${MM_today}${DD_today}.kml hms_smoke_${todays_date}.kml
   source ${scriptsdir}/mm_split_aqi_files.sh ${todays_date} ${workdir} smoke
else
   echo "HMS Smoke Shapefiles are unavailable"
fi
fi

#--------------------------------------------------
# -------------- MODIS --------------------------
#--------------------------------------------------
if [[ "${OBSTYPE}" == "MODIS_AQUA" ]]; then
  hsi get -N /BMC/fdr/Permanent/${YYYY_ytday}/${MM_ytday}/${DD_ytday}/data/sat/nasa/modis/aerosol/${YYYY_ytday}${MM_ytday}${DD_ytday}0000.zip .
  hsi get -N /BMC/fdr/Permanent/${YYYY_today}/${MM_today}/${DD_today}/data/sat/nasa/modis/aerosol/${YYYY_today}${MM_today}${DD_today}0000.zip .
  hsi get -N /BMC/fdr/Permanent/${YYYY_tomorrow}/${MM_tomorrow}/${DD_tomorrow}/data/sat/nasa/modis/aerosol/${YYYY_tomorrow}${MM_tomorrow}${DD_tomorrow}0000.zip .
  hsi get -N /BMC/fdr/Permanent/${YYYY_ytday}/${MM_ytday}/${DD_ytday}/data/sat/nasa/modis/aerosol/${YYYY_ytday}${MM_ytday}${DD_ytday}1200.zip .
  hsi get -N /BMC/fdr/Permanent/${YYYY_today}/${MM_today}/${DD_today}/data/sat/nasa/modis/aerosol/${YYYY_today}${MM_today}${DD_today}1200.zip .
  hsi get -N /BMC/fdr/Permanent/${YYYY_tomorrow}/${MM_tomorrow}/${DD_tomorrow}/data/sat/nasa/modis/aerosol/${YYYY_tomorrow}${MM_tomorrow}${DD_tomorrow}1200.zip .
  for file in *.zip
  do
    unzip ${file}
    rm -f ${file}
  done
  # Remove corrupt files
  for file in MY*
  do
    ncdump -hv AOD_550_Dark_Target_Deep_Blue_Combined ${file}
    if [[ $? -ne 0 ]]; then
      rm -f ${file}
    fi
  done
fi
if [[ "${OBSTYPE}" == "MODIS_TERRA" ]]; then
  hsi get -N /BMC/fdr/Permanent/${YYYY_ytday}/${MM_ytday}/${DD_ytday}/data/sat/nasa/modis/aerosol/${YYYY_ytday}${MM_ytday}${DD_ytday}0000.zip .
  hsi get -N /BMC/fdr/Permanent/${YYYY_today}/${MM_today}/${DD_today}/data/sat/nasa/modis/aerosol/${YYYY_today}${MM_today}${DD_today}0000.zip .
  hsi get -N /BMC/fdr/Permanent/${YYYY_tomorrow}/${MM_tomorrow}/${DD_tomorrow}/data/sat/nasa/modis/aerosol/${YYYY_tomorrow}${MM_tomorrow}${DD_tomorrow}0000.zip .
  hsi get -N /BMC/fdr/Permanent/${YYYY_ytday}/${MM_ytday}/${DD_ytday}/data/sat/nasa/modis/aerosol/${YYYY_ytday}${MM_ytday}${DD_ytday}1200.zip .
  hsi get -N /BMC/fdr/Permanent/${YYYY_today}/${MM_today}/${DD_today}/data/sat/nasa/modis/aerosol/${YYYY_today}${MM_today}${DD_today}1200.zip .
  hsi get -N /BMC/fdr/Permanent/${YYYY_tomorrow}/${MM_tomorrow}/${DD_tomorrow}/data/sat/nasa/modis/aerosol/${YYYY_tomorrow}${MM_tomorrow}${DD_tomorrow}1200.zip .
  for file in *.zip
  do
    unzip ${file}
    rm -f ${file}
  done
  # Remove corrupt files

  for file in MO*
  do
    ncdump -hv AOD_550_Dark_Target_Deep_Blue_Combined ${file}
    if [[ $? -ne 0 ]]; then
      rm -f ${file}
    fi
  done
fi
#
#--------------------------------------------------
# -------------- PollenSense --------------------------
#--------------------------------------------------
#
if [[ "${OBSTYPE}" == "PollenSense" ]]; then
#
# 
# Because the PollenSense data changes from obs to forecast, we grab the data
# two days earlier than other data
#
#
APIKEY=j3xWLmABCaI9cn9PoDyqkXLktPW1mohpDF10v0FBKdxYdsl6Z7kOy8ref9PBn9kD1128e6aisl3TABkoY7Fy3O
URL="https://model.pollensense.com/api/"
region=NA
agg=A
unit=PPM3
format=tiff
#
categories=(POL TRE GRA WEE OTHPAR)
ncat_loop=$((${#categories[@]}-1))
rm -f ${workdir}/*.tiff
#
for icat in $(seq 0 ${ncat_loop})
do
category=${categories[${icat}]}

# GET POLLEN
# Today is 4/22, the obs directory is 2025042212
# Grab the interpolated obs for yesterday, 4/21
# Grab today, tomorrow, and 2-day forecast, 4/22, 4/23, 4/24
#
# COMPARE POLLEN
# Today is 4/22, we are running analysis for 4/20 (4/19-4/21)
# 1st plot compares yesterday's interpolated obs to the day 1 RAP-Chem forecast
# - Model file: 2025042006/aqm_RAP-Chem_2025042006.nc (Times = 0-23)
# - Obs   file: 2025042112/POL_20250420.nc
#
# 2nd plot compares today's PS forecast to day 1 forecast of the following day
# - Model file: 2025042106/aqm_RAP-Chem_2025042106.nc (Times = 0-23 of full file)
# - Obs (today fcst)   file: 2025042112/POL_20250421.nc
#
# 3rd plot compares tomorrow's forecast to the day2 forecast of previous day
# - Model file: Model file: 2025042006/aqm_RAP-Chem_2025042106.nc (Times = 24-47)
# - Obs (tomorrow fcst)file: 2025041912/POL_20250420.nc
#

# Yesterday Obs
starting="${YYYY_ytday}-${MM_ytday}-${DD_ytday}"
starting2="${YYYY_ytday}${MM_ytday}${DD_ytday}"
curl -X 'GET' "${URL}/region?region=${region}&starting=${starting}&category=${category}&agg=${agg}&unit=${unit}&format=${format}&key=${APIKEY}" -H "accept: image/${format}" >> ${category}_${starting2}.tiff
python ${scriptsdir}/convert_tiff_to_netcdf.py ${workdir} ${category} ${starting2}

# Today Forecast
starting="${YYYY_today}-${MM_today}-${DD_today}"
starting2="${YYYY_today}${MM_today}${DD_today}"
curl -X 'GET' "${URL}/region?region=${region}&starting=${starting}&category=${category}&agg=${agg}&unit=${unit}&format=${format}&key=${APIKEY}" -H "accept: image/${format}" >> ${category}_${starting2}.tiff
python ${scriptsdir}/convert_tiff_to_netcdf.py ${workdir} ${category} ${starting2}

# Tomorrow forecast
starting="${YYYY_tomorrow}-${MM_tomorrow}-${DD_tomorrow}"
starting2="${YYYY_tomorrow}${MM_tomorrow}${DD_tomorrow}"
curl -X 'GET' "${URL}/region?region=${region}&starting=${starting}&category=${category}&agg=${agg}&unit=${unit}&format=${format}&key=${APIKEY}" -H "accept: image/${format}" >> ${category}_${starting2}.tiff
python ${scriptsdir}/convert_tiff_to_netcdf.py ${workdir} ${category} ${starting2}

# Two-day forecast
starting="${YYYY_twodays}-${MM_twodays}-${DD_twodays}"
starting2="${YYYY_twodays}${MM_twodays}${DD_twodays}"
curl -X 'GET' "${URL}/region?region=${region}&starting=${starting}&category=${category}&agg=${agg}&unit=${unit}&format=${format}&key=${APIKEY}" -H "accept: image/${format}" >> ${category}_${starting2}.tiff
python ${scriptsdir}/convert_tiff_to_netcdf.py ${workdir} ${category} ${starting2}

done
fi


#--------------------------------------------------
# -------------- TROPOMI --------------------------
#--------------------------------------------------
if [[ "${OBSTYPE}" == "TROPOMI" ]]; then
 ln -s /scratch4/BMC/public/data/sat/sentinel-5p/L2/NO2/* .
 ln -s /scratch4/BMC/public/data/sat/sentinel-5p/L2/CO/* .
 ln -s /scratch4/BMC/public/data/sat/sentinel-5p/L2/HCHO/* .
fi
#
#
#--------------------------------------------------
# -------------- VIIRS  --------------------------
#--------------------------------------------------
if [[ "${OBSTYPE}" == "VIIRS" ]]; then
 ln -s /scratch4/BMC/public/data/sat/nesdis/viirs/aod/conus/* .
fi

if [[ "${OBSTYPE}" == "Google_Pollen" ]]; then
   scp -o 'ProxyJump jschnell@gate.al.noaa.gov' jschnell@meiyu:/wrk/csd4/rahmadov/RAP-Chem/google_pollen/${YYYY_today}${MM_today}${DD_today}00/TRE_google_${YYYY_today}${MM_today}${DD_today}.png .
   scp -o 'ProxyJump jschnell@gate.al.noaa.gov' jschnell@meiyu:/wrk/csd4/rahmadov/RAP-Chem/google_pollen/${YYYY_today}${MM_today}${DD_today}00/GRA_google_${YYYY_today}${MM_today}${DD_today}.png .
   scp -o 'ProxyJump jschnell@gate.al.noaa.gov' jschnell@meiyu:/wrk/csd4/rahmadov/RAP-Chem/google_pollen/${YYYY_today}${MM_today}${DD_today}00/WEE_google_${YYYY_today}${MM_today}${DD_today}.png .
   exit 0
fi

if [[ "${OBSTYPE}" == "pollen_dot_com" ]]; then
   wget https://pollenapps.com/DF/pollen/map/pollenmapvideo.mp4
   python ${scriptsdir}/convert_mp4_to_images.py ${workdir}
fi
   

#--------------------------------------------------
# --------------  Pollen --------------------------
#--------------------------------------------------
if [[ "${OBSTYPE}" == "NAB_POLLEN" ]]; then
  scp -o 'ProxyJump jschnell@gate.al.noaa.gov' jschnell@meiyu:/wrk/csd4/rahmadov/RAP-Chem/nab_pollen/${YYYY_today}${MM_today}${DD_today}00/scraped_pollen_data_${YYYY_today}${MM_today}${DD_today}.csv .
  cp scraped_pollen_data_${YYYY_today}${MM_today}${DD_today}.csv ../scraped_pollen/scraped_pollen_data_${YYYY_today}${MM_today}${DD_today}.csv
fi

exit 0
