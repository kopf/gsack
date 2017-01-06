#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright Aengus Walton 2013-2014
# http://ventolin.org
# ventolin@gmail.com
#

from datetime import datetime, timedelta
import os
import re
import subprocess
import tempfile


from BeautifulSoup import BeautifulSoup
from icalendar import Calendar, Event
import logbook
import requests

OUTPUT_DIR = '/home/kopf/www/gsack-output'

URL = 'http://www.schaal-mueller.de/GelberSackinStuttgart.aspx'
PDF_URL = 'http://www.schaal-mueller.de/Portals/0/Dokumente/Gelber%20Sack%20Termine%20{year}%20Stuttgart.pdf'

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


def scrape_website():
    payload = {'__EVENTTARGET': 'ThatStreet'}
    retval = []
    for uid in range(1, 16):
        log.info('Processing UID {0}'.format(uid))
        payload['__EVENTARGUMENT'] = str(uid)
        resp = requests.post(URL, data=payload)
        soup = BeautifulSoup(resp.text)
        div = soup.find('div', {'id': 'dnn_ctr491_View_panResults'})
        area_name = div.find('span', {'id': 'dnn_ctr491_View_lblResults'}).text
        dates = [span.text for span in div.find('table').findAll('span')]
        retval.append({
            'dates': dates,
            'description': clean_description(DESC_TEXT.format(area_name))
        })
    return retval


def scrape_pdf():
    date_regex = '\d\d\.\d\d\.'
    current_year = datetime.now().year
    resp = requests.get(PDF_URL.format(year=current_year))
    _, filename = tempfile.mkstemp()
    with open(filename, 'wb') as f:
        f.write(resp.content)
    parsed = subprocess.check_output(['pdftotext', '-layout', filename, '-']).decode('utf-8')
    results = []
    for line in parsed.split('\n'):
        # Check that there are sets of dates in the line:
        if re.compile('{0} {0} {0}'.format(date_regex)).search(line):
            dates = re.findall(date_regex, line)
            for idx, date in enumerate(dates):
                if ((idx < len(dates) / 2 and '.12.' in date)
                        or (idx > len(dates) / 2 and '.01.' in date)):
                    # Either a pickup date from december from the previous year
                    # or a pickup date from january from the next year
                    del dates[idx]
            results.append({
                'dates': ['{}{}'.format(d, current_year) for d in dates],
                'description': "Gelber Sack Abholtermine"
            })
    assert len(results) == 15, ("Something went wrong! A new pickup area, or a pickup area is gone,"
                                " or we've parsed a line where there wasn't one")
    if os.path.exists(filename):
        os.remove(filename)
    return results


if __name__ == '__main__':
    try:
        data = scrape_website()
    except AttributeError:
        # They've removed the f*&king search again
        data = scrape_pdf()
    for uid, entry in enumerate(data):
        generate_ics_file(uid+1, entry)
    log.info('All done!')
