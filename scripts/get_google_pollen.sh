#!/bin/bash

YYYY=`date +%Y`
MM=`date +%m`
DD=`date +%d`

YYYYMMDD=${YYYY}${MM}${DD}
datestr=${YYYYMMDD}

cycleHH="00"

meiyudir=/wrk/csd4/rahmadov/RAP-Chem/google_pollen/${YYYYMMDD}${cycleHH}

mkdir -p ${meiyudir}

cd ${meiyudir}

rm -f *.png

zoom=5

for y in $(seq 9 14)
do
for x in $(seq 3 11)
do
if [[ $x -lt 10 ]]; then
  xstr="0"$x
else
  xstr=$x
fi
if [[ $y -lt 10 ]]; then
  ystr="0"$y
else
  ystr=$y
fi
curl -X 'GET' "https://pollen.googleapis.com/v1/mapTypes/TREE_UPI/heatmapTiles/${zoom}/${x}/${y}?key=AIzaSyCXaZY5moJdjzPbFrWrGNmiAj5t_BtL87E" >> TREE_${ystr}_${xstr}.png
curl -X 'GET' "https://pollen.googleapis.com/v1/mapTypes/GRASS_UPI/heatmapTiles/${zoom}/${x}/${y}?key=AIzaSyCXaZY5moJdjzPbFrWrGNmiAj5t_BtL87E" >> GRASS_${ystr}_${xstr}.png
curl -X 'GET' "https://pollen.googleapis.com/v1/mapTypes/WEED_UPI/heatmapTiles/${zoom}/${x}/${y}?key=AIzaSyCXaZY5moJdjzPbFrWrGNmiAj5t_BtL87E" >> WEED_${ystr}_${xstr}.png


done
done
#nyou ctgy betq ccwo
montage WEED*.png -tile 9x6 -geometry +0+0 WEE_google_$datestr.png
montage TREE*.png -tile 9x6 -geometry +0+0 TRE_google_$datestr.png
montage GRASS*.png -tile 9x6 -geometry +0+0 GRA_google_$datestr.png
