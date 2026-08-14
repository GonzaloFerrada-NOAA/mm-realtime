#!/bin/bash --login

module load hpss

hsi mkdir -p /5year/BMC/wrf-chem/aq_verification/${START_TIME}

htar -cvf /5year/BMC/wrf-chem/aq_verification/${START_TIME}/aq.nrt.verification.${START_TIME}.tar ${DIRTOARCHIVE}/*


