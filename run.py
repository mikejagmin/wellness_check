import os
import time
import re
from config import Config
import slack
import json
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
from concurrent.futures import ThreadPoolExecutor
from flask import Flask, render_template, request, url_for, jsonify, abort, make_response, redirect
from flask_basicauth import BasicAuth
from functools import wraps

# from message_parser import parse_message, redis_setex_handler, redis_get_handler, dict_factory, upload_from_file, save_image_to_storage
from message_parser import *

from twilio.twiml.messaging_response import MessagingResponse
from twilio.rest import Client
from twilio.request_validator import RequestValidator
from slackeventsapi import SlackEventAdapter
import phonenumbers
import pickle

pool = ThreadPoolExecutor(3)


app = Flask(__name__)

app.config['BASIC_AUTH_USERNAME'] = Config.login_user
app.config['BASIC_AUTH_PASSWORD'] = Config.login_password
basic_auth = BasicAuth(app)

twilio_client = Client(Config.TWILIO_SID, Config.TWILIO_TOKEN)

# instantiate Slack client
slack_client = slack.WebClient(Config.SLACK_BOT_TOKEN)
# starterbot's user ID in Slack: value is assigned after the bot starts up
starterbot_id = None

# constants
RTM_READ_DELAY = 1 # 1 second delay between reading from RTM
EXAMPLE_COMMAND = "do"
MENTION_REGEX = "^<@(|[WU].+?)>(.*)"

r = redis.Redis(
    host=Config.redis_host,
    port=Config.redis_port,
    db=0)

queue = Queue(Config.queue, connection=r)


    
def validate_twilio_request(f):
    """Validates that incoming requests genuinely originated from Twilio"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Create an instance of the RequestValidator class
        validator = RequestValidator(Config.TWILIO_TOKEN)

        # Validate the request using its URL, POST data,
        # and X-TWILIO-SIGNATURE header
        request_valid = validator.validate(
            request.url,
            request.form,
            request.headers.get('X-TWILIO-SIGNATURE', ''))

        # Continue processing the request if it's valid, return a 403 error if
        # it's not
        if request_valid:
            return f(*args, **kwargs)
        else:
            return abort(403)
    return decorated_function


"""Post incoming SMS to Slack"""
@app.route("/sms", methods=['POST'])
@validate_twilio_request
def queue_sms():
    values = request.values.to_dict()
    # print(values)
    final = pickle.dumps(values)
    resp = MessagingResponse()
    try:
        queue.enqueue_call(
            incoming_sms, args=(final,), result_ttl=0)
        return str(resp)
    except:
        future = pool.submit(incoming_sms, (final))
        # incoming_sms(final)
        return str(resp)

@app.route("/")
@basic_auth.required
def index():
    return render_template('report.html', location='')


@app.route("/report")
@basic_auth.required
def report():
    """View list of responses"""
    location = ''
    if 'location' in request.args and len(request.args.get('location')) > 0:
        location = request.args.get('location','').upper()
        print(location)
    return render_template('report.html', location=location)

@app.route("/contact/", methods=['GET','POST'])
@basic_auth.required
def contact():
    con = pymysql.connect(host=Config.myhost,
                                 user=Config.myuser,
                                 password=Config.mypw,
                                 db=Config.mydb,
                                 charset='utf8mb4',
                                 cursorclass=pymysql.cursors.DictCursor)
    cur = con.cursor()
    one = False
    x = 1
    if request.method == 'POST':
        """Updates Station Phone Numbers"""
        while request.form.get('row_id'+str(x)):
            try:
                phone = str(request.form['phone'+str(x)]).replace('(','').replace(')','').replace('-','').replace(' ','')
                if len(request.form['phone'+str(x)]) > 1 and len(request.form['location'+str(x)]) > 1:
                    cur.execute("""UPDATE contact set location = %s, area = %s, country_code = %s, phone = %s, first_name = %s,last_name = %s, active  = %s, whatsapp = %s WHERE row_id = %s;""",
                                (request.form['location'+str(x)], request.form['area'+str(x)], request.form['country_code'+str(x)], phone,
                                request.form['first_name'+str(x)],request.form['last_name'+str(x)], request.form['active'+str(x)],
                                request.form.get('whatsapp'+str(x),'0'), request.form['row_id'+str(x)]))
                con.commit()
                x +=1
            except Exception as e:
                # slack.post('Cotact Update Failure: ' + str(e))
                print(e)

        try:
            if len(request.form['phone_new']) > 1 and len(request.form['location_new']) > 1:
                phone = request.form['phone_new'].replace('(','').replace(')','').replace('-','').replace(' ','')
                cur.execute("""INSERT INTO contact (location,area, country_code, phone , first_name, last_name, active,whatsapp ) """ + \
                """ values( %s, %s, %s, %s, %s, %s, %s, %s);""",
                (request.form['location_new'], request.form['area_new'], request.form['country_code_new'], phone, request.form['first_name_new'],
                 request.form['last_name_new'],request.form['active_new'], request.form.get('whatsapp_new','0')))
                con.commit()
        except Exception as e:
                slack_client.chat_postMessage(
                    channel=Config.log_channel, username='worker',
                    text='New Cotact Failure: ' + str(e)
                )
    if 'phone_search' in request.args and (len(request.args.get('phone_search','')) > 0 or len(request.args.get('location_search','')) > 0 or len(request.args.get('group_search','')) > 0):
        q = """Select row_id, upper(id) as id, location, country_code, phone, trim(first_name) as first_name, trim(last_name) as last_name, active, area, """ + \
            """ ifnull(whatsapp,'0') as whatsapp from contact a join channels b on a.location = b.channel """
        if len(request.args.get('group_search','')) > 0:
            q = q + """ where area = %s order by location;"""
            cur.execute(q, request.args.get('group_search','').lower())
        elif len(request.args.get('location_search','')) > 0:
            q = q + """ where location = %s order by location;"""
            cur.execute(q, request.args.get('location_search','').lower())
        elif len(request.args.get('phone_search','')) > 0:
            q = q + """ where phone = %s order by location;"""
            cur.execute(q, request.args.get('phone_search'))
    elif request.form.get('location1',''):
        q = """Select row_id, upper(id) as id, location,country_code, phone, trim(first_name) as first_name, trim(last_name) as last_name, active, area, ifnull(whatsapp,'0') as whatsapp """ + \
            """ from contact a join channels b on a.location = b.channel """
        q = q + """ where location = %s order by location;"""
        cur.execute(q, request.form.get('location1'))
    else:
        cur.execute("""Select row_id, upper(id) as id, location, country_code, phone, trim(first_name) as first_name, trim(last_name) as last_name, active, area, ifnull(whatsapp,'0') as whatsapp """ + \
            """ from contact a join channels b on a.location = b.channel where b.channel is null order by location;""")
    rows = cur.fetchall()
    # print(rows)
    r = (rows[0] if rows else None) if one else rows

    # cur.execute("""Select channel from channels where channel not in ('general','random','bot') order by channel;""")
    # chans = cur.fetchall()
    # channel_list = (chans[0] if chans else None) if one else chans
    # print(channel_list)
    con.close()
    return render_template('contact.html', locations=r)

slack_events_adapter = SlackEventAdapter(
    Config.SLACK_SIGNING_SECRET, "/inbound/chats", app)

@app.route("/api/contacts", methods=['GET','POST'])
def api_contacts():
    try:
        if request.values.get('command', None) == '/contacts':
            con = pymysql.connect(host=Config.myhost,
                                user=Config.myuser,
                                password=Config.mypw,
                                db=Config.mydb,
                                charset='utf8mb4',
                                cursorclass=pymysql.cursors.DictCursor)
            cur = con.cursor()
            channel_name=request.values.get('channel_name', '').upper()
            # channel_name = 'tst'
            user_id = request.values.get('user_id', None)
            api_response = slack_client.im_open(
                user=user_id,
            )
            dm = api_response['channel']['id']
            cur.execute("""Select name, country_code, phone, location from contact where active = 1 and location = %s order by name;""",
                        (channel_name))
            rows = cur.fetchall()
            if len(rows) > 0:
                body = channel_name.upper() + ' Text Recipients\n'
                for r in rows:
                    phone = format_phone('+' + r['country_code'] + r['phone'])
                    body += r['name'] + ' ' + phone + '\n'
            else:
                body = 'No text recipients'
            response = slack_client.chat_postMessage(
                channel=dm,
                icon_emoji="robot_face",
                username="CSS Helper",
                text=body)
                
                # print(api_response)
    except Exception as e:
        error = " Directory Error " + str(e)
        slack_client.chat_postMessage(
            channel="CCT9Z8MT7",
            icon_emoji="robot_face",
            username="CSS Helper",
            text=error)

    return ('', 200)


# Create an event listener for "message" events
@slack_events_adapter.on("message")
def queue_events(slack_events):
    event = slack_events["event"]
    # print(slack_events)
    # print(event)
    if event["channel"] ==  Config.log_channel:
        if event.get("subtype") is None and event.get("text").lower() == 'ping':
            try:
                channel = event["channel"]
                slack_client.chat_postMessage(
                    channel=channel, username='web',
                    text='web_pong'
                )

            except:
                print('busted')
    else:
        try:
            queue.enqueue_call(
                parse_message, args=(slack_events,), result_ttl=0)
        except:
            # parse_message(slack_events)
            future = pool.submit(parse_message, (slack_events))
            print('no queue')
            # print(future.done())
    resp = jsonify(success=True)
    resp.status_code = 200
    return resp

@slack_events_adapter.on("view_submission")
def view_submission(payload):
    print(str(payload))

@slack_events_adapter.on("reaction_added")
def reaction_added(slack_events):
    event = slack_events["event"]
    try:
        queue.enqueue_call(
            reaction_parse, args=(event,), result_ttl=0)
    except:
        # parse_message(slack_events)
        future = pool.submit(reaction_parse, (event))
        print('no queue')
        # print(future.done())




# Error events
@slack_events_adapter.on("error")
def error_handler(err):
    print("ERROR: " + str(err))

@app.route('/api/report', methods=['GET'])
def api_report():

    q = """select location, area, first_name,last_name,country_code,phone, """ + \
        """ DATE_FORMAT(last_reply, "%c/%d-%H:%i") as last_reply, reply """ + \
        """ from contact """ 
    
    one = False
    con = pymysql.connect(host=Config.myhost,
                                user=Config.myuser,
                                password=Config.mypw,
                                db=Config.mydb,
                                charset='utf8mb4',
                                cursorclass=pymysql.cursors.DictCursor)
    cur = con.cursor()
    if request.args and len(request.args.get('location','')) > 1:
        location = (request.args.get('location')).upper()
        q = q.replace('%','%%')

        q = q + """ where upper(location) like concat(%s,'%%') order by last_reply;"""
        cur.execute(q,location)
    else:
        q = q + ' order by last_reply;'
        cur.execute(q)

    rows = cur.fetchall()
    r = (rows[0] if rows else None) if one else rows
    con.close()

    jsonresponse = jsonify({
        'results': r
    })

    return jsonresponse

if __name__ == "__main__":
    app.run(host='0.0.0.0',port=80,debug=True)
