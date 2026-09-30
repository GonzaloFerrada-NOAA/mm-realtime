#!/bin/bash
# We will check whether the mpassit files exist and are old enough to process:
# inputs:
START_TIME=$1
cycleHH=$2
MPAS_AER_DATADIR_NC=$3
# ---------------------------------------------
# Directories:
base_dir="${MPAS_AER_DATADIR_NC}/${START_TIME}${cycleHH}"
mpassit_dir=$(find "$base_dir" -maxdepth 1 -type d -name 'rrfs_mpassit_*' -print -quit)
datadir="${mpassit_dir}/det"

# Check at least 36 hours of forecast:
DATE1=$(date -d "${START_TIME} ${cycleHH}:00" +%s)
DATE2=$(( DATE1 + 36 * 3600 ))
for (( DATEAUX=DATE1; DATEAUX<=DATE2; DATEAUX+=3600 )); do
    datestr=$( date -d "@${DATEAUX}" '+%Y-%m-%d_%H.%M.%S' )
    file="${datadir}/mpassit.${datestr}.nc"
    if [[ ! -s "${file}" ]]; then
        echo "$file failed"
        exit 1
    fi
done
echo "todo bien po"
exit 0
