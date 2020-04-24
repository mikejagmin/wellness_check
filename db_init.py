import pymysql
from config import Config
con = pymysql.connect(host=Config.myhost,
                             user=Config.myuser,
                             password=Config.mypw,
                             db=Config.mydb,
                             charset='utf8mb4',
                             cursorclass=pymysql.cursors.DictCursor)
cur = con.cursor()

import sqlite3


def dict_factory(cursor, row):
    d = {}
    for idx, col in enumerate(cursor.description):
        d[col[0]] = row[idx]
    return d

lite_con = sqlite3.connect("alerts.db")
con.row_factory = dict_factory
lite_cur = lite_con.cursor()

cur.execute("DROP TABLE IF EXISTS slack;")
cur.execute("CREATE TABLE slack (id varchar(10) ,Name varchar(25), Location varchar(5), phone varchar(15), active bit, PRIMARY KEY (id));")
cur.execute("CREATE INDEX Location on slack(Location)")
con.commit()
# cur.execute("INSERT INTO slack values()")

cur.execute("DROP TABLE IF EXISTS contact;")
cur.execute("CREATE TABLE contact (row_id int(11) NOT NULL AUTO_INCREMENT, location varchar(25), area varchar(25), country_code varchar(5), phone varchar(15), first_name varchar(100), last_name varchar(100), active int,whatsapp int, last_reply datetime, reply text, PRIMARY KEY(location,country_code,phone), Key row_id(row_id), INDEX phone(country_code,phone), INDEX location (location), INDEX area (area));")


con.commit()
cur.execute("INSERT INTO contact (location,area,country_code,phone,first_name,last_name,active) values('aus','iah_alternates','1','3122449074','Mike','J',1);")
cur.execute("INSERT INTO contact (location,area,country_code,phone,first_name,last_name,active) values('sat','iah_alternates','1','3122449074','Melissa','L',1);")
con.commit()

cur.execute("DROP TABLE IF EXISTS channels;")
cur.execute("CREATE TABLE channels (id varchar(20), channel varchar(25), PRIMARY KEY (id), INDEX channel(channel));")
con.commit()

cur.execute("DROP TABLE IF EXISTS slack_users;")
cur.execute("CREATE TABLE slack_users (id varchar(20), name varchar(25), PRIMARY KEY (id), INDEX name(name));")
con.commit()


# print('db initalized')


# lite_cur.execute(""" DROP TABLE contact;""")
# lite_con.commit()
lite_cur.execute(""" CREATE TABLE contact (
  row_id,
  location,
  area,
  country_code,
  phone,
  first_name,
  last_name,
  active,
  whatsapp,
  last_reply,
  reply,
  PRIMARY KEY (country_code,phone,location));""" )

lite_con.commit()

# # lite_cur.execute(""" DROP TABLE slack_users;""")
# # lite_con.commit()

lite_cur.execute("""CREATE TABLE slack_users (
  id varchar(10) PRIMARY KEY,
  name varchar(50) DEFAULT NULL);""")

lite_cur.execute("""CREATE INDEX name
ON slack_users(name);""")
lite_con.commit()

# # lite_cur.execute(""" DROP TABLE channels;""")
# # lite_con.commit()

lite_cur.execute("""CREATE TABLE channels (
  id varchar(10) NOT NULL,
  channel varchar(25) DEFAULT NULL,
  PRIMARY KEY (id));""")
lite_con.commit()

lite_cur.execute("""CREATE INDEX channel
ON channels(channel);""")
lite_con.commit()
