import sys
import cv2

outdir=sys.argv[1]
videofile=outdir+"/pollenmapvideo.mp4"

vidcap = cv2.VideoCapture(videofile)
success,image = vidcap.read()
count = 61 # Pollen.com images start at January 21
while success:
  if count < 10:
    st = "00"+str(count)
  elif count > 10 and count < 100:
    st = "0"+str(count)
  elif count > 100:
    st = str(count)
#  cv2.imwrite("frame%d.png" % count, image)     # save frame as JPEG file      
  cv2.imwrite(outdir + "/" + "PollenDotCom_"+st+".png",image)
  success,image = vidcap.read()
  print('Read a new frame: ', success)
  count += 1
