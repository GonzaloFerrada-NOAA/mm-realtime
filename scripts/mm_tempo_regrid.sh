#!/bin/bash
#### sbatch --partition=u1-service --account=gsd-fv3-test --nodes=1 --time=1:00:00 --qos=batch --mem=50G mm_aggregate_tempo.sh
#### sbatch --partition=u1-service --account=gsd-fv3-test --nodes=1 --time=1:00:00 --qos=batch --mem=50G mm_aggregate_tempo.sh

set -e
export PS4='+ [$(date "+%Y-%m-%d %H:%M:%S")] ${LINENO}: '
set -x

# Test: # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #
# export START_TIME="20260908"
### export TEMPO_DIR=/public/data/grids/nesdis/tempo_aod/${START_TIME}
# export TEMPO_DIR="/scratch3/BMC/acomp/Gonzalo.Ferrada/verif/realtime/obs/tempo/${START_TIME}"
# export PATH_OUT="/scratch3/BMC/acomp/Gonzalo.Ferrada/verif/realtime/obs/tempo"
# export SCRIPTS_DIR="/scratch3/BMC/acomp/Gonzalo.Ferrada/verif/realtime/scripts"
# export CONDA_ENV="/scratch4/BMC/acomp/cheMPAS-Fire/envs/melodies-monet-nrt-vx"
# # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #

source ${SCRIPTS_DIR}/tools/workflow_tools.sh

# Redirect env variables for tempo agg script:
export TEMPO_FILE_OUT="${PATH_OUT}/tempo_aggregated_hourly_0p1deg_${START_TIME}00.nc"

ismkdir "${PATH_OUT}"

PYTHON="${CONDA_ENV}/bin/python"
SCRIPT="${SCRIPTS_DIR}/tempo_aggregation_uniform_grid.py"

# Run code:
srun --export=ALL --ntasks=1 --cpus-per-task=1 --mem=0 "${PYTHON}" -u "${SCRIPT}"
# "${PYTHON}" -u "${SCRIPT}"

checkstatus

isfile ${TEMPO_FILE_OUT}

exit 0

