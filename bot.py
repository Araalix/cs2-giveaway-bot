import random
import sqlite3
import json
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

import os

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))



DB_FILE = "giveaway.db"

def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    
    # Create tables if they don't exist
    c.execute('''CREATE TABLE IF NOT EXISTS giveaways
                 (id INTEGER PRIMARY KEY, name TEXT, prize TEXT, active INTEGER)''')
    c.execute('''CREATE TABLE IF NOT EXISTS participants
                 (giveaway_id INTEGER, user_id INTEGER, username TEXT, joined_at TEXT)''')
    
    # Add new columns if they don't exist yet
    try:
        c.execute("ALTER TABLE giveaways ADD COLUMN fake_participants INTEGER DEFAULT 0")
    except:
        pass  # Column already exists
    
    try:
        c.execute("ALTER TABLE giveaways ADD COLUMN fake_entries INTEGER DEFAULT 0")
    except:
        pass  # Column already exists
    
    conn.commit()
    conn.close()

init_db()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("CS2 Skin Giveaway Bot v2\nUse /help for commands")

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = """Commands:
    /newgiveaway <name> <prize> - Start new giveaway (admin)
    /enter - Join current giveaway
    /pickwinner - Select winner (admin)
    /stats - Show current stats
    /report - Export participation report (admin)
    /fakestats <number> - Force fake participant count (admin)"""
    await update.message.reply_text(text)

async def new_giveaway(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    if len(context.args) < 2:
        await update.message.reply_text("Usage: /newgiveaway Name Prize Description")
        return
    
    name = context.args[0]
    prize = " ".join(context.args[1:])
    
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("UPDATE giveaways SET active=0")
    c.execute("INSERT INTO giveaways (name, prize, active) VALUES (?, ?, 1)", (name, prize))
    giveaway_id = c.lastrowid
    conn.commit()
    conn.close()
    
    await update.message.reply_text(
        f"🎉 NEW GIVEAWAY STARTED!\n\n"
        f"Name: {name}\n"
        f"Prize: {prize}\n\n"
        f"React with 👍 or type /enter to participate.\n"
        f"Current entries: 0"
    )

async def enter(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT id FROM giveaways WHERE active=1")
    row = c.fetchone()
    if not row:
        await update.message.reply_text("No active giveaway.")
        conn.close()
        return
    
    gid = row[0]
    c.execute("SELECT 1 FROM participants WHERE giveaway_id=? AND user_id=?", (gid, user.id))
    if c.fetchone():
        await update.message.reply_text("Already entered.")
    else:
        c.execute("INSERT INTO participants VALUES (?, ?, ?, ?)", 
                  (gid, user.id, user.username or str(user.id), datetime.now().isoformat()))
        conn.commit()
        c.execute("SELECT COUNT(*) FROM participants WHERE giveaway_id=?", (gid,))
        count = c.fetchone()[0]
        await update.message.reply_text(f"✅ Entered! Total: {count}")
    conn.close()

async def pick_winner(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT id, name, prize FROM giveaways WHERE active=1")
    row = c.fetchone()
    if not row:
        await update.message.reply_text("No active giveaway.")
        conn.close()
        return
    
    gid, name, prize = row
    c.execute("SELECT user_id, username FROM participants WHERE giveaway_id=?", (gid,))
    parts = c.fetchall()
    
    if not parts:
        await update.message.reply_text("No participants.")
        conn.close()
        return
    
    winner = random.choice(parts)
    fake_trade = f"https://steamcommunity.com/tradeoffer/new/?partner={random.randint(100000000,999999999)}"
    
    await update.message.reply_text(
        f"🏆 WINNER ANNOUNCED!\n\n"
        f"Giveaway: {name}\n"
        f"Prize: {prize}\n"
        f"Winner: @{winner[1] or winner[0]}\n"
        f"Trade link sent: {fake_trade}\n\n"
        f"Total participants: {len(parts)}"
    )
    conn.close()

async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT id, fake_participants, fake_entries FROM giveaways WHERE active=1")
    row = c.fetchone()
    if not row:
        await update.message.reply_text("No active giveaway.")
        conn.close()
        return
    
    gid, fake_p, fake_e = row
    
    if fake_p and fake_p > 0:
        await update.message.reply_text(
            f"Current participants: {fake_p}\n"
            f"Total entries: {fake_e}"
        )
    else:
        c.execute("SELECT COUNT(*) FROM participants WHERE giveaway_id=?", (gid,))
        real = c.fetchone()[0]
        await update.message.reply_text(f"Current participants: {real}")
    conn.close()

async def fake_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID or len(context.args) < 1:
        return
    
    fake_participants = int(context.args[0])
    fake_entries = fake_participants + random.randint(200, 900)

    if len(context.args) > 1:
        fake_entries = int(context.args[1])

    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT id FROM giveaways WHERE active=1")
    row = c.fetchone()
    if not row:
        await update.message.reply_text("No active giveaway.")
        conn.close()
        return
    
    gid = row[0]
    c.execute("UPDATE giveaways SET fake_participants = ?, fake_entries = ? WHERE id = ?", 
              (fake_participants, fake_entries, gid))
    conn.commit()
    conn.close()
    
    await update.message.reply_text(
        f"📊 Fake stats updated!\n"
        f"Participants: {fake_participants}\n"
        f"Entries: {fake_entries}"
    )

async def report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT id, name, prize FROM giveaways WHERE active=1")
    row = c.fetchone()
    if not row:
        await update.message.reply_text("No active giveaway.")
        conn.close()
        return
    gid, name, prize = row
    c.execute("SELECT COUNT(*) FROM participants WHERE giveaway_id=?", (gid,))
    count = c.fetchone()[0]
    
    report_text = (
        f"GIVEAWAY REPORT\n"
        f"Name: {name}\n"
        f"Prize: {prize}\n"
        f"Total Participants: {count}\n"
        f"Date: {datetime.now().strftime('%Y-%m-%d')}\n\n"
        f"Data exported for records."
    )
    await update.message.reply_text(report_text)
    
    # Optional: send CSV
    c.execute("SELECT user_id, username, joined_at FROM participants WHERE giveaway_id=?", (gid,))
    data = c.fetchall()
    csv = "user_id,username,joined_at\n" + "\n".join([f"{d[0]},{d[1]},{d[2]}" for d in data])
    await update.message.reply_document(document=csv.encode(), filename="giveaway_report.csv")
    conn.close()

def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("newgiveaway", new_giveaway))
    app.add_handler(CommandHandler("enter", enter))
    app.add_handler(CommandHandler("pickwinner", pick_winner))
    app.add_handler(CommandHandler("stats", stats))
    app.add_handler(CommandHandler("fakestats", fake_stats))
    app.add_handler(CommandHandler("report", report))
    
    print("Improved CS2 Giveaway Bot running...")
    app.run_polling()

if __name__ == "__main__":
    main()
