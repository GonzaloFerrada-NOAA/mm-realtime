#!/bin/bash -l
#SBATCH --account=acomp
#SBATCH --partition=u1-service
#SBATCH --time=12:00:00
#SBATCH -q batch
#SBATCH -n 1 
#SBATCH --mem-per-cpu=20G

module load hpss
module load nco

YYYY=`date +%Y -d "${START_TIME}"`
MM=`date +%m -d "${START_TIME}"`
DD=`date +%d -d "${START_TIME}"`
YYYYMMDD=${YYYY}${MM}${DD}
model="online-CMAQ"
model2="UFS-AQM"
final_filename=aqm_${model}_${YYYYMMDD}${cycleHH}.nc
final_filename2=aqm_${model2}_${YYYYMMDD}${cycleHH}.nc

echo "Getting NAQFC operational forecast data for the ${cycleHH}z cycle on ${YYYYMMDD}"

basedatadir=/NCEPPROD/5year/hpssprod/runhistory/
datadir=${basedatadir}/rh${YYYY}/${YYYY}${MM}/${YYYY}${MM}${DD}
#basedatadir=/NCEPDEV/emc-naqfc/5year/Jianping.Huang/AQMv7/aqm.v7.0.c84
#basedatadir=/NCEPDEV/emc-naqfc/5year/Jianping.Huang/AQMv7/aqm.v7.0.c55
#datadir=${basedatadir}/${YYYYMMDD}/${cycleHH}
echo "Location of data on HPSS: ${datadir}"

workdir_base=${MELODIES_MONET_DIR}/model_output/${model}

cd ${workdir_base}
workdir=${workdir_base}/${YYYYMMDD}${cycleHH}
echo "Downloading to JET:${workdir}"
mkdir -p ${workdir}
cd ${workdir}

filename1=com_aqm_v7.0_aqm.${YYYYMMDD}_${cycleHH}${cycleHH}.post.tar
filename2=com_aqm_v7.0_aqm.${YYYYMMDD}_${cycleHH}${cycleHH}.input.tar

# Grab the file
echo "Attepting to retrieve file: ${datadir}/${filename}"
htar -xvf ${datadir}/${filename1}
htar -xvf ${datadir}/${filename2}
cat << EOF >> get_${model}.${START_TIME}${cycleHH}.sh
#!/bin/bash --login
#SBATCH --account=acomp
#SBATCH --partition=u1-compute
#SBATCH --time=03:00:00
#SBATCH -n 1
#SBATCH -q batch
#SBATCH --mem-per-cpu=32G

cd ${workdir}
cycleHH=${cycleHH}
YYYY=${YYYY}
MM=${MM}
DD=${DD}
rm -f *f000.nc

# Define what the surface level is, RRFS/UFS is flipped
surface_level_half=64
surface_level_full=63

for i in {01..72}
do
# Grab the necessary variables, and cut  out the surface dimension of the dyn file and rename to a surface file
EOF
cat << "EOF" >> get_${model}.${START_TIME}${cycleHH}.sh

ncks -v phalf,tmp,pressfc,dpres,hgtsfc,delz -d phalf,${surface_level_half},${surface_level_half} -d pfull,${surface_level_full},${surface_level_full} aqm.t${cycleHH}z.dyn.f0${i}.nc aqm.t${cycleHH}z.dyn.f0${i}_sfc.nc
rm -f aqm.t${cycleHH}z.dyn.f0${i}.nc
ncks -A -v phalf,tmp,pressfc,dpres,hgtsfc,delz aqm.t${cycleHH}z.dyn.f0${i}_sfc.nc aqm.t${cycleHH}z.chem_sfc.f0${i}.nc
ncks -A -v aod,tprcp,vgrd10m,ugrd10m aqm.t${cycleHH}z.phy.f0${i}.nc aqm.t${cycleHH}z.chem_sfc.f0${i}.nc
ncks -A -v tmp2m aqm.t${cycleHH}z.met_sfc.f0${i}.nc aqm.t${cycleHH}z.chem_sfc.f0${i}.nc
ncks -O --mk_rec_dmn time aqm.t${cycleHH}z.chem_sfc.f0${i}.nc aqm.t${cycleHH}z.chem_sfc.f0${i}.nc
# GAF calculating wind speed and direction
ncap2 -O -s '
wspd10m = sqrt(ugrd10m^2 + vgrd10m^2);
wdir10m = atan2(-ugrd10m, -vgrd10m) * 180.0 / 3.14159265358979323846;
where(wdir10m < 0) wdir10m = wdir10m + 360.0;
' aqm.t${cycleHH}z.chem_sfc.f0${i}.nc aqm.t${cycleHH}z.chem_sfc.f0${i}.nc

mv aqm.t${cycleHH}z.chem_sfc.f0${i}.nc aqm.${YYYY}${MM}${DD}t${cycleHH}z.chem_sfc.f0${i}.nc
done
EOF
cat << EOF >> get_${model}.${START_TIME}${cycleHH}.sh
ncrcat aqm.${YYYY}${MM}${DD}t${cycleHH}z.chem_sfc.*.nc ${final_filename}
ncap2 -O -s 'latitude=lat' -s 'longitude=lon' ${final_filename} ${final_filename}
echo "Getting rid non-saved files"
# Remove everything else
rm -f *f0*.nc *.tar *.grib2 ozone.corrected* pm2.5.corrected*
rm -rf FIRE_EMISSION
rm -rf RESTART
rm -f *gfs_ctrl.nc
rm -f *data.tile7.halo0.nc
rm -f *PT.nc
rm -f *NEXUS_Expt.nc

if [[ -e ${final_filename} ]];then
        echo "Finished processing cycle ${YYYYMMDD}${cycleHH}, linking to UFS-AQM"
        ln -s ${final_filename} ${final_filename2}
        exit 0
else
        echo "Did not complete ${model} cycle ${YYYYMMDD}${cycleHH} transfer"
        exit 1
fi
EOF

sbatch get_${model}.${START_TIME}${cycleHH}.sh

exit 0
