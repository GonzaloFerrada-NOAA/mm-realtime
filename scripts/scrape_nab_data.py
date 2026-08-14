#!/usr/bin/env python
# coding: utf-8

from datetime import datetime
import time
from selenium import webdriver     # 4.22.0
from selenium.webdriver.chrome.options import Options
import numpy as np
import pandas as pd

current_date = datetime.now()

base_url = 'http://pollen.aaaai.org/#/'
username = 'jordan.schnell@noaa.gov'
xpath_first_login_button  = '//*[@id="content"]/section/div/div/div/div/div/div[1]/div[2]/div[1]/div/button[2]'
xpath_username_field      = '//*[@id="username"]'
xpath_password_field      = '//*[@id="password"]'
xpath_second_login_button = '//*[@id="authModal___BV_modal_body_"]/div/div[1]/div[1]/form/button'
month_names = ("January", "Februrary", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December")
month_names_length = (7, 9, 5, 5, 3, 4, 4, 6, 9, 7, 8, 8)


options = Options()
options.binary_location = "/usr/bin/chromium-browser"
options.add_argument('--headless')
options.add_argument('--disable-gpu')
driver = webdriver.Chrome(options=options)
driver.get(base_url)
time.sleep(3)
page = driver.page_source
# This is returning everything we need
# Get the log-in button and click it
first_login_button = driver.find_element("xpath",xpath_first_login_button)
# Wait for the page load
time.sleep(2)
# Click it
first_login_button.click()
# Wait...
time.sleep(2)


username_field = driver.find_element("xpath",xpath_username_field) #"ID", "username")
password_field = driver.find_element("xpath",xpath_password_field) #"_BVID_27")
username_field.send_keys(username)
password_field.send_keys(password)
second_login_button = driver.find_element("xpath",xpath_second_login_button)
time.sleep(1)
second_login_button.click()
time.sleep(5)
# Now we are logged in!!
# First set up some empty arrays to hold the latest data
nsites = 44
tree_pollen  = np.zeros((nsites,1))
grass_pollen = np.zeros((nsites,1))
weed_pollen  = np.zeros((nsites,1))
mold         = np.zeros((nsites,1))
dates        = np.zeros((nsites,3))
names        = []
# Now we want to loop through each of the sites in My NAB and
# Grab the date associated with the count
# Grab the three pollen counts and the mold count
# Example relative xpaths of the 1st-3rd stations:

for isite in range(nsites):
  dates_element = driver.find_element("xpath",'//*[@id="content"]/section/div/div/div/div/div/div[1]/div[2]/div[1]/div/div/div/div['+str(isite+1)+']/div[1]/div[2]/h3').text
  dates_element_pytime = datetime.strptime(dates_element,'%B %d, %Y')
  # First site name xpath: /html/body/main/section/div/div/div/div/div/div[1]/div[2]/div[1]/div/div/div/div[1]/div[1]/div[1]/h3/a
  # 2nd   site name xpath: /html/body/main/section/div/div/div/div/div/div[1]/div[2]/div[1]/div/div/div/div[2]/div[1]/div[1]/h3/a
  names.append(driver.find_element("xpath",'//*[@id="content"]/section/div/div/div/div/div/div[1]/div[2]/div[1]/div/div/div/div['+str(isite+1)+']/div[1]/div[1]/h3/a').text)
  dates[isite,0] = dates_element_pytime.year
  dates[isite,1] = dates_element_pytime.month
  dates[isite,2] = dates_element_pytime.day
  for itype in range(3): # Here we loop over Trees, Weeds, Grass, Mold
    pollen_type = driver.find_element("xpath",'//*[@id="content"]/section/div/div/div/div/div/div[1]/div[2]/div[1]/div/div/div/div['+str(isite+1)+']/div[2]/div/div['+str(itype+1)+']/div[1]/h4').text
    pollen_count = driver.find_element("xpath",'//*[@id="content"]/section/div/div/div/div/div/div[1]/div[2]/div[1]/div/div/div/div['+str(isite+1)+']/div[2]/div/div['+str(itype+1)+']/div[3]/div/div[2]').text
    if not pollen_count: # check to make sure there is a valid count, otherwise fill with -999
      pollen_count = "-999"
    if pollen_type == "Trees":
      tree_pollen[isite] = float(pollen_count)
    elif pollen_type == "Weeds":
      weed_pollen[isite] = float(pollen_count)
    elif pollen_type == "Grass":
      grass_pollen[isite] = float(pollen_count)
    else:
      print("Undetermined count type: " + str(pollen_type))

year_str = str(current_date.year)
if current_date.month < 10:
   month_str = "0" + str(current_date.month)
else:
   month_str = str(current_date.month)
if current_date.day < 10:
   day_str   = "0" + str(current_date.day)
else:
   day_str   = str(current_date.day)
outfile_name = 'scraped_pollen_data_' + year_str + month_str + day_str + '.csv'
with open(outfile_name,'w') as file:
    file.write("site_name|Year|Month|Day|Tree|Weed|Grass")
    file.write('\n')
    for isite in range(nsites):
        file.write(str(names[isite]) + '|')
        file.write(str(dates[isite,0].astype('int')) +'|')
        file.write(str(dates[isite,1].astype('int')) +'|')
        file.write(str(dates[isite,2].astype('int')) +'|')
        file.write(str(tree_pollen[isite].item()) +'|')
        file.write(str(weed_pollen[isite].item()) +'|')
        file.write(str(grass_pollen[isite].item()))
        file.write('\n')


# Quit the driver
driver.quit()

