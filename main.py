import discord
import requests
import re
import asyncio
from datetime import datetime, timedelta
from itertools import islice
from youtube_comment_downloader import YoutubeCommentDownloader, SORT_BY_RECENT

# ===== তোমার তথ্য =====
DISCORD_TOKEN = "MTAxOTE4MTA5MzMxMzgzOTEyNQ.GfwBU2._cMCYwF0F8Ok_xOZgCtBcuwKvOCETJ2R6hAFcI"
TELEGRAM_TOKEN = "8851969173:AAG3VqYBR4uUnR2hb7SyWDD8JE8tdN98P8Q"

# এখানে দুইটা Telegram Chat ID দাও
TELEGRAM_CHAT_ID_1 = "8238941007"      # প্রথম অ্যাকাউন্ট
TELEGRAM_CHAT_ID_2 = "1234567890"      # দ্বিতীয় অ্যাকাউন্ট (আগেরটা)

TARGET_CHANNEL_ID = 1546211332939055266

client = discord.Client()
downloader = YoutubeCommentDownloader()

monitored_videos = {}

def send_to_telegram(text):
    """একসাথে দুইটা অ্যাকাউন্টে মেসেজ পাঠায়"""
    chat_ids = [TELEGRAM_CHAT_ID_1, TELEGRAM_CHAT_ID_2]
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    max_len = 4000

    for chat_id in chat_ids:
        for i in range(0, len(text), max_len):
            chunk = text[i:i + max_len]
            payload = {
                "chat_id": chat_id,
                "text": chunk,
                "parse_mode": "HTML",
                "disable_web_page_preview": True
            }
            try:
                requests.post(url, data=payload, timeout=15)
            except Exception as e:
                print(f"Telegram Error ({chat_id}): {e}")

def is_valid_credential(value):
    if not value:
        return False
    value = value.strip()
    if value.startswith("http") or "youtu" in value.lower() or "discord.com" in value.lower():
        return False
    if len(value) > 40:
        return False
    return True

def extract_youtube_id(text):
    patterns = [
        r'(?:youtube\.com/watch\?v=|youtu\.be/|youtube\.com/shorts/)([A-Za-z0-9_-]{11})',
        r'youtube\.com/embed/([A-Za-z0-9_-]{11})'
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return match.group(1)
    return None

def get_all_comments(video_id, limit=70):
    try:
        url = f"https://www.youtube.com/watch?v={video_id}"
        comments = downloader.get_comments_from_url(url, sort_by=SORT_BY_RECENT)
        result = []
        for comment in islice(comments, limit):
            cid = comment.get('cid') or comment.get('id') or str(hash(comment.get('text', '')))
            text = comment.get('text', '').strip()
            author = comment.get('author', 'Unknown')
            if text:
                result.append({"id": cid, "author": author, "text": text})
        return result
    except Exception as e:
        print(f"Comment fetch error: {e}")
        return []

async def monitor_video_comments(video_id, panel_link):
    end_time = datetime.now() + timedelta(hours=10)
    monitored_videos[video_id] = {"end_time": end_time, "seen": set()}

    print(f"⏳ {video_id} মনিটর শুরু (১০ ঘণ্টা)")

    comments = get_all_comments(video_id, limit=70)
    if comments:
        text = f"<b>📋 YouTube Comments</b>\nVideo: <code>{video_id}</code>\nPanel: {panel_link}\n\n"
        for c in comments:
            monitored_videos[video_id]["seen"].add(c["id"])
            text += f"<b>{c['author']}:</b>\n{c['text']}\n\n----------\n"
        send_to_telegram(text)
        print(f"✅ প্রথম {len(comments)}টা কমেন্ট পাঠানো হয়েছে")
    else:
        send_to_telegram(f"<b>📋 Comments</b>\nVideo: {video_id}\nকোনো কমেন্ট পাওয়া যায়নি।\nPanel: {panel_link}")

    while datetime.now() < end_time:
        await asyncio.sleep(60)

        if video_id not in monitored_videos:
            break

        new_comments = get_all_comments(video_id, limit=30)
        fresh = []
        for c in new_comments:
            if c["id"] not in monitored_videos[video_id]["seen"]:
                monitored_videos[video_id]["seen"].add(c["id"])
                fresh.append(c)

        if fresh:
            text = f"<b>🆕 New Comments</b>\nVideo: <code>{video_id}</code>\n\n"
            for c in fresh:
                text += f"<b>{c['author']}:</b>\n{c['text']}\n\n----------\n"
            send_to_telegram(text)
            print(f"✅ {len(fresh)}টা নতুন কমেন্ট পাঠানো হয়েছে")

    if video_id in monitored_videos:
        del monitored_videos[video_id]
    print(f"⏹️ {video_id} মনিটর শেষ")

@client.event
async def on_ready():
    print("="*50)
    print(f"✅ Logged in as: {client.user}")
    print(f"📡 Channel: {TARGET_CHANNEL_ID}")
    print(f"📱 Sending to 2 Telegram accounts")
    print("="*50)
    print("Bot is running...\n")

@client.event
async def on_message(message):
    if message.author.id == client.user.id:
        return
    if message.channel.id != TARGET_CHANNEL_ID:
        return

    content = message.content or ""
    if "external" not in content.lower() or "panel" not in content.lower():
        return

    print("\n📩 New Panel Message")

    # USER / PASS
    user = None
    password = None
    user_match = re.search(r'USER\s*[:：]\s*([^\n\r`*]+)', content, re.IGNORECASE)
    pass_match = re.search(r'PASS\s*[:：]\s*([^\n\r`*]+)', content, re.IGNORECASE)

    if user_match and is_valid_credential(user_match.group(1)):
        user = user_match.group(1).strip()
    if pass_match and is_valid_credential(pass_match.group(1)):
        password = pass_match.group(1).strip()

    # Links
    urls = re.findall(r'https?://[^\s<>"\'\)\]]+', content)
    panel_link = None
    youtube_id = None

    for url in urls:
        if "discord.com" in url or "discordapp.com" in url:
            continue
        if "youtube.com" in url or "youtu.be" in url:
            youtube_id = extract_youtube_id(url)
        else:
            panel_link = url

    if not panel_link:
        panel_link = "Panel link পাওয়া যায়নি"

    # কেস ১: সরাসরি USER + PASS
    if user and password:
        text = f"<b>🔥 EXTERNAL PANEL</b>\n\n"
        text += f"<b>USER:</b> <code>{user}</code>\n"
        text += f"<b>PASS:</b> <code>{password}</code>\n"
        text += f"\n<b>Download:</b>\n{panel_link}"
        send_to_telegram(text)
        print(f"✅ Direct USER/PASS পাঠানো হয়েছে → {user} | {password}")
        return

    # কেস ২: YouTube লিঙ্ক
    if youtube_id:
        send_to_telegram(f"<b>🔥 EXTERNAL PANEL</b>\n\n<b>Download:</b>\n{panel_link}")
        print(f"✅ Panel link পাঠানো হয়েছে")
        asyncio.create_task(monitor_video_comments(youtube_id, panel_link))
    else:
        send_to_telegram(f"<b>🔥 EXTERNAL PANEL</b>\n\n<b>Download:</b>\n{panel_link}\n\n<i>USER/PASS বা YouTube লিঙ্ক পাওয়া যায়নি</i>")
        print("⚠️ কিছুই পাওয়া যায়নি")

print("Starting bot...")
client.run(DISCORD_TOKEN)