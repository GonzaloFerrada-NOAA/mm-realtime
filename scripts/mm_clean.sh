#!/bin/bash


DELETE_MODELS=1
DELETE_RAW_PLOTS=1
DELETE_TOWEB_PLOTS=1
DELETE_OBS=1
DELETE_RUN=1
DELETE_LOGS=1

DATE1=$( date -d "${START_TIME} - 14 days" +%Y%m%d )
DATE2=$( date -d "${START_TIME} - 7 days" +%Y%m%d )


until [[ $DATE1 -ge $DATE2 ]]; do
    
    [[ ${DELETE_MODELS} -eq 1 ]] && rm -rf ${MODEL_OUTPUT_DIR}/*/${DATE1}*
    
    [[ ${DELETE_RAW_PLOTS} -eq 1 ]] && rm -rf ${RAW_PLOT_DIR}/${DATE1}*
    
    [[ ${DELETE_TOWEB_PLOTS} -eq 1 ]] && rm -rf ${TOWEB_DIR}/${DATE1}*
    
    [[ ${DELETE_OBS} -eq 1 ]] && rm -rf ${OBS_DIR}/${DATE1}*
    
    [[ ${DELETE_RUN} -eq 1 ]] && rm -rf ${RUN_DIR}/${DATE1}*
    
    [[ ${DELETE_LOGS} -eq 1 ]] && rm -rf ${LOGS_DIR}/${DATE1}*; rm -f ${LOGS_DIR}/workflow_melodies-monet.${DATE1}*.log
    
    DATE1=$( date -d "${DATE1} + 1 day" +%Y%m%d )
    
done

echo "done!"

exit 0


