#!/bin/bash --login


# ENVARS
# - START_TIME
# - NUM_DAYS_TO_KEEP
# - DELETE MODELS (1/0)
# - MODEL_OUTPUT_DIRECTORY
# - DELETE RAW PLOTS (1/0)
# - RAW PLOT OUT DIRECTORY
# - DELTE "TOWEB" PLOTS (1/0)
# - "TOWEB" PLOT DIRECTORY

delete_time=`date +%Y%m%d -d "${START_TIME} - ${NUM_DAYS_TO_KEEP} days"`
echo "Deleting data older than $delete_time"
#
if [[ ${DELETE_MODELS} -eq 1 ]] ; then
models=("ECMWF-CAMS"  "GEFS-Aerosol"  "GEOS-CF"  "HRRR-Smoke" "NAAPS" "NAQFC"  "NAQFC-para6d"  "NCAR-AQ-WATCH"  "NCAR-FIREX-AQ"  "RAP-Chem"  "RAP-Smoke"  "RAQMS"  "RRFS-SD"  "online-CMAQ")
nmodels=${#models[@]}
for j in $(seq 0 $((${nmodels}-1))) 
do
	cd ${MODEL_OUTPUT_DIR}/${models[$j]}
        for i in *
        do
		if [[ ${i} -lt ${delete_time}00 ]];then
			echo "Deleting cycle ${i} for ${models[${j}]}"
			rm -rf ${i}
		fi
	done
done
fi
#
#
#
if [[ ${DELETE_RAW_PLOTS} -eq 1 ]]; then
	cd ${RAW_PLOT_DIR}
	for i in * 
	do
		if [[ ${i} -lt ${delete_time} ]];then
			echo "Deleting raw plots for ${i}"
			rm -rf ${i}
		fi
	done
fi 
#
#
#
if [[ ${DELETE_TOWEB_PLOTS} -eq 1 ]]; then
        cd ${TOWEB_DIR}
        for i in *
        do
                if [[ ${i} -lt ${delete_time} ]];then
                	echo "Deleting toweb plots for ${i}"
			#rm -rf ${i}
                fi
        done
fi

