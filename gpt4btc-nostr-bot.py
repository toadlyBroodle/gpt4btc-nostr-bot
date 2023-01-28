#! /usr/bin/python3

import os
import sys
import signal
import argparse
import pprint
import json
import traceback
from time import sleep, localtime, strftime
from datetime import datetime
from random import randint

# Web Scraping, Parsing imports:
import getpass
#import requests, webbrowser, bs4
from selenium import webdriver
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.firefox.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException

import openai


# global variables
abs_dir = os.path.dirname(os.path.abspath(__file__)) #<-- absolute path to directory
# paths to files
path_creds = os.path.join(abs_dir, 'credentials.txt')
path_scrp_dmp = os.path.join(abs_dir, 'nostr_scrape_dump.txt')
path_log = os.path.join(abs_dir, 'log.txt')


# get headless browser driver
options = Options()
#options.add_argument("--headless")
#options.add_argument("--start-maximized")
driver = webdriver.Firefox(options=options)


# record certain events in log.txt
def log(s):
    t = strftime("%Y%b%d %H:%M:%S", localtime()) + " " + s

    with open(path_log, 'a') as l:
        l.write(t + "\n")

    # also print truncated log to screen
    p = t[:90] + (t[90:] and '..')
    print(p)

def wait(min, max):
    wt = randint(min, max)
    print("sleeping " + str(wt) + "s...")
    sleep(wt)

# get authentication credentials
def auth():

    global path_creds
    global driver

    # get authorization credentials from credentials file
    with open(path_creds, 'r') as creds:

        # init empty array to store credentials
        cred_lines = [None] * 3

        # strip end of line characters and any trailing spaces, tabs off credential lines
        cred_lines_raw = creds.readlines()
        for i in range(len(cred_lines_raw)):
            cred_lines[i] = (cred_lines_raw[i].strip())

        # set openai api key
        openai.api_key = cred_lines[2]

        # login to nostrgram.co
        try:
            # load gpt4btc profile page
            driver.get("https://nostrgram.co/#profile:allEvents:939ddb0c77d18ccd1ebb44c7a32b9cdc29b489e710c54db7cf1383ee86674a24")
    
            loginIcon = WebDriverWait(driver, 5).until(EC.presence_of_element_located((By.CSS_SELECTOR, '#desktopHeaders > div:nth-child(1) > table:nth-child(1) > tbody:nth-child(1) > tr:nth-child(1) > td:nth-child(1) > div:nth-child(1) > span:nth-child(1)')))
            loginIcon.click() # click on login key icon
            loginInput = WebDriverWait(driver, 5).until(EC.visibility_of_element_located((By.CSS_SELECTOR, '.loginInput')))
            loginInput.send_keys(cred_lines[0]) # input private key
            loginName = WebDriverWait(driver, 5).until(EC.presence_of_element_located((By.CSS_SELECTOR, '.loginName')))
            driver.find_element(By.CSS_SELECTOR, 'button.ui-button:nth-child(3)').click() # click OK
            
        except Exception as e:
            traceback.print_exc()
            print("Login to nostrgram.co failed.")



def buildDumpLine(b):
    timestamp = b.find_element(By.XPATH, './div[contains(@class, "noteTimestamp")]').timestamp

    return (timestamp+
                + "TWT_ID" + str(tweet.id)
                + "SCRN_NAME" + tweet.user.screen_name
                + "TWT_TXT" + tweet.text.replace("\n", "") + "\n")

def parseDumpLine(dl):
    # parse scrape dump file, separate tweet ids from screen names
    try:
        a1 = dl.split('TWT_ID')
        a2 = a1[1].split('SCRN_NAME')
        a3 = a2[1].split('TWT_TXT')
        # [time, twt_id, scrn_name, twt_txt]
        return [a1[0], a2[0], a3[0], a3[1]]
    except IndexError:
        raise IndexError


def argument_handler():
    parser = argparse.ArgumentParser(description="Beep, boop.. I'm gpt4btc - a nostr bot!")

    # Nostr arguments
    # group_scrape = parser.add_argument_group('query')
    # group_scrape.add_argument('-s', '--scrape', action='store_true', dest='n_scr', help='scrape 50 results')
    # group_scrape.add_argument('-c', '--continuous', action='store_true', dest='n_con', help='scrape continuously')

    # promote_browser = parser.add_argument_group('browser')
    # promote_browser.add_argument('-b', '--browser', action='store_true', dest='n_bro', help='reply to all scraped results')

    return parser.parse_args()


# get command line arguments and execute appropriate functions
def main(argv):
    # for logging purposes
    start_time = datetime.now()

    count_reply = 0

    # deal with passed in arguments 
    args = argument_handler()

    def report_job_status():
        # report how many actions performed
        log("Replied to {rep} notes.".format(rep=str(count_reply)))

        log("Total run time: " + str(datetime.now() - start_time))

    # catch SIGINTs and KeyboardInterrupts
    def signal_handler(signal, frame):
        log("Current job terminated: received KeyboardInterrupt kill signal.")
        report_job_status()
        sys.exit(0)
    
    # set SIGNINT listener to catch kill signals
    signal.signal(signal.SIGINT, signal_handler)

    executed = 0 # catches any command/args that fall through below tree

    # login to nostrgram.co
    #auth()

    # get scrape dump lines
    f = open(path_scrp_dmp, "r")
    scrp_lines = f.readlines()
    f.close()


    # load 'gpt4btc' search page
    driver.get('https://nostrgram.co/#search:allEvents:gpt4btc')

    searchNoteGrid = WebDriverWait(driver, 5).until(EC.visibility_of_element_located((By.CSS_SELECTOR, '#searchNostrgram')))

    # get descendant divs with classnames 'noteBody'
    noteBodies = WebDriverWait(searchNoteGrid, 10).until(EC.presence_of_all_elements_located((By.XPATH, './/div[contains(@class, "noteBody")]')))
    

    for body in noteBodies:

        #buildDumpLine(body)

        # get child timestamp
        timestamp = body.find_element(By.XPATH, './div[contains(@class, "noteTimestamp")]').get_attribute('timestamp')
        
        # get descendant noteAuthorPubKey
        pubKey = body.find_element(By.XPATH, './/span[contains(@class, "noteAuthorPubKey")]').text

        # get child noteContents
        content = body.find_element(By.XPATH, './div[contains(@class, "noteContent")]').text
    
        print(timestamp + '\n' + pubKey + '\n' + content)


    driver.quit()


# so main() isn't executed if file is imported
if __name__ == "__main__":
    # remove first script name argument
    main(sys.argv[1:])

