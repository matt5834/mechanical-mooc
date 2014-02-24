from mailgun import api as mailgun_api
from mailgun.utils import parse_timestamp
from signup import models as signup_api
from groups import models as groups_api
from data.utils import write_to_csv
from data.emails import export_emails

from django.conf import settings

import sqlite3
import unicodecsv
from datetime import datetime

def old_sequence_users(sequence):
    conn = sqlite3.connect('/home/dirk/workspace/mooc-heroku/prod-2013-03-26.db')
    cur = conn.execute('select email, timezone, created_at, group_id from users where round={0};'.format(sequence))
    data = cur.fetchall()
    users = []
    labels = [p[0] for p in cur.description]
    for row in data:
        users += [dict(zip(labels, row))]
    return users


def _fetch_all(fetch_function):
    results = []
    page = 0
    while True:
        try:
            print('Fetching page {0}'.format(page))
            new = fetch_function(page)
            if not isinstance(new, list) or len(new) == 0:
                break
            results += new
            page += 1
        except Exception as e:
            print(e)
            print('something went wrong. retrying')
    return results


def get_old_data_aggregated():
    # get campaign data for mooc sequence 1,2 & 3
    sequences = [('1', 'bqtde'), ('2', 'br67o'), ('3','brmcg')]
    for sequence, campaign_id in sequences:
        print(sequence)
        print('getting opens')
        get_opens = lambda p: mailgun_api.get_campaign_opens(campaign_id, ['recipient', 'day'], page=p)
        opens = _fetch_all(get_opens)
        write_to_csv(opens, 'sequence_{0}_opens.csv'.format(sequence))
    
        print('getting clicks')
        get_clicks = lambda p: mailgun_api.get_campaign_clicks(campaign_id, ['recipient', 'day'], page=p)
        clicks = _fetch_all(get_clicks)
        write_to_csv(clicks, 'sequence_{0}_clicks.csv'.format(sequence))

        print('getting links')
        get_links = lambda p: mailgun_api.get_campaign_clicks(campaign_id, ['link', 'day'], page=p)
        links = _fetch_all(get_links)
        write_to_csv(links, 'sequence_{0}_links.csv'.format(sequence))


def dump_old_data():

    sequences = [('1', 'bqtde'), ('2', 'br67o'), ('3','brmcg')]
    user_keys = ['email', 'created_at', 'group_id', 'group_size']
    event_keys = ['event', 'timestamp', 'tags', 'link']
    for sequence, campaign_id in sequences:
        writer = unicodecsv.writer(open('sequence_{0}_all.csv'.format(sequence), 'w'))
        users = old_sequence_users(sequence)
        for user in users:
            user['group_size'] = 0
            if user['group_id']:
                user['group_size'] = len([u for u in users if u['group_id'] == user['group_id']])
        sequence_data = []
        for i, user in enumerate(users):
            print('getting data for user {0} of {1}: {2}'.format(i,len(users),user['email']))
            get_stats = lambda p: mailgun_api.get_campaign_events(campaign_id, ['opened', 'clicked'], recipient=user['email'], page=p)
            user_stats = _fetch_all(get_stats)
            for event in user_stats:
                if 'link' not in event:
                    event['link'] = ''
                event['tags'] = str(event['tags'])
                row = [ user[key] for key in user_keys ]
                row += [ event[key] for key in event_keys ]
                writer.writerow(row)


def get_user_mail_activity(logs, email):
    logs = mailgun_api.get_logs(limit=0)
    user_emails = filter(event_filter, logs)


def dump_data(prefix=''):
    sequences = [(4, 'sequence_4_campaign'), (5, 'sequence_5_campaign')]
    #sequences = [(1, 'sequence_1_campaign')]
    user_keys = ['email', 'date_created', 'group_id', 'group_size']
    event_keys = ['event', 'timestamp', 'tags', 'link']
    for sequence, campaign_id in sequences:
        users = signup_api.get_signups_for_archiving(sequence)
        for user in users:
            user['group_size'] = 0
            user['group_id'] = None
            user_groups = groups_api.get_member_groups(user['email'])
            if len(user_groups) == 1:
                user['group_id'] = user_groups[0]['address']
                user['group_size'] = len(user_groups[0]['members'])
            user.update(user['questions'])
            del user['questions']

        # open file for writing data
        timestamp = datetime.now().date().isoformat()
        filename = '_'.join([prefix, 'sequence', str(sequence), 'users', timestamp]).strip('_') + '.csv'
        write_to_csv(users, filename)

        filename = '_'.join([prefix, 'sequence', str(sequence), 'events', timestamp]).strip('_') + '.csv'
        writer = unicodecsv.writer(open(filename, 'w'))
        writer.writerow(user_keys + event_keys)

        sequence_data = []
        for i, user in enumerate(users):
            print('getting data for user {0} of {1}: {2}'.format(i,len(users),user['email']))
            get_stats = lambda p: mailgun_api.get_campaign_events(campaign_id, ['opened', 'clicked'], recipient=user['email'], page=p)
            user_stats = _fetch_all(get_stats)
            for event in user_stats:
                if 'link' not in event:
                    event['link'] = ''
                event['tags'] = str(event['tags'])
                row = [ user[key] for key in user_keys ]
                row += [ event[key] for key in event_keys ]
                writer.writerow(row)

        export_emails('_'.join([prefix, 'sequence', str(sequence)]).strip('_'))
