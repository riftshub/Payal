#!/usr/bin/env python3
"""
Shopsy Bot – Advanced Features with Admin Commands & Anti-Abuse Protection
"""

import asyncio
import logging
import json
import os
from typing import Dict
from datetime import datetime, timedelta
from io import BytesIO

from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ConversationHandler,
    filters,
    ContextTypes,
)

from autobot import (
    AsyncShopsyClient,
    LiveLog,
    GAMES,
    DEFAULT_PARALLEL,
    parallel_game_exploit_async,
    parallel_gullak_exploit_async,
)

# ========== KEEP ALIVE IMPORT ==========
from keep_alive import keep_alive

# ========== CONFIG ==========
TOKEN = "8785356635:AAF_eXQO1_KA9jtSyaSnUS5ZPigkgHHkV9Q"
REQUIRED_CHANNEL = "@earnflowspidy"
DB_FILE = "bot_data.json"
ADMIN_LOG_FILE = "admin_actions.log"
BOT_USERNAME = "ShopsyBotUsername"

# ========== ADMIN IDS (Add your admin user IDs here) ==========
ADMIN_IDS = [
    1429768597,  # Main admin
]

# ========== TELEGRAM PROGRAMS ==========
TELEGRAM_PROGRAMS = {
    "airdrop": {
        "name": "🎁 Airdrop Program",
        "channel": "@earnflowspidy",
        "description": "Exclusive airdrop rewards",
        "bonus_points": 2,  
        "required": True
    },
    "community": {
        "name": "👥 Community Group",
        "channel": "@MoneyFlowLoots",
        "description": "Connect with other users",
        "bonus_points": 0,  
        "required": True
    },
    "updates": {
        "name": "📢 Updates Channel",
        "channel": "@UpdatesChannel",
        "description": "Get latest bot updates",
        "bonus_points": 0,  
        "required": False
    }
}

# ========== STATES ==========
PHONE, OTP, MAIN_MENU, WAITING_VERIFY, VERIFY_PROGRAMS = range(5)
MAX_OTP_ATTEMPTS = 3
MAX_RESEND_ATTEMPTS = 5

# ========== LOGGING ==========
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def log_admin_action(admin_id, action, details=""):
    timestamp = datetime.now().isoformat()
    log_entry = f"[{timestamp}] Admin {admin_id}: {action} - {details}\n"
    with open(ADMIN_LOG_FILE, "a") as f:
        f.write(log_entry)
    logger.info(f"Admin Action: {action} by {admin_id}")

# ========== DATABASE ==========
def load_db():
    if not os.path.exists(DB_FILE):
        return {}
    with open(DB_FILE, "r") as f:
        try:
            return json.load(f)
        except:
            return {}

def save_db(db):
    with open(DB_FILE, "w") as f:
        json.dump(db, f, indent=4)

def get_users_only(db):
    return {k: v for k, v in db.items() if k != "bot_settings" and str(k).lstrip("-").isdigit()}

def get_user(uid):
    return load_db().get(str(uid), {})

def get_points(uid):
    return get_user(uid).get("points", 0)

def set_points(uid, pts):
    db = load_db()
    uid = str(uid)
    if uid == "bot_settings":
        return
    if uid not in db:
        db[uid] = {}
    db[uid]["points"] = max(0, pts)
    save_db(db)

def add_points(uid, amt):
    if str(uid) == "bot_settings":
        return
    set_points(uid, get_points(uid) + amt)

def deduct_points(uid, amt):
    current = get_points(uid)
    if current >= amt:
        set_points(uid, current - amt)
        return True
    return False

def init_user(uid):
    uid = str(uid)
    if uid not in load_db():
        set_points(uid, 1)

def get_accounts(uid):
    return get_user(uid).get("accounts", {})

def save_account(uid, acc_id, data):
    db = load_db()
    uid = str(uid)
    if uid not in db:
        db[uid] = {"points": 1}
    if "accounts" not in db[uid]:
        db[uid]["accounts"] = {}
    db[uid]["accounts"][acc_id] = data
    save_db(db)

def delete_account(uid, acc_id):
    db = load_db()
    uid = str(uid)
    if uid in db and "accounts" in db[uid]:
        db[uid]["accounts"].pop(acc_id, None)
        if not db[uid]["accounts"]:
            db[uid].pop("accounts", None)
        save_db(db)

def was_referred(uid):
    return "referred_by" in get_user(uid)

def set_referred(uid, ref):
    uid = str(uid)
    if was_referred(uid):
        return False
    if str(uid) == str(ref):
        return False
    db = load_db()
    if uid not in db:
        db[uid] = {}
    db[uid]["referred_by"] = str(ref)
    db[uid]["referred_at"] = datetime.now().isoformat()
    db[uid]["referred_verified"] = False
    save_db(db)
    return True

def get_referral_count(uid):
    db = load_db()
    count = 0
    uid = str(uid)
    for user_id, user_data in db.items():
        if user_data.get("referred_by") == uid and user_data.get("referred_verified"):
            count += 1
    return count

def verify_referral_bonus(uid):
    uid = str(uid)
    user = get_user(uid)
    if user.get("referred_verified"):
        return False
    ref_uid = user.get("referred_by")
    if not ref_uid:
        return False
    db = load_db()
    if uid in db:
        db[uid]["referred_verified"] = True
        save_db(db)
    add_points(ref_uid, 2)
    logger.info(f"Referral verified: {uid} -> {ref_uid}, +2 points awarded")
    return True

def record_task_completion(uid, acc_id, task_name, earned_coins):
    db = load_db()
    uid = str(uid)
    if uid not in db:
        db[uid] = {}
    if "task_history" not in db[uid]:
        db[uid]["task_history"] = {}
    task_key = f"{acc_id}_{task_name}"
    db[uid]["task_history"][task_key] = {
        "completed_at": datetime.now().isoformat(),
        "earned_coins": earned_coins
    }
    save_db(db)

def has_completed_task_today(uid, acc_id, task_name):
    user = get_user(uid)
    history = user.get("task_history", {})
    task_key = f"{acc_id}_{task_name}"
    if task_key not in history:
        return False
    last_completed = datetime.fromisoformat(history[task_key]["completed_at"])
    return (datetime.now() - last_completed) < timedelta(hours=24)

def get_joined_programs(uid):
    return get_user(uid).get("joined_programs", [])

def mark_program_joined(uid, program_id):
    db = load_db()
    uid = str(uid)
    if uid not in db:
        db[uid] = {}
    if "joined_programs" not in db[uid]:
        db[uid]["joined_programs"] = []
    if program_id not in db[uid]["joined_programs"]:
        db[uid]["joined_programs"].append(program_id)
        bonus = TELEGRAM_PROGRAMS[program_id]["bonus_points"]
        db[uid]["points"] = db[uid].get("points", 0) + bonus
        save_db(db)
        logger.info(f"Program joined: {uid} -> {program_id}, +{bonus} points")
        return True
    return False

async def all_required_programs_joined(bot, user_id):
    for prog_id, prog_info in TELEGRAM_PROGRAMS.items():
        if prog_info["required"]:
            if not await check_join(bot, user_id, prog_info["channel"]):
                return False
    return True

def get_program_status(uid):
    joined = get_joined_programs(uid)
    status = ""
    for prog_id, prog_info in TELEGRAM_PROGRAMS.items():
        emoji = "✅" if prog_id in joined else "❌"
        required = "*(required)*" if prog_info["required"] else ""
        status += f"{emoji} {prog_info['name']} {required} (+{prog_info['bonus_points']} pts)\n"
    return status

def is_admin(user_id):
    return int(user_id) in ADMIN_IDS

async def check_join(bot, user_id, channel):
    try:
        m = await bot.get_chat_member(channel, user_id)
        return m.status in ['member', 'administrator', 'creator']
    except:
        return False

def main_keyboard():
    return ReplyKeyboardMarkup([
        ["📋 My Accounts", "➕ Add Account"],
        ["🪙 Coins", "💰 My Points"],
        ["📱 Programs", "🔗 Referral Link"],
        ["🚀 Run All", "❌ Logout"]
    ], resize_keyboard=True, is_persistent=True)

def admin_keyboard():
    return ReplyKeyboardMarkup([
        ["👥 Users Stats", "🎁 Bonus All"],
        ["🗑️ Clear All", "📢 Broadcast"],
        ["📊 Admin Log", "🚪 Exit Admin"]
    ], resize_keyboard=True, is_persistent=True)

def phone_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("❌ Cancel", callback_data="cancel_phone")]
    ])

def otp_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔄 Resend", callback_data="resend_otp")],
        [InlineKeyboardButton("❌ Cancel", callback_data="cancel_login")]
    ])

async def run_exploit(uid, acc_id, update, context):
    uid = str(uid)
    accounts = get_accounts(uid)
    if acc_id not in accounts:
        await update.effective_chat.send_message("❌ Account not found.")
        return
    
    data = accounts[acc_id]
    session = data.get("session")
    if not session:
        await update.effective_chat.send_message("❌ Session missing. Re‑add account.")
        return
    
    client = AsyncShopsyClient(log=LiveLog(debug=False), fast=True, session_data=session)
    try:
        await client.__aenter__()
        try:
            await client.get_user_async(refresh=True)
        except:
            await update.effective_chat.send_message("⚠️ Session expired. Re‑add account.")
            return

        parallel = DEFAULT_PARALLEL
        msg = await update.effective_chat.send_message(
            f"⏳ Exploit on {data.get('phone', acc_id)} (x{parallel})..."
        )
        earned = 0
        lines = []
        
        for game in GAMES:
            await update.effective_chat.send_message(f"🎮 {game['name']} (x{parallel}) starting...")
            try:
                coins = await parallel_game_exploit_async(client, game, parallel, 0.0, 0.0)
                earned += coins
                lines.append(f"✅ {game['name']}: +{coins}")
                await update.effective_chat.send_message(f"✅ {game['name']} done +{coins}")
                record_task_completion(uid, acc_id, game['name'], coins)
            except Exception as e:
                lines.append(f"❌ {game['name']}: {str(e)[:50]}")
                await update.effective_chat.send_message(f"❌ {game['name']} failed")
            await asyncio.sleep(0.5)

        await update.effective_chat.send_message("💰 Gullak...")
        try:
            g = await parallel_gullak_exploit_async(client, 10)
            earned += g
            lines.append(f"💰 Gullak: +{g}")
            await update.effective_chat.send_message(f"💰 Gullak +{g}")
            record_task_completion(uid, acc_id, "Gullak", g)
        except Exception as e:
            lines.append(f"❌ Gullak: {str(e)[:50]}")
            await update.effective_chat.send_message("❌ Gullak failed")

        user = await client.get_user_async(refresh=True)
        name = user.get("name", "Unknown")
        balance = user.get("totalCoins", 0)
        
        points_earned = max(1, earned // 1000)
        add_points(uid, points_earned)
        
        summary = (
            f"🚀 *Exploit Completed on {data.get('phone', acc_id)}*\n\n"
            f"👤 {name} (`{client.ctx.account_id}`)\n"
            f"🪙 Earned: {earned}\n"
            f"💰 Balance: {balance}\n"
            f"⭐ Bot Points: +{points_earned}\n\n"
            "📊 " + "\n".join(lines)
        )
        await msg.edit_text(summary, parse_mode="Markdown")
    except Exception as e:
        logger.error(f"Exploit error: {e}")
        await update.effective_chat.send_message(f"❌ Error: {str(e)[:100]}")
    finally:
        await client.__aexit__(None, None, None)

async def enforce_membership(update, context, uid):
    bot = context.bot
    chat_id = update.effective_chat.id
    query = update.callback_query
    
    if not await check_join(bot, chat_id, REQUIRED_CHANNEL):
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("📢 Join Channel", url=f"https://t.me/{REQUIRED_CHANNEL.replace('@','')}")],
            [InlineKeyboardButton("✅ I've Joined (Retry)", callback_data="verify_join")],
            [InlineKeyboardButton("❌ Cancel", callback_data="cancel_verify")]
        ])
        text = f"🚨 *Hold on! You left our channel.*\n\nPlease join {REQUIRED_CHANNEL} to continue using the bot."
        
        if query:
            try: await query.answer("You must join the channel first!", show_alert=True)
            except: pass
            await query.edit_message_text(text, parse_mode="Markdown", reply_markup=kb)
        else:
            await update.effective_chat.send_message(text, parse_mode="Markdown", reply_markup=kb)
        return WAITING_VERIFY
        
    if not await all_required_programs_joined(bot, int(uid)):
        if query:
            try: await query.answer("You left a required group!", show_alert=True)
            except: pass
        else:
            await update.effective_chat.send_message(
                "🚨 *Hold on! You left a required group/channel.*\n\nPlease join them back to continue.",
                parse_mode="Markdown"
            )
        return await verify_programs(update, context)
        
    return None

async def start(update, context):
    uid = str(update.effective_user.id)
    chat_id = update.effective_chat.id
    bot = context.bot

    if maintenance_check(uid):
        _, maint_msg = get_maintenance_status()
        await update.message.reply_text(f"🛠 *BOT UNDER MAINTENANCE*\n\n{maint_msg}", parse_mode="Markdown")
        return ConversationHandler.END

    if is_admin(int(uid)):
        await update.message.reply_text(f"✅ Admin detected! ID: {uid}\nUse /admin to access admin panel.")

    args = update.message.text.split()
    if len(args) > 1:
        ref = args[1]
        if ref != uid and ref.isdigit():
            if set_referred(uid, ref):
                await bot.send_message(int(ref), f"🎉 Referral started! +2 points when they verify.")

    init_user(uid)

    if not await check_join(bot, chat_id, REQUIRED_CHANNEL):
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("📢 Join Channel", url=f"https://t.me/{REQUIRED_CHANNEL.replace('@','')}")],
            [InlineKeyboardButton("✅ I've Joined", callback_data="verify_join")],
            [InlineKeyboardButton("❌ Cancel", callback_data="cancel_verify")]
        ])
        await update.message.reply_text(
            f"🚨 *Please join {REQUIRED_CHANNEL} first!*",
            parse_mode="Markdown", reply_markup=kb
        )
        return WAITING_VERIFY

    verify_referral_bonus(uid)

    if not await all_required_programs_joined(bot, int(uid)):
        return await verify_programs(update, context)

    await update.message.reply_text(
        "🔄 *Welcome! Use the buttons below.*",
        parse_mode="Markdown", reply_markup=main_keyboard()
    )
    return MAIN_MENU

async def admin_panel(update, context):
    uid = int(update.effective_user.id)
    if not is_admin(uid):
        await update.message.reply_text("❌ You are not an admin!")
        return
    
    msg = "🔐 *ADMIN PANEL*\n\n"
    msg += "Commands:\n"
    msg += "👥 /stats - Show bot statistics\n"
    msg += "🎁 /bonusall <points> - Give points to all users\n"
    msg += "🗑️ /clearall - Set all users points to 0\n"
    msg += "📢 /broadcast <message> - Send message to all users\n"
    msg += "🟢 /chat [message] - Send Bot Live message to all users\n"
    msg += "📊 /adminlog - View admin actions log\n"
    msg += "🚪 /exit - Exit admin panel\n\n"
    msg += "Example: `/bonusall 5` gives 5 points to all users"
    
    await update.message.reply_text(msg, parse_mode="Markdown", reply_markup=admin_keyboard())

async def stats_command(update, context):
    uid = int(update.effective_user.id)
    if not is_admin(uid): return
    
    db = load_db()
    users = get_users_only(db)
    total_users = len(users)
    total_points = sum(u.get("points", 0) for u in users.values())
    total_accounts = sum(len(u.get("accounts", {})) for u in users.values())
    total_referrals = sum(1 for u in users.values() if u.get("referred_verified"))
    
    msg = f"""
📊 *BOT STATISTICS*

👥 Total Users: {total_users}
💰 Total Points: {total_points}
📱 Total Accounts: {total_accounts}
🔗 Total Referrals: {total_referrals}

🎮 Avg Points/User: {int(total_points/total_users) if total_users > 0 else 0}
📱 Avg Accounts/User: {int(total_accounts/total_users) if total_users > 0 else 0}
"""
    await update.message.reply_text(msg, parse_mode="Markdown")

async def bonus_all_command(update, context):
    uid = int(update.effective_user.id)
    if not is_admin(uid): return
    if not context.args or not context.args[0].isdigit():
        await update.message.reply_text("❌ Usage: /bonusall <points>\nExample: /bonusall 5")
        return
    
    bonus_points = int(context.args[0])
    db = load_db()
    users = get_users_only(db)
    affected_users = 0
    for user_id in users.keys():
        add_points(user_id, bonus_points)
        affected_users += 1
    
    msg = f"✅ Bonus applied!\n\n📌 {affected_users} users received +{bonus_points} points"
    await update.message.reply_text(msg)
    log_admin_action(uid, "BONUSALL", f"Gave {bonus_points} points to {affected_users} users")

async def clear_all_command(update, context):
    uid = int(update.effective_user.id)
    if not is_admin(uid): return
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ YES, Clear All", callback_data="confirm_clearall")],
        [InlineKeyboardButton("❌ NO, Cancel", callback_data="cancel_clearall")]
    ])
    await update.message.reply_text("⚠️ *WARNING!* This will set ALL users points to 0.\n\nAre you sure?", parse_mode="Markdown", reply_markup=kb)

async def confirm_clearall(update, context):
    query = update.callback_query
    await query.answer()
    uid = int(update.effective_user.id)
    if not is_admin(uid):
        await query.edit_message_text("❌ Not authorized!")
        return
    db = load_db()
    users = get_users_only(db)
    affected_users = 0
    for user_id in users.keys():
        set_points(user_id, 0)
        affected_users += 1
    await query.edit_message_text(f"✅ Cleared!\n\n📌 {affected_users} users' points set to 0")
    log_admin_action(uid, "CLEARALL", f"Cleared points for {affected_users} users")

async def cancel_clearall(update, context):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("❌ Cancelled.")

async def broadcast_command(update, context):
    uid = int(update.effective_user.id)
    if not is_admin(uid): return
    context.user_data["broadcast_mode"] = True
    await update.message.reply_text(
        "📢 *BROADCAST MODE*\n\nSend your message (supports Markdown)\n\nExample:\n"
        "🎉 *NEW UPDATE!*\n\nWe have new features...\n\n"
        "Send /cancel to exit broadcast mode"
    )

async def broadcast_message(update, context):
    uid = int(update.effective_user.id)
    if not is_admin(uid) or not context.user_data.get("broadcast_mode"):
        return
    message = update.message.text
    db = load_db()
    sent = 0
    failed = 0
    msg = await update.message.reply_text("📢 Broadcasting... Please wait")
    users = get_users_only(db)
    for user_id in users.keys():
        try:
            await context.bot.send_message(chat_id=int(user_id), text=message, parse_mode="Markdown")
            sent += 1
            if sent % 10 == 0: await asyncio.sleep(0.5)
        except Exception as e:
            failed += 1
            logger.error(f"Failed to send to {user_id}: {e}")
    context.user_data["broadcast_mode"] = False
    result = f"✅ *BROADCAST COMPLETE*\n\n✓ Sent: {sent}\n✗ Failed: {failed}\n📊 Total: {sent + failed}"
    await msg.edit_text(result, parse_mode="Markdown")
    log_admin_action(uid, "BROADCAST", f"Sent to {sent} users, {failed} failed")

async def chat_command(update, context):
    uid = int(update.effective_user.id)
    if not is_admin(uid): return
    message = " ".join(context.args)
    if not message: message = "🟢 *Bot is Live!*\n\nYou can start using the bot now."
    db = load_db()
    users = get_users_only(db)
    sent = 0
    failed = 0
    msg = await update.message.reply_text("📢 Sending live status to all users...")
    for user_id in users.keys():
        try:
            await context.bot.send_message(chat_id=int(user_id), text=message, parse_mode="Markdown")
            sent += 1
            if sent % 10 == 0: await asyncio.sleep(0.5)
        except Exception:
            failed += 1
    result = f"✅ *Status Broadcast Complete*\n\n✓ Sent: {sent}\n✗ Failed: {failed}"
    await msg.edit_text(result, parse_mode="Markdown")
    log_admin_action(uid, "CHAT_BROADCAST", f"Sent live message to {sent} users")

async def admin_log_command(update, context):
    uid = int(update.effective_user.id)
    if not is_admin(uid): return
    if not os.path.exists(ADMIN_LOG_FILE):
        await update.message.reply_text("📋 No admin actions logged yet.")
        return
    with open(ADMIN_LOG_FILE, "r") as f:
        logs = f.readlines()
    recent_logs = logs[-20:]
    log_text = "".join(recent_logs)
    if len(log_text) > 4000:
        await update.message.reply_text(f"📊 *Recent Admin Actions (Last 20):*\n\n`{log_text}`", parse_mode="Markdown")
    else:
        await update.message.reply_text(f"📊 *Admin Actions Log:*\n\n`{log_text}`", parse_mode="Markdown")

async def exit_admin(update, context):
    uid = int(update.effective_user.id)
    if not is_admin(uid): return
    context.user_data["broadcast_mode"] = False
    await update.message.reply_text("👋 Exited admin panel.", reply_markup=main_keyboard())
    return MAIN_MENU

def get_maintenance_status():
    db = load_db()
    settings = db.get("bot_settings", {})
    return settings.get("is_maintenance", False), settings.get("maintenance_msg", "🛠 Bot is under maintenance. Please wait...")

def set_maintenance(enabled: bool, msg: str = ""):
    db = load_db()
    if "bot_settings" not in db: db["bot_settings"] = {}
    db["bot_settings"]["is_maintenance"] = enabled
    if msg: db["bot_settings"]["maintenance_msg"] = msg
    save_db(db)

def maintenance_check(uid: str) -> bool:
    is_on, _ = get_maintenance_status()
    return is_on and not is_admin(int(uid))

async def maintenance_command(update, context):
    uid = int(update.effective_user.id)
    if not is_admin(uid): return
    args = context.args
    if not args:
        is_on, maint_msg = get_maintenance_status()
        status = "ON 🔴" if is_on else "OFF 🟢"
        await update.message.reply_text(
            f"🛠 *Maintenance Status:* {status}\n📝 Message: {maint_msg}\n\nUsage:\n`/maintenance on [optional message]`\n`/maintenance off`",
            parse_mode="Markdown"
        )
        return
    if args[0].lower() == "on":
        custom_msg = " ".join(args[1:]) if len(args) > 1 else "🛠 Bot is under maintenance. Please wait..."
        set_maintenance(True, custom_msg)
        log_admin_action(uid, "MAINTENANCE ON", custom_msg)
        await update.message.reply_text(f"✅ *Maintenance Mode ON*\n📝 Message: {custom_msg}", parse_mode="Markdown")
    elif args[0].lower() == "off":
        set_maintenance(False)
        log_admin_action(uid, "MAINTENANCE OFF", "")
        await update.message.reply_text("✅ *Maintenance Mode OFF* — Bot is live again! 🟢", parse_mode="Markdown")

async def add_points_command(update, context):
    uid = int(update.effective_user.id)
    if not is_admin(uid): return
    if not context.args or len(context.args) != 2:
        await update.message.reply_text("❌ Usage: `/addpoints <user_id> <amount>`", parse_mode="Markdown")
        return
    target_uid, amount_str = context.args[0], context.args[1]
    if not amount_str.lstrip("-").isdigit(): return
    amount = int(amount_str)
    db = load_db()
    if target_uid not in db:
        await update.message.reply_text(f"❌ User `{target_uid}` not found.", parse_mode="Markdown")
        return
    add_points(target_uid, amount)
    new_balance = get_points(target_uid)
    log_admin_action(uid, "ADD_POINTS", f"User {target_uid} +{amount} pts → balance: {new_balance}")
    await update.message.reply_text(f"✅ *Done!*\n👤 User: `{target_uid}`\n➕ Added: {amount} points\n💰 New Balance: {new_balance}", parse_Mode="Markdown")
    try:
        action = "add kiye" if amount >= 0 else "deduct kiye"
        await context.bot.send_message(chat_id=int(target_uid), text=f"🎉 Admin ne aapke account mein *{abs(amount)} points* {action}!\n💰 New Balance: *{new_balance} points*", parse_mode="Markdown")
    except Exception:
        pass

async def verify_callback(update, context):
    query = update.callback_query
    await query.answer()
    uid = str(update.effective_user.id)
    if await check_join(context.bot, update.effective_chat.id, REQUIRED_CHANNEL):
        await query.edit_message_text("✅ Channel Verified!")
        verify_referral_bonus(uid)
        if not await all_required_programs_joined(context.bot, int(uid)):
            await update.effective_chat.send_message("Now let's verify programs...")
            return await verify_programs(update, context)
        await update.effective_chat.send_message("Choose an option:", reply_markup=main_keyboard())
        return MAIN_MENU
    else:
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("📢 Join Channel", url=f"https://t.me/{REQUIRED_CHANNEL.replace('@','')}")],
            [InlineKeyboardButton("✅ I've Joined (Retry)", callback_data="verify_join")],
            [InlineKeyboardButton("❌ Cancel", callback_data="cancel_verify")]
        ])
        await query.edit_message_text("❌ Not joined yet. Retry.", reply_markup=kb)
        return WAITING_VERIFY

async def cancel_verify(update, context):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("❌ Cancelled. Send /start to try again.")
    return ConversationHandler.END

async def verify_programs(update, context):
    uid = str(update.effective_user.id)
    query = update.callback_query if update.callback_query else None
    bot = context.bot
    missing_required = []
    for prog_id, prog_info in TELEGRAM_PROGRAMS.items():
        if prog_info["required"]:
            if not await check_join(bot, int(uid), prog_info["channel"]):
                missing_required.append(prog_id)
    kb = []
    for prog_id in missing_required:
        prog = TELEGRAM_PROGRAMS[prog_id]
        kb.append([InlineKeyboardButton(f"📱 Join {prog['name']}", url=f"https://t.me/{prog['channel'].replace('@','')}")])
    kb.append([InlineKeyboardButton("✅ I've Joined All", callback_data="verify_programs")])
    kb.append([InlineKeyboardButton("❌ Cancel", callback_data="cancel_verify")])
    msg = "📱 *Join Required Programs:*\n\n"
    for prog_id in missing_required:
        prog = TELEGRAM_PROGRAMS[prog_id]
        msg += f"• {prog['name']}\n  {prog['description']}\n\n"
    if query:
        await query.edit_message_text(msg, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(kb))
    else:
        await update.effective_chat.send_message(msg, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(kb))
    return VERIFY_PROGRAMS

async def verify_programs_callback(update, context):
    query = update.callback_query
    await query.answer()
    uid = str(update.effective_user.id)
    bot = context.bot
    all_verified = True
    verified_count = 0
    for prog_id, prog_info in TELEGRAM_PROGRAMS.items():
        if prog_info["required"]:
            if await check_join(bot, update.effective_chat.id, prog_info["channel"]):
                if mark_program_joined(uid, prog_id):
                    verified_count += 1
            else:
                all_verified = False
    if all_verified:
        msg = f"✅ *Programs Verified!*\n\n"
        if verified_count > 0:
            msg += f"🎉 Earned {sum(TELEGRAM_PROGRAMS[p]['bonus_points'] for p in get_joined_programs(uid))} bonus points!\n\n"
        msg += "Welcome to the bot! Choose an option:"
        await query.edit_message_text(msg, parse_mode="Markdown")
        await update.effective_chat.send_message("Choose an option:", reply_markup=main_keyboard())
        return MAIN_MENU
    else:
        await query.edit_message_text("❌ Some programs not verified yet. Please join them and try again.")
        return await verify_programs(update, context)

async def add_account(update, context):
    uid = str(update.effective_user.id)
    state = await enforce_membership(update, context, uid)
    if state is not None: return state

    await update.message.reply_text(
        "📱 Send **10‑digit phone** (without +91):",
        parse_mode="Markdown",
        reply_markup=phone_keyboard()
    )
    context.user_data["otp_attempts"] = 0
    context.user_data["resend_attempts"] = 0
    return PHONE

async def cancel_phone(update, context):
    query = update.callback_query
    await query.answer()
    client = context.user_data.get("client")
    if client:
        try: await client.__aexit__(None, None, None)
        except: pass
    context.user_data.clear()
    await query.edit_message_text("❌ Cancelled.")
    await update.effective_chat.send_message("Back to menu.", reply_markup=main_keyboard())
    return MAIN_MENU

async def phone_received(update, context):
    phone = update.message.text.strip().replace("+91", "").replace(" ", "")
    if not phone.isdigit() or len(phone) != 10:
        await update.message.reply_text("❌ Invalid number. Send exactly 10 digits.", reply_markup=phone_keyboard())
        return PHONE
    context.user_data["phone"] = phone
    context.user_data["otp_attempts"] = 0
    context.user_data["resend_attempts"] = 0
    try:
        log = LiveLog(debug=False)
        client = AsyncShopsyClient(log=log, fast=True)
        await client.__aenter__()
        context.user_data["client"] = client
        await client.bootstrap_async()
        req = await client.send_otp_async(phone)
        context.user_data["request_id"] = req
        await update.message.reply_text(f"📲 OTP sent to +91{phone}\nEnter the 6‑digit code:", reply_markup=otp_keyboard())
        return OTP
    except Exception as e:
        logger.error(f"OTP send error: {e}")
        await update.message.reply_text(f"❌ OTP send failed: {str(e)[:80]}\nTry again.", reply_markup=phone_keyboard())
        return PHONE

async def resend_otp(update, context):
    query = update.callback_query
    await query.answer()
    resend_attempts = context.user_data.get("resend_attempts", 0)
    if resend_attempts >= MAX_RESEND_ATTEMPTS:
        await query.edit_message_text(f"❌ Max resend attempts ({MAX_RESEND_ATTEMPTS}) reached. Start over with /start")
        return ConversationHandler.END
    phone = context.user_data.get("phone")
    client = context.user_data.get("client")
    if not phone or not client:
        await query.edit_message_text("❌ Session expired. Restart with /start")
        return ConversationHandler.END
    try:
        req = await client.send_otp_async(phone)
        context.user_data["request_id"] = req
        context.user_data["otp_attempts"] = 0
        context.user_data["resend_attempts"] = resend_attempts + 1
        await query.edit_message_text(f"📲 OTP resent to +91{phone}\nAttempts: {context.user_data['resend_attempts']}/{MAX_RESEND_ATTEMPTS}", reply_markup=otp_keyboard())
        return OTP
    except Exception as e:
        logger.error(f"Resend OTP error: {e}")
        await query.edit_message_text(f"❌ Resend failed: {str(e)[:80]}")
        return OTP

async def cancel_login(update, context):
    query = update.callback_query
    await query.answer()
    client = context.user_data.get("client")
    if client:
        try: await client.__aexit__(None, None, None)
        except: pass
    await query.edit_message_text("❌ Cancelled.")
    context.user_data.clear()
    await update.effective_chat.send_message("Back to menu.", reply_markup=main_keyboard())
    return MAIN_MENU

async def otp_received(update, context):
    otp = update.message.text.strip()
    if not otp.isdigit() or len(otp) != 6:
        await update.message.reply_text("❌ Invalid OTP (must be 6 digits). Try again.", reply_markup=otp_keyboard())
        return OTP
    otp_attempts = context.user_data.get("otp_attempts", 0) + 1
    context.user_data["otp_attempts"] = otp_attempts
    if otp_attempts > MAX_OTP_ATTEMPTS:
        await update.message.reply_text(f"❌ Max OTP attempts ({MAX_OTP_ATTEMPTS}) exceeded. Start over.", reply_markup=ReplyKeyboardMarkup([["/start"]], resize_keyboard=True))
        return ConversationHandler.END
    phone = context.user_data.get("phone")
    req = context.user_data.get("request_id")
    client = context.user_data.get("client")
    if not phone or not req or not client:
        await update.message.reply_text("❌ Session expired. /start again.")
        return ConversationHandler.END
    try:
        await client.verify_otp_async(phone, otp, req)
        if not client.ctx.is_logged_in: raise RuntimeError("Login failed - not logged in")
        uid = str(update.effective_user.id)
        acc_id = client.ctx.account_id or phone
        session_dict = {
            "dc_id": client.ctx.dc_id, "at": client.ctx.at, "sn": client.ctx.sn,
            "vid": client.ctx.vid, "secure_token": client.ctx.secure_token,
            "secure_cookie": client.ctx.secure_cookie, "account_id": client.ctx.account_id,
            "user_name": client.ctx.user_name, "is_logged_in": True,
            "device_id": client.ctx.device_id, "visit_id": client.ctx.visit_id,
            "added_at": datetime.now().isoformat(),
        }
        save_account(uid, acc_id, {"phone": phone, "account_id": client.ctx.account_id, "session": session_dict, "device": client.device})
        await update.message.reply_text(f"✅ *Account added!*\n📱 {phone}\n👤 {client.ctx.user_name or 'User'}", parse_mode="Markdown", reply_markup=main_keyboard())
        context.user_data.clear()
        return MAIN_MENU
    except Exception as e:
        logger.error(f"OTP verification error: {e}")
        remaining = MAX_OTP_ATTEMPTS - otp_attempts
        await update.message.reply_text(f"❌ OTP error: {str(e)[:80]}\nAttempts remaining: {remaining}", reply_markup=otp_keyboard())
        return OTP

async def my_accounts(update, context):
    uid = str(update.effective_user.id)
    state = await enforce_membership(update, context, uid)
    if state is not None: return state

    accs = get_accounts(uid)
    if not accs:
        await update.message.reply_text("📋 No accounts added yet.", reply_markup=main_keyboard())
        return MAIN_MENU
    
    kb = []
    for aid, data in accs.items():
        phone = data.get('phone', aid)
        kb.append([
            InlineKeyboardButton(f"🚀 {phone}", callback_data=f"run_{aid}"),
            InlineKeyboardButton(f"📤 Export", callback_data=f"export_{aid}")
        ])
    kb.append([InlineKeyboardButton("🗑️ Delete Account", callback_data="delete_account")])
    kb.append([InlineKeyboardButton("🔙 Back", callback_data="back_to_main")])
    await update.message.reply_text(f"📋 *Your Accounts ({len(accs)}):*", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(kb))
    return MAIN_MENU

async def show_coins(update, context):
    uid = str(update.effective_user.id)
    state = await enforce_membership(update, context, uid)
    if state is not None: return state

    accs = get_accounts(uid)
    if not accs:
        await update.message.reply_text("🪙 No accounts to check.", reply_markup=main_keyboard())
        return MAIN_MENU
    
    msg = "🪙 *Balances:*\n\n"
    for aid, data in accs.items():
        sess = data.get("session")
        phone = data.get("phone", aid)
        if not sess:
            msg += f"📱 {phone}: ❌ No session\n"
            continue
        try:
            log = LiveLog(debug=False)
            client = AsyncShopsyClient(log=log, fast=True, session_data=sess)
            await client.__aenter__()
            try:
                user = await client.get_user_async(refresh=True)
                bal = user.get("totalCoins", 0)
                name = user.get("name", "Unknown")
                msg += f"📱 {phone}\n👤 {name}\n💰 {bal} coins\n\n"
            except Exception as e:
                msg += f"📱 {phone}: ❌ {str(e)[:50]}\n\n"
            finally:
                await client.__aexit__(None, None, None)
        except Exception as e:
            msg += f"📱 {phone}: ❌ Error\n\n"
        await asyncio.sleep(0.3)
    await update.message.reply_text(msg, parse_mode="Markdown", reply_markup=main_keyboard())
    return MAIN_MENU

async def my_points(update, context):
    uid = str(update.effective_user.id)
    state = await enforce_membership(update, context, uid)
    if state is not None: return state

    pts = get_points(uid)
    ref_count = get_referral_count(uid)
    await update.message.reply_text(f"💰 *Your Points:* {pts}\n\n👥 *Referrals:* {ref_count}\n🎯 *Earn:* Run tasks to earn points!\n🔗 Share your link to get +2 points per referral", parse_mode="Markdown", reply_markup=main_keyboard())
    return MAIN_MENU

async def show_programs(update, context):
    uid = str(update.effective_user.id)
    state = await enforce_membership(update, context, uid)
    if state is not None: return state

    status = get_program_status(uid)
    kb = []
    joined = get_joined_programs(uid)
    for prog_id, prog_info in TELEGRAM_PROGRAMS.items():
        if prog_id not in joined:
            kb.append([InlineKeyboardButton(f"📱 Join {prog_info['name']}", url=f"https://t.me/{prog_info['channel'].replace('@','')}")])
    if len(joined) < len(TELEGRAM_PROGRAMS):
        kb.append([InlineKeyboardButton("✅ I've Joined Some", callback_data="verify_new_programs")])
    kb.append([InlineKeyboardButton("🔙 Back", callback_data="back_to_main")])
    msg = "📱 *Telegram Programs:*\n\n" + status + f"\n💰 *Total Bonus:* {sum(TELEGRAM_PROGRAMS[p]['bonus_points'] for p in joined)} points earned"
    await update.message.reply_text(msg, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(kb))
    return MAIN_MENU

async def verify_new_programs(update, context):
    uid = str(update.effective_user.id)
    state = await enforce_membership(update, context, uid)
    if state is not None: return state
    
    query = update.callback_query
    await query.answer()
    
    joined = get_joined_programs(uid)
    verified_new = 0
    for prog_id, prog_info in TELEGRAM_PROGRAMS.items():
        if prog_id not in joined:
            if await check_join(context.bot, update.effective_chat.id, prog_info["channel"]):
                if mark_program_joined(uid, prog_id):
                    verified_new += 1
    if verified_new > 0:
        bonus = sum(TELEGRAM_PROGRAMS[p]['bonus_points'] for p in get_joined_programs(uid) if p not in joined)
        await query.edit_message_text(f"✅ Verified {verified_new} new program(s)!\n🎉 +{bonus} points!")
        await update.effective_chat.send_message("Menu:", reply_markup=main_keyboard())
    else:
        await query.edit_message_text("❌ No new programs verified. Join more and try again!")
    return MAIN_MENU

async def referral_link(update, context):
    uid = str(update.effective_user.id)
    state = await enforce_membership(update, context, uid)
    if state is not None: return state

    try:
        bot_info = await context.bot.get_me()
        bot_username = bot_info.username
        if not bot_username:
            await update.message.reply_text("❌ Bot username not configured. Contact admin.", reply_markup=main_keyboard())
            return MAIN_MENU
    except Exception as e:
        logger.error(f"Failed to get bot info: {e}")
        await update.message.reply_text("❌ Error getting bot info. Try again.", reply_markup=main_keyboard())
        return MAIN_MENU
    
    link = f"https://t.me/{bot_username}?start={uid}"
    ref_count = get_referral_count(uid)
    await update.message.reply_text(f"🔗 *Your Referral Link:*\n\n`{link}`\n\n📊 Active Referrals: {ref_count}\n💰 Earning: +2 points per referral\n\n📋 How it works:\n1. Share your link\n2. Friends click & add accounts\n3. You get +2 points!", parse_mode="Markdown", reply_markup=main_keyboard())
    return MAIN_MENU

async def run_all(update, context):
    uid = str(update.effective_user.id)
    state = await enforce_membership(update, context, uid)
    if state is not None: return state

    if get_points(uid) <= 0:
        await update.message.reply_text(
            "❌ *Insufficient Points!*\n\nYou need at least 1 point to run the bot. Share your referral link to earn points!",
            parse_mode="Markdown", 
            reply_markup=main_keyboard()
        )
        return MAIN_MENU

    accs = get_accounts(uid)
    if not accs:
        await update.message.reply_text("🚀 No accounts to run.", reply_markup=main_keyboard())
        return MAIN_MENU
    
    kb = []
    for aid, data in accs.items():
        kb.append([InlineKeyboardButton(f"🚀 {data.get('phone', aid)}", callback_data=f"run_{aid}")])
    kb.append([InlineKeyboardButton("🔙 Back", callback_data="back_to_main")])
    await update.message.reply_text("🚀 *Select account to exploit:*", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(kb))
    return MAIN_MENU

async def export_callback(update, context):
    uid = str(update.effective_user.id)
    state = await enforce_membership(update, context, uid)
    if state is not None: return state
    
    query = update.callback_query
    await query.answer()
    data = query.data
    
    if data.startswith("export_"):
        acc_id = data[7:]
        accounts = get_accounts(uid)
        if acc_id not in accounts:
            await query.edit_message_text("❌ Account not found.")
            return MAIN_MENU
        account_data = accounts[acc_id]
        phone = account_data.get('phone', acc_id)
        export_data = {
            "user_id": uid, "account_id": acc_id, "phone": phone,
            "exported_at": datetime.now().isoformat(), "account_data": account_data
        }
        json_str = json.dumps(export_data, indent=4, default=str)
        file_obj = BytesIO(json_str.encode('utf-8'))
        filename = f"session_{phone}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        file_obj.name = filename
        await query.edit_message_text(f"⏳ Exporting account {phone}...")
        await update.effective_chat.send_document(document=file_obj, filename=filename, caption=f"📦 Session data for {phone}. Keep it safe.")
        return MAIN_MENU
    await query.edit_message_text("Unknown action.")
    return MAIN_MENU

async def logout(update, context):
    context.user_data.clear()
    await update.message.reply_text("👋 Logged out. /start to re‑enter.", reply_markup=ReplyKeyboardMarkup([["/start"]], resize_keyboard=True))
    return ConversationHandler.END

async def callback_handler(update, context):
    uid = str(update.effective_user.id)
    state = await enforce_membership(update, context, uid)
    if state is not None: return state
    
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "back_to_main":
        await query.edit_message_text("↩️ Back to menu.", reply_markup=main_keyboard())
        return MAIN_MENU

    if data == "delete_account":
        accs = get_accounts(uid)
        if not accs:
            await query.edit_message_text("No accounts to delete.")
            return MAIN_MENU
        kb = []
        for aid, d in accs.items():
            kb.append([InlineKeyboardButton(f"❌ {d.get('phone', aid)}", callback_data=f"del_{aid}")])
        kb.append([InlineKeyboardButton("🔙 Cancel", callback_data="back_to_main")])
        await query.edit_message_text("Select account to delete:", reply_markup=InlineKeyboardMarkup(kb))
        return MAIN_MENU

    if data.startswith("del_"):
        aid = data[4:]
        delete_account(uid, aid)
        await query.edit_message_text("✅ Account deleted.")
        await update.effective_chat.send_message("Menu:", reply_markup=main_keyboard())
        return MAIN_MENU

    if data.startswith("run_"):
        if get_points(uid) <= 0:
            await query.edit_message_text("❌ *Insufficient Points!*\nShare your referral link to earn points.", parse_mode="Markdown")
            await update.effective_chat.send_message("Choose an option:", reply_markup=main_keyboard())
            return MAIN_MENU
            
        aid = data[4:]
        await query.edit_message_text("⏳ Running exploit...")
        asyncio.create_task(run_exploit(uid, aid, update, context))
        return MAIN_MENU

    await query.edit_message_text("Unknown action.")
    return MAIN_MENU

async def main_fallback(update, context):
    uid = str(update.effective_user.id)

    if maintenance_check(uid):
        _, maint_msg = get_maintenance_status()
        await update.message.reply_text(f"🛠 *BOT UNDER MAINTENANCE*\n\n{maint_msg}", parse_mode="Markdown")
        return MAIN_MENU

    state = await enforce_membership(update, context, uid)
    if state is not None: return state

    if context.user_data.get("broadcast_mode") and is_admin(int(uid)):
        await broadcast_message(update, context)
        return

    await update.message.reply_text("Use the buttons below.", reply_markup=main_keyboard())
    return MAIN_MENU

# ========== MAIN ==========
def main():
    app = Application.builder().token(TOKEN).build()
    conv = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            WAITING_VERIFY: [
                CallbackQueryHandler(verify_callback, pattern="^verify_join$"),
                CallbackQueryHandler(cancel_verify, pattern="^cancel_verify$"),
            ],
            VERIFY_PROGRAMS: [
                CallbackQueryHandler(verify_programs_callback, pattern="^verify_programs$"),
                CallbackQueryHandler(cancel_verify, pattern="^cancel_verify$"),
            ],
            PHONE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, phone_received),
                CallbackQueryHandler(cancel_phone, pattern="^cancel_phone$"),
            ],
            OTP: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, otp_received),
                CallbackQueryHandler(resend_otp, pattern="^resend_otp$"),
                CallbackQueryHandler(cancel_login, pattern="^cancel_login$"),
            ],
            MAIN_MENU: [
                MessageHandler(filters.Regex("^📋 My Accounts$"), my_accounts),
                MessageHandler(filters.Regex("^➕ Add Account$"), add_account),
                MessageHandler(filters.Regex("^🪙 Coins$"), show_coins),
                MessageHandler(filters.Regex("^💰 My Points$"), my_points),
                MessageHandler(filters.Regex("^📱 Programs$"), show_programs),
                MessageHandler(filters.Regex("^🔗 Referral Link$"), referral_link),
                MessageHandler(filters.Regex("^🚀 Run All$"), run_all),
                MessageHandler(filters.Regex("^❌ Logout$"), logout),
                MessageHandler(filters.Regex("^👥 Users Stats$"), stats_command),
                MessageHandler(filters.Regex("^🎁 Bonus All$"), bonus_all_command),
                MessageHandler(filters.Regex("^🗑️ Clear All$"), clear_all_command),
                MessageHandler(filters.Regex("^📢 Broadcast$"), broadcast_command),
                MessageHandler(filters.Regex("^📊 Admin Log$"), admin_log_command),
                MessageHandler(filters.Regex("^🚪 Exit Admin$"), exit_admin),
                CallbackQueryHandler(callback_handler, pattern="^(run_|del_|back_to_main|delete_account)"),
                CallbackQueryHandler(export_callback, pattern="^export_"),
                CallbackQueryHandler(verify_new_programs, pattern="^verify_new_programs$"),
                CallbackQueryHandler(confirm_clearall, pattern="^confirm_clearall$"),
                CallbackQueryHandler(cancel_clearall, pattern="^cancel_clearall$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, main_fallback),
            ],
        },
        fallbacks=[CommandHandler("start", start)],
    )
    app.add_handler(conv)
    
    app.add_handler(CommandHandler("admin", admin_panel))
    app.add_handler(CommandHandler("stats", stats_command))
    app.add_handler(CommandHandler("bonusall", bonus_all_command))
    app.add_handler(CommandHandler("clearall", clear_all_command))
    app.add_handler(CommandHandler("broadcast", broadcast_command))
    app.add_handler(CommandHandler("chat", chat_command))  
    app.add_handler(CommandHandler("adminlog", admin_log_command))
    app.add_handler(CommandHandler("exit", exit_admin))
    app.add_handler(CommandHandler("maintenance", maintenance_command))
    app.add_handler(CommandHandler("addpoints", add_points_command))
    
    print("✅ Bot started with STRICT Membership Enforcement on ALL features.")
    
    # === KEEP ALIVE START ===
    keep_alive()
    # ========================
    
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
