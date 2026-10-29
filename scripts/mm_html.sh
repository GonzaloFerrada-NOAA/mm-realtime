#!/bin/bash --login
#
# Build the verification dashboard: ONE self-contained html per cycle and model_type,
# from the MELODIES-MONET time-series CSVs (mm_run task) and the HMS fire text files.
#
# Environment (Rocoto XML):
#   START_TIME          cycle day, YYYYMMDD
#   MELODIES_MONET_DIR  main directory of the real-time system
#   model_type          regional_smoke | regional_chemistry | regional_aerosols | global | all
#   WORKDIR             working directory of this task
#   OBSDIR              observations of this cycle (not used by the dashboard)
#   SCRIPTS_DIR         real-time scripts (generate_dashboard.py, yaml_templates/)
#   PLOT_OUTPUT_DIR     <species>/<platform>/plot_grp1.timeseries.*.csv of this cycle
#   HMS_TXT_DIR         HMS fire text files (hms_fireYYYYMMDD.txt)
#   CONDA_ENV           conda environment with pandas + pyyaml
#
module load rdhpcs-conda
conda activate ${CONDA_ENV}
set -x

# Cycle 00Z of START_TIME; the dashboard shows START_TIME-24h .. START_TIME+24h
cycle=$(/bin/date -u -d "${START_TIME}" +"%Y-%m-%d 00:00")

# Paths without a trailing slash
plot_dir=${PLOT_OUTPUT_DIR%/}
hms_dir=${HMS_TXT_DIR%/}
out_dir=${plot_dir}/html                                  # same place as the old folium output
out_html=${out_dir}/fullhtml_sfc_regional_smoke.html
run_dir=${WORKDIR%/}
mkdir -p ${out_dir} ${run_dir}
cd ${run_dir}

# Fill the yaml template for this cycle / model_type
template=${SCRIPTS_DIR}/yaml_templates/html_dashboard.yaml
config=${run_dir}/dashboard.yaml
if [[ ! -f ${template} ]] ; then
    echo "FATAL: yaml template not found: ${template}"
    exit 1
fi
sed -e "s|__CYCLE__|${cycle}|g" \
    -e "s|__PLOT_OUTPUT_DIR__|${plot_dir}|g" \
    -e "s|__HMS_TXT_DIR__|${hms_dir}|g" \
    -e "s|__OUTPUT_HTML__|${out_html}|g" \
    ${template} > ${config}

# Build the html
python ${SCRIPTS_DIR}/generate_dashboard.py ${config}
status=$?
if [[ ${status} -ne 0 || ! -s ${out_html} ]] ; then
    echo "FATAL: generate_dashboard.py failed (exit ${status}) or ${out_html} is empty"
    exit 1
fi
chmod a+r ${out_html}                                       # readable by the web server

exit 0