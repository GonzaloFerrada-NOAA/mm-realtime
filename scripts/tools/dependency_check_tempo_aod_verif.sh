#!/bin/bash

YMD="$1"
HH="$2"
MODEL_OUTPUT="$3"
NAMELIST="$4"

mapfile -t MODEL_LIST < <(awk -F',' '!/^#/ {print $1}' "${NAMELIST}")
TOTAL_MODELS=${#MODEL_LIST[@]}

# --- Time-based grace window ---
# Cycle time in UTC epoch seconds (e.g. 20260912 00 -> 2026-09-12 00:00 UTC)
CYCLE_EPOCH=$( date -u -d "${YMD} ${HH}00" +%s )

# activation_offset (48h) + how long we're willing to wait for all files (3h)
ACTIVATION_OFFSET_HR=48
GRACE_PERIOD_HR=3
DEADLINE_EPOCH=$((CYCLE_EPOCH + (ACTIVATION_OFFSET_HR + GRACE_PERIOD_HR) * 3600))

NOW_EPOCH=$(date -u +%s)

FILE_COUNT=0
for MODEL_NAME in "${MODEL_LIST[@]}"; do
    FILE="${MODEL_OUTPUT}/${MODEL_NAME}/${YMD}${HH}/aqm_${MODEL_NAME}_${YMD}${HH}.nc"
    if [[ -s "$FILE" ]]; then
        ((++FILE_COUNT))
    fi
done

if (( NOW_EPOCH < DEADLINE_EPOCH )); then
    # Still inside the 3h grace window past activation: require ALL models present
    if (( FILE_COUNT == TOTAL_MODELS )); then
        exit 0
    else
        exit 1
    fi
else
    # Past the grace window: fall back to "at least one file" so the task
    # doesn't stall forever waiting on a straggling/missing model
    if (( FILE_COUNT > 0 )); then
        exit 0
    else
        exit 1
    fi
fi


