#!/bin/bash --login
module load hpss
source ${MELODIES_MONET_DIR}/scripts/tools/workflow_tools.sh

TARGET_DIR="/5year/BMC/wrf-chem/aq_verification_ursa/${START_TIME}"
TARGET_TAR="aq.nrt.verification.${START_TIME}.tar"

cd ${MELODIES_MONET_DIR}

tar --format=posix -cvf ${TARGET_TAR} \
    model_output/*/${START_TIME}* \
    plot_output/${START_TIME}* \
    toweb/${START_TIME}* \
    logs/${START_TIME}*

checkstatus

# Create target directory:
hsi mkdir -p "${TARGET_DIR}"
checkstatus

# Store files:
hsi "put ${TARGET_TAR} : ${TARGET_DIR}/${TARGET_TAR}"
checkstatus

rm -f ${TARGET_TAR}

echo "done!"

exit 0
