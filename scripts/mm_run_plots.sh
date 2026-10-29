#!/bin/bash
#==============================================================================
# mm_run_plots.sh -- MELODIES-MONET verification for ONE model_type/platform.
# Loops over all SPECIES of the platform, and for each over PLOT_TYPES.
# control.yaml is assembled from static templates in ${YAML_TEMPLATE_DIR};
# only cycle-dependent parts are generated:
#   - analysis dates/output dir      (@START_TIME@ @END_TIME@ @OUTPUT_DIR@)
#   - model block                    (which models have data this cycle)
#   - obs-model pairs / model names  (@DATA@ @MODEL_NAMES@)
#   - domain lists                   (@DOMAIN_TYPE@ @DOMAIN_NAME@)
#   - CSI thresholds                 (@CSI_THRESHOLDS@, from csi_thresholds.txt)
#
# Failure handling: each species and each plot type runs in its own subshell,
# so a crash (or 'exit') only ends that species/plot type; the rest continue.
#
# Environment (from Rocoto): START_TIME WORKDIR OBS_DIR PLOT_OUTPUT_DIR
#   SCRIPTS_DIR model_type OBS_PLATFORM NAMELIST CONDA_ENV
# Optional: YAML_TEMPLATE_DIR, MODEL_OUTPUT_DIR
#==============================================================================
# set -e
# export PS4='+ [$(date "+%Y-%m-%d %H:%M:%S")] ${LINENO}: '
# set -x

platform=${OBS_PLATFORM}
scriptsdir=${SCRIPTS_DIR}
output_directory=${PLOT_OUTPUT_DIR}
TEMPLATE_DIR=${YAML_TEMPLATE_DIR:-${SCRIPTS_DIR}/yaml_templates}
MODEL_OUTPUT_DIR=${MODEL_OUTPUT_DIR:-${MELODIES_MONET_DIR}/model_output}
PYTHON="${CONDA_ENV}/bin/python"
TOP_WORKDIR=${WORKDIR%/}                     # per-species workdirs go below this

PLOT_TYPES=( "ts_regional" "spatial_overlay" "spatial_bias" "boxplot" "taylor" "scorecard" "csi" "stats" )

# Species evaluated for each platform
case ${platform} in
    airnow)   SPECIES=( "PM2.5"  "PM10"  "OZONE"  "NO2"  "CO"  "TEMP" ) ;;
    openaq)   SPECIES=( "PM2.5"  "PM10"  "OZONE"  "NO2"  "CO" ) ;;
    aeronet)  SPECIES=( "aod_550nm" ) ;;
    ish)      SPECIES=( "vsb"  "ceiling" ) ;;
    ish-lite) SPECIES=( "temp"  "dew_pt_temp"  "wdir"  "ws"  "precip_1hr" ) ;;
    *)        echo "ERROR: unsupported platform ${platform}"; exit 1 ;;
esac
# read -ra SPECIES <<< "$(lookup ${SCRIPTS_DIR}/config.species "${platform}")"

if (( ${#SPECIES[@]} == 0 )); then
    echo "ERROR: unsupported platform ${platform}"
    exit 1
fi

case ${platform} in     # MONET driver script per platform
    airnow)   monet_py=melodies_monet_analysis.py ;;
    aeronet)  monet_py=melodies_monet_analysis.py ;;
    ish)      monet_py=Monet-analysis-example-plots-wrf-rapchemtest_ish.py ;;
    ish-lite) monet_py=Monet-analysis-example-plots-wrf-rapchemtest_ish-lite.py ;;
    openaq)   monet_py=melodies_monet_analysis.py ;;
esac

mdl_lw=1.5 # model line width in plots

#------------------------------------------------------------------------------
# Helpers
#------------------------------------------------------------------------------
# fill FILE TOKEN VALUE : replace every @TOKEN@ in FILE with VALUE
fill() {
  local v=${3//\\/\\\\}; v=${v//&/\\&}; v=${v//|/\\|}   # escape sed specials
  sed -i "s|@${2}@|${v}|g" "$1"
}
# lookup FILE KEY : print everything after KEY on its line (empty if not found)
lookup() {
  awk -v k="$2" '$1==k { $1=""; sub(/^ +/,""); print; exit }' "$1"
}
# join SEP ITEMS... : join items with SEP
join() { local IFS="$1"; shift; echo "$*"; }

# record SPECIES PLOT_TYPE STATUS : append one line to the status file.
# Subshells can't change parent arrays, so results are passed through a file.
STATUS_FILE=${TOP_WORKDIR}/plot_status.txt
record() { printf "%-12s %-18s %s\n" "$1" "$2" "$3" >> ${STATUS_FILE}; }

#------------------------------------------------------------------------------
# Environment
#------------------------------------------------------------------------------
# module load rdhpcs-conda    # GAF
# conda activate ${CONDA_ENV} # GAF
module load nco

#------------------------------------------------------------------------------
# Dates: analysis window is day N-1 00Z to day N+1 00Z
#------------------------------------------------------------------------------
todays_date=${START_TIME}   # YYYYMMDD
start_time_yaml=$(date -u -d "${todays_date} - 1 day" +%Y-%m-%d-00:00:00)
end_time_yaml=$(date -u -d "${todays_date} + 1 day" +%Y-%m-%d-00:00:00)

#------------------------------------------------------------------------------
# Checks that apply to ALL species (platform-level: fail once)
#------------------------------------------------------------------------------
for f in analysis.yaml obs/${platform}.yaml; do
    if [[ ! -r ${TEMPLATE_DIR}/${f} ]]; then
        echo "ERROR: missing template ${TEMPLATE_DIR}/${f}"
        exit 1
    fi
done

obsfile="${OBS_DIR}/test5.${platform}.${todays_date}.nc"
if [[ ! -e ${obsfile} ]]; then
    echo "NO ${platform} DATA (${obsfile}), nothing to plot..."
    exit 1
fi

mkdir -p ${TOP_WORKDIR} ${output_directory}
: > ${STATUS_FILE}                           # start with an empty status file

#==============================================================================
# SPECIES loop. Each species runs in a subshell: an 'exit' inside (missing
# template, no model data, crash) only ends THIS species.
#==============================================================================
for species in "${SPECIES[@]}"; do

  echo ""
  echo "##################################################################"
  echo "### ${species} (${platform}, ${model_type}): starting $(date -u)"
  echo "##################################################################"

  (
    WORKDIR=${TOP_WORKDIR}/${species}        # isolate files per species
    mkdir -p ${WORKDIR}
    cd ${WORKDIR} || exit 1

    if [[ ! -r ${TEMPLATE_DIR}/variables/${species}.yaml ]]; then
      echo "ERROR: missing template ${TEMPLATE_DIR}/variables/${species}.yaml"
      record "${species}" "ALL" "FAILED (no variables template)"
      exit 1
    fi

    #--------------------------------------------------------------------------
    # Model block: one entry per model/init time that has data and the variable.
    # Namelist columns: model_name,model_type,init,run_len,relative_day,color,
    #   marker,linestyle,species   ('/' separates init times; species = mod:obs/mod:obs)
    #--------------------------------------------------------------------------
    model_block=${WORKDIR}/model_block.yaml
    echo "model:" > ${model_block}
    pairs=()                                 # 'platform_label' entries for data:
    models=()                                # 'label' entries for model_name_list:

    while IFS=, read -r name mtype init run_len relday color marker lstyle rawspecies; do
      IFS=/ read -ra inits   <<< "${init}"  # split multi-init fields on '/'
      IFS=/ read -ra reldays <<< "${relday}"
      IFS=/ read -ra colors  <<< "${color}"
      IFS=/ read -ra markers <<< "${marker}"
      IFS=/ read -ra lstyles <<< "${lstyle}"
      IFS=/ read -ra spc     <<< "${rawspecies//:/\/}"   # mod,obs,mod,obs,...

      # find the model variable mapped to this obs species
      modvar=""
      for ((k=0; k<${#spc[@]}; k+=2)); do
        [[ ${spc[k+1]} == "${species}" ]] && modvar=${spc[k]}
      done
      [[ -z ${modvar} ]] && continue         # model doesn't provide this species

      for j in "${!inits[@]}"; do
        ymd=$(date -u -d "${todays_date} - ${reldays[j]} days" +%Y%m%d)
        run=${ymd}${inits[j]}
        testfile=${MODEL_OUTPUT_DIR}/${name}/${run}/aqm_${name}_${run}.nc

        if [[ ! -r ${testfile} ]]; then
          echo "Missing ${testfile}, skipping ${name} ${inits[j]}Z"; continue
        fi
        if ! ncdump -hv ${modvar} ${testfile} > /dev/null 2>&1; then
          echo "Variable ${modvar} not in ${testfile}, skipping ${name}"; continue
        fi

        label=${name}_${ymd}-${inits[j]}Z
        pairs+=("'${platform}_${label}'")
        models+=("'${label}'")
        echo "Using model ${label}"

        {                                    # append this model's YAML entry
          echo "  ${label}:"
          echo "    files: ${testfile}"
          echo "    mod_type: '${mtype}'"
          case ${mtype} in
            hrrr|wrfchem) printf "    mod_kwargs:\n      surf_only_nc: True\n" ;;
            rrfs|raqms)   printf "    mod_kwargs:\n      surf_only: True\n" ;;
          esac
          [[ ${platform} == airnow ]] && echo "    projection: None"
          echo "    radius_of_influence: 12000 #meters"
          echo "    mapping: #model species name : obs species name"
          echo "      ${platform}:"
          echo "        ${modvar}: \"${species}\""
          echo "    plot_kwargs:"
          echo "      color: '${colors[j]}'"
          echo "      marker: '${markers[j]}'"
          echo "      linestyle: '${lstyles[j]}'"
          echo "      markersize: 8"
          echo "      linewidth: ${mdl_lw}"
        } >> ${model_block}
      done
    done < <(sed 1d ${scriptsdir}/${NAMELIST})   # process substitution keeps arrays

    # No model provides this species (e.g. NO2 for a smoke-only namelist): skip
    if (( ${#pairs[@]} == 0 )); then
      echo "NO model data for ${species} on ${todays_date}, skipping species"
      record "${species}" "ALL" "SKIPPED (no model data)"
      exit 0
    fi

    # Base YAML shared by every plot type: analysis + model + obs + variables
    base_yaml=${WORKDIR}/base.control.yaml
    cat ${TEMPLATE_DIR}/analysis.yaml \
        ${model_block} \
        ${TEMPLATE_DIR}/obs/${platform}.yaml \
        ${TEMPLATE_DIR}/variables/${species}.yaml > ${base_yaml}
    fill ${base_yaml} START_TIME "${start_time_yaml}"
    fill ${base_yaml} END_TIME   "${end_time_yaml}"
    fill ${base_yaml} OUTPUT_DIR "${output_directory}"

    data_list=$(join , "${pairs[@]}")
    model_list=$(join , "${models[@]}")
    csi_thr=$(lookup ${TEMPLATE_DIR}/csi_thresholds.txt "${species}")

    # Regional domains: CONUS + EPA regions (AirNow only)
    rgn_names=("'CONUS'"); rgn_types=("'isinconus'")
    if [[ ${platform} == airnow ]]; then
      regions=$(lookup ${TEMPLATE_DIR}/epa_regions.txt "${species}")
      for r in ${regions:-R1 R2 R3 R4 R5 R6 R7 R8 R9 R10}; do
        rgn_names+=("'${r}'"); rgn_types+=("'epa_region'")
      done
    fi

    #--------------------------------------------------------------------------
    # PLOT_TYPE loop (nested subshell per plot type)
    #--------------------------------------------------------------------------
    for plot_type in "${PLOT_TYPES[@]}"; do

    #   if [[ ! -e ${SCRIPTS_DIR}/task_list_files/do_${model_type}_${species}_${platform}_${plot_type}.txt ]]; then
    #     echo "=== ${species} ${plot_type}: not enabled, skipping"; continue
    #   fi
      if [[ ! -r ${TEMPLATE_DIR}/plots/${plot_type}.yaml ]]; then
        echo "=== ${species} ${plot_type}: no template"
        record "${species}" "${plot_type}" "FAILED (no plot template)"
        continue
      fi
      echo "=== ${species} ${plot_type}: starting $(date -u)"

      (
        workdir=${WORKDIR}/${plot_type}
        mkdir -p ${workdir}
        cd ${workdir} || exit 1
        rm -f tmp.control.yaml* control.yaml
        ln -sf ${obsfile} test5.nc

        dnames=("${rgn_names[@]}"); dtypes=("${rgn_types[@]}")

        # Assemble control.yaml = base + plot template, then fill tokens
        YAML=tmp.control.yaml.${species}.${todays_date}.${plot_type}
        cat ${base_yaml} ${TEMPLATE_DIR}/plots/${plot_type}.yaml > ${YAML}
        fill ${YAML} DOMAIN_TYPE "$(join , "${dtypes[@]}")"
        fill ${YAML} DOMAIN_NAME "$(join , "${dnames[@]}")"
        fill ${YAML} DATA        "${data_list}"
        fill ${YAML} MODEL_NAMES "${model_list}"
        if [[ -n ${csi_thr} ]]; then
          fill ${YAML} CSI_THRESHOLDS "${csi_thr}"
        else
          sed -i '/@CSI_THRESHOLDS@/d' ${YAML}   # species without thresholds
        fi
        ln -sf ${YAML} control.yaml

        ${PYTHON} ${scriptsdir}/${monet_py} ${platform} ${plot_type}  # subshell exit status = this # GAF
      )
      rc=$?
      if (( rc != 0 )); then
        echo "=== ${species} ${plot_type}: FAILED (exit ${rc}), continuing"
        record "${species}" "${plot_type}" "FAILED (exit ${rc})"
      else
        echo "=== ${species} ${plot_type}: done $(date -u)"
        record "${species}" "${plot_type}" "SUCCESS"
      fi

    done # PLOT_TYPES
  )
  rc=$?

  # Species subshell died before recording anything (unexpected crash)
  if (( rc != 0 )) && ! grep -q "^${species} " ${STATUS_FILE}; then
    record "${species}" "ALL" "FAILED (exit ${rc})"
  fi
  echo "### ${species}: finished $(date -u)"

done # SPECIES

# -------------------------------------------------------
# Summary report (from the status file)
# -------------------------------------------------------
n_success=$(grep -c ' SUCCESS$'  ${STATUS_FILE})
n_failed=$( grep -c ' FAILED'    ${STATUS_FILE})
n_skipped=$(grep -c ' SKIPPED'   ${STATUS_FILE})

echo ""
echo "=========================================================="
echo "     SUMMARY: ${model_type} / ${platform} / ${todays_date}"
echo "=========================================================="
printf "%-12s %-18s %s\n" "SPECIES" "PLOT_TYPE" "STATUS"
echo "----------------------------------------------------------"
cat ${STATUS_FILE}
echo "=========================================================="
echo "Succeeded: ${n_success}   Failed: ${n_failed}   Skipped: ${n_skipped}"
echo "=========================================================="

# -------------------------------------------------------
# Final Rocoto task exit status: DEAD only if everything attempted failed
# -------------------------------------------------------
if (( n_failed > 0 && n_success == 0 )); then
    echo "All attempted plots failed"
    exit 1
fi
if (( n_failed > 0 )); then
    echo "Some plots failed (see summary above)"
fi
exit 0