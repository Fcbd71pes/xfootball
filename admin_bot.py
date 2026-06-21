# admin_bot.py — eFootball Admin Panel Bot
# Token: 8883943020:AAHlgb8zztd0SPDXdipKK5e-6j_yye28AyU
# Username: @xfootball_admin_bot
# Same DB as main bot — no data duplication

import asyncio
import logging
import json
from datetime import datetime
from telegram import (
    Update, InlineKeyboardMarkup, InlineKeyboardButton,
    ReplyKeyboardMarkup, KeyboardButton
)
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, filters, ContextTypes
)

import db
import config
from utils import esc

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger(__name__)

ADMIN_TOKEN = '8883943020:AAHlgb8zztd0SPDXdipKK5e-6j_yye28AyU'

# Players কে message পাঠানোর জন্য main bot instance
from telegram import Bot as TGBot
main_bot = TGBot(token=config.TOKEN)


# ════════════════════════════════════════════════════════════════
#  AUTH CHECK
# ════════════════════════════════════════════════════════════════

def is_staff(uid: int) -> bool:
    return uid in config.ADMINS or uid in config.MANAGERS


def staff_only(func):
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        uid = update.effective_user.id
        if not is_staff(uid):
            await update.effective_message.reply_text("❌ Access denied.")
            return
        return await func(update, context)
    return wrapper


# ════════════════════════════════════════════════════════════════
#  MAIN MENU
# ════════════════════════════════════════════════════════════════

def main_menu_kb():
    return ReplyKeyboardMarkup([
        ["📊 Reports", "👤 Users"],
        ["🎮 Matches", "🏆 Tournament"],
        ["💰 Payments", "📢 Broadcast"],
        ["⚙️ Settings", "💾 Database"],
    ], resize_keyboard=True)


@staff_only
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid  = update.effective_user.id
    name = update.effective_user.first_name
    role = "👑 Admin" if uid in config.ADMINS else "🛡 Manager"
    await update.message.reply_text(
        f"🎮 <b>eFootball Admin Panel</b>\n\n"
        f"স্বাগতম, {esc(name)}!\n"
        f"Role: {role}\n\n"
        f"নিচের menu থেকে কাজ বেছে নাও:",
        parse_mode='HTML',
        reply_markup=main_menu_kb()
    )


# ════════════════════════════════════════════════════════════════
#  REPORTS
# ════════════════════════════════════════════════════════════════

async def show_reports(update: Update, context: ContextTypes.DEFAULT_TYPE):
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("📈 Daily Report",        callback_data="rpt_daily")],
        [InlineKeyboardButton("⏳ Pending Results",     callback_data="rpt_results")],
        [InlineKeyboardButton("💳 Pending Deposits",    callback_data="rpt_deposits")],
        [InlineKeyboardButton("💸 Pending Withdrawals", callback_data="rpt_withdrawals")],
        [InlineKeyboardButton("🏅 Leaderboard",         callback_data="rpt_lb")],
    ])
    await update.message.reply_text("📊 <b>Reports</b>", parse_mode='HTML', reply_markup=kb)


# ════════════════════════════════════════════════════════════════
#  USERS
# ════════════════════════════════════════════════════════════════

async def show_users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔍 User Info",       callback_data="usr_info")],
        [InlineKeyboardButton("✏️ Fix IGN",         callback_data="usr_ign")],
        [InlineKeyboardButton("➕ Add Balance",      callback_data="usr_addbal")],
        [InlineKeyboardButton("➖ Deduct Balance",   callback_data="usr_dedbal")],
        [InlineKeyboardButton("🎯 Set Balance",      callback_data="usr_setbal")],
        [InlineKeyboardButton("🔄 Reset State",      callback_data="usr_reset")],
        [InlineKeyboardButton("🚫 Ban User",         callback_data="usr_ban")],
        [InlineKeyboardButton("✅ Unban User",        callback_data="usr_unban")],
    ])
    await update.message.reply_text("👤 <b>User Management</b>", parse_mode='HTML', reply_markup=kb)


# ════════════════════════════════════════════════════════════════
#  MATCHES
# ════════════════════════════════════════════════════════════════

async def show_matches(update: Update, context: ContextTypes.DEFAULT_TYPE):
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔍 Match Info",         callback_data="mch_info")],
        [InlineKeyboardButton("🏆 Force Win",          callback_data="mch_forcewin")],
        [InlineKeyboardButton("🔴 Cancel + Refund",    callback_data="mch_cancel")],
        [InlineKeyboardButton("⏳ Pending Results",    callback_data="rpt_results")],
    ])
    await update.message.reply_text("🎮 <b>Match Management</b>", parse_mode='HTML', reply_markup=kb)


# ════════════════════════════════════════════════════════════════
#  TOURNAMENT
# ════════════════════════════════════════════════════════════════

async def show_tournament(update: Update, context: ContextTypes.DEFAULT_TYPE):
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🆕 Create Tournament",   callback_data="trn_create")],
        [InlineKeyboardButton("📋 Tournament Status",   callback_data="trn_status")],
        [InlineKeyboardButton("📢 Announce",            callback_data="trn_announce")],
        [InlineKeyboardButton("🔒 Close Registration",  callback_data="trn_close")],
        [InlineKeyboardButton("▶️ Generate Round",      callback_data="trn_round")],
    ])
    await update.message.reply_text("🏆 <b>Tournament</b>", parse_mode='HTML', reply_markup=kb)


# ════════════════════════════════════════════════════════════════
#  PAYMENTS
# ════════════════════════════════════════════════════════════════

async def show_payments(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Current payment info দেখাও
    mfs_text = ""
    for key, info in config.MOBILE_BANKING.items():
        mfs_text += f"  {info['emoji']} {info['name']}: <code>{info['number']}</code>\n"
    exc_text = ""
    for key, info in config.EXCHANGERS.items():
        uid_val = info.get('our_uid', '')
        if uid_val:
            exc_text += f"  {info['emoji']} {info['name']}: <code>{uid_val}</code>\n"

    dep_rate = await db.deposit_rate()
    wit_rate = await db.withdraw_rate()

    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("📱 MFS নম্বর পরিবর্তন",   callback_data="pay_mfs")],
        [InlineKeyboardButton("🏦 Exchanger UID পরিবর্তন", callback_data="pay_exc")],
        [InlineKeyboardButton("📈 Deposit Rate",           callback_data="pay_deprate")],
        [InlineKeyboardButton("📉 Withdrawal Rate",        callback_data="pay_witrate")],
        [InlineKeyboardButton("⏳ Pending Deposits",       callback_data="rpt_deposits")],
        [InlineKeyboardButton("💸 Pending Withdrawals",    callback_data="rpt_withdrawals")],
    ])
    await update.message.reply_text(
        f"💰 <b>Payment Settings</b>\n\n"
        f"<b>📱 MFS:</b>\n{mfs_text}\n"
        f"<b>🏦 Exchangers (active):</b>\n{exc_text or '  কোনো active exchanger নেই'}\n\n"
        f"📈 Deposit Rate: <b>{dep_rate} TK/USDT</b>\n"
        f"📉 Withdraw Rate: <b>{wit_rate} TK/USDT</b>",
        parse_mode='HTML', reply_markup=kb
    )


# ════════════════════════════════════════════════════════════════
#  BROADCAST
# ════════════════════════════════════════════════════════════════

async def show_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("📢 সব Users কে",          callback_data="bc_all")],
        [InlineKeyboardButton("👤 নির্দিষ্ট User কে",   callback_data="bc_user")],
        [InlineKeyboardButton("📣 Channel Announce",      callback_data="bc_channel")],
        [InlineKeyboardButton("🏆 Tournament Announce",   callback_data="bc_tourney")],
    ])
    await update.message.reply_text("📢 <b>Broadcast</b>", parse_mode='HTML', reply_markup=kb)


# ════════════════════════════════════════════════════════════════
#  SETTINGS
# ════════════════════════════════════════════════════════════════

async def show_settings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    free_mode = await db.get_setting('free_mode') or 'off'
    free_status = "✅ চালু" if free_mode == 'on' else "❌ বন্ধ"
    free_btn = "🔴 Free Mode বন্ধ করো" if free_mode == 'on' else "🟢 Free Mode চালু করো"
    free_cb  = "set_free_off" if free_mode == 'on' else "set_free_on"

    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton(free_btn,                   callback_data=free_cb)],
        [InlineKeyboardButton("📜 Rules সেট করো",        callback_data="set_rules")],
        [InlineKeyboardButton("🎥 Tutorial সেট করো",     callback_data="set_tutorial")],
        [InlineKeyboardButton("👥 Manager যোগ করো",      callback_data="set_addmgr")],
        [InlineKeyboardButton("👥 Manager সরাও",         callback_data="set_rmmgr")],
        [InlineKeyboardButton("📋 Manager তালিকা",       callback_data="set_listmgr")],
    ])
    await update.message.reply_text(
        f"⚙️ <b>Bot Settings</b>\n\n"
        f"🆓 Free Mode: {free_status}",
        parse_mode='HTML', reply_markup=kb
    )


# ════════════════════════════════════════════════════════════════
#  DATABASE
# ════════════════════════════════════════════════════════════════

async def show_database(update: Update, context: ContextTypes.DEFAULT_TYPE):
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("💾 Backup নাও",    callback_data="db_backup")],
        [InlineKeyboardButton("♻️ Restore করো",  callback_data="db_restore")],
        [InlineKeyboardButton("📊 DB Stats",      callback_data="db_stats")],
    ])
    await update.message.reply_text("💾 <b>Database</b>", parse_mode='HTML', reply_markup=kb)


# ════════════════════════════════════════════════════════════════
#  TEXT HANDLER — state machine
# ════════════════════════════════════════════════════════════════

async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if not is_staff(uid):
        return

    txt   = update.message.text.strip()
    state = context.user_data.get('state')

    # Menu buttons
    menu_map = {
        "📊 Reports":   show_reports,
        "👤 Users":     show_users,
        "🎮 Matches":   show_matches,
        "🏆 Tournament":show_tournament,
        "💰 Payments":  show_payments,
        "📢 Broadcast": show_broadcast,
        "⚙️ Settings":  show_settings,
        "💾 Database":  show_database,
    }
    if txt in menu_map:
        context.user_data.clear()
        return await menu_map[txt](update, context)

    if txt in ("❌ Cancel", "বাতিল"):
        context.user_data.clear()
        return await update.message.reply_text("✅ বাতিল।", reply_markup=main_menu_kb())

    # State handlers
    if not state:
        return

    # ── User Info ──
    if state == 'usr_info':
        try:
            target = int(txt)
            user = await db.get_user(target)
            if not user:
                return await update.message.reply_text("❌ User পাওয়া যায়নি।")
            wins   = user.get('wins', 0)
            losses = user.get('losses', 0)
            text = (
                f"👤 <b>User Info</b>\n\n"
                f"ID: <code>{target}</code>\n"
                f"IGN: <b>{esc(user.get('ingame_name', '?'))}</b>\n"
                f"Phone: {user.get('phone', '?')}\n"
                f"Balance: <b>{user.get('available_bal', 0):.2f} TK</b>\n"
                f"Locked: {user.get('locked_bal', 0):.2f} TK\n"
                f"W/L: {wins}/{losses}\n"
                f"ELO: {user.get('elo', 1000)}\n"
                f"Banned: {'🚫 Yes' if user.get('is_banned') else '✅ No'}\n"
                f"Joined: {str(user.get('created_at', ''))[:10]}"
            )
            kb = InlineKeyboardMarkup([
                [InlineKeyboardButton("➕ Add Balance",    callback_data=f"quick_addbal_{target}"),
                 InlineKeyboardButton("➖ Deduct",         callback_data=f"quick_dedbal_{target}")],
                [InlineKeyboardButton("✏️ Fix IGN",       callback_data=f"quick_ign_{target}"),
                 InlineKeyboardButton("🔄 Reset State",   callback_data=f"quick_reset_{target}")],
                [InlineKeyboardButton("🚫 Ban",           callback_data=f"quick_ban_{target}"),
                 InlineKeyboardButton("✅ Unban",         callback_data=f"quick_unban_{target}")],
            ])
            await update.message.reply_text(text, parse_mode='HTML', reply_markup=kb)
        except ValueError:
            await update.message.reply_text("❌ Valid User ID দাও।")
        context.user_data.clear()
        return

    # ── Fix IGN ──
    if state == 'usr_ign_id':
        try:
            context.user_data['target_uid'] = int(txt)
            context.user_data['state'] = 'usr_ign_name'
            await update.message.reply_text("✏️ নতুন IGN লেখো:")
        except ValueError:
            await update.message.reply_text("❌ Valid ID দাও।")
        return

    if state == 'usr_ign_name':
        target = context.user_data.get('target_uid')
        old_user = await db.get_user(target)
        old_ign  = old_user.get('ingame_name', '?') if old_user else '?'
        await db.update_user(target, ingame_name=txt)
        try:
            await context.bot.send_message(target, f"✅ Admin আপনার IGN আপডেট করেছে: <b>{esc(txt)}</b>", parse_mode='HTML')
        except Exception:
            pass
        await update.message.reply_text(f"✅ IGN আপডেট!\nআগে: {old_ign}\nএখন: {txt}", reply_markup=main_menu_kb())
        context.user_data.clear()
        return

    # ── Add Balance ──
    if state == 'usr_addbal_id':
        try:
            context.user_data['target_uid'] = int(txt)
            context.user_data['state'] = 'usr_addbal_amt'
            await update.message.reply_text("💰 কত TK যোগ করবে?")
        except ValueError:
            await update.message.reply_text("❌ Valid ID দাও।")
        return

    if state == 'usr_addbal_amt':
        target = context.user_data.get('target_uid')
        try:
            amount = float(txt)
            await db.adjust_balance(target, amount, 'admin_add', f'Admin added {amount} TK')
            user = await db.get_user(target)
            try:
                await context.bot.send_message(target, f"💰 Admin আপনার account এ <b>{amount:.2f} TK</b> যোগ করেছে!", parse_mode='HTML')
            except Exception:
                pass
            await update.message.reply_text(
                f"✅ {amount:.2f} TK যোগ হয়েছে!\nNew balance: {user.get('available_bal', 0):.2f} TK",
                reply_markup=main_menu_kb()
            )
        except ValueError:
            await update.message.reply_text("❌ Valid amount দাও।")
        context.user_data.clear()
        return

    # ── Deduct Balance ──
    if state == 'usr_dedbal_id':
        try:
            context.user_data['target_uid'] = int(txt)
            context.user_data['state'] = 'usr_dedbal_amt'
            await update.message.reply_text("💰 কত TK কাটবে?")
        except ValueError:
            await update.message.reply_text("❌ Valid ID দাও।")
        return

    if state == 'usr_dedbal_amt':
        target = context.user_data.get('target_uid')
        try:
            amount = float(txt)
            await db.adjust_balance(target, -amount, 'admin_deduct', f'Admin deducted {amount} TK')
            user = await db.get_user(target)
            try:
                await context.bot.send_message(target, f"⚠️ Admin আপনার account থেকে <b>{amount:.2f} TK</b> কেটেছে।", parse_mode='HTML')
            except Exception:
                pass
            await update.message.reply_text(
                f"✅ {amount:.2f} TK কাটা হয়েছে!\nNew balance: {user.get('available_bal', 0):.2f} TK",
                reply_markup=main_menu_kb()
            )
        except ValueError:
            await update.message.reply_text("❌ Valid amount দাও।")
        context.user_data.clear()
        return

    # ── Broadcast All ──
    if state == 'bc_all':
        import aiosqlite
        msg = txt
        ok = fail = 0
        async with aiosqlite.connect(db.DB) as conn:
            conn.row_factory = aiosqlite.Row
            async with conn.execute("SELECT user_id FROM users WHERE is_registered=1") as cur:
                users = await cur.fetchall()
        for row in users:
            try:
                await context.bot.send_message(
                    row['user_id'],
                    f"📢 <b>eFootball Announcement</b>\n\n{msg}",
                    parse_mode='HTML'
                )
                ok += 1
            except Exception:
                fail += 1
            if (ok + fail) % 25 == 0:
                await asyncio.sleep(1)
        await update.message.reply_text(f"✅ Broadcast শেষ!\n✅ Success: {ok}\n❌ Failed: {fail}", reply_markup=main_menu_kb())
        context.user_data.clear()
        return

    # ── Broadcast Channel ──
    if state == 'bc_channel':
        for chat_id in [config.LOBBY_CHANNEL_ID, config.GROUP_ID]:
            if chat_id:
                try:
                    await context.bot.send_message(
                        chat_id,
                        f"📣 <b>eFootball Announcement</b>\n\n{txt}",
                        parse_mode='HTML'
                    )
                except Exception:
                    pass
        await update.message.reply_text("✅ Channel/Group এ পাঠানো হয়েছে!", reply_markup=main_menu_kb())
        context.user_data.clear()
        return

    # ── Broadcast single user ──
    if state == 'bc_user_id':
        try:
            context.user_data['target_uid'] = int(txt)
            context.user_data['state'] = 'bc_user_msg'
            await update.message.reply_text("✉️ Message লেখো:")
        except ValueError:
            await update.message.reply_text("❌ Valid ID দাও।")
        return

    if state == 'bc_user_msg':
        target = context.user_data.get('target_uid')
        try:
            await context.bot.send_message(
                target,
                f"📬 <b>Admin Message:</b>\n\n{txt}",
                parse_mode='HTML'
            )
            await update.message.reply_text("✅ পাঠানো হয়েছে!", reply_markup=main_menu_kb())
        except Exception as e:
            await update.message.reply_text(f"❌ {e}", reply_markup=main_menu_kb())
        context.user_data.clear()
        return

    # ── MFS Number ──
    if state == 'pay_mfs_method':
        context.user_data['mfs_method'] = txt.lower()
        context.user_data['state'] = 'pay_mfs_number'
        await update.message.reply_text("📱 নতুন নম্বর লেখো:")
        return

    if state == 'pay_mfs_number':
        method = context.user_data.get('mfs_method')
        if method in config.MOBILE_BANKING:
            config.MOBILE_BANKING[method]['number'] = txt
            await db.set_setting(f'mfs_number_{method}', txt)
            name = config.MOBILE_BANKING[method]['name']
            await update.message.reply_text(f"✅ {name}: <code>{txt}</code>", parse_mode='HTML', reply_markup=main_menu_kb())
        else:
            await update.message.reply_text("❌ Method পাওয়া যায়নি।", reply_markup=main_menu_kb())
        context.user_data.clear()
        return

    # ── Exchanger UID ──
    if state == 'pay_exc_key':
        context.user_data['exc_key'] = txt.lower()
        context.user_data['state'] = 'pay_exc_uid'
        await update.message.reply_text("🔢 নতুন UID লেখো (বন্ধ করতে - লেখো):")
        return

    if state == 'pay_exc_uid':
        key = context.user_data.get('exc_key')
        uid_val = '' if txt == '-' else txt
        if key in config.EXCHANGERS:
            config.EXCHANGERS[key]['our_uid'] = uid_val
            await db.set_setting(f'exc_uid_{key}', uid_val)
            name = config.EXCHANGERS[key]['name']
            status = f"<code>{uid_val}</code>" if uid_val else "বন্ধ"
            await update.message.reply_text(f"✅ {name} UID: {status}", parse_mode='HTML', reply_markup=main_menu_kb())
        else:
            await update.message.reply_text("❌ Exchanger পাওয়া যায়নি।", reply_markup=main_menu_kb())
        context.user_data.clear()
        return

    # ── Rates ──
    if state == 'pay_deprate':
        try:
            rate = float(txt)
            await db.set_setting('deposit_rate', str(rate))
            await update.message.reply_text(f"✅ Deposit rate: <b>{rate} TK/USDT</b>", parse_mode='HTML', reply_markup=main_menu_kb())
        except ValueError:
            await update.message.reply_text("❌ Valid number দাও।", reply_markup=main_menu_kb())
        context.user_data.clear()
        return

    if state == 'pay_witrate':
        try:
            rate = float(txt)
            await db.set_setting('withdraw_rate', str(rate))
            await update.message.reply_text(f"✅ Withdraw rate: <b>{rate} TK/USDT</b>", parse_mode='HTML', reply_markup=main_menu_kb())
        except ValueError:
            await update.message.reply_text("❌ Valid number দাও।", reply_markup=main_menu_kb())
        context.user_data.clear()
        return

    # ── Match Info ──
    if state == 'mch_info':
        mid = txt.upper()
        match = await db.get_match(mid)
        if not match:
            await update.message.reply_text("❌ Match পাওয়া যায়নি।")
            context.user_data.clear()
            return
        p1 = await db.get_user(match['p1_id'])
        p2 = await db.get_user(match['p2_id'])
        p1_ign = esc(p1.get('ingame_name', '?') if p1 else '?')
        p2_ign = esc(p2.get('ingame_name', '?') if p2 else '?')
        text = (
            f"🎮 <b>Match #{mid}</b>\n"
            f"Status: {match['status']}\n"
            f"Fee: {match['fee']} TK\n\n"
            f"P1: {p1_ign} ({match['p1_id']})\n"
            f"  SS: {'✅' if match.get('p1_screenshot') else '❌'}\n\n"
            f"P2: {p2_ign} ({match['p2_id']})\n"
            f"  SS: {'✅' if match.get('p2_screenshot') else '❌'}"
        )
        kb = None
        if match['status'] == 'in_progress':
            kb = InlineKeyboardMarkup([
                [InlineKeyboardButton(f"🏆 {p1_ign} জিতেছে", callback_data=f"verify_{mid}_{match['p1_id']}"),
                 InlineKeyboardButton(f"🏆 {p2_ign} জিতেছে", callback_data=f"verify_{mid}_{match['p2_id']}")],
                [InlineKeyboardButton("🔴 Cancel + Refund", callback_data=f"admin_cancel_{mid}")],
            ])
        await update.message.reply_text(text, parse_mode='HTML', reply_markup=kb)
        context.user_data.clear()
        return

    # ── Tournament Status ──
    if state == 'trn_status':
        try:
            tid = int(txt)
            tourney = await db.get_tournament(tid)
            if not tourney:
                await update.message.reply_text("❌ Tournament পাওয়া যায়নি।")
                context.user_data.clear()
                return
            players = await db.get_tourney_players(tid)
            active  = [p for p in players if p.get('status') == 'ACTIVE']
            text = (
                f"🏆 <b>{esc(tourney['name'])}</b> (#{tid})\n"
                f"Status: {tourney['status']}\n"
                f"Entry: {tourney['entry_fee']:.0f} TK | Prize: {tourney['prize_pool']:.0f} TK\n"
                f"Players: {len(players)}/{tourney['slots']}\n\n"
            )
            for i, p in enumerate(active, 1):
                u = await db.get_user(p['user_id'])
                text += f"{i}. {esc(u.get('ingame_name', '?') if u else '?')}\n"
            kb = InlineKeyboardMarkup([
                [InlineKeyboardButton("▶️ Generate Round",  callback_data=f"trn_gen_{tid}"),
                 InlineKeyboardButton("📢 Announce",        callback_data=f"trn_ann_{tid}")],
                [InlineKeyboardButton("🔒 Close Reg",       callback_data=f"trn_cls_{tid}")],
            ])
            await update.message.reply_text(text, parse_mode='HTML', reply_markup=kb)
        except ValueError:
            await update.message.reply_text("❌ Valid Tournament ID দাও।")
        context.user_data.clear()
        return

    # ── Tournament Create ──
    if state == 'trn_create':
        try:
            parts = [p.strip() for p in txt.split('|')]
            if len(parts) < 4:
                await update.message.reply_text("❌ Format: নাম|slots|fee|prize")
                return
            name     = parts[0]
            slots    = int(parts[1])
            fee      = float(parts[2])
            prize    = float(parts[3])
            tid = await db.create_tournament(name, slots, fee, prize)
            await update.message.reply_text(
                f"✅ Tournament তৈরি হয়েছে!\n"
                f"ID: #{tid}\n"
                f"নাম: {name}\n"
                f"Slots: {slots} | Fee: {fee:.0f} TK | Prize: {prize:.0f} TK\n\n"
                f"Announce করতে: Tournament → Announce → #{tid}",
                reply_markup=main_menu_kb()
            )
        except Exception as e:
            await update.message.reply_text(f"❌ {e}")
        context.user_data.clear()
        return

    # ── Add Manager ──
    if state == 'set_addmgr':
        try:
            mgr_id = int(txt)
            await db.add_manager(mgr_id, uid)  # uid = admin who added
            if mgr_id not in config.MANAGERS:
                config.MANAGERS.append(mgr_id)
            await update.message.reply_text(f"✅ Manager যোগ হয়েছে: <code>{mgr_id}</code>", parse_mode='HTML', reply_markup=main_menu_kb())
        except Exception as e:
            await update.message.reply_text(f"❌ {e}", reply_markup=main_menu_kb())
        context.user_data.clear()
        return

    # ── Remove Manager ──
    if state == 'set_rmmgr':
        try:
            mgr_id = int(txt)
            await db.remove_manager(mgr_id)
            if mgr_id in config.MANAGERS:
                config.MANAGERS.remove(mgr_id)
            await update.message.reply_text(f"✅ Manager সরানো হয়েছে: <code>{mgr_id}</code>", parse_mode='HTML', reply_markup=main_menu_kb())
        except Exception as e:
            await update.message.reply_text(f"❌ {e}", reply_markup=main_menu_kb())
        context.user_data.clear()
        return

    # ── Announce Tournament ──
    if state == 'trn_announce':
        try:
            tid = int(txt)
            tourney = await db.get_tournament(tid)
            if not tourney:
                await update.message.reply_text("❌ Tournament পাওয়া যায়নি।")
                context.user_data.clear()
                return
            players = await db.get_tourney_players(tid)
            joined  = len(players)
            rem     = tourney['slots'] - joined
            join_kb = InlineKeyboardMarkup([[
                InlineKeyboardButton(
                    f"🟢 Join করো ({joined}/{tourney['slots']}) — {rem} বাকি",
                    url=f"https://t.me/{config.BOT_USERNAME}?start=tjoin_{tid}"
                )
            ]])
            ann = (
                f"🏆 <b>eFootball Tournament!</b>\n"
                f"━━━━━━━━━━━━━━━━━\n"
                f"🎮 <b>{esc(tourney['name'])}</b>\n"
                f"💰 Entry: <b>{tourney['entry_fee']:.0f} TK</b>\n"
                f"🎁 Prize: <b>{tourney['prize_pool']:.0f} TK</b>\n"
                f"👥 Slots: <b>{joined}/{tourney['slots']}</b>\n"
                f"━━━━━━━━━━━━━━━━━\n"
                f"👇 Join করতে নিচের বাটনে ক্লিক করো!"
            )
            for chat_id in [config.LOBBY_CHANNEL_ID, config.GROUP_ID]:
                if chat_id:
                    try:
                        await context.bot.send_message(chat_id, ann, parse_mode='HTML', reply_markup=join_kb)
                    except Exception:
                        pass
            await update.message.reply_text("✅ Announcement পাঠানো হয়েছে!", reply_markup=main_menu_kb())
        except ValueError:
            await update.message.reply_text("❌ Valid Tournament ID দাও।")
        context.user_data.clear()
        return

    # ── Reset State ──
    if state == 'usr_reset':
        try:
            target = int(txt)
            await db.set_state(target, None)
            try:
                await context.bot.send_message(target, "🔄 Admin আপনার session reset করেছে।")
            except Exception:
                pass
            await update.message.reply_text(f"✅ User {target} এর state reset হয়েছে।", reply_markup=main_menu_kb())
        except ValueError:
            await update.message.reply_text("❌ Valid ID দাও।", reply_markup=main_menu_kb())
        context.user_data.clear()
        return


# ════════════════════════════════════════════════════════════════
#  CALLBACK HANDLER
# ════════════════════════════════════════════════════════════════

@staff_only
async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q    = update.callback_query
    await q.answer()
    data = q.data
    uid  = q.from_user.id

    cancel_kb = InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel", callback_data="cancel")]])

    # Reports
    if data == 'rpt_daily':
        report = await db.get_daily_report()
        await q.message.reply_text(f"📊 <b>Daily Report</b>\n\n{report}", parse_mode='HTML')
        return

    if data == 'rpt_results':
        pending = await db.get_pending_matches()
        if not pending:
            await q.message.reply_text("✅ কোনো pending result নেই।")
            return
        for m in pending[:5]:
            p1 = await db.get_user(m['p1_id'])
            p2 = await db.get_user(m['p2_id'])
            p1_ign = esc(p1.get('ingame_name', '?') if p1 else '?')
            p2_ign = esc(p2.get('ingame_name', '?') if p2 else '?')
            mid = m['match_id']
            kb = InlineKeyboardMarkup([[
                InlineKeyboardButton(f"🏆 {p1_ign}", callback_data=f"verify_{mid}_{m['p1_id']}"),
                InlineKeyboardButton(f"🏆 {p2_ign}", callback_data=f"verify_{mid}_{m['p2_id']}"),
            ], [
                InlineKeyboardButton("🔴 Cancel", callback_data=f"admin_cancel_{mid}"),
            ]])
            text = (
                f"🎮 Match #{mid}\n"
                f"{p1_ign} vs {p2_ign}\n"
                f"Fee: {m['fee']} TK\n"
                f"P1 SS: {'✅' if m.get('p1_screenshot') else '❌'} | "
                f"P2 SS: {'✅' if m.get('p2_screenshot') else '❌'}"
            )
            if m.get('p1_screenshot'):
                await q.message.reply_photo(m['p1_screenshot'], caption=f"P1: {p1_ign}")
            if m.get('p2_screenshot'):
                await q.message.reply_photo(m['p2_screenshot'], caption=f"P2: {p2_ign}", reply_markup=kb)
            else:
                await q.message.reply_text(text, parse_mode='HTML', reply_markup=kb)
        return

    if data == 'rpt_deposits':
        pending = await db.get_pending_mfs_deposits()
        exc_pending = await db.get_pending_exc_deposits() if hasattr(db, 'get_pending_exc_deposits') else []
        all_pending = list(pending) + list(exc_pending)
        if not all_pending:
            await q.message.reply_text("✅ কোনো pending deposit নেই।")
        else:
            await q.message.reply_text(f"⏳ {len(all_pending)} টা pending deposit আছে। Main bot থেকে দেখো।")
        return

    if data == 'rpt_withdrawals':
        await q.message.reply_text("💸 Pending withdrawals main bot এ দেখো।")
        return

    if data == 'rpt_lb':
        import aiosqlite
        async with aiosqlite.connect(db.DB) as conn:
            conn.row_factory = aiosqlite.Row
            async with conn.execute(
                "SELECT ingame_name, elo, wins, losses FROM users ORDER BY elo DESC LIMIT 10"
            ) as cur:
                rows = await cur.fetchall()
        text = "🏅 <b>Leaderboard</b>\n\n"
        medals = ["🥇", "🥈", "🥉"] + ["4️⃣","5️⃣","6️⃣","7️⃣","8️⃣","9️⃣","🔟"]
        for i, r in enumerate(rows):
            text += f"{medals[i]} {esc(r['ingame_name'])} — ⭐ {r['elo']} ({r['wins']}W/{r['losses']}L)\n"
        await q.message.reply_text(text, parse_mode='HTML')
        return

    # Users
    if data == 'usr_info':
        context.user_data['state'] = 'usr_info'
        await q.message.reply_text("🔍 User ID দাও:")
        return

    if data == 'usr_ign':
        context.user_data['state'] = 'usr_ign_id'
        await q.message.reply_text("👤 User ID দাও:")
        return

    if data == 'usr_addbal':
        context.user_data['state'] = 'usr_addbal_id'
        await q.message.reply_text("👤 User ID দাও:")
        return

    if data == 'usr_dedbal':
        context.user_data['state'] = 'usr_dedbal_id'
        await q.message.reply_text("👤 User ID দাও:")
        return

    if data == 'usr_setbal':
        context.user_data['state'] = 'usr_setbal_id'
        await q.message.reply_text("👤 User ID দাও:")
        return

    if data == 'usr_reset':
        context.user_data['state'] = 'usr_reset'
        await q.message.reply_text("👤 User ID দাও:")
        return

    if data == 'usr_ban':
        context.user_data['state'] = 'usr_ban'
        await q.message.reply_text("🚫 Ban করার User ID দাও:")
        return

    if data == 'usr_unban':
        context.user_data['state'] = 'usr_unban'
        await q.message.reply_text("✅ Unban করার User ID দাও:")
        return

    # Quick action from user info
    if data.startswith('quick_ign_'):
        target = int(data[10:])
        context.user_data['state'] = 'usr_ign_name'
        context.user_data['target_uid'] = target
        await q.message.reply_text(f"✏️ User {target} এর নতুন IGN লেখো:")
        return

    if data.startswith('quick_addbal_'):
        target = int(data[13:])
        context.user_data['state'] = 'usr_addbal_amt'
        context.user_data['target_uid'] = target
        await q.message.reply_text(f"💰 User {target} এ কত TK যোগ করবে?")
        return

    if data.startswith('quick_dedbal_'):
        target = int(data[13:])
        context.user_data['state'] = 'usr_dedbal_amt'
        context.user_data['target_uid'] = target
        await q.message.reply_text(f"💰 User {target} থেকে কত TK কাটবে?")
        return

    if data.startswith('quick_reset_'):
        target = int(data[12:])
        await db.set_state(target, None)
        try:
            await context.bot.send_message(target, "🔄 Admin আপনার session reset করেছে।")
        except Exception:
            pass
        await q.answer(f"✅ Reset done!", show_alert=True)
        return

    if data.startswith('quick_ban_'):
        target = int(data[10:])
        await db.update_user(target, is_banned=1)
        await q.answer(f"🚫 User {target} banned!", show_alert=True)
        return

    if data.startswith('quick_unban_'):
        target = int(data[12:])
        await db.update_user(target, is_banned=0)
        await q.answer(f"✅ User {target} unbanned!", show_alert=True)
        return

    # Match
    if data == 'mch_info':
        context.user_data['state'] = 'mch_info'
        await q.message.reply_text("🎮 Match ID দাও:")
        return

    if data == 'mch_forcewin':
        context.user_data['state'] = 'mch_forcewin_id'
        await q.message.reply_text("🎮 Match ID দাও:")
        return

    if data == 'mch_cancel':
        context.user_data['state'] = 'mch_cancel'
        await q.message.reply_text("🔴 Cancel করার Match ID দাও:")
        return

    if data.startswith('verify_'):
        parts    = data.split('_')
        match_id = parts[1]
        winner_id = int(parts[2])
        match = await db.get_match(match_id)
        if not match or match['status'] != 'in_progress':
            return await q.answer("Already resolved.", show_alert=True)
        m = await db.resolve_match(match_id, winner_id, uid)
        w = await db.get_user(winner_id)
        loser_id = m['p2_id'] if winner_id == m['p1_id'] else m['p1_id']
        prize    = m['fee'] * 1.8
        w_lang   = await db.get_user_lang(winner_id)
        l_lang   = await db.get_user_lang(loser_id)
        from lang import t
        try:
            await context.bot.send_message(winner_id, t('match_won', w_lang, mid=match_id, prize=prize))
        except Exception:
            pass
        try:
            await context.bot.send_message(loser_id, t('match_lost', l_lang, mid=match_id))
        except Exception:
            pass
        w_ign = esc(w.get('ingame_name') if w else '?')
        await q.edit_message_reply_markup(reply_markup=None)
        await q.message.reply_text(f"✅ Winner: <b>{w_ign}</b>\n💰 Prize: {prize:.0f} TK", parse_mode='HTML')
        return

    if data.startswith('admin_cancel_'):
        mid = data[13:]
        match = await db.get_match(mid)
        if not match or match['status'] != 'in_progress':
            return await q.answer("Already resolved.", show_alert=True)
        await db.cancel_match_refund(mid)
        for pid in (match['p1_id'], match['p2_id']):
            try:
                await context.bot.send_message(pid, f"⚠️ Match #{mid} cancel করা হয়েছে। Fee refund হয়েছে।")
                await db.set_state(pid, None)
            except Exception:
                pass
        await q.edit_message_reply_markup(reply_markup=None)
        await q.message.reply_text(f"✅ Match #{mid} cancel + refund done.")
        return

    # Tournament callbacks
    if data.startswith('trn_gen_'):
        tid = int(data[8:])
        try:
            import random
            tourney = await db.get_tournament(tid)
            if not tourney:
                await q.answer("Tournament পাওয়া যায়নি।", show_alert=True)
                return
            players = await db.get_tourney_players(tid, 'ACTIVE')
            if len(players) < 2:
                await q.answer("❌ কমপক্ষে ২ জন active player লাগবে।", show_alert=True)
                return
            if tourney['status'] == 'OPEN':
                await db.update_tournament_status(tid, 'RUNNING')
            random.shuffle(players)
            count = 0
            for i in range(0, len(players) - 1, 2):
                p1_id = players[i]['user_id']
                p2_id = players[i+1]['user_id']
                mid = await db.create_match(p1_id, p2_id, 0, tourney_id=tid)
                u1  = await db.get_user(p1_id)
                u2  = await db.get_user(p2_id)
                p1_ign = esc(u1.get('ingame_name', '?') if u1 else '?')
                p2_ign = esc(u2.get('ingame_name', '?') if u2 else '?')
                from utils import cancel_kb
                l1 = await db.get_user_lang(p1_id)
                l2 = await db.get_user_lang(p2_id)
                # main_bot দিয়ে players কে message পাঠাও
                try:
                    await main_bot.send_message(
                        p1_id,
                        f"⚔️ <b>Tournament Match!</b>\n\n"
                        f"🎮 তোমার প্রতিপক্ষ: <b>{p2_ign}</b>\n\n"
                        f"Room বানাও এবং 8-digit code এখানে পাঠাও।",
                        parse_mode='HTML',
                        reply_markup=cancel_kb(l1)
                    )
                    await db.set_state(p1_id, 'awaiting_room_code', mid)
                except Exception:
                    pass
                try:
                    await main_bot.send_message(
                        p2_id,
                        f"⚔️ <b>Tournament Match!</b>\n\n"
                        f"🎮 তোমার প্রতিপক্ষ: <b>{p1_ign}</b>\n\n"
                        f"Room code এর জন্য অপেক্ষা করো...",
                        parse_mode='HTML'
                    )
                except Exception:
                    pass
                count += 1
            # Bye player (বেজোড় হলে)
            if len(players) % 2 != 0:
                bye_id = players[-1]['user_id']
                try:
                    await main_bot.send_message(bye_id, "🍀 এই round এ তোমার BYE — পরের round এ খেলবে!")
                except Exception:
                    pass
            await q.message.reply_text(
                f"✅ Round তৈরি হয়েছে!\n"
                f"⚔️ {count}টা match শুরু হয়েছে।\n"
                f"Players দের কাছে notification পাঠানো হয়েছে।"
            )
        except Exception as e:
            await q.answer(f"❌ {e}", show_alert=True)
        return

    if data.startswith('trn_ann_'):
        tid = int(data[8:])
        context.user_data['state'] = 'trn_announce'
        context.user_data['trn_announce_id'] = tid
        await q.message.reply_text(f"Tournament #{tid} announce করব?", reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("✅ হ্যাঁ", callback_data=f"trn_ann_confirm_{tid}"),
            InlineKeyboardButton("❌ না",    callback_data="cancel"),
        ]]))
        return

    if data.startswith('trn_ann_confirm_'):
        tid = int(data[16:])
        tourney = await db.get_tournament(tid)
        if not tourney:
            await q.answer("❌ Tournament পাওয়া যায়নি।", show_alert=True)
            return
        players = await db.get_tourney_players(tid)
        joined  = len(players)
        rem     = tourney['slots'] - joined
        join_kb = InlineKeyboardMarkup([[
            InlineKeyboardButton(
                f"🟢 Join করো ({joined}/{tourney['slots']}) — {rem} বাকি",
                url=f"https://t.me/{config.BOT_USERNAME}?start=tjoin_{tid}"
            )
        ]])
        ann = (
            f"🏆 <b>eFootball Tournament!</b>\n"
            f"━━━━━━━━━━━━━━━━━\n"
            f"🎮 <b>{esc(tourney['name'])}</b>\n"
            f"💰 Entry: <b>{tourney['entry_fee']:.0f} TK</b>\n"
            f"🎁 Prize: <b>{tourney['prize_pool']:.0f} TK</b>\n"
            f"👥 Slots: <b>{joined}/{tourney['slots']}</b>\n"
            f"━━━━━━━━━━━━━━━━━\n"
            f"👇 Join করতে নিচের বাটনে ক্লিক করো!"
        )
        for chat_id in [config.LOBBY_CHANNEL_ID, config.GROUP_ID]:
            if chat_id:
                try:
                    await context.bot.send_message(chat_id, ann, parse_mode='HTML', reply_markup=join_kb)
                except Exception:
                    pass
        await q.edit_message_text("✅ Announcement পাঠানো হয়েছে!")
        return

    if data.startswith('trn_cls_'):
        tid = int(data[8:])
        await db.update_tournament_status(tid, 'RUNNING')
        players = await db.get_tourney_players(tid)
        tourney = await db.get_tournament(tid)
        for p in players:
            try:
                await context.bot.send_message(
                    p['user_id'],
                    f"🏆 <b>{esc(tourney['name'])}</b> শুরু হতে চলেছে!\n"
                    f"👥 {len(players)} জন player | ⚔️ প্রস্তুত থাকুন!",
                    parse_mode='HTML'
                )
            except Exception:
                pass
        await q.answer(f"✅ Registration বন্ধ! {len(players)} জন notify হয়েছে।", show_alert=True)
        return

    # Tournament
    if data == 'trn_create':
        context.user_data['state'] = 'trn_create'
        await q.message.reply_text(
            "🏆 Tournament তৈরি করো:\n\n"
            "Format: <code>নাম|slots|fee|prize</code>\n\n"
            "উদাহরণ:\n<code>Weekly Cup|8|50|320</code>",
            parse_mode='HTML'
        )
        return

    if data == 'trn_status':
        context.user_data['state'] = 'trn_status'
        await q.message.reply_text("🏆 Tournament ID দাও:")
        return

    if data == 'trn_announce':
        context.user_data['state'] = 'trn_announce'
        await q.message.reply_text("🏆 Tournament ID দাও:")
        return

    if data == 'trn_close':
        context.user_data['state'] = 'trn_close'
        await q.message.reply_text("🏆 Tournament ID দাও:")
        return

    if data == 'trn_round':
        context.user_data['state'] = 'trn_round'
        await q.message.reply_text("🏆 Tournament ID দাও:")
        return

    # Payments
    if data == 'pay_mfs':
        methods = '\n'.join([f"  <code>{k}</code> — {v['name']}" for k, v in config.MOBILE_BANKING.items()])
        context.user_data['state'] = 'pay_mfs_method'
        await q.message.reply_text(
            f"📱 Method লেখো:\n{methods}",
            parse_mode='HTML'
        )
        return

    if data == 'pay_exc':
        keys = '\n'.join([f"  <code>{k}</code> — {v['name']}" for k, v in config.EXCHANGERS.items()])
        context.user_data['state'] = 'pay_exc_key'
        await q.message.reply_text(
            f"🏦 Exchanger key লেখো:\n{keys}",
            parse_mode='HTML'
        )
        return

    if data == 'pay_deprate':
        dep_rate = await db.deposit_rate()
        context.user_data['state'] = 'pay_deprate'
        await q.message.reply_text(f"📈 নতুন deposit rate লেখো (TK/USDT)\nবর্তমান: {dep_rate}:")
        return

    if data == 'pay_witrate':
        wit_rate = await db.withdraw_rate()
        context.user_data['state'] = 'pay_witrate'
        await q.message.reply_text(f"📉 নতুন withdraw rate লেখো (TK/USDT)\nবর্তমান: {wit_rate}:")
        return

    # Broadcast
    if data == 'bc_all':
        context.user_data['state'] = 'bc_all'
        await q.message.reply_text("📢 সব user কে যে message পাঠাবে লেখো:")
        return

    if data == 'bc_user':
        context.user_data['state'] = 'bc_user_id'
        await q.message.reply_text("👤 User ID দাও:")
        return

    if data == 'bc_channel':
        context.user_data['state'] = 'bc_channel'
        await q.message.reply_text("📣 Channel/Group এ যে message পাঠাবে লেখো:")
        return

    if data == 'bc_tourney':
        context.user_data['state'] = 'trn_announce'
        await q.message.reply_text("🏆 Tournament ID দাও:")
        return

    # Settings
    if data == 'set_free_on':
        await db.set_setting('free_mode', 'on')
        config.FREE_MODE = True
        for chat_id in [config.LOBBY_CHANNEL_ID, config.GROUP_ID]:
            if chat_id:
                try:
                    await context.bot.send_message(
                        chat_id,
                        "🎉 <b>FREE MODE চালু!</b>\nএখন ফ্রিতে eFootball match খেলো! Bot এ যাও →",
                        parse_mode='HTML'
                    )
                except Exception:
                    pass
        await q.edit_message_text("✅ Free Mode চালু হয়েছে! Channel এ announce করা হয়েছে।")
        return

    if data == 'set_free_off':
        await db.set_setting('free_mode', 'off')
        config.FREE_MODE = False
        await q.edit_message_text("✅ Free Mode বন্ধ হয়েছে।")
        return

    if data == 'set_rules':
        context.user_data['state'] = 'set_rules'
        await q.message.reply_text("📜 নতুন rules লেখো:")
        return

    if data == 'set_addmgr':
        context.user_data['state'] = 'set_addmgr'
        await q.message.reply_text("👥 Manager এর Telegram ID দাও:")
        return

    if data == 'set_rmmgr':
        context.user_data['state'] = 'set_rmmgr'
        await q.message.reply_text("👥 Remove করার Manager ID দাও:")
        return

    if data == 'set_listmgr':
        mgrs = config.MANAGERS or []
        text = "👥 <b>Managers:</b>\n"
        if mgrs:
            for m in mgrs:
                u = await db.get_user(m)
                name = esc(u.get('ingame_name', '?') if u else '?')
                text += f"  • {name} (<code>{m}</code>)\n"
        else:
            text += "  কোনো manager নেই।"
        await q.message.reply_text(text, parse_mode='HTML')
        return

    # Database
    if data == 'db_backup':
        try:
            backup_path = f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
            await db.safe_backup(backup_path)
            with open(backup_path, 'rb') as f:
                await q.message.reply_document(
                    f,
                    filename=backup_path,
                    caption=f"💾 DB Backup\n{datetime.now().strftime('%Y-%m-%d %H:%M')}"
                )
            import os
            os.remove(backup_path)
        except Exception as e:
            await q.message.reply_text(f"❌ Backup failed: {e}")
        return

    if data == 'db_restore':
        await q.message.reply_text(
            "♻️ Restore করতে:\n"
            ".db ফাইল পাঠাও এই bot এ — automatic restore হবে।"
        )
        return

    if data == 'db_stats':
        import aiosqlite
        async with aiosqlite.connect(db.DB) as conn:
            conn.row_factory = aiosqlite.Row
            async with conn.execute("SELECT COUNT(*) as c FROM users") as cur:
                users_count = (await cur.fetchone())['c']
            async with conn.execute("SELECT COUNT(*) as c FROM users WHERE is_registered=1") as cur:
                reg_count = (await cur.fetchone())['c']
            async with conn.execute("SELECT COUNT(*) as c FROM matches") as cur:
                match_count = (await cur.fetchone())['c']
            async with conn.execute("SELECT COUNT(*) as c FROM matches WHERE status='in_progress'") as cur:
                active_count = (await cur.fetchone())['c']
        await q.message.reply_text(
            f"📊 <b>DB Stats</b>\n\n"
            f"👤 Total users: {users_count}\n"
            f"✅ Registered: {reg_count}\n"
            f"🎮 Total matches: {match_count}\n"
            f"⚡ Active matches: {active_count}",
            parse_mode='HTML'
        )
        return

    if data == 'cancel':
        context.user_data.clear()
        await q.edit_message_text("✅ বাতিল।")
        return


# ════════════════════════════════════════════════════════════════
#  DOCUMENT HANDLER — auto restore
# ════════════════════════════════════════════════════════════════

@staff_only
async def document_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    doc = update.message.document
    if not doc or not doc.file_name.endswith('.db'):
        return
    await update.message.reply_text("⏳ Restore হচ্ছে...")
    try:
        import shutil, os
        file = await context.bot.get_file(doc.file_id)
        temp = f"restore_temp_{doc.file_name}"
        await file.download_to_drive(temp)
        backup = f"pre_restore_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
        await db.safe_backup(backup)
        shutil.copy2(temp, config.LOCAL_DB)
        os.remove(temp)
        await update.message.reply_text(
            f"✅ Restore সফল!\n"
            f"📁 File: {doc.file_name}\n"
            f"💾 Safety backup: {backup}"
        )
    except Exception as e:
        await update.message.reply_text(f"❌ Restore ব্যর্থ: {e}")


# ════════════════════════════════════════════════════════════════
#  MAIN
# ════════════════════════════════════════════════════════════════

async def main():
    await db.init_db()
    await db.load_payment_settings()

    app = Application.builder().token(ADMIN_TOKEN).build()

    app.add_handler(CommandHandler('start', cmd_start))
    app.add_handler(CommandHandler('menu',  cmd_start))
    app.add_handler(CallbackQueryHandler(callback_handler))
    app.add_handler(MessageHandler(filters.Document.ALL, document_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))

    logger.info("🛡 Admin Bot starting...")
    async with app:
        await app.start()
        await app.updater.start_polling(drop_pending_updates=True)
        await asyncio.Event().wait()  # চলতে থাকবে
        await app.updater.stop()
        await app.stop()


if __name__ == '__main__':
    asyncio.run(main())
