import os
import time
import re
from config import Config
import slack
import pickle
import pymysql
import redis
import sqlite3
import mimetypes
import requests
import shutil
from urllib.parse import urlparse
import io
from google.cloud import storage

from rq import Queue

from twilio.twiml.messaging_response import MessagingResponse
from twilio.rest import Client
from config import Config
from slackeventsapi import SlackEventAdapter
import phonenumbers
from openpyxl import Workbook
from openpyxl.utils import get_column_letter

twilio_client = Client(Config.TWILIO_SID, Config.TWILIO_TOKEN)

slack_client = slack.WebClient(Config.SLACK_BOT_TOKEN)

r = redis.Redis(
    host=Config.redis_host,
    port=Config.redis_port,
    db=0)

def redis_setex_handler(key, expiration, value):
    try:
        return r.setex(key, expiration, value)
        # print('redis set', key, value)
    except:
        return None

def redis_get_handler(key):
    try:
        return r.get(key)
    except:
        return None


def dict_factory(cursor, row):
    d = {}
    for idx, col in enumerate(cursor.description):
        d[col[0]] = row[idx]
    return d

def twilio_mms(params):
    num_media = int(params.get("NumMedia"))
    files = []
    try:
        if num_media > 0:
            # Handling for twilio MMS
            for idx in range(num_media):
                media_url = params.get(f'MediaUrl{idx}')
                media_content = params.get(f'MediaContentType{idx}')
                # media_url = params.get('MediaUrl[0]')
                # media_content = params.get('MediaContentType[0]')
                file_extension = mimetypes.guess_extension(media_content)
                if file_extension == '.jpe':
                    file_extension = '.jpeg'
                content = requests.get(media_url, stream=True).raw
                media_sid = os.path.basename(urlparse(media_url).path)
                filename = '{sid}{ext}'.format(sid=media_sid, ext=file_extension)
                files.append(filename)
                with open(filename, 'wb') as out:
                    shutil.copyfileobj(content, out)
                # public_url = upload_from_file(filename)
                # files.append(public_url)
                return files
        else:
            return []
    except Exception as e:
        slack_client.chat_postMessage(
                    channel=Config.log_channel, username='worker',
                    text='Twilio Image Error ' + str(e)
                )
def upload_from_file(filename):
    client = storage.Client.from_service_account_json(
        'gcs.json')
    bucket = client.get_bucket(Config.CLOUD_STORAGE_BUCKET)
    blob = bucket.blob(filename)
    blob.upload_from_filename(filename=filename)
    url = blob.public_url
    return url


def save_image_to_storage(url, filename):
    headers = {'Authorization': 'Bearer ' + Config.SLACK_BOT_TOKEN}
    content = requests.get(url, headers=headers, stream=True).raw
    with open(filename, 'wb') as out:
        shutil.copyfileobj(content, out)
    public_url = upload_from_file(filename)
    return public_url

def format_phone(number):
    try:
        p = phonenumbers.parse(number, None)
        formatted_num = phonenumbers.format_number(
            p, phonenumbers.PhoneNumberFormat.INTERNATIONAL)
    except:
        formatted_num = number
    return formatted_num

def get_slack_display_name(id):

    mysql = None
    if id is None:
        return 'CSS'
    try:
        con = pymysql.connect(host=Config.myhost,
                                user=Config.myuser,
                                password=Config.mypw,
                                db=Config.mydb,
                                charset='utf8mb4',
                                cursorclass=pymysql.cursors.DictCursor)
        cur = con.cursor()
        mysql = True
    except:
        slack_client.chat_postMessage(
                    channel=Config.log_channel, username='worker',
                    text='Sqllite being used'
                )

        lite_con = sqlite3.connect(Config.mydb+'.db')
        lite_con.row_factory = dict_factory
        lite_cur = lite_con.cursor()

    if mysql:
        cur.execute(
            (""" select id, name from slack_users where id = %s;"""), (id))
        usr = cur.fetchone()
    else:
        lite_cur.execute(
            (""" select id, name from slack_users where id = ?;"""), (id,))
        usr = lite_cur.fetchone()

    if usr is None:
        return 'Unknown User'
    else:
        return usr['name']

    try:
        con.close()
    except:
        lite_con.close()

def send_message(message, to_who, whatsapp=0, media=None):
    # Send text through twilio
    b = ''
    try:
        if whatsapp == 1:
            # Set WhatsApp prefix and check redis to see if template is needed
            prefix = 'whatsapp:'
            final_from = 'whatsapp:' + Config.TWILIO_NUM
            redis_value = redis_get_handler(to_who)
            if redis_value is not None:
                final_message = message
            else:
                final_message = Config.w_app_template_header + \
                    message + Config.w_app_template_footer

        else:
            redis_value = None
            final_message = message
            prefix = ''
            final_from = Config.TWILIO_NUM
        to_who = prefix + '+' + \
            to_who.replace('(', '').replace(')', '').replace('-', '')
        # Send images if Gcloud module activated
        if Config.GC_IMAGE_SERVICE and  media is not None and (redis_value is not None or whatsapp == 0):
            twilio_client.api.account.messages.create(
                to=to_who,
                from_=final_from,
                body=final_message,
                media_url=media)
        else:
            twilio_client.api.account.messages.create(
                to=to_who,
                from_=final_from,
                body=final_message)
    except Exception as e:
        slack_client.chat_postMessage(
                    channel=Config.log_channel, username='worker',
                    text='Twilio failed to: ' + to_who + " " + str(e))



def send_from_id(message, channel_id, sender,media=[]):
    mysql = None
    try:
        con = pymysql.connect(host=Config.myhost,
                              user=Config.myuser,
                              password=Config.mypw,
                              db=Config.mydb,
                              charset='utf8mb4',
                              cursorclass=pymysql.cursors.DictCursor)
        cur = con.cursor()
        mysql = True
    except:
        slack_client.chat_postMessage(
                    channel=Config.log_channel, username='worker',
                    text='Sqlite being used')
        lite_con = sqlite3.connect(Config.mydb+'.db')
        lite_con.row_factory = dict_factory
        lite_cur = lite_con.cursor()
    sender_check = sender[-8:]
    if mysql:
        """Use channel id to lookup phone numbers to send message to"""
        if sender == '':
            cur.execute((""" select concat(a.country_code, a.phone) as phone, a.whatsapp from contact a left join channels b on a.location = b.channel """ +
                            """ left join channels c on a.area = c.channel where active = 1 AND (b.id = %s or c.id = %s) ;"""), (channel_id, channel_id))
        else:
            cur.execute((""" select concat(a.country_code, a.phone) as phone, a.whatsapp from contact a left join channels b on a.location = b.channel """ +
                            """ left join channels c on a.area = c.channel where active = 1 AND (b.id = %s or c.id = %s) and right(concat(a.country_code, a.phone),8) <> %s ;"""), (channel_id, channel_id, sender_check))
        rows = cur.fetchall()
    else:

        if sender == '':
            lite_cur.execute((""" select (a.country_code || a.phone) as phone, a.whatsapp from contact a left join channels b on a.location = b.channel """ +
                                """ left join channels c on a.area=c.channel where active=1 AND (b.id= ? or c.id = ?); """), (channel_id, channel_id,))
        else:
            lite_cur.execute((""" select a.country_code, (a.country_code || a.phone) as phone, a.whatsapp from contact a left join channels b on a.location = b.channel """ +
                                """ left join channels c on a.area=c.channel where active=1 AND (b.id= ? or c.id = ?) and right((a.country_code || a.phone),8) <> ?; """), (channel_id, channel_id, sender_check,))
        rows = lite_cur.fetchall()

    if len(rows) > 0:
        for r in rows:
            phone = r['phone']
            whatsapp = r['whatsapp']
            # Send out images if Google Cloud Image Module enabled
            if Config.GC_IMAGE_SERVICE and len(media) > 0:
                media_urls = media
            else:
                media_urls = None
            send_message(message, phone, whatsapp, media_urls)
            # print(message,phone, whatsapp)
    try:
        con.close()
    except:
        lite_con.close()

def parse_message(slack_events):
    """
        Parses a list of events coming from the Slack Events API to find messages.
        If a bot command is found, this function calls a function to send texts to the correct user(s) of the channel.
        If its not found, then this function returns None, None.
    """
    try:

        file_list = []
        mysql = None
        try:
            con = pymysql.connect(host=Config.myhost,
                                  user=Config.myuser,
                                  password=Config.mypw,
                                  db=Config.mydb,
                                  charset='utf8mb4',
                                  cursorclass=pymysql.cursors.DictCursor)
            cur = con.cursor()
            mysql = True
        except:
            slack_client.chat_postMessage(
                    channel=Config.log_channel, username='worker',
                    text='Sqlite being used')
            lite_con = sqlite3.connect(Config.mydb+'.db')
            lite_con.row_factory = dict_factory
            lite_cur = lite_con.cursor()
        event = slack_events["event"]
    # Quick check allows admin to make sure app is responding
        if event.get("subtype") is None and event.get("text").lower() == 'ping':
            try:
                message = event["text"]
                channel = event["channel"]
                slack_client.chat_postMessage(
                    channel=Config.log_channel, username='worker',
                    text='worker_pong'
                )
            except Exception as e:

                slack_client.chat_postMessage(
                    channel=Config.log_channel, username='worker',
                    text='Ping failed: ' + str(e)
                )
    # Handling storing>uploaading> and sharing resulting image links to twilio to send MMS
        elif event.get("subtype") is None or (Config.GC_IMAGE_SERVICE and event.get("subtype") == 'file_share'):
            channel = event["channel"].lower()
            message = event["text"]
            user = event['user']
            title = ''
            try:
                if Config.GC_IMAGE_SERVICE and len(event.get('files', '')) > 0:
                         for r in event['files']:
                            title = r["title"]
                            media_url = str(r['url_private'])
                            filename = str(r['name']) + str(r['timestamp'])
                            public_url = save_image_to_storage(
                                media_url, filename)
                            file_list.append(public_url)
            except Exception as e:
                slack_client.chat_postMessage(
                    channel=Config.log_channel, username='worker',
                    text='Image Error: ' + str(e)
                )
    # If no body in MMS text, add body of 'media message'
            if len(message) < 2:
                message = message = ' media message '
            if mysql:
                cur.execute(
                    (""" select id, name from slack_users where id = %s;"""), (user))
                usr = cur.fetchone()
            else:
                lite_cur.execute(
                    (""" select id, name from slack_users where id = ?;"""), (user,))
                usr = lite_cur.fetchone()
            try:
                if usr['id'] == Config.bot_user and len(title) > 5:
                    user = title
                else:
                    user = ' -' + usr['name']
                message = message + user
                send_from_id(message, channel, user, file_list)
            except:
                slack_client.chat_postMessage(
                    channel=Config.log_channel, username='worker',
                    text="Unknown User: ' + str(user))")
    # Rebroadcast Inbound SMS Messages (or any messages posted by bot)
        elif Config.BROADCAST_REPLY and event.get("subtype") == "bot_message":
            if event['username'] not in ['ErrorReporting']:
                channel = event["channel"].lower()
                message = event["text"]
                user_start = event['username'].find(': ')
                user = event['username'][user_start+2:]
                if mysql:
                    cur.execute(
                        (""" select name from slack_users where id = %s;"""), (user))
                    usr = cur.fetchone()
                else:
                    lite_cur.execute(
                        (""" select name from slack_users where id = ?;"""), (user,))
                    usr = lite_cur.fetchone()
                message = message + '- ' + event['username']
                send_from_id(message, channel, user, file_list)
    # Set Channel topic control of areas for area wide messages
        elif event["subtype"] == "channel_topic":
            print(event)
            topic = event["topic"]
            station_list = topic.split(',')
            channel = event["channel"]
            cur.execute(
                    ("""Select * from channels where id = %s;"""), channel)
            rows = cur.fetchone()
            parent = rows['channel']
            cur.execute((
                    """update contact set area = '' where area = %s;"""), (parent))
            con.commit()
            for row in station_list:
                print(row.strip().lower(), ' set to ', parent)
                cur.execute(
                    ("""update contact set area = %s where lower(location) = %s and active = '1';"""), (parent, row.strip().lower()))
                con.commit()
        try:
            con.close()
        except:
            lite_con.close()

        return None, None
    except Exception as e:
        slack_client.chat_postMessage(
                    channel=Config.log_channel, username='worker',
                    text='Big Error: ' + str(e)
                )


def incoming_sms(pick):
    params = pickle.loads(pick)
    # print(params)
    mysql = None
    try:
        con = pymysql.connect(host=Config.myhost,
                              user=Config.myuser,
                              password=Config.mypw,
                              db=Config.mydb,
                              charset='utf8mb4',
                              cursorclass=pymysql.cursors.DictCursor)
        cur = con.cursor()
        mysql = True
    except:
        print('sqlite being used')
        lite_con = sqlite3.connect(Config.mydb+'.db')
        lite_con.row_factory = dict_factory
        lite_cur = lite_con.cursor()

    """Use phone number to lookup station/channel"""

    
    body = params.get('Body', None)
    from_ = params.get('From', None)
    

    files= twilio_mms(params)

    if from_[0:9] == 'whatsapp:':
        from_number = from_[10:]
        icon = ':whatsapp:'
        # Set redis to 24 hour expiration from most recent response for number
        redis_setex_handler(from_number, 86400, from_number)
    else:
        from_number = from_[1:]
        icon = ":iphone"

    if mysql:
        cur.execute(
            ("""Select * from contact a join channels b on a.location = b.channel where concat(country_code,phone) = %s order by a.active desc;"""), from_number)
        rows = cur.fetchone()
        # Set last reply nd timestamp in db
        cur.execute(("""update contact set last_reply = UTC_TIMESTAMP(), reply = %s where concat(country_code,phone) = %s;"""),(body, from_number,))
        con.commit()
    else:
        lite_cur.execute(
            ("""Select id, location, ifnull(first_name,'') as first_name, ifnull(last_name,'') as last_name  """ + \
            """ from contact a join channels b on a.location = b.channel where (country_code || phone) = ? order by a.active desc;"""), (from_number,))
        rows = lite_cur.fetchone()

    if rows:
        ###### Replace channel/user w method for phone number to station lookup #################
        channel = rows['id']
        from_user = rows['location'].upper() + ' ' + \
            rows['first_name'] + ' ' + str(rows.get('last_name','')) + ': ' + from_number
        if len(files) > 0:
            for p in files:
                with io.open(p, 'rb') as f:
                    response = slack_client.files_upload(
                        channels=channel, username=from_user,
                        file=f, filename=p, title=body+ ' - ' + str(from_user),
                        text=body + ' - ' + str(from_user)
                    )
                    # print(response)
        else:
            slack_client.chat_postMessage(
                channel=channel, username=from_user,
                text=body, icon_emoji=icon
            )
    else:
        # Post text's from unknown users to #general
        cur.execute(("""Select * from channels where channel = 'general';"""))
        rows = cur.fetchone()
        slack_client.chat_postMessage(
            channel=rows['channel'], username='UNKNOWN '+str(from_),
            text=body, icon_emoji=":iphone:"
        )
    try:
        con.close()
    except:
        lite_con.close()
    
def reaction_parse(event):
    # Look for eyes and post these messages to Config.escalation_channel
    try:
        item = event["item"]
        m_type = item["type"]
        react_type = event["reaction"]
        user = event["user"]
        from_user = get_slack_display_name(user)
        if m_type == "message" and react_type == "eyes":
            channel = item["channel"]
            ts = item["ts"]
            #Get link to message
            perma_link = slack_client.chat_getPermalink(
                    channel=channel, message_ts=ts
                )
            link = perma_link['permalink']
            #post to escalated channel
            slack_client.chat_postMessage(
                channel=Config.escalation_channel, username=from_user,
                text=link, icon_emoji=":eyes:",
                unfurl_links='true'
            )
    except Exception as e:
        slack_client.chat_postMessage(
                    channel=Config.log_channel, username='worker',
                    text='reaction Failed: ' + str(e)
                )

def create_excel(channel_name,user_id):
    try:
        con = pymysql.connect(host=Config.myhost,
                            user=Config.myuser,
                            password=Config.mypw,
                            db=Config.mydb,
                            charset='utf8mb4',
                            cursorclass=pymysql.cursors.DictCursor)
        cur = con.cursor()

        api_response = slack_client.im_open(
            user=user_id,
        )
        dm = api_response['channel']['id']
        cur.execute("""Select location, first_name,last_name, country_code, phone,""" + \
            """ DATE_FORMAT(last_reply, "%%c/%%d-%%H:%%i") as last_reply, reply """ + \
            """ from contact where active = 1 and upper(location) like concat(%s,'%%') order by last_reply;""",
                    (channel_name))
        rows = cur.fetchall()
        wb = Workbook()
        dest_filename = channel_name + '_report.xlsx'
        dest_filelocation = 'files/'+ dest_filename
        ws1 = wb.active
        ws1.title = channel_name
        header = ['Location','First Name','Last Name','Phone', 'Last Reply','Reply']
        ws1.append(header)
        if len(rows) > 0:
            for r in rows:
                phone = format_phone('+' + r['country_code'] + r['phone'])
                li = [r['location'],r['first_name'], r['last_name'],phone,r['last_reply'],r['reply']]
                ws1.append(li)
        else:
            ws1['A2'].value = 'No Contacts Available'
        wb.save(filename = dest_filelocation)
        con.close()

        with io.open(dest_filelocation, 'rb') as f:
                response = slack_client.files_upload(
                    channels=dm, username='Reporter',icon_emoji="robot_face",
                    file=f, filename=dest_filename, title= 'Report for ' + channel_name,
                    text='Report for ' + channel_name
                )

    except Exception as e:
        error = " Excel Create Error " + str(e)
        slack_client.chat_postMessage(
            channel=Config.log_channel,
            icon_emoji="robot_face",
            username="CSS Helper",
            text=error)

def noreply(user_id,view,hours):
    try:
        channel_blob = view.get('private_metadata').split('|')
        channel_id = channel_blob[0]
        channel_name = channel_blob[1]
        channel_name = str(channel_name).upper()
        blocks = view.get('blocks')
        state = view.get('state')

        api_response = slack_client.im_open(
            user=user_id,
        )
        dm = api_response['channel']['id']
        con = pymysql.connect(host=Config.myhost,
                user=Config.myuser,
                password=Config.mypw,
                db=Config.mydb,
                charset='utf8mb4',
                cursorclass=pymysql.cursors.DictCursor)
        cur = con.cursor()
        cur.execute("""Select first_name,last_name, country_code, phone, location, """ + \
            """ DATE_FORMAT(last_reply, "%%c/%%d-%%H:%%i") as last_reply """ + \
            """ from contact where active = 1 and upper(location) like concat(%s,'%%') and """ + \
            """ last_reply < DATE_ADD(utc_timestamp(), INTERVAL -%s HOUR) order by last_reply desc;""",
        (channel_name, hours))
        rows = cur.fetchall()
        if len(rows) > 0:
            body = channel_name.upper() + ' No Reply in last ' + hours + ' hours\n'
            for r in rows:
                phone = format_phone('+' + r['country_code'] + r['phone'])
                body += r['location'] + ': ' + r['first_name'] + ' ' + r['last_name'] + ' ' + \
                    phone + ' last reply: ' + r['last_reply'] + '\n'
            con.close()
        else:
            body = 'No matches found'
            con.close()
        response = slack_client.chat_postMessage(
            channel=dm,
            icon_emoji="robot_face",
            username="Helper",
            text=body)
    except Exception as e:
        error = " No Reply Worker Error " + str(e)
        slack_client.chat_postMessage(
            channel=Config.log_channel,
            icon_emoji="robot_face",
            username="CSS Helper",
            text=error)

def dm_contacts(channel_name,user_id):
    try:
        con = pymysql.connect(host=Config.myhost,
                                    user=Config.myuser,
                                    password=Config.mypw,
                                    db=Config.mydb,
                                    charset='utf8mb4',
                                    cursorclass=pymysql.cursors.DictCursor)
        cur = con.cursor()

        api_response = slack_client.im_open(
            user=user_id,
        )
        dm = api_response['channel']['id']
        cur.execute("""Select first_name,last_name, country_code, phone, location from contact where active = 1 and location = %s order by last_name;""",
                    (channel_name))
        rows = cur.fetchall()
        if len(rows) > 0:
            body = channel_name.upper() + ' Text Recipients\n'
            for r in rows:
                phone = format_phone('+' + r['country_code'] + r['phone'])
                body += r['location'] + ': ' + r['first_name'] + ' ' + r['last_name'] + ' ' + phone + '\n'
            con.close()
        else:
            body = 'No text recipients'
            con.close()
        response = slack_client.chat_postMessage(
            channel=dm,
            icon_emoji="robot_face",
            username="CSS Helper",
            text=body)
            # print(api_response)
    except Exception as e:
        error = "DM Contacts Worker Error " + str(e)
        slack_client.chat_postMessage(
            channel=Config.log_channel,
            icon_emoji="robot_face",
            username="CSS Helper",
            text=error)
