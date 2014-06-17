#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright Aengus Walton 2013-2014
# http://ventolin.org
# ventolin@gmail.com
#

from datetime import datetime, timedelta
import json
import os

from BeautifulSoup import BeautifulSoup
from icalendar import Calendar, Event
import logbook
import requests

OUTPUT_DIR = '/home/kopf/www/gsack-output'

URL = 'http://www.schaal-mueller.de/GelberSackinStuttgart.aspx'

DESC_TEXT = u'Gelber Sack Abholtermine fuer {0}'

log = logbook.Logger('gsack.scraper.scrape')


def clean_description(text):
    """Replaces umlauts and Eszett with non-unicode equivalents, removes unnecessary crap"""
    trans_map = {
        u'ä': 'ae',
        u'ö': 'oe',
        u'ü': 'ue',
        u'ß': 'ss',
        u' () ': ' '
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

if __name__ == '__main__':
    payload = {'__EVENTTARGET': 'ThatStreet'}
    for uid in range(1, 17):
        log.info('Processing UID {0}'.format(uid))
        payload['__EVENTARGUMENT'] = str(uid)
        resp = requests.post(URL, data=payload)
        soup = BeautifulSoup(resp.text)
        div = soup.find('div', {'id': 'dnn_ctr491_View_panResults'})
        area_name = div.find('span', {'id': 'dnn_ctr491_View_lblResults'}).text
        dates = [span.text for span in div.find('table').findAll('span')]
        data = {
            'dates': dates, 
            'description': clean_description(DESC_TEXT.format(area_name))
        }
        generate_ics_file(uid, data)
    log.info('All done!')
