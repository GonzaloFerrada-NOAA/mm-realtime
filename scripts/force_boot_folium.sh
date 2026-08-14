#!/bin/bash --login
#SBATCH --account=acomp
#SBATCH --partition=u1-compute
#SBATCH --time=00:05:00
#SBATCH -n 1
#SBATCH -q batch


d=`date -d "-2 days" +%Y%m%d`

cd /home/Jordan.Schnell/xmls/

rocotoboot -w melodies-monet.verification.xml -d melodies-monet.verification.db -c ${d}1200 -m mm_folium
