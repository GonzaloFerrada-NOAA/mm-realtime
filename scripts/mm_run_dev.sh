#!/bin/bash
#==============================================================================
# mm_run.sh -- MELODIES-MONET verification for ONE model_type/species/platform.
# Loops over PLOT_TYPES inside the job. control.yaml is assembled from static
# templates in ${YAML_TEMPLATE_DIR}; only cycle-dependent parts are generated:
#   - analysis dates/output dir      (@START_TIME@ @END_TIME@ @OUTPUT_DIR@)
#   - model block                    (which models have data this cycle)
#   - obs-model pairs / model names  (@DATA@ @MODEL_NAMES@)
#   - domain lists                   (@DOMAIN_TYPE@ @DOMAIN_NAME@; sites are daily)
#   - CSI thresholds                 (@CSI_THRESHOLDS@, from csi_thresholds.txt)
#
# Environment (from Rocoto): START_TIME WORKDIR OBS_DIR PLOT_OUTPUT_DIR
#   SCRIPTS_DIR model_type SPECIES_TO_VERIFY OBS_PLATFORM namelist CONDA_ENV
# Optional: YAML_TEMPLATE_DIR, MODEL_OUTPUT_DIR
#==============================================================================

# Test:
START_TIME="20260926"
HH="12"
model_type="regional_smoke"
SPECIES_TO_VERIFY="PM2.5"
OBS_PLATFORM="airnow"
namelist="monet_namelist.${model_type}"
CONDA_ENV="/scratch4/BMC/acomp/cheMPAS-Fire/envs/melodies-monet-nrt-vx"
MELODIES_MONET_DIR="/scratch4/BMC/acomp/cheMPAS-Fire/realtime/melodies-monet"
SCRIPTS_DIR="${MELODIES_MONET_DIR}/scripts"
OBS_DIR="${MELODIES_MONET_DIR}/obs/${START_TIME}${HH}/"
# WORKDIR="${MELODIES_MONET_DIR}/run/${START_TIME}${HH}/${model_type}/${SPECIES_TO_VERIFY}_${OBS_PLATFORM}/"
WORKDIR="/scratch3/BMC/acomp/Gonzalo.Ferrada/verif/tmp/"
# PLOT_OUTPUT_DIR="${MELODIES_MONET_DIR}/plot_output/${START_TIME}${HH}/${model_type}/${SPECIES_TO_VERIFY}/${OBS_PLATFORM}/"
PLOT_OUTPUT_DIR="${WORKDIR}/"





species=${SPECIES_TO_VERIFY}
platform=${OBS_PLATFORM}
scriptsdir=${SCRIPTS_DIR}
output_directory=${PLOT_OUTPUT_DIR}
TEMPLATE_DIR=${YAML_TEMPLATE_DIR:-${SCRIPTS_DIR}/yaml_templates}
MODEL_OUTPUT_DIR=${MODEL_OUTPUT_DIR:-/scratch4/BMC/acomp/cheMPAS-Fire/realtime/melodies-monet/model_output}
PYTHON="${CONDA_ENV}/bin/python"

# PLOT_TYPES=( "ts_regional" "ts_site" "spatial_overlay" "spatial_bias" "boxplot" "taylor" "scorecard" "csi" "stats" ) # GAF
# PLOT_TYPES=( "ts_regional" "spatial_overlay" "spatial_bias" "boxplot" "taylor" "scorecard" "csi" "stats" )
PLOT_TYPES=( "ts_site" )
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
# Checks that apply to ALL plot types (fail/skip once, not 9 times)
#------------------------------------------------------------------------------
for f in analysis.yaml obs/${platform}.yaml variables/${species}.yaml; do
	if [[ ! -r ${TEMPLATE_DIR}/${f} ]]; then
		echo "ERROR: missing template ${TEMPLATE_DIR}/${f}"
		exit 1
	fi
done

case ${platform} in     # MONET driver script per platform
    airnow)   monet_py=Monet-analysis-example-plots-wrf-rapchemtest_dev.py ;;
    aeronet)  monet_py=Monet-analysis-example-plots-wrf-rapchemtest_aeronet.py ;;
    ish)      monet_py=Monet-analysis-example-plots-wrf-rapchemtest_ish.py ;;
    ish-lite) monet_py=Monet-analysis-example-plots-wrf-rapchemtest_ish-lite.py ;;
    openaq)   monet_py=Monet-analysis-example-plots-wrf-rapchemtest_openaq.py ;;
    *)        echo "ERROR: unsupported platform ${platform}"; exit 1 ;;
esac

obsfile="${OBS_DIR}/test5.${platform}.${todays_date}.nc"
if [[ ! -e ${obsfile} ]]; then
    echo "NO ${platform} DATA (${obsfile}), nothing to plot..."
    exit 0
fi

mkdir -p ${WORKDIR} ${output_directory}
cd ${WORKDIR} || exit 1

#------------------------------------------------------------------------------
# Model block: one entry per model/init time that has data and the variable.
# Namelist columns: model_name,model_type,init,run_len,relative_day,color,
#   marker,linestyle,species   ('/' separates init times; species = mod:obs/mod:obs)
#------------------------------------------------------------------------------
model_block=${WORKDIR}/model_block.yaml
echo "model:" > ${model_block}
pairs=()                                     # 'platform_label' entries for data:
models=()                                    # 'label' entries for model_name_list:

while IFS=, read -r name mtype init run_len relday color marker lstyle rawspecies; do
  IFS=/ read -ra inits   <<< "${init}"      # split multi-init fields on '/'
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
  [[ -z ${modvar} ]] && continue             # model doesn't provide this species

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

    {                                        # append this model's YAML entry
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
done < <(sed 1d ${scriptsdir}/${namelist})   # process substitution keeps arrays

if (( ${#pairs[@]} == 0 )); then
  echo "NO model data for ${species} on ${todays_date}, nothing to plot"
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

#------------------------------------------------------------------------------
# Plot-type loop. Each iteration runs in a subshell: an 'exit' inside only
# ends that plot type, and a failure doesn't stop the rest.
#------------------------------------------------------------------------------
failed=()

for plot_type in "${PLOT_TYPES[@]}"; do

  if [[ ! -e ${SCRIPTS_DIR}/task_list_files/do_${model_type}_${species}_${platform}_${plot_type}.txt ]]; then
    echo "=== ${plot_type}: not enabled, skipping"; continue
  fi
  if [[ ! -r ${TEMPLATE_DIR}/plots/${plot_type}.yaml ]]; then
    echo "=== ${plot_type}: no template, skipping"; failed+=("${plot_type}"); continue
  fi
  echo "=== ${plot_type}: starting $(date -u)"

  (
    workdir=${WORKDIR}/${plot_type}
    mkdir -p ${workdir}
    cd ${workdir} || exit 1
    rm -f tmp.control.yaml* control.yaml
    ln -sf ${obsfile} test5.nc

    # Domains: sites for ts_site, regions for everything else
    if [[ ${plot_type} == ts_site ]]; then
      case ${platform} in
        aeronet)        site_py=site_analysis_aeronet.py ;;
        airnow)         site_py=site_analysis_airnow.py ;;
        ish|ish-lite)   site_py=site_analysis_ish.py ;;
        openaq)         site_py=site_analysis_openaq.py ;;
      esac
      ${PYTHON} ${scriptsdir}/${site_py} ${species} > sitefile.txt || exit 1 # GAF
      readarray -t dnames < sitefile.txt     # site IDs, already quoted
      cp sitefile.txt ${OBS_DIR}/sitefile.txt.${species}.${platform}.${todays_date}
      stype="'siteid'"; [[ ${platform} == airnow ]] && stype="'site'"
      dtypes=(); for s in "${dnames[@]}"; do dtypes+=("${stype}"); done
    else
      dnames=("${rgn_names[@]}"); dtypes=("${rgn_types[@]}")
    fi

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

    do_stats=0; [[ ${plot_type} == stats ]] && do_stats=1
    echo "${PYTHON} ${scriptsdir}/${monet_py} ${do_stats} ${plot_type}"
    ${PYTHON} ${scriptsdir}/${monet_py} ${do_stats} ${plot_type}  # subshell exit status = this # GAF
  )
  rc=$?
  if (( rc != 0 )); then
    echo "=== ${plot_type}: FAILED (exit ${rc}), continuing"
    failed+=("${plot_type}")
  else
    echo "=== ${plot_type}: done $(date -u)"
  fi

done # PLOT_TYPES

# Task shows DEAD in rocotostat if any plot type failed
if (( ${#failed[@]} > 0 )); then
  echo "Failed plot types: ${failed[*]}"
  exit 1
fi
exit 0