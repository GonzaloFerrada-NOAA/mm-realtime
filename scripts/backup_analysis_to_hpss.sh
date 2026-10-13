#!/bin/bash --login

module load hpss

hsi mkdir -p /5year/BMC/wrf-chem/aq_verification_ursa/${START_TIME}

if [[ "${model_type}" == "regional_smoke" ]]; then
htar -cvf /5year/BMC/wrf-chem/aq_verification_ursa/${START_TIME}/aq.nrt.verification.${START_TIME}.tar ${DIRTOARCHIVE}/*
fi

htar -cvf /5year/BMC/wrf-chem/aq_verification_ursa/${START_TIME}/aq.nrt.verification.${model_type}.raw.${START_TIME}.tar ${DIRTOARCHIVE2}/*


