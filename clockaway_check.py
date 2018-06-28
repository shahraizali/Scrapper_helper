'''
------MAPcheck.py------
Purpose: Uses .csv file to search https://www.clockway.com/
         and compare MAP to seller price.
         If a violation occurs, a screenshot
         is captured and data is logged into
         a .csv file.
'''

import csv
import datetime
import logging
import os
import random
import time

import mechanicalsoup
import subprocess

import sys
from selenium import webdriver
from selenium.webdriver.chrome.options import Options

from re import sub
from decimal import Decimal

TEST = "server"
APP_NAME = "clockway"
logger = logging.getLogger()
LOG_LEVEL = logging.INFO


def setup_logger():
    logger.setLevel(LOG_LEVEL)
    logging.getLogger('requests').setLevel(logging.WARNING)
    LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    formatter = logging.Formatter(LOG_FORMAT)
    ch = logging.FileHandler(APP_NAME + ".log", mode='a', encoding=None, delay=False)
    ch.setLevel(LOG_LEVEL)
    ch.setFormatter(formatter)
    logger.addHandler(ch)
    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(LOG_LEVEL)
    ch.setFormatter(formatter)
    logger.addHandler(ch)


setup_logger()

chrome_options = Options()
chrome_options.add_argument("--headless")
chrome_options.add_argument("--window-size=1920x1080")
chrome_options.add_argument("--no-sandbox")


# -----Main Functions-----
# The next five functions ("def getSOMETHING")
# assign the cols in .csv file being searched
# to variables.
def getASIN():
    with open('csvs/Amazon Catalog.csv') as csvfile:
        rdr = csv.DictReader(csvfile)
        for row in rdr:
            asins = row['ASIN']
            yield asins


def getModel():
    with open('csvs/Amazon Catalog.csv') as csvfile:
        rdr = csv.DictReader(csvfile)
        for row in rdr:
            modelnum = row['MFG model number']
            yield modelnum


def getUPC():
    with open('csvs/Amazon Catalog.csv') as csvfile:
        rdr = csv.DictReader(csvfile)
        for row in rdr:
            upc = row['ALTUPC']
            yield upc


def getTitle():
    with open('csvs/Amazon Catalog.csv') as csvfile:
        rdr = csv.DictReader(csvfile)
        for row in rdr:
            title = row['TITLE']
            yield title


def getMAP():
    with open('csvs/Amazon Catalog.csv') as csvfile:
        rdr = csv.DictReader(csvfile)
        for row in rdr:
            maps = (row['MAP'])
            yield maps


# Pulls webpage data.
def pullPage(modelnum):
    browser = mechanicalsoup.StatefulBrowser(soup_config={'features': 'lxml'})
    browser.open('https://www.clockway.com/mm5/merchant.mvc?')
    browser.select_form('form[action="/mm5/merchant.mvc?"]')
    
    search_key = ""
    if len(modelnum) == 6:
        search_key = modelnum[0:3] + "-" + modelnum[3:6]
    elif len(modelnum) == 4:
        search_key = "ridgeway " + modelnum
    browser["Search"] = search_key
    page=browser.submit_selected()

    soup = page.soup    
    return soup


# Captures screenshot of pullPage().
def screenShot(link, filename):
    logger.info("Making screenshot to filename %s from link %s" % (filename, link))

    if TEST == "server":
        driver = webdriver.Chrome(chrome_options=chrome_options, executable_path="/usr/local/bin/chromedriver")
    else:
        driver = webdriver.Chrome(chrome_options=chrome_options, executable_path="/usr/lib/chromium-browser/chromedriver")

    try:
        driver.get(link)
        driver.get_screenshot_as_file(filename)
        driver.close()
    except:
        logger.exception("cannot create image")
        driver.close()
    
    try:
        if TEST == "server":
            aws_log = subprocess.check_output(
                ["aws", "s3", "cp", filename, 's3://mapviolations/%s' % filename],
                stderr=subprocess.STDOUT)
            logger.info(aws_log)
        else:
            subprocess.call('cp ' + filename + ' /home/mike/Pictures/', shell=True)
    except:
        logger.exception("cannot upload to s3")

    time.sleep(5)
    os.remove(str(filename).replace('"', ''))


# Writes MAP violation data to .csv file.
def writeLog(aprice, seller, asins, maps, modelnum, upc, title, url, fba, imgurl, clockaway_modelnum):
    with open('csvs/HM Violations.csv', 'ab') as f:
        writer = csv.writer(f)
        dd = str(datetime.datetime.fromtimestamp(time.time()).strftime('%Y-%m-%d %H:%M'))
        if fba == "FulfillmentbyAmazon":
            row = (modelnum, upc, asins, title, seller, 'TRUE', maps, aprice, '', '', dd, url, imgurl)
        else:
            row = (modelnum, upc, asins, title, seller, 'FALSE', maps, aprice, '', '', dd, url, imgurl)
        writer.writerow(row)
        f.close()


def write_xref(modelnum, clockaway_modelnum):
    with open('csvs/clockawayxref.csv', 'ab') as f:
        writer = csv.writer(f)
        row = (modelnum, clockaway_modelnum)
        writer.writerow(row)
        f.close()


global asins, maps, modelnum, upc, title

with open('csvs/clockawayxref.csv', 'w') as f:
    f.close()

# Assigning input .csv data to variables
asins = list(getASIN())
maps = list(getMAP())
modelnum = list(getModel())
upc = list(getUPC())
title = list(getTitle())

# Main Loop:  Loop through every row in .csv file.
count = len(asins)
for i in range(count):
    # If MAP not available logger.infos alert and skips to next.
    if maps[i] == '#N/A':
        logger.info('no MAP for row: ' + str(i) + ' - ASIN:' + str(asins[i]))

    else:
        try:
            # Pull webpage data needed.
            logger.info(i)
            
            model_number = modelnum[i].strip()
                        
            soup = pullPage(model_number)

            search_results = soup.find("div", attrs={'class':'productcat'})            
            if search_results:
                url = soup.find("a", class_="product_link").get("href")
                filename = APP_NAME + '_' + model_number + '_' + str(
                            datetime.datetime.fromtimestamp(time.time()).strftime('%Y-%m-%d_%H:%M')).replace(',',
                                                                                                             ' ') + '.png'
                
                imgurl = 'https://s3-us-west-2.amazonaws.com/mapviolations/' + filename
                #price = search_results.find("i").find("big").text
                #price = Decimal(sub(r'[^\d.]', '', price))
                price = float(str(search_results).split('Our Price:')[1].split('<')[0].split('$')[1].replace(',', ''))
                clockaway_modelnum = search_results.find("span", class_="text_cat_product_id").text
                map_price = float(maps[i])

                write_xref(modelnum[i], clockaway_modelnum)

                if price < map_price:
                    logger.info("%s: violation price %f : %f" % (modelnum[i], price, map_price))
                    writeLog(price, APP_NAME, asins[i], maps[i], modelnum[i], upc[i], title[i], url, 'N',
                                 imgurl,clockaway_modelnum)
                    screenShot(url, filename)
                else:
                    logger.info("%s: price ok %f : %f" % (modelnum[i], price, map_price))                
            else:
                logger.info("%s model number can't find" % modelnum[i])
                continue


            # Pause to help prevent interruption/blocking from Amazon.
            time.sleep(random.randint(1, 2))

            # If a value error occurs, logger.infos alert and skips.
        except ValueError as v:
            logger.info(v)

            # Pause to help prevent interruption/blocking from Amazon.
            time.sleep(random.randint(1, 5))

            # If a Attribute error occurs, logger.infos alert and skips.
        except AttributeError as e:
            logger.info(e)

            # Pause to help prevent interruption/blocking from Amazon.
            time.sleep(random.randint(1, 5))

            # If error occurs within main process, logger.infos alert and skips.
        except Exception as x:
            logger.info(x)

            # Pause to help prevent interruption/blocking from Amazon.
            time.sleep(random.randint(1, 10))
