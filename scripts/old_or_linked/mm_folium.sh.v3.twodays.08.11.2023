#!/bin/bash --login
#
DATE=/bin/date
#
#
module load rdhpcs-conda
conda activate ${CONDA_ENV}
module load imagemagick
set -x
todays_date=${START_TIME}
#
# Today variables 
YYYY_today=`${DATE} +%Y -d "${todays_date}"`
MM_today=`${DATE} +%m -d "${todays_date}"`
DD_today=`${DATE} +%d -d "${todays_date}"`
HH_today=`${DATE} +%H -d "${todays_date}"`
#
# Yesterday Variables
YYYY_ytday=`${DATE} +%Y -d "${todays_date} - 24 hours"`
MM_ytday=`${DATE} +%m -d "${todays_date} - 24 hours"`
DD_ytday=`${DATE} +%d -d "${todays_date} - 24 hours"`
#
# Yesterday Variables
YYYY_tomorrow=`${DATE} +%Y -d "${todays_date} + 24 hours"`
MM_tomorrow=`${DATE} +%m -d "${todays_date} + 24 hours"`
DD_tomorrow=`${DATE} +%d -d "${todays_date} + 24 hours"`
#
# Dates also need to be for yesterday
start_time_reformat=`${DATE} -d "${YYYY_ytday}${MM_ytday}${DD_ytday}" +%Y-%m-%d`
end_time_reformat=`${DATE} -d "${YYYY_tomorrow}${MM_tomorrow}${DD_tomorrow}" +%Y-%m-%d`
#
output_directory=${PLOT_OUTPUT_DIR}
scriptsdir=${SCRIPTS_DIR}
#
cd ${output_directory}
# Remove any old plots
#
if [[ ${remove_old_converted_images} -eq 1 ]] ; then
  rm -f *resized.png
  rm -f *.webp
fi
#
#
# Create a directory for folium
mkdir folium
cd folium
cp ${scriptsdir}/folium_site_map.py .
#
# Link the obs files and site files
#ln -sf ${OBSDIR}/test5* .
#ln -sf ${OBSDIR}/*.json .
#ln -sf ${OBSDIR}/sitefile* .
## Link the timeseries plots (plot_grp1)
#ln -sf ${PLOT_OUTPUT_DIR}/*/*/plot_grp1* .
#
python folium_site_map.py ${start_time_reformat} ${end_time_reformat} ${todays_date} ${model_type} ${PLOT_OUTPUT_DIR} ${OBSDIR}
#
exit 0
