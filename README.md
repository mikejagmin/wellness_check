# Wellness Check

## About
A **WIP** prototype leveraging Slack as a front end to twilio for use as an notification platform for emergency alerts/wellness. The application allows the Slack user to send SMS text/WhatsApp messages to large groups of SMS/WhatsApp contacts. Contacts can be organized by using Slack Channels and rolled up into a parent channel. All SMS/WhatsApp responses are posted to the contact's assigned Slack channel and also recorded in the database for response auditng. Includes a basic dataTables report with export options.

![Example Of Wellness Check](/images/updates.PNG)


## Todo
* Unit Tests
* Login with flask-login
* Drag and Drop Excel File Upload to import contacts

## How it works
Phone numbers are entered into the database either by updating the **files/contat_updated.xlsx** and leveraging the **import_contacts.py** or by using **/contact** portion of the site.
![Image Of Contact Editor](/images/modify.PNG)

**Channels** Channels should be named to correspond to the **location** contacts are assigned to. A message input into a channel will send to all contacts assigned to that channel **that have a value of 1 for active**

By default no text responses will be texted out to other contacts assigned to the channel. This can be changed by **setting BROADCAST_REPLY = True in config file. This setting enables resending of SMS text message posts to the group to create a psuedo group text**

**Channel Topics** You can leverage channel topics to create pseduo (single level) 'group messaging hierarchy'. If another channel name is added to the topic of the channel, all users of the 'child' channels will receive any messages posted to the 'parent' channel.
All responses will show up in the contact's assigned channel.

**Note each channel can only have 1 parent and the most recent parent assigned will be the parent. You can enter multiple channels into a topic by seperating with a comma (chicago, milwaukee, madison)

Incoming MMS mesages are saved to the server working/files directory by default and posted to the contact's assigned channel
**Sending of MMS messages needs to be enabled in config GC_IMAGE_SERVICE and Google cloud bucket configured**

**Adding ::eyes: reaction** The eyes reaction will trigger the message to be linked to the channel set to **'escalation_channel'** in config.py. Intention is to highlight important messages to entire workspace even if they are not subscribed to the channel the message was originally posted in.

Uses MySQL (sqlite as a fallback for critical methods such as inbound/outbound messages) for a database and a redis for a worker queue/message expiration cache for WhatsApp message template requirements (details below). Basic functionality will work without redis by leverging concurrent futures.

Slack is used for error reporting and errors are sent to channel assigned to **log_channel** in config.py 

Most Reporting/Auditing responses can be conducted from within Slack leveraging the ['slash commands'](#slash-commands)

A dataTables report is included which includes:
* Search by station
* Realtime search/filter of displayed data
* Copying the table
* Export to xls
* Export to pdf
![Example Of Web Report](/images/web_report.PNG)

## Setup

**Clone/Download this repoistory**
Install a compatible version of Python (Built on 3.7 but believe it will work on 3.6 on)

```
pip install -r requirements.txt
```

Install MySQL Server and create a database https://dev.mysql.com/downloads/
Create Redis Queue (if desired, will run with futures if redis not avialable): https://redis.io/download
Create Twilio account phone number with text capabilities.https://www.twilio.com/try-twilio

**Update example_config.py and save as config.py**

Script to create MySQL and SQLite databases.
```
python db_init.py 
``` 


Boot Development Webserver: 
```
python run.py -dev
```

I used this tutorial to get this application to production (and using https!) following this tutorial: 
https://www.digitalocean.com/community/tutorials/how-to-serve-flask-applications-with-gunicorn-and-nginx-on-ubuntu-18-04

Create a SLACK workspace if needed: https://slack.com/get-started#/

Create an App in your SLACK workspace. https://api.slack.com/

App will need to subscribe to below events at a miniumum
message.channels
reaction_added

**Your app will need to be added to the channels you want it to be able to post in.**

Add SLACK_SIGNING_SECRET to config.py and update url to https://your.address.com/inbound/chats
(I recommend ngrok for initial testing) https://ngrok.com/

You Bot will need a token to interact with the workspace for the following scopes:
channels:history View messages and other content in public channels that alerts has been added to
channels:join Join public channels in the workspace
channels:read View basic information about public channels in the workspace
chat:write Send messages as @alerts
chat:write.customize Send messages as @alerts with a customized username and avatar
chat:write.public Send messages to channels @alerts isn't a member of
im:write Start direct messages with people
files:read View files shared in channels and conversations that alerts has been added to
files:write Upload, edit, and delete files as alerts
users:read

** Once you connect to slack you will need to run utils.py to sync the slack users and channels to the MySQL/SQLite databases. You can either run this manually with 
```
python utils.py
```
or a cronjob 
```
 /5 * * * * cd ~./wellness_check && ~/slackalert/utils.py > ~/cronlog.txt 2>&1
```

***If Whatsapp is used, Approved templates are required for any message initiated by the integration after 24 hours of no responses from the recipient. I use redis to cache response times.***

If GC module is not used, outbound images will not be sent. You can enable this module by setting in config.py
```
GC_IMAGE_SERVICE = False 
```


You may enable rebroadcasting of text responses back to all recipients assigned to that channel by setting in config.py
```
BROADCAST_REPLY = True
``` 


## Slash Commands
Currently there are 3 custom slash commands to assist with audting wellness checks:

**/report** generates the excel report for the channel you are currently in and the integration uploads an xlsx report to you in a direct message
![Example Of Report](/images/report.PNG)

**/noreply** sends you a direct message with all contacts for that channel you initiate the command from that have not replied within the entered number of hours. You can enter the hours with the initial command if you like as follows: /noreply 24  Will return any contact that has not responded in the last 24 hours.
![Example Of No Reply](/images/slow.PNG)

**/contacts** Bot will send you a dm with all currently active contacts for the channel you are currently in.
![Example Of Contacts](/images/contacts.PNG)

# Configuring Slash Commands
Naviate to your previously created SLACK App via: https://api.slack.com/apps/

Naviagate to 'Slash Commands':  
Create New commands  
**Command:** /noreply  
**Request URL:** https://yoursite.come/api/noresponse  
**Short Desc:** Sends user a list of contacts who have not replied  
**Usage Hint:** [hours since last reply]  

**Command:** /contacts  
**Request URL:** https://yoursite.come/api/contacts  
**Short Desc:** Return a direct message of text message recipients for channel  
**Usage Hint:** (Blank)  

**Command:** /report  
**Request URL:** https://yoursite.come/api/excel  
**Short Desc:** Generate Excel Response Report for Channel  
**Usage Hint:** (Blank)  

Navigate to 'Interactivity & Shortcuts'  
**Requst URL:** https://yoursite.come/api/interactions  
