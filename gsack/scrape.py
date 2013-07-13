#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright Aengus Walton 2013
# http://ventolin.org
# ventolin@gmail.com
#

from datetime import datetime, timedelta
import json
import os
import re
import time
from urlparse import parse_qs

import BeautifulSoup
from icalendar import Calendar, Event
import logbook
import requests

from gsack.settings import POSTCODES, OUTPUT_DIR, SCRAPE_SLEEP
from gsack.lib.soupselect import select as soup_select


URL = 'https://www.sita-deutschland.de/loesungen/privathaushalte/abfuhrkalender/stuttgart.html?plz={0}'
BASE_URL = u'https://www.sita-deutschland.de/{0}'

SCRAPED = {}

log = logbook.Logger('gsack.scraper.scrape')


class UpstreamError(Exception):
    pass


def download(url):
    time.sleep(SCRAPE_SLEEP)
    try:
        retval = requests.get(url)
    except (requests.exceptions.ConnectionError,
            requests.exceptions.SSLError), e:
        log.error(u'Exception occured getting {0}: {1}'.format(url, e))
        raise UpstreamError()
    return retval


def clean_description(text):
    """Replaces umlauts and Eszett with non-unicode equivalents, removes unnecessary crap"""
    trans_map = {
        u'ä': 'ae',
        u'ö': 'oe',
        u'ü': 'ue',
        u'ß': 'ss',
        u' () ': ''
    }
    for char, replacement in trans_map.iteritems():
        text = text.replace(char, replacement)
    return text


def generate_ics_file(uid, data):
    """Processes scraped data and generates an .ics file"""
    cal = Calendar()
    cal.add('prodid', '-//GSack Calendar Generator - github.com/kopf/gsack //NONSGML//DE')
    cal.add('version', '2.0')
    cal.add('x-wr-calname', 'Gelber Sack Abholtermine')
    cal.add('x-original-url', 'http://ventolin.org/code/gelber-sack')
    cal.add('x-wr-caldesc', data.get('description'))
    for datestr in data['dates']:
        start = datetime.strptime(datestr, '%d.%m.%Y').date()
        end = start + timedelta(days=1)
        event = Event()
        event.add('summary', 'Gelber Sack Abholtermin')
        event.add('dtstart', start)
        event.add('dtend', end)
        cal.add_component(event)
    filename = '{0}.ics'.format(uid)
    with open(os.path.join(OUTPUT_DIR, filename), 'wb') as f:
        f.write(cal.to_ical())


def process_dates_page(path):
    """Processes page with on which the Abholtermine are"""
    r = download(BASE_URL.format(path))
    soup = BeautifulSoup.BeautifulSoup(r.text)
    desc = []
    for line in soup_select(soup, 'div.table p'):
        desc.append(line.text)
    desc = clean_description(u' '.join(desc))

    table = soup.find('table', {'class': 'listing'})
    regex = re.compile('\d\d\.\d\d\.\d\d\d\d')
    dates = []
    for cell in table.findAll('td'):
        result = regex.search(cell.text)
        if result is not None:
            dates.append(result.group())
    if len(dates) < 4:
        log.warn(u'Less than 4 dates scraped from {0}'.format(path))
    return {'dates': dates, 'description': desc}


def save_plz_metadata(plz, soup):
    """Save metadata for each PLZ used by the search interface"""
    result = []
    table_body = soup.find('tbody')
    rows = table_body.findAll('tr')
    for tr in rows:
        link = tr.find('td', {'class': 'cols2'}).a['href']
        uid = parse_qs(link)['uid'][0]
        street = tr.find('td', {'class': 'cols2'}).text
        info_list = []
        for element in tr.find('td', {'class': 'cols4'}).contents:
            if not isinstance(element, BeautifulSoup.Tag):
                info_list.append(element)
        amtliche_nr = tr.find('td', {'class': 'cols5'}).text
        result.append({
            'uid': uid,
            'street': street,
            'info': ', '.join(info_list),
            'amtliche_nr': amtliche_nr
        })
    with open(os.path.join(OUTPUT_DIR, '{0}.json'.format(plz)), 'w') as f:
        json.dump(result, f, indent=4)


def main():
    links = []
    for plz in POSTCODES:
        log.info('Scraping URLs for PLZ {0}'.format(plz))
        r = download(URL.format(plz))
        soup = BeautifulSoup.BeautifulSoup(r.text)
        links.extend(soup_select(soup, '.cols2 a'))
        save_plz_metadata(plz, soup)

    counter = 0
    for link in links:
        counter += 1
        if counter % 100 == 0:
            log.info('[{0}/{1}] calendar pages scraped...'.format(counter, len(links)))
        uid = parse_qs(link['href'])['uid'][0]
        if uid in SCRAPED:
            log.error('Encountered uid {0} more than once, quitting...')
            return
        try:
            raw_data = process_dates_page(link['href'])
        except UpstreamError:
            continue
        generate_ics_file(uid, raw_data)

    log.info('All done!')


if __name__ == '__main__':
    main()
