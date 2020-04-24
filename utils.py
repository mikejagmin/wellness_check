import slack
from config import Config
import pymysql
# slack_token = Config.SLACK_BOT_TOKEN
slack_token = Config.SLACK_BOT_TOKEN
import time
import sqlite3


sc =  slack.WebClient(slack_token)


def dict_factory(cursor, row):
    d = {}
    for idx, col in enumerate(cursor.description):
        d[col[0]] = row[idx]
    return d


def load_channels():
    con = pymysql.connect(host=Config.myhost,
                                 user=Config.myuser,
                                 password=Config.mypw,
                                 db=Config.mydb,
                                 charset='utf8mb4',
                                 cursorclass=pymysql.cursors.DictCursor)
    cur = con.cursor()
    lite_con = sqlite3.connect(Config.mydb+'.db')
    con.row_factory = dict_factory
    lite_cur = lite_con.cursor()


    r = sc.api_call("channels.list")

    lite_cur.execute("""DELETE FROM channels;""")
    lite_con.commit()

    for row in r['channels']:
        # print(row['name'], row['id'])
        # print(row)
        print(row['id'],row['name'])
        cur.execute(("""INSERT INTO channels (id, channel) VALUES (%s, %s) ON DUPLICATE KEY UPDATE id = %s, channel = %s;"""),(row['id'],row['name'],row['id'],row['name']))
        lite_cur.execute(("""INSERT INTO channels (id, channel) VALUES (?, ?);"""),
                            (row['id'], row['name']))

    con.commit()
    lite_con.commit()

    con.close()

def load_users():
    con = pymysql.connect(host=Config.myhost,
                                 user=Config.myuser,
                                 password=Config.mypw,
                                 db=Config.mydb,
                                 charset='utf8mb4',
                                 cursorclass=pymysql.cursors.DictCursor)
    cur = con.cursor()
    lite_con = sqlite3.connect(Config.mydb+'.db')
    lite_con.row_factory = dict_factory
    lite_cur = lite_con.cursor()


    sc = slack.WebClient(Config.SLACK_BOT_TOKEN)

    r = sc.api_call("users.list")
    if len(r['members']) > 0:
        lite_cur.execute("""DELETE FROM slack_users;""")
        lite_con.commit()

        for row in r['members']:
            # print(row['name'], row['id'])
            # print(row['id'],row['profile']['display_name'])

            if len(row['profile']['display_name']) < 3:
                name = row['profile']['real_name']
            else:
                name = row['profile']['display_name']
            print(row['id'], name)
            # print(row['profile'], name)
            cur.execute(("""INSERT INTO slack_users (id, name) VALUES (%s, %s) ON DUPLICATE KEY UPDATE id = %s, name = %s;"""),
                        (row['id'], name, row['id'], name))
            lite_cur.execute(("""INSERT INTO slack_users (id, name) VALUES (?, ?);"""),
                        (row['id'], name,))
        con.commit()
        lite_con.commit()

    con.close()
    lite_con.close()

def copy_contacts():
    con = pymysql.connect(host=Config.myhost,
                                 user=Config.myuser,
                                 password=Config.mypw,
                                 db=Config.mydb,
                                 charset='utf8mb4',
                                 cursorclass=pymysql.cursors.DictCursor)
    cur = con.cursor()
    lite_con = sqlite3.connect(Config.mydb+'.db')
    con.row_factory = dict_factory
    lite_cur = lite_con.cursor()

    cur.execute("""Select * from contact;""")
    rows = cur.fetchall()
    if len(rows) > 5:
        lite_cur.execute("""DELETE FROM contact;""")
        lite_con.commit()
        for r in rows:
            lite_cur.execute("""INSERT INTO contact (location,area, country_code, phone , first_name, last_name, active,whatsapp ) """ +
                        """ values( ?, ?, ?, ?, ?, ?, ?, ?);""",
                             (r['location'], r['area'], r['country_code'], r['phone'],r['first_name'],r['last_name'], r['active'], r['whatsapp']))
        lite_con.commit()


load_channels()
load_users()
copy_contacts()