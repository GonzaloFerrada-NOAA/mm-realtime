#!/bin/bash
# We will check whether the mpassit files exist and are old enough to process:
# inputs:
START_TIME=$1
cycleHH=$2
FWX_DATA_DATADIR_NC=$3
# ---------------------------------------------
# Directories:
base_dir="${FWX_DATA_DATADIR_NC}/${START_TIME}${cycleHH}"
mpassit_dir=$(find "$base_dir" -maxdepth 1 -type d -name 'rrfs_mpassit_*' -print -quit)
datadir="${mpassit_dir}"

lead_times=( $(seq 0 1 24) )
should_fail=0
for h in "${lead_times[@]}"; do

    daux=$(date -d "${START_TIME} ${cycleHH}:00:00 ${h} hours" "+%F_%H.%M.%S")
    f="${datadir}/${h}/mpassit.${daux}.nc"
    
    if [[ -s "${f}" ]]; then
        echo "OK      ${f}"
    else
        echo "MISSING ${f}"
        should_fail=1
    fi
    
done

[[ ${should_fail} -eq 1 ]] && exit 1

exit 0
