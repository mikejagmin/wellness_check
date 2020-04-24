# slackalert

## About
A prototype leveraging SLACK as a front end to twilio for use as an messaging platform for emergency alerts/wellness. The app will post all responses to the recipents assigned channel and also records responses in the database with a basic dataTables report.

## How it works
Phone numbers are entered into the  database under a location which will align to a slack channel

When a message is sent to the channel, every phone number (As long as marked active) will receive the message.

Channel Topics. You can leverage channel topics to create pseduo (single level) 'group messaging hierarchy'. If another channel name is added to the topic of the channel, all users of the entered 'child' channels will receive any messages posted to the 'parent' channel. Note each channel can only have 1 parent and the most recent parent assigned will be the parent. You can enter multiple channels into a topic by seperating with a comma (chicago, milwaukee, madison)

Any message sent to a 'group channel' will send the message to everyone in the channels listed in the 'channel topic'.
All responses will show up in the contact's assigned channel.
***You can set BROADCAST_REPLY = True in config file to rebroadcast all replies back out to the group to create a psuedo group text***

Incoming MMS mesages are saved to the server working directory by default and posted to the contact's assigned channel
***Sending of MMS messages needs to be enabled in config GC_IMAGE_SERVICE and Google cloud bucket configured***

Uses Mysql (sqlite as a fallback) for a database and a redis for a worker queue/message expiration cache for WhatsApp message template requirements (details below). Basic functionality will work without redis by leverging concurrent futures.

Slack is used for error reporting and sent to channel set in 'log_channel' in config.py 

Setup:
Create MySQL Database, redis server, twilio account phone number with text capabilities.
update example_config and save as config.py

run db_init.py script to create mysql and sqlite databases.

Create a SLACK workspace if needed: https://slack.com/get-started#/

Create an App in your SLACK workspace. https://api.slack.com/

App will need to subscribe to below events at a miniumum
message.channels
reaction_added

***Your app will need to be added to the channels you want it to be able to post in.***

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

***If Whatsapp is used, they require approved templates for any message initiated by the integration after 24 hours of no responses from the recipient. I use redis to cache response times.***

If GC module is not used, outbound images will not be sent. You can enable this module by setting GC_IMAGE_SERVICE = False in config.py

You may enable rebroadcasting of text responses back to all recipients assigned to that channel by setting 'broadcast_reply' = True in config.py



