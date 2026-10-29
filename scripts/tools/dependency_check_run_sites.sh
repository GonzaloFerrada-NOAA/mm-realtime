#!/bin/bash
# dependency_check_run_sites.sh YMD HH MODEL_OUTPUT NAMELIST [SPECIES]
# Exit 0 if the most recent required run of every model is present, else 1.

YMD="$1"
HH="$2"                       # not used for date math (mm_run_sites uses @Y@m@d only); kept for logging
MODEL_OUTPUT="$3"
NAMELIST="$4"
SPECIES="${5:-}"              # optional: only check models that provide this obs species

# Test:
# YMD="20261020"
# HH="12"
# MODEL_OUTPUT="/scratch3/BMC/acomp/Gonzalo.Ferrada/verif/mm-realtime/model_output"
# NAMELIST="/scratch3/BMC/acomp/Gonzalo.Ferrada/verif/mm-realtime/scripts/monet_namelist.all"
# SPECIES=aod_550nm

missing=0

while IFS=, read -r name mtype init run_len relday color marker lstyle rawspecies; do
  [[ -z ${name} || ${name} == \#* ]] && continue      # skip blank/commented lines

  # Optional species filter, same mod:obs/mod:obs parsing as mm_run_sites.sh
  if [[ -n ${SPECIES} ]]; then
    IFS=/ read -ra spc <<< "${rawspecies//:/\/}"
    provides=0
    for ((k=1; k<${#spc[@]}; k+=2)); do               # odd indices = obs species names
      [[ ${spc[k]} == "${SPECIES}" ]] && provides=1
    done
    (( provides )) || continue
  fi

  IFS=/ read -ra inits   <<< "${init}"                 # e.g. 00/06/12
  IFS=/ read -ra reldays <<< "${relday}"               # matching day offsets

  # Newest run among this model's (init, relday) pairs; YYYYMMDDHH compares as an integer
  latest=""
  for j in "${!inits[@]}"; do
    run=$(date -u -d "${YMD} - ${reldays[j]} days" +%Y%m%d)${inits[j]}
    [[ -z ${latest} || ${run} -gt ${latest} ]] && latest=${run}
  done

  f="${MODEL_OUTPUT}/${name}/${latest}/aqm_${name}_${latest}.nc"

  # -s: exists and non-empty; ncdump -h (if available) catches truncated/in-progress files
  if [[ -s ${f} ]] && { ! command -v ncdump >/dev/null || ncdump -h "${f}" >/dev/null 2>&1; }; then
    echo "OK      ${name} ${latest}"
  else
    echo "MISSING ${name} ${latest}: ${f}"
    missing=1
  fi
done < <(sed 1d "${NAMELIST}")                        # skip header, same as mm_run_sites.sh

echo "Cycle ${YMD}${HH}: $([[ ${missing} -eq 0 ]] && echo ready || echo not ready)"
exit ${missing}