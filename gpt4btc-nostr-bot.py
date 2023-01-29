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
from selenium.common.exceptions import NoSuchElementException

import openai


# global variables
abs_dir = os.path.dirname(os.path.abspath(__file__)) #<-- absolute path to directory
# paths to files
path_creds = os.path.join(abs_dir, 'credentials.txt')
path_scrp_dmp = os.path.join(abs_dir, 'nostr_scrape_dump.txt')
path_log = os.path.join(abs_dir, 'log.txt')

nostrgram_profile = 'https://nostrgram.co/#profile:allEvents:939ddb0c77d18ccd1ebb44c7a32b9cdc29b489e710c54db7cf1383ee86674a24'
nostrgram_notifications = 'https://nostrgram.co/#notifications:allNotifications'

# get headless browser driver, TODO according to args
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

def get_creds():
    # get authorization credentials from credentials file
    with open(path_creds, 'r') as creds:

        # init empty array to store credentials
        cred_lines = [None] * 3

        # strip end of line characters and any trailing spaces, tabs off credential lines
        cred_lines_raw = creds.readlines()
        for i in range(len(cred_lines_raw)):
            cred_lines[i] = (cred_lines_raw[i].strip())

        return cred_lines

def authOpenAI():
    creds = get_creds()
    # set openai api key
    openai.api_key = creds[2]
    print('openai authorized')

# get authentication credentials
def authNostr():

    creds = get_creds()

    # login to nostrgram.co
    try:
        # load gpt4btc profile page
        driver.get(nostrgram_profile)

        loginIcon = WebDriverWait(driver, 5).until(EC.presence_of_element_located((By.CSS_SELECTOR, '#desktopHeaders > div:nth-child(1) > table:nth-child(1) > tbody:nth-child(1) > tr:nth-child(1) > td:nth-child(1) > div:nth-child(1) > span:nth-child(1)')))
        loginIcon.click() # click on login key icon
        loginInput = WebDriverWait(driver, 5).until(EC.visibility_of_element_located((By.CSS_SELECTOR, '.loginInput')))
        loginInput.send_keys(creds[0]) # input private key
        loginName = WebDriverWait(driver, 5).until(EC.presence_of_element_located((By.CSS_SELECTOR, '.loginName')))
        print('nostr logged in: ' + loginName.text)
        driver.find_element(By.CSS_SELECTOR, 'button.ui-button:nth-child(3)').click() # click OK
        
    except Exception as e:
        traceback.print_exc()
        print("Login to nostrgram.co failed.")



def build_dump_line(b):
    # get child timestamp
    timestamp = b.find_element(By.XPATH, './div[contains(@class, "noteTimestamp")]').get_attribute('timestamp')    
    
    # get descendant noteAuthorPubKey
    name = b.find_element(By.XPATH, './/span[contains(@class, "noteAuthorName")]').text
    pub_key = b.find_element(By.XPATH, './/span[contains(@class, "noteAuthorPubKey")]').text
    
    # get child noteContents
    content = b.find_element(By.XPATH, './div[contains(@class, "noteContent")]').text

    return (timestamp + "NSTR_NM" + name + "NSTR_KY" + pub_key + "NSTR_CT" + content.replace("\n", " ") + "\n")

def parse_dump_line(dl):
    # separate scrape dump line into fields
    try:
        a1 = dl.split('NSTR_NM')
        a2 = a1[1].split('NSTR_KY')
        a3 = a2[1].split('NSTR_CT')
        # [time, nstr_name, nstr_pubkey, nstr_content]
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

def scrape_nostr():

    # get scrape dump lines
    f = open(path_scrp_dmp, "r")
    scrp_lines = f.readlines()
    f.close()

    # load 'gpt4btc' search page, doesn't always work!
    #driver.get('https://nostrgram.co/#search:allEvents:gpt4btc')

    # search for 'gpt4btc'
    #driver.get(nostrgram_profile)
    #WebDriverWait(driver, 2).until(EC.presence_of_element_located((By.CSS_SELECTOR, 'span.searchFeed:nth-child(2)'))).click()
    #searchQuery = WebDriverWait(driver, 2).until(EC.presence_of_element_located((By.CSS_SELECTOR, '#searchQuery')))
    #searchQuery.send_keys('gpt4btc')
    #driver.find_element(By.CSS_SELECTOR, '#dialogSearch > p:nth-child(1) > button:nth-child(2)').click()
    #searchNoteGrid = WebDriverWait(driver, 5).until(EC.presence_of_element_located((By.CSS_SELECTOR, '#searchNostrgram')))

    # scrape profile for @gpt4btc tags
    #driver.get(nostrgram_notifications)
    WebDriverWait(driver, 2).until(EC.presence_of_element_located((By.XPATH, '/html/body/div[1]/div[2]/div/table/tbody/tr/td[3]/span[1]/span[1]'))).click()
    
    # get all notifications
    notifications = WebDriverWait(driver, 2).until(EC.presence_of_element_located((By.CSS_SELECTOR, '#notificationsNostrgram')))
    allNoteItems = WebDriverWait(notifications, 10).until(EC.presence_of_all_elements_located((By.XPATH, './/div[contains(@class, "event noteItem")]')))
    
    # find only @gpt4btc tagged items
    taggedItems = []
    for item in allNoteItems:
        # add only @gpt4btc tags to taggedItems[]
        try:
            tag = item.find_element(By.XPATH, './/span[contains(@class, "profileName")]').text
            if '@gpt4btc' in tag:
                taggedItems.append(item)
        except NoSuchElementException:
            continue

    print('@gpt4btc tagged items found: ' + str(len(taggedItems)))

    with open(path_scrp_dmp, "r+") as scrp_dmp: # read and write file
        scrp_lines = scrp_dmp.readlines()

        new_notes = 0
        for item in taggedItems:
            # get child noteBody
            body = item.find_element(By.XPATH, './div[contains(@class, "noteBody")]')

            dl = build_dump_line(body)
            pl = parse_dump_line(dl)

            # ignore this bot's own notes
            if 'npub1jww..q7nawfa' in pl[2]:
                continue

            # ignore notes already in scrape dump file and notes from self
            is_new_note = True
            for line in scrp_lines:
                if pl[0] in line: # check note timestamp
                    is_new_note = False
                    break

            if is_new_note:
                # write new note to scrape dump
                scrp_dmp.writelines(dl)
                new_notes += 1

                # request response from openai
                answer = query_openai(pl[3])
                
                post_note(answer, body, item)

    print('replied to new notes: ' + str(new_notes))

def post_note(n, b, i):
    # click note reply button
    b.find_element(By.XPATH, './/span[contains(@class, "noteReply")]').click()

    # get replyContainer
    replyContainer = i.find_element(By.XPATH, './div[contains(@class, "replyContainer")]')

    # send note to edit box
    replyEditor = WebDriverWait(replyContainer, 5).until(EC.element_to_be_clickable((By.XPATH, './textarea[contains(@class, "replyEditor")]')))
    replyEditor.click()
    replyEditor.send_keys(n)
    # click reply button
    replyButton = WebDriverWait(replyContainer, 5).until(EC.presence_of_element_located((By.XPATH, './/button[contains(@class, "replyButton")]')))
    replyButton.click()


def query_openai(p):
    response = openai.Completion.create(model="text-davinci-003", prompt=p, temperature=0, max_tokens=40)
    content = response.choices[0].text
    print('openai returned response: ' + content)
    return content

# get command line arguments and execute appropriate functions
def main(argv):
    # for logging purposes
    start_time = datetime.now()

    # deal with passed in arguments 
    args = argument_handler()

    count_reply = 0

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


    # authorize openai and login to nostrgram.co
    authOpenAI()
    authNostr()

    scrape_nostr()

    driver.quit()


# so main() isn't executed if file is imported
if __name__ == "__main__":
    # remove first script name argument
    main(sys.argv[1:])

