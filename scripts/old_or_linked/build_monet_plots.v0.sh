#!/bin/bash -l
#SBATCH --account=acomp
#SBATCH --partition=u1-service
#SBATCH --time=03:30:00
#SBATCH -q batch
#SBATCH -n 1 
#SBATCH --mem-per-cpu=16G

module purge
module load imagemagick
set -x

# Construct some dates
YYYY=`date +%Y -d "${START_TIME}"`
MM=`date +%m -d "${START_TIME}"`
DD=`date +%d -d "${START_TIME}"`

YYYYMMDD=`date +"%Y%m%d" -d "${YYYY}${MM}${DD}"`
YESTERDAY=`date +"%Y%m%d" -d "${YYYY}${MM}${DD} -1 day"`      # Start of analysis 
TWODAYSAGO=`date +"%Y%m%d" -d "${YYYY}${MM}${DD} -2 days"`
TOMORROW=`date +"%Y%m%d" -d "${YYYY}${MM}${DD} +1 day"`

# Directories
echo "Building the MELODIES-MONET plots from the analysis performed on ${YYYYMMDD} for ${YESTERDAY} with forecast run on ${TWODAYSAGO}"
#
mkdir -p ${workdir}
cd ${plotdir}
#
# <model_type>_<species>_<platform>_f<col>.png
# Loop over the available species
if [[ `ls | wc -l` -gt 0 ]]; then
for ispecies in *
do
 if [[ "${ispecies}" == "folium" ]]; then
    continue
 else
  cd ${ispecies}
  if [[ `ls | wc -l` -gt 0 ]]; then
  for iplatform in *
  do
    cd ${iplatform}
    for iplot in {1..10}
    do
       echo "working on species=${ispecies}, platform=${iplatform}, plot=${iplot}"
       if [[ ${iplot} -eq 10 ]]; then
          nfigs=`ls stats*CONUS* | wc -l`
       else
          nfigs=`ls plot_grp${iplot}.*CONUS*.png | wc -l`
       fi
       if [[ ${nfigs} -eq 0 ]]; then
          continue
       else
       # First handle CONUS
       mkdir ${workdir}/full
       if [[ ${iplot} -eq 10 ]] ;then
#          magick montage -geometry 900x400+0+0 -tile 1x${nfigs} ${plotdir}/${ispecies}/${iplatform}/stats*CONUS*.png ${workdir}/full/${model_type}_${ispecies}_${iplatform}_f${iplot}.png
          cp ${plotdir}/${ispecies}/${iplatform}/stats*CONUS*.png ${workdir}/full/${model_type}_${ispecies}_${iplatform}_f${iplot}.png
       # elif [[ ${iplot} -eq 3 ]] && [[ "${ispecies}" == "aod_550nm" ]]; then
       elif [[ "${iplatform}" == "VIIRS" ]] && [[ "${ispecies}" == "aod_550nm" ]]; then
            # AOD spatial plot: copy at full resolution, no montage/resize
            cp ${plotdir}/${ispecies}/${iplatform}/plot_grp${iplot}.*CONUS*.png  ${workdir}/full/${model_type}_${ispecies}_${iplatform}_f0${iplot}.png
       else
          magick montage -geometry 900x400+0+0 -tile 1x${nfigs} ${plotdir}/${ispecies}/${iplatform}/plot_grp${iplot}.*CONUS*.png ${workdir}/full/${model_type}_${ispecies}_${iplatform}_f0${iplot}.png
       fi
       zip -j ${workdir}/full/files.zip ${workdir}/full/*.png
       fi

       # Now handle the EPA regions *(for airnow)
       if [[ "${iplatform}" == "airnow" ]]; then
       for r in $(seq 1 10)
       do
          if [[ ${r} -ne 10 ]]; then
             key1="R${r}"
             key2="r0${r}"
          else
             key1="R${r}"
	     key2="r${r}"
          fi
          mkdir -p ${workdir}/${key2} 
          if [[ ${iplot} -ne 10 ]] ;then
             nfigs=`ls plot_grp${iplot}.*epa_region.${key1}.*png | wc -l`
          else
             nfigs=`ls stats*epa_region.${key1}.*png | wc -l`
          fi
          if [[ ${nfigs} -eq 0 ]]; then
             continue
          else
            if [[ ${iplot} -eq 10 ]]; then
#               magick montage -geometry 900x400+0+0 -tile 1x${nfigs} ${plotdir}/${ispecies}/${iplatform}/stats*epa_region.${key1}.*.png ${workdir}/${key2}/${model_type}_${ispecies}_${key2}${iplatform}_f${iplot}.png
               cp  ${plotdir}/${ispecies}/${iplatform}/stats*epa_region.${key1}.*.png ${workdir}/${key2}/${model_type}_${ispecies}_${key2}${iplatform}_f${iplot}.png
            else
               magick montage -geometry 900x400+0+0 -tile 1x${nfigs} ${plotdir}/${ispecies}/${iplatform}/plot_grp${iplot}.*epa_region.${key1}.*png ${workdir}/${key2}/${model_type}_${ispecies}_${key2}${iplatform}_f0${iplot}.png
            fi
            zip -j ${workdir}/${key2}/files.zip ${workdir}/${key2}/*.png
          fi
       done # EPA Regions
       fi  # if airnow/for epa regions
    done # iplot
    cd ../
  done # iplatform
  fi
  fi
  cd ${plotdir}
done # ispecies
fi

# HTML files
cd ${workdir}
cp ${plotdir}/folium/*.html ${workdir}/full/
cd ${workdir}/full/
zip -j files.zip *.html


exit 0
