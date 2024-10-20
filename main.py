import discord
from discord.ext import commands, tasks
from os import getenv, name
import time
from dotenv import load_dotenv
from datetime import date
import mysql.connector

intents = discord.Intents.default()
intents.voice_states = True
intents.members = True

client = discord.Client(intents=intents)
load_dotenv()

DB_HOST = getenv("DB_HOST")
DB_USER = getenv("DB_USER")
DB_PASS = getenv("DB_PASS")
DB_NAME = getenv("DB_NAME")

conn = mysql.connector.connect(
    host = DB_HOST,
    user = DB_USER,
    password = DB_PASS,
    database = DB_NAME
)

today = date.today()

#VC入退出時
@client.event
async def on_voice_state_update(member, before, after):

    if before.channel != after.channel:    
        #ユーザー入室時
        if after.channel is not None:
            cur = conn.cursor()
            cur.execute("SELECT * FROM users WHERE user_id = %s AND user_guild_id = %s", (member.id, member.guild.id))
            row = cur.fetchall()
            #登録済みユーザーではない場合の処理
            if not row:
                cur.execute("INSERT INTO users VALUES (%s, %s, %s, %s, %s)",(member.id, member.name, "0", "0", member.guild.id))
                print(member.name + "is resistered.")
                #ログイン時間の初回記録
                cur.execute("INSERT INTO day_logintime VALUES (%s, %s, %s, %s)",(member.id, str(time.time()), '0', member.guild.id))
                conn.commit()
            #2回目以降のログイン    
            else:
                cur.execute("SELECT * FROM day_logintime WHERE user_id = %s AND user_guild_id = %s", (member.id, member.guild.id))
                rec = cur.fetchall()
                rec_time = rec[0][2]
                cur.execute("UPDATE day_logintime SET user_login_time = %s, total_stay_time = %s WHERE user_id = %s AND user_guild_id = %s", (str(time.time()), rec_time, member.id, member.guild.id))
                conn.commit()
            
        #ユーザー退出時
        if before.channel is not None:
            cur = conn.cursor()
            cur.execute("SELECT * FROM day_logintime WHERE user_id = %s AND user_guild_id = %s", (member.id, member.guild.id))
            rows = cur.fetchall()
            login_time = rows[0][1]
            print(member.name + " enter the " + before.channel.name + " at " + str(login_time))

            #ユーザーの1日のログイントータル時間を登録
            cur.execute("SELECT * FROM day_logintime WHERE user_id = %s AND user_guild_id = %s", (member.id, member.guild.id))

            dayStayTime_rows = cur.fetchall()
            day_stay_time = dayStayTime_rows[0][2]
            delta_day_stay_time = float(time.time()) - float(login_time) + float(day_stay_time)
            cur.execute("UPDATE day_logintime SET user_login_time = '0', total_stay_time = %s WHERE user_id = %s AND user_guild_id = %s",(str(delta_day_stay_time), member.id, member.guild.id))
            conn.commit()


#日付管理
@tasks.loop(minutes = 1)
async def dateCheaker():
    
    global today

    if today != date.today():
        for member in client.get_all_members():
            await points_grant(member)
        today = date.today()
        print(member.id)


#日付変更時
async def points_grant(member):

    cur = conn.cursor()
    cur.execute("SELECT * FROM day_logintime WHERE user_id = %s AND user_guild_id = %s", (member.id, member.guild.id))
    rows = cur.fetchall()

    if rows:

        day_total_time = float(rows[0][2]) / 60
        cur.execute("UPDATE users SET login_total_time = %s WHERE user_id = %s AND user_guild_id = %s",(str(day_total_time), member.id, member.guild.id))
        conn.commit()
        #1日のログイン時間が120分以上
        if day_total_time >= 120:
            cur.execute("SELECT * FROM users WHERE user_id = %s AND user_guild_id = %s", (member.id, member.guild.id))    
            record_rows = cur.fetchall()
            points = record_rows[0][3]
            delta_points = points + 2
            total_time = float(record_rows[0][2])
            delta_time = total_time + day_total_time
            cur.execute("UPDATE users SET login_total_time = %s, user_points = %s WHERE user_id = %s AND user_guild_id = %s", (str(delta_time), delta_points, member.id, member.guild.id))
            cur.execute("UPDATE day_logintime SET total_stay_time = '0' WHERE user_id = %s AND user_guild_id = %s", (member.id, member.guild.id))
            conn.commit()

            print(member.id + "に2ポイント付与しました。")

            #1日のログイン時間が60分以上       
        elif day_total_time >= 60:
            cur.execute("SELECT * FROM users WHERE user_id = %s AND user_guild_id = %s", (member.id, member.guild.id))    
            record_rows = cur.fetchall()
            points = record_rows[0][3]
            delta_points = points + 1
            total_time = float(record_rows[0][2])
            delta_time = total_time + day_total_time
            cur.execute("UPDATE users SET login_total_time = %s, user_points = %s WHERE user_id = %s AND user_guild_id = %s", (str(delta_time), delta_points, member.id, member.guild.id))
            cur.execute("UPDATE day_logintime SET total_stay_time = '0' WHERE user_id = %s AND user_guild_id = %s", (member.id, member.guild.id))
            conn.commit()
            #1日のログイン時間が60分未満
            
            print(member.id + "に1ポイント付与しました。")

        else:
            cur.execute("UPDATE day_logintime SET total_stay_time = '0' WHERE user_id = %s AND user_guild_id = %s", (member.id, member.guild.id))
            conn.commit()
    
    else:
        pass

@client.event
async def on_ready():
    print(f'Logged in')
    dateCheaker.start()  # ループを開始

token = getenv('DISCORD_BOT_TOKEN')
client.run(token)