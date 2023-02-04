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
from selenium.common.exceptions import TimeoutException, NoSuchElementException

import openai


# global variables
abs_dir = os.path.dirname(os.path.abspath(__file__)) #<-- absolute path to directory
# paths to files
path_creds = os.path.join(abs_dir, 'credentials.txt')
path_scrp_dmp = os.path.join(abs_dir, 'nostr_scrape_dump.txt')
path_log = os.path.join(abs_dir, 'log.txt')
limit_list = os.path.join(abs_dir, 'limit_list.txt')
block_list = os.path.join(abs_dir, 'block_list.txt')

nostrgram_profile = 'https://nostrgram.co/#profile:allEvents:939ddb0c77d18ccd1ebb44c7a32b9cdc29b489e710c54db7cf1383ee86674a24'
nostrgram_notifications = 'https://nostrgram.co/#notifications:allNotifications'

def get_curr_timestamp():
    return int(datetime.now().timestamp())

# record certain events in log.txt
start_time = datetime.now()
def get_runtime():
    return "total run time: " + str(datetime.now() - start_time)
def log(s):
    t = strftime("%Y%b%d %H:%M:%S", localtime()) + " " + s

    with open(path_log, 'a') as l:
        l.write(t + "\n")

    # also print log to terminal
    print(t)

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

def auth_openai():
    creds = get_creds()
    # set openai api key
    openai.api_key = creds[2]
    log('openai authorized')

# get authentication credentials
def auth_nostr(driver):

    creds = get_creds()

    # login to nostrgram.co
    try:
        # load gpt4btc profile page
        driver.get(nostrgram_profile) 
        
        # dismiss possible error loading relays
        try:
            ui_dialog = WebDriverWait(driver, 2).until(EC.presence_of_element_located((By.XPATH, './/div[contains(@class, "ui-dialog")]')))
            ui_dialog.find_element(By.XPATH, './/button[contains(@class, "ui-button")]').click()
            print('dismissed error dialog')
        except: 
            print('no error dialog to dismiss')

        loginIcon = WebDriverWait(driver, 5).until(EC.presence_of_element_located((By.CSS_SELECTOR, '#desktopHeaders > div:nth-child(1) > table:nth-child(1) > tbody:nth-child(1) > tr:nth-child(1) > td:nth-child(1) > div:nth-child(1) > span:nth-child(1)')))
        loginIcon.click() # click on login key icon
        loginInput = WebDriverWait(driver, 5).until(EC.visibility_of_element_located((By.CSS_SELECTOR, '.loginInput')))
        loginInput.send_keys(creds[0]) # input private key
        loginName = WebDriverWait(driver, 5).until(EC.presence_of_element_located((By.CSS_SELECTOR, '.loginName')))
        log('nostr logged in: ' + loginName.text)
        driver.find_element(By.CSS_SELECTOR, 'button.ui-button:nth-child(3)').click() # click OK
        
    except Exception as e:
        traceback.print_exc()
        log("Login to nostrgram.co failed.")


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

def parse_limit_line(dl):
    # separate scrape dump line into fields
    try:
        a1 = dl.split('NSTR_NM')
        a2 = a1[1].split('NSTR_KY')
        a3 = a2[1].split('NSTR_CT')
        # [time, nstr_name, nstr_pubkey]
        return [a1[0], a2[0], a3[0]]
    except IndexError:
        raise IndexError

def scrape_nostr(driver, r_ply):
    reply_cnt = 0

    # get scrape dump lines
    f = open(path_scrp_dmp, "r")
    scrp_lines = f.readlines()
    f.close()

    # search for '@gpt4btc'
    driver.get(nostrgram_profile)
    WebDriverWait(driver, 2).until(EC.presence_of_element_located((By.CSS_SELECTOR, 'span.searchFeed:nth-child(2)'))).click()
    search_query = WebDriverWait(driver, 2).until(EC.presence_of_element_located((By.CSS_SELECTOR, '#searchQuery')))
    search_query.send_keys('gpt4btc')
    driver.find_element(By.CSS_SELECTOR, '#dialogSearch > p:nth-child(1) > button:nth-child(2)').click()
    search_note_grid = WebDriverWait(driver, 5).until(EC.presence_of_element_located((By.CSS_SELECTOR, '#searchNostrgram')))
    
    # get all searched items including '@gpt4btc' strings
    all_searched_items = WebDriverWait(search_note_grid, 10).until(EC.presence_of_all_elements_located((By.XPATH, './/div[contains(@class, "event noteItem")]')))

    tagged_search_items = []
    for item in all_searched_items:
        try:
            content = item.find_element(By.XPATH, './/div[contains(@class, "noteContent")]').text
            # add only @gpt4btc tags to tagged_items[]
            if '@gpt4btc' in content:
                tagged_search_items.append(item)
        except NoSuchElementException:
            continue

    #log('search "@gpt4btc" items found: ' + str(len(tagged_search_items)))
    
    reply_cnt += reply_to_items(driver, r_ply, tagged_search_items)

    # click notifications icon to load nostrgram_notifications page
    WebDriverWait(driver, 2).until(EC.presence_of_element_located((By.XPATH, '/html/body/div[1]/div[2]/div/table/tbody/tr/td[3]/span[1]/span[1]'))).click()
    # get all notifications
    notifications = WebDriverWait(driver, 2).until(EC.presence_of_element_located((By.CSS_SELECTOR, '#notificationsNostrgram')))
    allNoteItems = WebDriverWait(notifications, 10).until(EC.presence_of_all_elements_located((By.XPATH, './/div[contains(@class, "event noteItem")]')))
    # find only @gpt4btc tagged items
    tagged_items = []
    for item in allNoteItems:
        try:
            # get list of all user tags in post
            tags = item.find_elements(By.XPATH, './/span[contains(@class, "profileName")]')
            for tag in tags:
                # add only @gpt4btc tags to tagged_items[]
                if '@gpt4btc' in tag.text:
                    tagged_items.append(item)
        except NoSuchElementException:
            continue

    #log('tagged @gpt4btc items found: ' + str(len(tagged_items)))
    
    reply_cnt += reply_to_items(driver, r_ply, tagged_items)

    '''
    # load direct notifications only
    driver.find_element(By.CSS_SELECTOR, '.userActions > span:nth-child(1)').click()
    direct_notif_checkbox = WebDriverWait(driver, 5).until(EC.element_to_be_clickable((By.CSS_SELECTOR, '#settingsDirectNotificationsOnly')))
    # select checkbox, if not already selected
    if not direct_notif_checkbox.is_selected():
        direct_notif_checkbox.click()
    # click ok to accept settings
    driver.find_element(By.XPATH, '/html/body/div[16]/div[3]/div/button').click()
    '''
    # click notifications icon to load nostrgram_notifications page
    WebDriverWait(driver, 2).until(EC.presence_of_element_located((By.XPATH, '/html/body/div[1]/div[2]/div/table/tbody/tr/td[3]/span[1]/span[1]'))).click()

    # hide reactions, if not already hidden
    hide_reactions_checkbox = WebDriverWait(driver, 2).until(EC.element_to_be_clickable((By.CSS_SELECTOR, '#notificationsHideReactions')))
    if not hide_reactions_checkbox.is_selected():
        hide_reactions_checkbox.click()

    # get all notifications
    notifications = WebDriverWait(driver, 2).until(EC.presence_of_element_located((By.CSS_SELECTOR, '#notificationsNostrgram')))
    all_notif_items = WebDriverWait(notifications, 10).until(EC.presence_of_all_elements_located((By.XPATH, './/div[contains(@class, "event noteItem")]')))
    # remove reactions and no content tags
    for item in all_notif_items:
        if 'isReaction' in item.get_attribute('class'):
            all_notif_items.remove(item)
            continue
        content = item.find_element(By.XPATH, './/div[contains(@class, "noteContent")]').text
        if content == '@gpt4btc':
            all_notif_items.remove(item)


    # reply only to notifications replying to @gpt4btc
    #log('notification gpt4btc items loaded: ' + str(len(all_notif_items)))
    
    reply_cnt += reply_to_items(driver, r_ply, all_notif_items)

    return reply_cnt
    

def reply_to_items(driver, r_ply, tagged_items):
    reply_cnt = 0
    with open(path_scrp_dmp, "r+") as scrp_dmp: # read and write file
        scrp_lines = scrp_dmp.readlines()

        for item in reversed(tagged_items): # go from oldest to youngest
            # get child noteBody
            body = item.find_element(By.XPATH, './div[contains(@class, "noteBody")]')

            dl = build_dump_line(body)
            pl = parse_dump_line(dl)

            p = pl[3]

            # ignore this bot's own notes
            if 'npub1jww..q7nawfa' in pl[2]:
                continue

            # ignore notes already in scrape dump file
            is_new_note = True
            for line in reversed(scrp_lines): # read from last to first for efficiency
                if pl[0] in line: # check note timestamp
                    is_new_note = False
                    break

            if is_new_note:

                # ignore empty notes and reactions
                if not p or p == ' ' or p == '\n' or p == '🤙' or p == '❤️':
                    log('ignoring empty prompt')
                    scrp_dmp.write(dl)
                    continue

                # if only scraping then write to scrape dump without replying
                if r_ply == False:
                    scrp_dmp.writelines(dl)
                    continue

                # if user is spamming, add to limit list for 1hr
                limit = limit_user_replies(item, scrp_lines)
                answer = None
                if limit == 'added':
                    answer = 'It\'s been fun chatting, but I\'m taking a short break now. We can chat all you like in the app: https://chatgpt3-android.app'
                elif limit == 'ignore' : # ignore user's post
                    continue
                else: # request response from openai - limit='no'
                    answer = query_openai(pl[3])
                
                # don't reply to empty prompts
                if answer == None:
                    continue

                log('prompt: ' + pl[3] + 'response: ' + answer)

                '''# try to reply
                success = ""
                try:
                    post_reply(driver, answer, body, item)
                except Exception:
                    log('post_reply failed:\n' + traceback.format_exc())
                    success = "x" # marked failed dump lines with 'x' prefix

                    # reload current page to close any open widgets/windows
                    current_page = driver.current_url
                    driver.get(current_page)
                '''
                post_reply(driver, answer, body, item)
                reply_cnt += 1

                # write new replied to note to scrape dump
                scrp_dmp.writelines(dl)

                # don't post to network too fast to hopefully avoid spam filters
                wait(4, 10)

    return reply_cnt

# only reply to user 10 times in 5m
def limit_user_replies(item, scrp_lines):
    # extract info from item
    item_dl = build_dump_line(item.find_element(By.XPATH, './div[contains(@class, "noteBody")]'))
    new_pl = parse_dump_line(item_dl)

    # ignore post if user added to limit list less than 5m before post
    time_5m_before_post = int(new_pl[0]) - 300
    print(time_5m_before_post)
    with open(limit_list, 'r') as ll:
        lll = ll.readlines()
        for l in reversed(lll): # get most recent user limit
            if (new_pl[2] in l): # is user in limit list?
                pl = parse_limit_line(l)
                if (time_5m_before_post < int(pl[0])): # was user added to ll less than 5m before post?
                    log('ignoring post from ' + new_pl[1] + ' at ' + new_pl[0])
                    # add ignored note to scrape dump
                    with open(path_scrp_dmp, 'a') as sd:
                        sd.write(item_dl)
                    return 'ignore'

    key_cnt = 0
    for line in reversed(scrp_lines): # read from last to first
        pl = parse_dump_line(line)

        # if user keys match, increment cnt
        if new_pl[2] == pl[2]:
            key_cnt += 1
        
            # add user to limit list if exceeds 10 posts in 5m
            if key_cnt > 9:
                
                # write user info to limit list
                lll = item_dl.split('NSTR_CT')
                with open(limit_list, 'a') as ll:
                    ll.write(lll[0] + '\n')

                log('add user to limit list: ' + lll[0])
                return 'added'

        # if dump line is older than 5m before post, then user is not spamming
        if time_5m_before_post > int(pl[0]):
            return 'no'
    return 'no'

def query_openai(p):
    # limit prompt length to ~80 words
    p = p[:400]

    # bot was overly shilling fake btc abilities, so remove tag
    q = p.replace('@gpt4btc', '@gpt')

    # make replies concise
    q = 'answer concisely: ' + q

    response = openai.Completion.create(model="text-davinci-003", prompt=q, temperature=0, max_tokens=80)
    content = response.choices[0].text

    # put original tags back in
    return content.replace('@gpt', '@gpt4btc')


def post_reply(driver, n, b, i):
    '''
    success = ""
    
    # determine if note is a reply in thread
    is_reply = False
    try:
        #reply_to = i.get_attribute('replyTo')
        # if not a reply to thread, this will trigger exception
        b.find_element(By.XPATH, './/span[contains(@class, "noteReplyId")]').click()
        is_reply = True
    except:
        None

    if is_reply:
        # open thread
        thread_id = i.get_attribute('threadid')
        thread = WebDriverWait(driver, 5).until(EC.presence_of_element_located((By.ID, 'thread_' + thread_id)))

        # find corresponding note id in thread
        note_id = i.get_attribute('id')
        thread_note = WebDriverWait(thread, 5).until(EC.presence_of_element_located((By.ID, note_id)))

        # open replyEditor
        openReplyEditorButton = WebDriverWait(thread_note, 5).until(EC.presence_of_element_located((By.XPATH, './/span[contains(@class, "noteReply hasClick")]')))
        openReplyEditorButton.click()

        # get replyContainer
        replyContainer = WebDriverWait(thread_note, 5).until(EC.presence_of_element_located((By.XPATH, './div[contains(@class, "replyContainer")]')))

        # send note to edit box
        replyEditor = WebDriverWait(replyContainer, 5).until(EC.element_to_be_clickable((By.XPATH, './textarea[contains(@class, "replyEditor")]')))
        #replyEditor.click() # this may be needed? but for now needlessly opens thread window
        replyEditor.send_keys(n)
        # click reply button
        replyButton = WebDriverWait(replyContainer, 5).until(EC.presence_of_element_located((By.XPATH, './/button[contains(@class, "replyButton")]')))
        #replyButton.click()

        # close reply thread widget
        #thread.find_element(By.XPATH, './/button[contains(@class, "button.ui-button.ui-corner-all.ui-widget.ui-button-icon-only.ui-dialog-titlebar-close")]').click()


    else: # handle original notes not replying to thread
    '''
    # click note reply button
    #b.find_element(By.XPATH, './/span[contains(@class, "noteReply")]').click()
    WebDriverWait(b, 5).until(EC.element_to_be_clickable((By.XPATH, './/span[contains(@class, "noteReply hasClick")]'))).click()

    # get replyContainer
    replyContainer = i.find_element(By.XPATH, './div[contains(@class, "replyContainer")]')

    # send note to edit box
    replyEditor = WebDriverWait(replyContainer, 5).until(EC.element_to_be_clickable((By.XPATH, './textarea[contains(@class, "replyEditor")]')))
    #replyEditor.click() # this may be needed? but for now needlessly opens thread window
    replyEditor.send_keys(n)
    # click reply button
    replyButton = WebDriverWait(replyContainer, 5).until(EC.element_to_be_clickable((By.XPATH, './/button[contains(@class, "replyButton")]')))
    replyButton.click()


def post_new_note(driver, p_ost):
    # get new note text area and enter input argument
    new_note = WebDriverWait(driver, 2).until(EC.element_to_be_clickable((By.XPATH, './/div[contains(@id, "newNote")]')))
    new_note_textarea = new_note.find_element(By.XPATH, './/textarea[contains(@class, "replyEditor")]')
    new_note_textarea.send_keys(p_ost)

    # get, click send button
    send_button = WebDriverWait(new_note, 2).until(EC.element_to_be_clickable((By.XPATH, './/button[contains(@class, "replyButton")]')))
    send_button.click()

def argument_handler():
    parser = argparse.ArgumentParser(description="Beep, boop.. I'm gpt4btc - a nostr bot!")

    # Nostr arguments
    group_scrape = parser.add_argument_group('scrape')
    group_scrape.add_argument('-s', '--scrape-once', action='store_true', dest='r_scr', help='scrape once')
    group_scrape.add_argument('-c', '--scrape-loop', action='store_true', dest='r_scn', help='scrape continuously')
    group_scrape.add_argument('-n', '--headless', action='store_true', dest='r_hds', help='scrape in headless mode')
    group_scrape.add_argument('-r', '--reply', action='store_true', dest='r_ply', help='reply to scraped notes')

    group_post = parser.add_argument_group('post')
    group_post.add_argument('-p', '--post-new-note', type=str, action='store', dest='p_ost', help='post new note')

    return parser.parse_args()

# get command line arguments and execute appropriate functions
def main(argv):
    # deal with passed in arguments 
    args = argument_handler()

    # catch SIGINTs and KeyboardInterrupts
    def signal_handler(signal, frame):
        log("Current job terminated: received KeyboardInterrupt kill signal.")
        log(get_runtime())
        sys.exit(0)
    
    # set SIGNINT listener to catch kill signals
    signal.signal(signal.SIGINT, signal_handler)

    driver = None
    def init(r_hds):
        # get headless browser driver, according to args
        options = Options()
        if args.r_hds:
            options.add_argument("--headless")
            #options.add_argument("--start-maximized")
        driver = webdriver.Firefox(options=options)

        # login to nostrgram.co and authorize openai
        auth_nostr(driver)
        auth_openai()
        
        return driver

    # scrape feed once
    if args.r_scr:
        driver = init(args.r_hds)

        # scrape, and reply?
        reply_cnt = scrape_nostr(driver, args.r_ply)

        log("new replies: " + str(reply_cnt))

    # scrape feed continuously
    if args.r_scn:
        driver = init(args.r_hds)

        num_errors = 0
        while num_errors < 3: # exit after three errors caught
            try:
                # scrape, and reply?
                reply_cnt = scrape_nostr(driver, args.r_ply)

                log("new replies: " + str(reply_cnt))

                # wait 5-10m between passes
                wait(300, 600)

            except Exception:
                log('Error while scraping continuously: ' + traceback.format_exc())
                num_errors += 1
                init(args.r_hds) # reboot

    # post new note
    if args.p_ost:
        driver = init(args.r_hds)

        post_new_note(driver, args.p_ost)
        log('posted note: ' + args.p_ost)

    driver.quit()
    log(get_runtime())

# so main() isn't executed if file is imported
if __name__ == "__main__":
    # remove first script name argument
    main(sys.argv[1:])