#!/bin/bash --login


module load rdhpcs-conda
conda activate ${CONDA_ENV_STABLE}
YYYY=`date +%Y -d "${START_TIME}"`
MM=`date +%m -d "${START_TIME}"`
DD=`date +%d -d "${START_TIME}"`

basedir=${MELODIES_MONET_DIR}/model_output/ECMWF-CAMS
workdir=${basedir}/${YYYY}${MM}${DD}00
mkdir -p ${workdir}
model="ECMWF-CAMS"
final_filename=aqm_${model}_${YYYY}${MM}${DD}${cycleHH}.nc
cd ${workdir}

cat << EOF >> getcams.py
#!/usr/bin/env python
import cdsapi
import yaml

c = cdsapi.Client()

c.retrieve(
    'cams-global-atmospheric-composition-forecasts',
    {
        'type': 'forecast',
        'format': 'netcdf_zip',
        'variable': [
            'ammonium_aerosol_mass_mixing_ratio', 'ammonium_aerosol_optical_depth_550nm', 'black_carbon_aerosol_optical_depth_550nm',
            'carbon_monoxide', 'dust_aerosol_optical_depth_550nm', 'nitrate_aerosol_optical_depth_550nm',
            'nitrate_fine_mode_aerosol_mass_mixing_ratio', 'nitrogen_dioxide', 'organic_matter_aerosol_optical_depth_550nm',
            'ozone', 'particulate_matter_10um', 'particulate_matter_2.5um',
            'sea_salt_aerosol_optical_depth_550nm', 'sulphate_aerosol_mixing_ratio', 'sulphur_dioxide',
            'temperature', 'total_aerosol_optical_depth_550nm'
        ],
        'model_level': [
            '1','137'
        ],
        'date': '${YYYY}-${MM}-${DD}/${YYYY}-${MM}-${DD}',
        'time': '00:00',
        'leadtime_hour': [
            '0', '1', '10',
            '100', '101', '102',
            '103', '104', '105',
            '106', '107', '108',
            '109', '11', '110',
            '111', '112', '113',
            '114', '115', '116',
            '117', '118', '119',
            '12', '120', '13',
            '14', '15', '16',
            '17', '18', '19',
            '2', '20', '21',
            '22', '23', '24',
            '25', '26', '27',
            '28', '29', '3',
            '30', '31', '32',
            '33', '34', '35',
            '36', '37', '38',
            '39', '4', '40',
            '41', '42', '43',
            '44', '45', '46',
            '47', '48', '49',
            '5', '50', '51',
            '52', '53', '54',
            '55', '56', '57',
            '58', '59', '6',
            '60', '61', '62',
            '63', '64', '65',
            '66', '67', '68',
            '69', '7', '70',
            '71', '72', '73',
            '74', '75', '76',
            '77', '78', '79',
            '8', '80', '81',
            '82', '83', '84',
            '85', '86', '87',
            '88', '89', '9',
            '90', '91', '92',
            '93', '94', '95',
            '96', '97', '98',
            '99',
        ],
        'area': [
            70, -140, 10,
            -40,
        ],
    },
    'download.netcdf_zip')
EOF
#
python getcams.py
cat << EOF >> get_${model}.${START_TIME}${cycleHH}.sh
#!/bin/bash --login
#SBATCH --account=acomp
#SBATCH --partition=u1-compute
#SBATCH --time=03:00:00
#SBATCH -n 1
#SBATCH -q batch
#SBATCH --mem-per-cpu=20G

cd ${workdir}


unzip download.netcdf_zip
#
# Grab only the bottom layer for the ml fields
ncks -O -d level,1,1 levtype_ml.nc levtype_ml.nc
ncwa -O -a level levtype_ml.nc levtype_ml.nc
ncks -O -x -v level levtype_ml.nc levtype_ml.nc
#
# Create the record dimensions
ncks -O --mk_rec_dmn time levtype_sfc.nc levtype_sfc.nc 
#ncks -O --mk_rec_dmn time levtype_ml.nc levtype_ml.nc
ncrename -O -d time,time_old levtype_ml.nc levtype_ml.nc
ncrename -O -v time,time_old levtype_ml.nc levtype_ml.nc
#
EOF
cat << "EOF" >> get_${model}.${START_TIME}${cycleHH}.sh
fields=("go3" "no2" "co" "t" "so2")
nfields=${#fields[@]}
for i in $(seq 0 $(($nfields - 1)))
do
ncrename -O -v ${fields[$i]},${fields[$i]}_old levtype_ml.nc levtype_ml.nc
ncap2 -O -s "${fields[${i}]}=pm10" levtype_sfc.nc levtype_sfc.nc
ncap2 -O -s "${fields[${i}]}(:,:,:)=pm10@_FillValue" levtype_sfc.nc levtype_sfc.nc
ncks -A -v ${fields[$i]}_old levtype_ml.nc levtype_sfc.nc
done

timelength_sfc=`ncap2 -v -O -s 'print(time.size(),"%ld\n");' levtype_sfc.nc foo.nc`
rm -f foo.nc
timelength_ml=`ncap2 -v -O -s 'print(time_old.size(),"%ld\n");' levtype_ml.nc foo.nc`
rm -f foo.nc

cp levtype_sfc.nc levtype_sfc.nc.bk

#for i in $(seq 0 $(($nfields - 1)))
#do
#   for i in $(seq 0 $((${timelength_ml}-1))) ; do ncap2 -O -s "${fields[$i]}($i*3,:,:)=${fields[$i]}_old($i,:,:)" levtype_sfc.nc levtype_sfc.nc ; done
#done
for i in $(seq 0 $((${timelength_ml}-1))) ; do ncap2 -O -s "go3($i*3,:,:)=go3_old($i,:,:)" levtype_sfc.nc levtype_sfc.nc ; done
for i in $(seq 0 $((${timelength_ml}-1))) ; do ncap2 -O -s "no2($i*3,:,:)=no2_old($i,:,:)" levtype_sfc.nc levtype_sfc.nc ; done
for i in $(seq 0 $((${timelength_ml}-1))) ; do ncap2 -O -s "co($i*3,:,:)=co_old($i,:,:)" levtype_sfc.nc levtype_sfc.nc ; done
for i in $(seq 0 $((${timelength_ml}-1))) ; do ncap2 -O -s "t($i*3,:,:)=t_old($i,:,:)" levtype_sfc.nc levtype_sfc.nc ; done
for i in $(seq 0 $((${timelength_ml}-1))) ; do ncap2 -O -s "so2($i*3,:,:)=so2_old($i,:,:)" levtype_sfc.nc levtype_sfc.nc ; done
EOF
cat << EOF >> get_${model}.${START_TIME}${cycleHH}.sh
# Move to final filename
mv levtype_sfc.nc ${final_filename} 
ncap2 -O -s 'pm2p5=1.e9*pm2p5' -s 'pm10=1.e9*pm10' -s 'go3=28.9644/47.99821*1.e9*go3' -s 'co=28.9644/28.0101*1.e9*co' -s 'no2=28.9644/46.0055*1.e9*no2' -s 'so2=28.9644/64.0638*1.e9*so2' ${final_filename} ${final_filename}

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
