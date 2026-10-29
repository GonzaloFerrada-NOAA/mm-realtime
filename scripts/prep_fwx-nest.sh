#!/bin/bash -l
module load nco
module load cdo eccodes/2.34.0
source ${SCRIPTS_DIR}/tools/workflow_tools.sh

set -e
export PS4='+ [$(date "+%Y-%m-%d %H:%M:%S")] ${LINENO}: '
set -x

# Test
# source tools/workflow_tools.sh
# START_TIME="20261027"
# cycleHH="00"
# MELODIES_MONET_DIR="/scratch3/BMC/acomp/Gonzalo.Ferrada/verif/tmp"
# FWX_DATA_DATADIR_NC="/scratch3/BMC/wrfruc/mpas/fire/fwx1.25km/stmp"
# SCRIPTS_DIR="/scratch4/BMC/acomp/cheMPAS-Fire/realtime/melodies-monet/scripts"


YYYY=$(date +%Y -d "${START_TIME}")
YY=$(  date +%y -d "${START_TIME}")
MM=$(  date +%m -d "${START_TIME}")
DD=$(  date +%d -d "${START_TIME}")
YYYYMMDD=${YYYY}${MM}${DD}

model="FWx-nest"
MODEL_DT_HOURS=1

# Directories:
base_dir="${FWX_NEST_DATADIR_NC}/${YYYYMMDD}${cycleHH}"
mpassit_dir=$(find "$base_dir" -maxdepth 1 -type d -name 'rrfs_mpassit_*' -print -quit)
datadir="${mpassit_dir}"
workdir="${MELODIES_MONET_DIR}/model_output/${model}/${YYYYMMDD}${cycleHH}"
mkdir -p ${workdir}

final_fout="${workdir}/aqm_${model}_${YYYYMMDD}${cycleHH}.nc"
# final_fout_3d="${workdir}/aqm3D_${model}_${YYYYMMDD}${cycleHH}.nc"

# # Determine the output hours to process:
# # this function outputs LEAD_HH_START and LEAD_HH_END
# get_group_leads "${FCST_LENGTH_HOURS}" "${MODEL_DT}" "${NGROUPS}" "${GROUP}"

# Begin:
vars2="XLONG,XLAT,XTIME,AOD550,FRP_OUT"
vars3="PM2_5,P,PB,T"

lead_times=( $(seq 0 "${MODEL_DT_HOURS}" 24) )

for h in "${lead_times[@]}"; do

    daux=$(date -d "${START_TIME} ${cycleHH}:00:00 ${h} hours" "+%F_%H.%M.%S")
    f="${datadir}/${h}/mpassit.${daux}.nc"
    isfile "${f}"
    echo "${f}"

    fout="${workdir}/frame_$( basename $f )"
    ftmp="${workdir}/tmp_$( basename $f )"
    
    # 2-D
    ncks -h -O -v ${vars2}                                                      ${f}    ${fout}
    # 3-D only first layer
    ncks -h -A -v ${vars3} -d bottom_top,0                                      ${f}    ${fout}
    
    # wind
    ncks  -h -O -v U10MEAN,V10MEAN -d bottom_top,0                              ${f}    ${ftmp}
    ncap2 -h -A -s 'WIND10MEAN=float((U10MEAN^2+V10MEAN^2)^(0.5))'              ${ftmp} ${ftmp}
    ncap2 -h -A -s 'WDIR10=float(180.+(180./3.14159)*atan2(U10MEAN,V10MEAN))'   ${ftmp} ${ftmp}
    ncks -h -A -v WIND10MEAN,WDIR10                                             ${ftmp} ${fout}
    rm -f ${ftmp}
    
    # precip, temperature, visibility
    # ncks -h -O -v PREC_ACC_C,PREC_ACC_NC,T2,VIS,Q2,PSFC                         ${f}    ${ftmp}
    ncks -h -O -v PREC_ACC_C,PREC_ACC_NC,T2,Q2,PSFC                             ${f}    ${ftmp}
    ncap2 -h -A -s 'PRECIP_1HR=float(PREC_ACC_C+PREC_ACC_NC)'                   ${ftmp} ${ftmp}
    ncap2 -h -A -s 'T2=float(T2-273.15)'                                        ${ftmp} ${ftmp}
    # ncap2 -h -A -s 'VIS=float(VIS*0.621371/1000.0)'                             ${ftmp} ${ftmp}
    # ncks -h -A -v PRECIP_1HR,T2,VIS                                             ${ftmp} ${fout}
    ncks -h -A -v PRECIP_1HR,T2                                                 ${ftmp} ${fout}
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
    
    # lat/lon: 2-D (south_north, west_east) from first time slice; keep both naming styles like RRFS-SD
    ncap2 -O -h -s 'latitude=XLAT(0,:,:);longitude=XLONG(0,:,:);lat=latitude;lon=longitude' ${fout} ${fout}

    # time coordinate from XTIME (minutes since cycle start), on the existing record dim
    ncap2 -O -h -s 'time=abs(XTIME)' ${fout} ${fout}

    # drop WRF-style leftovers (-C needed since they're referenced in 'coordinates' attributes)
    ncks -O -h -C -x -v XLAT,XLONG,XTIME ${fout} ${fout}

    # remove the size-1 bottom_top dim: PM2_5(Time,bottom_top,..) -> PM2_5(Time,..)
    # --no_cll_mth: don't add a 'cell_methods' attribute
    ncwa -O -h --no_cll_mth -a bottom_top ${fout} ${fout}
    
    # Crop NaN edges:
    ncks -O -h -d south_north,256,2342 -d west_east,258,2340 ${fout} ${fout}
    
    echo "========================================================================"
    
done

# concatenate all frames (netCDF3: safe for ncrename and readable by scipy/hrrr reader)
ncrcat -O -h -3 ${workdir}/frame_*.nc ${final_fout}
isfile "${final_fout}"
rm -f ${workdir}/frame_*.nc

# generic dimension names
ncrename -O -h -d Time,time -d south_north,y -d west_east,x ${final_fout}

# coordinates attribute for every data variable (bash array keeps the space in the value)
datavars="AOD550 FRP_OUT PM2_5 WIND10MEAN WDIR10 PRECIP_1HR T2 TD2 P PB"
crd_args=()
for v in ${datavars}; do crd_args+=( -a "coordinates,${v},o,c,lon lat" ); done

# ncatted applies the edits in order: delete first, then create
ncatted -O -h \
    -a ,global,d,, -a Conventions,global,c,c,"CF-1.0" \
    -a FieldType,,d,, -a MemoryOrder,,d,, -a stagger,,d,, -a coordinates,,d,, \
    "${crd_args[@]}" \
    -a units,time,o,c,"minutes since ${YYYY}-${MM}-${DD} ${cycleHH}:00:00" \
    -a description,time,d,, -a long_name,time,o,c,"time" \
    -a description,latitude,d,,  -a long_name,latitude,o,c,"latitude"   -a units,latitude,o,c,"degrees_north" \
    -a description,longitude,d,, -a long_name,longitude,o,c,"longitude" -a units,longitude,o,c,"degrees_east" \
    -a description,lat,d,,       -a long_name,lat,o,c,"latitude"        -a units,lat,o,c,"degrees_north" \
    -a description,lon,d,,       -a long_name,lon,o,c,"longitude"       -a units,lon,o,c,"degrees_east" \
    -a units,T2,o,c,"C"   -a description,T2,o,c,"2-m temperature" \
    -a units,WDIR10,o,c,"degree" -a description,WDIR10,o,c,"10 m wind direction (meteorological)" \
    -a description,WIND10MEAN,o,c,"Mean 10 m wind speed since last output" \
    -a description,PRECIP_1HR,o,c,"1-h total (convective + non-convective) precipitation" \
    ${final_fout}
checkstatus
echo "${final_fout} created!"


echo "Producing AOD files for TEMPO/VIIRS verification..."

CDO_REGRID_FILE_VIIRS="${SCRIPTS_DIR}/aux/cdo_regrid_global_0p05.txt"
CDO_REGRID_FILE_TEMPO="${SCRIPTS_DIR}/aux/cdo_regrid_regional_0p1.txt"
AOD_FILE_VIIRS="${workdir}/aod550_${model}_${YYYYMMDD}${cycleHH}.0p05.nc"
AOD_FILE_TEMPO="${workdir}/aod550_${model}_${YYYYMMDD}${cycleHH}.0p1.nc"
AOD_FILE_TMP="${workdir}/tmp.aod550.${model}_${YYYYMMDD}${cycleHH}.nc"

ncks -h -O -v AOD550                    "${final_fout}"    "${AOD_FILE_TMP}"
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
