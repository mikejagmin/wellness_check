import os
import time
import re
from config import Config
import slack

import pymysql
from redis import Redis
import sqlite3
import mimetypes
import requests
import shutil
from urllib.parse import urlparse
import io
from google.cloud import storage

import sys
from rq import Connection, Worker

from message_parser import *


from twilio.twiml.messaging_response import MessagingResponse
from twilio.rest import Client
from config import Config
from slackeventsapi import SlackEventAdapter

twilio_client = Client(Config.TWILIO_SID, Config.TWILIO_TOKEN)

slack_client = slack.WebClient(Config.SLACK_BOT_TOKEN)

listen = [Config.queue]

with Connection():
    qs = sys.argv[1:] or listen

    w = Worker(qs, connection=Redis(Config.redis_host))

w.work()
