import argparse
import collections
import datetime
import json
import os
import os.path
import sys
import time
from playwright.sync_api import sync_playwright

MAP = collections.OrderedDict([
    ('be-our-guest', '16660079'),
    ('cinderella', '90002464'),
    ('crystal-palace', '90002660'),
])

LUNCH = '80000717'
DINNER = '80000714'

API = 'https://disneyworld.disney.go.com/finder/api/v1/explorer-service/dining-availability/x/wdw/%(uuid)s;entityType=restaurant/table-service/%(guests)s/%(date)s/?mealPeriod=%(meal)s'

AGENT = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:89.0) Gecko/20100101 Firefox/89.0'

COOKIE_PATH = './cookies'

def login(page, username, password):
    page.goto('https://disneyworld.disney.go.com/dining/magic-kingdom/be-our-guest-restaurant/availability-modal/')
    page.wait_for_selector('iframe')
    frame = page.query_selector('iframe').content_frame()
    frame.fill('input[type=email]', username)
    frame.fill('input[type=password]', password)
    frame.click('button[type=submit]')
    page.wait_for_selector('#search-time-button button')

def search(username, password, date, guests=4):
    print(f"Searching for availability for {guests} on {date}...")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        browser_kwargs = {'user_agent': AGENT}
        if os.path.exists(COOKIE_PATH):
            browser_kwargs['storage_state'] = COOKIE_PATH
        context = browser.new_context(**browser_kwargs)
        page = context.new_page()

        if not os.path.exists(COOKIE_PATH):
            print(f"Logging in...")
            login(page, username, password)

        context.storage_state(path=COOKIE_PATH)

        print(f"Fetching schedule data...")
        for k, v in MAP.items():
            print('---')
            times = []
            for meal in (LUNCH, DINNER):
                url = API % {'uuid': v, 'guests': guests, 'date': date, 'meal': meal}
                page.goto(url)
                data = json.loads(page.inner_text('body'))
                times.extend(data.get('offers', []))
            if times:
                print(f'\x1B[32m {k} \x1B[0m')
                for t in times:
                    print(f'    - {t["time"]}')
            else:
                print(f'\x1B[31m {k} \x1B[0m')
        browser.close()

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument(
        'date',
        type=lambda s: datetime.datetime.strptime(s, '%Y-%m-%d'),
    )
    args = parser.parse_args()
    username = os.getenv('DISNEY_USERNAME')
    password = os.getenv('DISNEY_PASSWORD')
    search(username, password, args.date.date())
