#! /usr/bin/env python3
#
# $ pip install playwright
# $ playwright install chromium
#
import asyncio
import argparse
import collections
import datetime
import json
import os
import os.path
import sys
import time
from distutils.util import strtobool

import arrow
from playwright.sync_api import sync_playwright
from playwright.async_api import async_playwright

MAP = collections.OrderedDict([
    ('be-our-guest', {
        'id': '16660079',
        'url': 'https://disneyworld.disney.go.com/dining/magic-kingdom/be-our-guest-restaurant/availability-modal',
    }),
    ('ohana', {
        'id': '90002606',
        'url': 'https://disneyworld.disney.go.com/dining/polynesian-resort/ohana/availability-modal',
    }),
    ('cinderella', {
        'id': '90002464',
        'url': 'https://disneyworld.disney.go.com/dining/magic-Kingdom/cinderella-royal-table/availability-modal',
    }),
    ('crystal-palace', {
        'id': '90002660',
        'url': 'https://disneyworld.disney.go.com/dining/magic-kingdom/crystal-palace/availability-modal',
    }),
    ("oga's cantina", {
        'id': '19267226',
        'url': 'https://disneyworld.disney.go.com/dining/hollywood-studios/ogas-cantina/availability-modal',
    }),
    ('chef mickey', {
        'id': '90001369',
        'url': 'https://disneyworld.disney.go.com/dining/contemporary-resort/chef-mickeys/availability-modal',
    }),
    #('snow-white-storybook', {
    #    'id': '$CLOSED$',
    #    'url': 'https://disneyworld.disney.go.com/dining/wilderness-lodge-resort/artist-point/availability-modal',
    #}),
    #('akershus', {
    #    'id': '$CLOSED$',
    #    'url': 'https://disneyworld.disney.go.com/dining/epcot/akershus-royal-banquet-hall/availability-modal',
    #}),
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

def search(username, password, date, guests=4, extra_days=0, headless=False):
    if extra_days:
        end = date + datetime.timedelta(days=extra_days)
        print(f"Searching for availability for {guests} guests from {date} to {end}...")
    else:
        print(f"Searching for availability for {guests} guests on {date}...")
    if not os.path.exists(COOKIE_PATH):
        print(f"Logging in...")
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=headless)
            context = browser.new_context(user_agent=AGENT)
            page = context.new_page()
            login(page, username, password)
            context.storage_state(path=COOKIE_PATH)
            browser.close()

    urls = {}
    for k, v in MAP.items():
        for meal in (LUNCH, DINNER):
            url = API % {'uuid': v['id'], 'guests': guests, 'date': date, 'meal': meal}
            urls.setdefault(k, []).append(url)
            while extra_days > 0:
                date += datetime.timedelta(days=1)
                url = API % {'uuid': v['id'], 'guests': guests, 'date': date, 'meal': meal}
                urls[k].append(url)
                extra_days -= 1
    fetch(urls, username, password, headless=headless)


def fetch(urls, username, password, headless=False):

    async def _fetch(restaurant, _urls, headless=False):
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=headless)
            context = await browser.new_context(user_agent=AGENT, storage_state=COOKIE_PATH)
            await context.storage_state(path=COOKIE_PATH)
            page = await context.new_page()
            times = []
            for u in _urls:
                await page.goto(u)
                body = await page.inner_text('body')
                body = json.loads(body)
                body['restaurant'] = restaurant
                times.append(body)
            return times

    async def fetch_all(urls, loop, headless):
        return await asyncio.wait([
            loop.create_task(
                _fetch(restaurant, url, headless=headless)
            ) for restaurant, url in urls.items()
        ])

    loop = asyncio.get_event_loop()

    print(f"Fetching schedule data...")
    results = loop.run_until_complete(fetch_all(urls, loop, headless))
    offers = {}
    for r in results:
        for task in r:
            for time in task.result():
                if 'offers' in time:
                    offers.setdefault(
                        time['restaurant'], []
                    ).extend([
                        arrow.get(o['dateTime']).date().strftime('%b %d') + ' @ ' + o['time']
                        for o in time['offers']])

    for k, v in MAP.items():
        if offers.get(k):
            url = v['url']
            print(f'\x1B[32m {k} \x1B[0m {url}')
            for t in offers[k]:
                print(f'    - {t}')
        else:
            print(f'\x1B[31m {k} \x1B[0m')

    loop.close()

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('guests', type=int)
    parser.add_argument(
        'date',
        type=lambda s: datetime.datetime.strptime(s, '%Y-%m-%d'),
    )
    parser.add_argument('--extra-days', type=int, help='length of trip, e.g., 7', default=0)
    parser.add_argument("--headless", type=strtobool, nargs='?',
                        const=True, default=True)
    args = parser.parse_args()
    username = os.getenv('DISNEY_USERNAME')
    password = os.getenv('DISNEY_PASSWORD')
    search(
        username, password, args.date.date(), extra_days=args.extra_days,
        guests=args.guests, headless=True if args.headless else False
    )
