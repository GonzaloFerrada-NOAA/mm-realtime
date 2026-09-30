#!/bin/bash -l
module load nco
module load cdo eccodes/2.34.0

source ${SCRIPTS_DIR}/tools/workflow_tools.sh
set -e
export PS4='+ [$(date "+%Y-%m-%d %H:%M:%S")] ${LINENO}: '
set -x

# Env variables:
# FCST_LENGTH_HOURS=$((10#$FCST_LENGTH_HOURS))
# NGROUPS=$((10#$NGROUPS))
# GROUP=$((10#$GROUP))
# MODEL_DT=1

YYYY=$(date +%Y -d "${START_TIME}")
YY=$(  date +%y -d "${START_TIME}")
MM=$(  date +%m -d "${START_TIME}")
DD=$(  date +%d -d "${START_TIME}")
YYYYMMDD=${YYYY}${MM}${DD}

model="MPAS-Aerosols"

# Directories:
base_dir="${MPAS_AER_DATADIR_NC}/${YYYYMMDD}${cycleHH}"
mpassit_dir=$(find "$base_dir" -maxdepth 1 -type d -name 'rrfs_mpassit_*' -print -quit)
datadir="${mpassit_dir}/det"
workdir="${MELODIES_MONET_DIR}/model_output/${model}/${YYYYMMDD}${cycleHH}"
mkdir -p ${workdir}

final_fout="${workdir}/aqm_${model}_${YYYYMMDD}${cycleHH}.nc"
# final_fout_3d="${workdir}/aqm3D_${model}_${YYYYMMDD}${cycleHH}.nc"

# # Determine the output hours to process:
# # this function outputs LEAD_HH_START and LEAD_HH_END
# get_group_leads "${FCST_LENGTH_HOURS}" "${MODEL_DT}" "${NGROUPS}" "${GROUP}"


# Begin:
files=$( find ${datadir} -name 'mpassit*.nc' | sort ) # list of files
vars2="XLONG,XLAT,XTIME,AOD550,AOD550_SIMPLE"
vars3="PM2_5,PM10,POLP_TREE,POLP_WEED,POLP_GRASS"
# ,U10MEAN,V10MEAN,PREC_ACC_C,PREC_ACC_NC,Q2,PSFC,"
for f in ${files[@]}; do

    fout="${workdir}/frame_$( basename $f )"
    ftmp="${workdir}/tmp_$( basename $f )"
    
    # 2-D
    ncks -h -O -v ${vars2}                                                      ${f}    ${fout}
    # 3-D only first layer
    ncks -h -A -v ${vars3} -d bottom_top,0                                      ${f}    ${fout}
    ncrename -v POLP_TREE,polp_tree -v POLP_WEED,polp_weed -v POLP_GRASS,polp_grass     ${fout}
    # wind
    ncks  -h -O -v U10MEAN,V10MEAN -d bottom_top,0                              ${f}    ${ftmp}
    ncap2 -h -A -s 'WIND10MEAN=float((U10MEAN^2+V10MEAN^2)^(0.5))'              ${ftmp} ${ftmp}
    ncap2 -h -A -s 'WDIR10=float(180.+(180./3.14159)*atan2(U10MEAN,V10MEAN))'   ${ftmp} ${ftmp}
    ncks -h -A -v WIND10MEAN,WDIR10                                             ${ftmp} ${fout}
    rm -f ${ftmp}
    # precip, temperature, visibility
    ncks -h -O -v PREC_ACC_C,PREC_ACC_NC,T2,VIS,Q2,PSFC                         ${f}    ${ftmp}
    ncap2 -h -A -s 'PRECIP_1HR=float(PREC_ACC_C+PREC_ACC_NC)'                   ${ftmp} ${ftmp}
    ncap2 -h -A -s 'T2=float(T2-273.15)'                                        ${ftmp} ${ftmp}
    ncap2 -h -A -s 'VIS=float(VIS*0.621371/1000.0)'                             ${ftmp} ${ftmp}
    ncks -h -A -v PRECIP_1HR,T2,VIS                                             ${ftmp} ${fout}
    rm -f ${ftmp}
    # dew point
    ncap2 -A -v -s \
        '*Pmb=PSFC/100.0; *e=Q2*Pmb/(0.622+Q2); *es=6.112*exp(17.67*(T2-273.15)/(T2-29.65)); 
        *rh=100.0*e/es; where(rh>100.0) rh=100.0; *gcx=461.5/(1000.0*4.186); 
        *lhv=(597.3-0.57*(T2-273.15))*gcx; 
        TD2=float((T2*lhv/(lhv-T2*log(rh/100.0)))-273.15); TD2@units="C"; TD2@description="2-m dewpoint temperature";' \
        ${f} ${ftmp}
    ncks -h -A -v TD2                                                           ${ftmp} ${fout}
    rm -f ${ftmp}
    
    
    # lat and lon
    # ncap2 -O -s 'latitude=XLAT' -s 'longitude=XLONG' ${fout} ${fout}
    ncap2 -O -s 'latitude=XLAT(0,:,:);longitude=XLONG(0,:,:)' ${fout} ${fout}
    ncap2 -O -s 'XLAT=XLAT(0,:,:);XLONG=XLONG(0,:,:)' ${fout} ${fout}
    
    # time:
    # this is needed by the VIIRS and TEMPO comparison since the dimensions of AOD550 are
    # (Time, south_north, west_east), and Time doesn't exist in the file...
    ncap2 -O -s 'Time=abs(XTIME)' ${fout} ${fout}
    ncap2 -O -s 'time=abs(XTIME)' ${fout} ${fout}
    
    echo "========================================================================"
    
done

# concatenate all frames:
# ncrcat -O -h -4 -L 3 ${workdir}/frame_*.nc ${final_fout}
ncrcat -O -h ${workdir}/frame_*.nc ${final_fout}
isfile "${final_fout}"
rm -f ${workdir}/frame_*.nc

echo "${final_fout} created!"


echo "Producing AOD files for TEMPO/VIIRS verification..."

CDO_REGRID_FILE_VIIRS="${SCRIPTS_DIR}/aux/cdo_regrid_global_0p05.txt"
CDO_REGRID_FILE_TEMPO="${SCRIPTS_DIR}/aux/cdo_regrid_regional_0p1.txt"
AOD_FILE_VIIRS="${workdir}/aod550_${model}_${YYYYMMDD}${cycleHH}.0p05.nc"
AOD_FILE_TEMPO="${workdir}/aod550_${model}_${YYYYMMDD}${cycleHH}.0p1.nc"
AOD_FILE_TMP="${workdir}/tmp.aod550.${model}_${YYYYMMDD}${cycleHH}.nc"

ncks -h -O -v AOD550,AOD550_SIMPLE      "${final_fout}"    "${AOD_FILE_TMP}"
ncatted -h -a ,global,d,,               "${AOD_FILE_TMP}"
ncks -h -3 -O                           "${AOD_FILE_TMP}"  "${AOD_FILE_TMP}"
ncrename -h -d Time,time -v Time,time   "${AOD_FILE_TMP}"
ncks -h -4 -O                           "${AOD_FILE_TMP}"  "${AOD_FILE_TMP}"
cdo remapbil,${CDO_REGRID_FILE_VIIRS}   "${AOD_FILE_TMP}" "${AOD_FILE_VIIRS}"
cdo remapbil,${CDO_REGRID_FILE_TEMPO}   "${AOD_FILE_TMP}" "${AOD_FILE_TEMPO}"

isfile "${AOD_FILE_VIIRS}"; isfile "${AOD_FILE_TEMPO}"
rm -f  "${AOD_FILE_TMP}"

# Compress:
ncks -O -h -4 -L 3 "${AOD_FILE_VIIRS}" "${AOD_FILE_VIIRS}"
ncks -O -h -4 -L 3 "${AOD_FILE_TEMPO}" "${AOD_FILE_TEMPO}"
isfile "${AOD_FILE_VIIRS}"; isfile "${AOD_FILE_TEMPO}"


echo "prep_mpas-aerosols completed!"

exit 0
