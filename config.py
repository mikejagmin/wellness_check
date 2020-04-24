from dotenv import load_dotenv
import os
load_dotenv()

class Config(object):
    SLACK_BOT_TOKEN = os.environ.get("SLACK_BOT_TOKEN")
    SLACK_SIGNING_SECRET = os.environ.get("SLACK_SIGNING_SECRET")
    IMAGE_TOKEN = os.environ.get("IMAGE_TOKEN")
    TWILIO_SID = os.environ.get("TWILIO_SID")
    TWILIO_TOKEN = os.environ.get("TWILIO_TOKEN")
    myhost = os.environ.get("myhost")
    myuser = os.environ.get("myuser")
    mypw = os.environ.get("mypw")
    mydb = os.environ.get("mydb")
    SLACK_HOOK = os.environ.get("SLACK_HOOK")
    # TWILIO_NUM = "+13126636115"
    TWILIO_NUM = os.environ.get("TWILIO_NUM")
    login_user = os.environ.get("login_user")
    login_password = os.environ.get("login_password")
    log_channel = os.environ.get("log_channel")
    escalation_channel = os.environ.get("escalation_channel")

    SLACK_TOKEN = os.environ.get("SLACK_TOKEN")
    
    redis_host = os.environ.get("redis_host")
    redis_port = os.environ.get("redis_port")
    CLOUD_STORAGE_BUCKET = os.environ.get("CLOUD_STORAGE_BUCKET")
    CLOUD_PROJECT = os.environ.get("CLOUD_PROJECT")
    GCS_TOKEN = os.environ.get("GCS_TOKEN")

    BROADCAST_REPLY = False
    GC_IMAGE_SERVICE = False
    w_app_template_header = 'You have a message from Demo:'
    w_app_template_footer = 'Please confirm receipt'
    
    bot_user = 'bot_user'
    queue = 'alert'