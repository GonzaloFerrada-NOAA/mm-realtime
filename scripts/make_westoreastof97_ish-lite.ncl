begin
;
START_TIME=getenv("START_TIME")
;
f=addfile("test5.ish-lite."+START_TIME+".nc","w")
;
siteid=f->siteid
longitude=f->longitude
latitude=f->latitude
;
westoreastof97=siteid
isinconus=siteid
;
westoreastof97 = where(longitude .le. -97.0,"west","east")
isinconus = where(longitude .le. -67 .and. longitude .ge. -125. .and. latitude .le. 49. .and. latitude .ge. 25.,"CONUS","NOCON")
;
f->westoreastof97=westoreastof97
f->isinconus=isinconus
;
end
