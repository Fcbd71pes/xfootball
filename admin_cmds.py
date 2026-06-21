# admin_cmds.py
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes
import db
import config
from lang import t
from utils import esc, staff_ids, main_kb


def _admin_only(f):
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        if update.effective_user.id not in config.ADMINS:
            return await update.message.reply_text("❌ Admin only.")
        return await f(update, context)
    wrapper.__name__ = f.__name__
    return wrapper


def _staff_only(f):
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        if update.effective_user.id not in staff_ids():
            return await update.message.reply_text("❌ Staff only.")
        return await f(update, context)
    wrapper.__name__ = f.__name__
    return wrapper


# ── Manager management ────────────────────────────────────────────────────

@_admin_only
async def cmd_addmanager(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        mgrs = await db.get_managers()
        lines = [f"🔧 {m}" for m in mgrs] or ["(none)"]
        return await update.message.reply_text(
            "Managers:\n" + "\n".join(lines) + "\n\nAdd: /addmanager <user_id>"
        )
    try:
        uid = int(context.args[0])
        if uid in config.ADMINS:
            return await update.message.reply_text("❌ Cannot add admin as manager.")
        await db.add_manager(uid, update.effective_user.id)
        if uid not in config.MANAGERS:
            config.MANAGERS.append(uid)
        await update.message.reply_text(f"✅ Manager {uid} added.")
        try:
            await context.bot.send_message(uid, "✅ You have been added as Manager.")
        except Exception:
            pass
    except ValueError:
        await update.message.reply_text("❌ Invalid user ID.")


@_admin_only
async def cmd_removemanager(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        return await update.message.reply_text("Usage: /removemanager <user_id>")
    try:
        uid = int(context.args[0])
        if uid in config.ADMINS:
            return await update.message.reply_text("❌ Cannot remove admin.")
        removed = await db.remove_manager(uid)
        if uid in config.MANAGERS:
            config.MANAGERS.remove(uid)
        if removed:
            await update.message.reply_text(f"✅ Manager {uid} removed.")
            try:
                await context.bot.send_message(uid, "ℹ️ You have been removed as Manager.")
            except Exception:
                pass
        else:
            await update.message.reply_text(f"❌ {uid} is not a manager.")
    except ValueError:
        await update.message.reply_text("❌ Invalid user ID.")


@_admin_only
async def cmd_listmanagers(update: Update, context: ContextTypes.DEFAULT_TYPE):
    mgrs  = await db.get_managers()
    lines = [f"👑 Admin: {a}" for a in config.ADMINS]
    lines += [f"🔧 Manager: {m}" for m in mgrs]
    await update.message.reply_text("Staff:\n" + "\n".join(lines) if lines else "No staff.")


# ── Financial settings ────────────────────────────────────────────────────

@_admin_only
async def cmd_setdeprate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        v = await db.get_setting('usdt_deposit_rate')
        return await update.message.reply_text(f"Current deposit rate: 1 USDT = {v} TK\nSet: /setdeprate <rate>")
    try:
        rate = float(context.args[0])
        await db.set_setting('usdt_deposit_rate', str(rate))
        await update.message.reply_text(f"✅ Deposit rate: 1 USDT = {rate} TK")
    except ValueError:
        await update.message.reply_text("❌ Invalid number.")


@_admin_only
async def cmd_setwitrate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        v = await db.get_setting('usdt_withdraw_rate')
        return await update.message.reply_text(f"Current withdraw rate: 1 USDT = {v} TK\nSet: /setwitrate <rate>")
    try:
        rate = float(context.args[0])
        await db.set_setting('usdt_withdraw_rate', str(rate))
        await update.message.reply_text(f"✅ Withdraw rate: 1 USDT = {rate} TK")
    except ValueError:
        await update.message.reply_text("❌ Invalid number.")


@_admin_only
async def cmd_setrules(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        rules = await db.get_setting('rules_text')
        return await update.message.reply_text(f"Current rules:\n{rules or '(not set)'}\n\nSet: /setrules <text>")
    await db.set_setting('rules_text', ' '.join(context.args))
    await update.message.reply_text("✅ Rules updated.")


# ── Daily report ──────────────────────────────────────────────────────────

@_admin_only
async def cmd_report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    r = await db.get_daily_report()
    text = (
        f"📊 Daily Report — {r['date']}\n"
        f"{'='*30}\n\n"
        f"👥 Total users: {r['total_users']} (+{r['new_users']} today)\n\n"
        f"🎮 Matches: {r['matches']} | Completed: {r['completed']}\n"
        f"   Fees collected: {r['fees']:.2f} TK\n\n"
        f"💳 MFS Deposits: {r['mfs_dep_count']} × {r['mfs_dep_amount']:.2f} TK\n"
        f"💎 Exc Deposits: {r['exc_dep_count']} × {r['exc_dep_usdt']:.4f} USDT ({r['exc_dep_tk']:.2f} TK)\n\n"
        f"💸 MFS Withdrawals: {r['mfs_wit_amount']:.2f} TK\n"
        f"💸 Exc Withdrawals: {r['exc_wit_usdt']:.4f} USDT\n\n"
        f"⏳ Pending\n"
        f"   MFS dep: {r['pending_mfs_dep']} | Exc dep: {r['pending_exc_dep']}\n"
        f"   MFS wit: {r['pending_mfs_wit']} | Exc wit: {r['pending_exc_wit']}\n\n"
        f"{'='*30}\n"
        f"💱 Rates: Dep 1 USDT={r['dep_rate']} TK | Wit 1 USDT={r['wit_rate']} TK"
    )
    await update.message.reply_text(text)


# ── User management ───────────────────────────────────────────────────────

@_staff_only
async def cmd_userinfo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        return await update.message.reply_text("Usage: /userinfo <user_id>")
    try:
        uid  = int(context.args[0])
        user = await db.get_user(uid)
        if not user:
            return await update.message.reply_text("❌ Not found.")
        text = (
            f"👤 User {uid}\n"
            f"IGN: {esc(user.get('ingame_name'))}\n"
            f"Phone: {esc(user.get('phone'))}\n"
            f"Available: {user['available_bal']:.2f} TK\n"
            f"Locked: {user['locked_bal']:.2f} TK\n"
            f"ELO: {user['elo']} | Won: {user['wins']} | Lost: {user['losses']}\n"
            f"Banned: {'Yes' if user['is_banned'] else 'No'}"
        )
        kb = InlineKeyboardMarkup([[
            InlineKeyboardButton("🔒 Ban", callback_data=f"admin_ban_{uid}"),
        ]])
        await update.message.reply_text(text, reply_markup=kb)
    except ValueError:
        await update.message.reply_text("❌ Invalid ID.")


@_admin_only
async def cmd_banuser(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        return await update.message.reply_text("Usage: /banuser <user_id>")
    try:
        uid = int(context.args[0])
        await db.update_user(uid, is_banned=1)
        await update.message.reply_text(f"✅ Banned {uid}.")
        try:
            await context.bot.send_message(uid, "❌ Your account has been banned.")
        except Exception:
            pass
    except ValueError:
        await update.message.reply_text("❌ Invalid ID.")


@_admin_only
async def cmd_unbanuser(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        return await update.message.reply_text("Usage: /unbanuser <user_id>")
    try:
        uid = int(context.args[0])
        await db.update_user(uid, is_banned=0)
        await update.message.reply_text(f"✅ Unbanned {uid}.")
        try:
            await context.bot.send_message(uid, "✅ Your account has been restored.")
        except Exception:
            pass
    except ValueError:
        await update.message.reply_text("❌ Invalid ID.")


@_admin_only
async def cmd_addbalance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args or len(context.args) < 2:
        return await update.message.reply_text("Usage: /addbalance <user_id> <amount> [note]")
    try:
        uid    = int(context.args[0])
        amount = float(context.args[1])
        note   = ' '.join(context.args[2:]) or 'admin bonus'
        user   = await db.get_user(uid)
        if not user:
            return await update.message.reply_text("❌ Not found.")
        await db.admin_adjust_balance(uid, amount, note)
        await update.message.reply_text(f"✅ Added {amount:.2f} TK to {esc(user.get('ingame_name'))}.")
        try:
            await context.bot.send_message(uid, f"✅ {amount:.2f} TK added. ({note})")
        except Exception:
            pass
    except ValueError:
        await update.message.reply_text("❌ Invalid input.")


@_admin_only
async def cmd_deductbalance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args or len(context.args) < 2:
        return await update.message.reply_text("Usage: /deductbalance <user_id> <amount> [note]")
    try:
        uid    = int(context.args[0])
        amount = float(context.args[1])
        note   = ' '.join(context.args[2:]) or 'admin deduct'
        user   = await db.get_user(uid)
        if not user:
            return await update.message.reply_text("❌ Not found.")
        if user['available_bal'] < amount:
            return await update.message.reply_text("❌ Insufficient balance.")
        await db.admin_adjust_balance(uid, -amount, note)
        await update.message.reply_text(f"✅ Deducted {amount:.2f} TK from {esc(user.get('ingame_name'))}.")
    except ValueError:
        await update.message.reply_text("❌ Invalid input.")


# ── Match management ──────────────────────────────────────────────────────

@_staff_only
async def cmd_pending_results(update: Update, context: ContextTypes.DEFAULT_TYPE):
    pending = await db.get_pending_matches()
    if not pending:
        return await update.message.reply_text("✅ No pending matches.")
    for m in pending:
        p1 = await db.get_user(m['p1_id'])
        p2 = await db.get_user(m['p2_id'])
        p1_ign = esc(p1.get('ingame_name') if p1 else '?')
        p2_ign = esc(p2.get('ingame_name') if p2 else '?')
        text = f"🎮 Match #{m['match_id']}\n{p1_ign} vs {p2_ign}\nFee: {m['fee']} TK"
        kb   = InlineKeyboardMarkup([[
            InlineKeyboardButton(f"✅ {p1_ign}", callback_data=f"verify_{m['match_id']}_{m['p1_id']}"),
            InlineKeyboardButton(f"✅ {p2_ign}", callback_data=f"verify_{m['match_id']}_{m['p2_id']}"),
        ]])
        await update.message.reply_text(text, reply_markup=kb)


@_staff_only
async def cmd_pending_deposits(update: Update, context: ContextTypes.DEFAULT_TYPE):
    mfs = await db.get_pending_mfs_deposits()
    exc = await db.get_pending_exc_deposits()
    if not mfs and not exc:
        return await update.message.reply_text("✅ No pending deposits.")
    for d in mfs:
        user = await db.get_user(d['user_id'])
        info = config.MOBILE_BANKING.get(d['method'], {})
        cap  = (
            f"💳 MFS Deposit #{d['id']}\n"
            f"👤 {esc(user.get('ingame_name') if user else '?')} ({d['user_id']})\n"
            f"📱 {info.get('name', d['method'])} | TxID: {d['txid']}\n"
            f"💰 {d['amount']:.2f} TK"
        )
        kb = InlineKeyboardMarkup([[
            InlineKeyboardButton(f"✅ #{d['id']}", callback_data=f"mdep_approve_{d['id']}"),
            InlineKeyboardButton(f"❌ #{d['id']}", callback_data=f"mdep_reject_{d['id']}"),
        ]])
        try:
            await context.bot.send_photo(update.effective_user.id, d['screenshot'], caption=cap, reply_markup=kb)
        except Exception:
            await update.message.reply_text(cap, reply_markup=kb)
    for d in exc:
        user = await db.get_user(d['user_id'])
        info = config.EXCHANGERS.get(d['exchanger'], {})
        cap  = (
            f"💎 Exc Deposit #{d['id']}\n"
            f"👤 {esc(user.get('ingame_name') if user else '?')} ({d['user_id']})\n"
            f"🏦 {info.get('name', d['exchanger'])}\n"
            f"💵 {d['amount_usdt']:.4f} USDT = {d['amount_tk']:.2f} TK\n"
            f"📥 Our UID: {d.get('our_uid', '?')}\n"
            f"📤 Their UID: {d.get('user_uid', '?')}"
        )
        kb = InlineKeyboardMarkup([[
            InlineKeyboardButton(f"✅ #{d['id']}", callback_data=f"edep_approve_{d['id']}"),
            InlineKeyboardButton(f"❌ #{d['id']}", callback_data=f"edep_reject_{d['id']}"),
        ]])
        try:
            await context.bot.send_photo(update.effective_user.id, d['screenshot'], caption=cap, reply_markup=kb)
        except Exception:
            await update.message.reply_text(cap, reply_markup=kb)


@_staff_only
async def cmd_pending_withdrawals(update: Update, context: ContextTypes.DEFAULT_TYPE):
    mfs = await db.get_pending_mfs_withdrawals()
    exc = await db.get_pending_exc_withdrawals()
    if not mfs and not exc:
        return await update.message.reply_text("✅ No pending withdrawals.")
    for w in mfs:
        user = await db.get_user(w['user_id'])
        info = config.MOBILE_BANKING.get(w['method'], {})
        text = (
            f"💸 MFS Withdrawal #{w['id']}\n"
            f"👤 {esc(user.get('ingame_name') if user else '?')} ({w['user_id']})\n"
            f"📱 {info.get('name', w['method'])}: {w['account']}\n"
            f"💰 {w['amount']:.2f} TK"
        )
        kb = InlineKeyboardMarkup([[
            InlineKeyboardButton(f"✅ #{w['id']}", callback_data=f"mwit_approve_{w['id']}"),
            InlineKeyboardButton(f"❌ #{w['id']}", callback_data=f"mwit_reject_{w['id']}"),
        ]])
        await update.message.reply_text(text, reply_markup=kb)
    for w in exc:
        user = await db.get_user(w['user_id'])
        info = config.EXCHANGERS.get(w['exchanger'], {})
        our_uid = info.get('our_uid', '?')
        text = (
            f"💸 Exc Withdrawal #{w['id']}\n"
            f"👤 {esc(user.get('ingame_name') if user else '?')} ({w['user_id']})\n"
            f"🏦 {info.get('name', w['exchanger'])}\n"
            f"💵 {w['amount_usdt']:.4f} USDT = {w['amount_tk']:.2f} TK\n"
            f"📤 Their UID: {w['user_uid']}\n"
            f"📥 Our UID: {our_uid}"
        )
        kb = InlineKeyboardMarkup([[
            InlineKeyboardButton(f"✅ #{w['id']}", callback_data=f"ewit_approve_{w['id']}"),
            InlineKeyboardButton(f"❌ #{w['id']}", callback_data=f"ewit_reject_{w['id']}"),
        ]])
        await update.message.reply_text(text, reply_markup=kb)


# ── Broadcast ─────────────────────────────────────────────────────────────

@_admin_only
async def cmd_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        return await update.message.reply_text("Usage: /broadcast <message>")
    import aiosqlite
    msg  = ' '.join(context.args)
    ok   = 0
    fail = 0
    async with aiosqlite.connect(db.DB) as conn:
        conn.row_factory = aiosqlite.Row
        async with conn.execute("SELECT user_id FROM users WHERE is_registered=1") as cur:
            users = await cur.fetchall()
    import asyncio
    for row in users:
        try:
            await context.bot.send_message(row['user_id'], f"📢 {msg}")
            ok += 1
        except Exception:
            fail += 1
        if (ok + fail) % 25 == 0:
            await asyncio.sleep(1)
    await update.message.reply_text(f"✅ Broadcast done. OK: {ok} | Failed: {fail}")


@_admin_only
async def cmd_message_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args or len(context.args) < 2:
        return await update.message.reply_text("Usage: /message_user <user_id> <text>")
    try:
        uid  = int(context.args[0])
        text = ' '.join(context.args[1:])
        await context.bot.send_message(uid, f"📬 Message from admin:\n\n{text}")
        await update.message.reply_text("✅ Sent.")
    except Exception as e:
        await update.message.reply_text(f"❌ {e}")


# ── Tournament management ─────────────────────────────────────────────────

@_admin_only
async def cmd_create_tourney(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = ' '.join(context.args)
    if '|' not in text:
        return await update.message.reply_text(
            "Usage: /create_tourney <name> | <slots> | <fee> | <prize>\n"
            "e.g.: /create_tourney Friday Cup | 16 | 50 | 500"
        )
    parts = [p.strip() for p in text.split('|')]
    if len(parts) != 4:
        return await update.message.reply_text("❌ Need 4 parts separated by |")
    try:
        name, slots, fee, prize = parts[0], int(parts[1]), float(parts[2]), float(parts[3])
        tid = await db.create_tournament(name, slots, fee, prize)
        await update.message.reply_text(
            f"✅ Tournament #{tid} created!\n{name}\n{slots} slots | {fee} TK fee | {prize} TK prize"
        )
    except Exception as e:
        await update.message.reply_text(f"❌ {e}")


@_admin_only
async def cmd_generate_round(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        return await update.message.reply_text("Usage: /generate_round <tourney_id>")
    import random
    try:
        tid     = int(context.args[0])
        tourney = await db.get_tournament(tid)
        if not tourney:
            return await update.message.reply_text("❌ Tournament not found.")
        players = await db.get_tourney_players(tid, 'ACTIVE')
        if len(players) < 2:
            return await update.message.reply_text("❌ Not enough players.")
        if tourney['status'] == 'OPEN':
            await db.update_tournament_status(tid, 'RUNNING')
        random.shuffle(players)
        count = 0
        for i in range(0, len(players) - 1, 2):
            p1, p2 = players[i]['user_id'], players[i+1]['user_id']
            mid = await db.create_match(p1, p2, 0, tourney_id=tid)
            u1 = await db.get_user(p1)
            u2 = await db.get_user(p2)
            l1 = await db.get_user_lang(p1)
            l2 = await db.get_user_lang(p2)
            try:
                await context.bot.send_message(
                    p1,
                    f"⚔️ Tournament match!\nvs {esc(u2.get('ingame_name') if u2 else '?')}\n\nCreate a room and send the 8-digit code here.",
                    reply_markup=__import__('utils').cancel_kb(l1)
                )
                await db.set_state(p1, 'awaiting_room_code', mid)
                await context.bot.send_message(
                    p2,
                    f"⚔️ Tournament match!\nvs {esc(u1.get('ingame_name') if u1 else '?')}\n\nWaiting for room code...",
                )
            except Exception:
                pass
            count += 1
        if len(players) % 2 != 0:
            bye = players[-1]['user_id']
            blang = await db.get_user_lang(bye)
            try:
                await context.bot.send_message(bye, "🍀 BYE — you advance to the next round!")
            except Exception:
                pass
        await update.message.reply_text(f"✅ Round generated! {count} match(es) created.")
    except Exception as e:
        await update.message.reply_text(f"❌ {e}")


# ── Background jobs ───────────────────────────────────────────────────────

async def job_daily_backup(context):
    """Daily SQLite backup using native backup API."""
    from datetime import datetime
    dest = f"backup_{datetime.now().strftime('%Y-%m-%d')}.db"
    try:
        await db.safe_backup(dest)
        # Remove backups older than 7 days
        import os, glob
        from datetime import timedelta
        for path in glob.glob("backup_*.db"):
            try:
                date_str = path[7:17]
                file_date = datetime.strptime(date_str, '%Y-%m-%d')
                if (datetime.now() - file_date).days > 7:
                    os.remove(path)
            except Exception:
                pass
    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f"Backup failed: {e}")


@_admin_only
async def cmd_backup(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("⏳ ডাটাবেজ ব্যাকআপ তৈরি হচ্ছে, দয়া করে অপেক্ষা করুন...")
    from datetime import datetime
    dest = f"manual_backup_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.db"
    try:
        await db.safe_backup(dest)
        import os
        with open(dest, 'rb') as doc:
            await context.bot.send_document(
                chat_id=update.effective_user.id,
                document=doc,
                filename=dest,
                caption="✅ আপনার ডাটাবেজ ব্যাকআপ সফলভাবে সম্পন্ন হয়েছে!"
            )
        os.remove(dest)  # সেন্ড করার পর সার্ভার থেকে মুছে ফেলবে যাতে স্টোরেজ না ভরে
    except Exception as e:
        await update.message.reply_text(f"❌ ব্যাকআপ নিতে সমস্যা হয়েছে: {e}")


@_admin_only
async def cmd_settutorial(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.reply_to_message or not update.message.reply_to_message.video:
        return await update.message.reply_text("❌ আপনাকে প্রথমে বটকে একটি ভিডিও পাঠাতে হবে, তারপর সেই ভিডিওতে রিপ্লাই করে /settutorial লিখতে হবে।")
    
    file_id = update.message.reply_to_message.video.file_id
    await db.set_setting('tutorial_video_id', file_id)
    await update.message.reply_text("✅ চমৎকার! টিউটোরিয়াল ভিডিও সফলভাবে ডাটাবেজে সেভ হয়েছে। এখন ইউজাররা 'How to Play' তে ক্লিক করলেই এই ভিডিওটি দেখতে পাবে।")


# ════════════════════════════════════════════════════════════════════════════
#  PAYMENT INFO EDIT COMMANDS
# ════════════════════════════════════════════════════════════════════════════

@_admin_only
async def cmd_set_mfs_number(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Usage: /set_mfs_number bkash 01XXXXXXXXX"""
    if len(context.args) < 2:
        methods = ', '.join(config.MOBILE_BANKING.keys())
        return await update.message.reply_text(
            f"📱 <b>MFS নম্বর পরিবর্তন</b>\n\n"
            f"ব্যবহার: /set_mfs_number &lt;method&gt; &lt;number&gt;\n\n"
            f"উদাহরণ: /set_mfs_number bkash 01711223344\n\n"
            f"Available methods: {methods}",
            parse_mode='HTML'
        )
    method = context.args[0].lower()
    number = context.args[1]
    if method not in config.MOBILE_BANKING:
        return await update.message.reply_text(f"❌ '{method}' পাওয়া যায়নি। Available: {', '.join(config.MOBILE_BANKING.keys())}")
    config.MOBILE_BANKING[method]['number'] = number
    await db.set_setting(f'mfs_number_{method}', number)
    name = config.MOBILE_BANKING[method]['name']
    await update.message.reply_text(f"✅ {name} নম্বর আপডেট হয়েছে: <b>{number}</b>", parse_mode='HTML')


@_admin_only
async def cmd_set_exc_uid(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Usage: /set_exc_uid binance 837755101"""
    if len(context.args) < 2:
        exchangers = ', '.join(config.EXCHANGERS.keys())
        return await update.message.reply_text(
            f"🏦 <b>Exchanger UID পরিবর্তন</b>\n\n"
            f"ব্যবহার: /set_exc_uid &lt;exchanger&gt; &lt;uid&gt;\n\n"
            f"উদাহরণ: /set_exc_uid binance 837755101\n"
            f"UID খালি করতে: /set_exc_uid binance -\n\n"
            f"Available: {exchangers}",
            parse_mode='HTML'
        )
    exc_key = context.args[0].lower()
    uid_val = context.args[1]
    if exc_key not in config.EXCHANGERS:
        return await update.message.reply_text(f"❌ '{exc_key}' পাওয়া যায়নি।")
    if uid_val == '-':
        uid_val = ''
    config.EXCHANGERS[exc_key]['our_uid'] = uid_val
    await db.set_setting(f'exc_uid_{exc_key}', uid_val)
    name = config.EXCHANGERS[exc_key]['name']
    status = f"<b>{uid_val}</b>" if uid_val else "বন্ধ (hidden from users)"
    await update.message.reply_text(f"✅ {name} UID আপডেট: {status}", parse_mode='HTML')


@_admin_only
async def cmd_set_exc_note(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Usage: /set_exc_note binance bn আমাদের Binance UID-এ USDT পাঠান।"""
    if len(context.args) < 3:
        return await update.message.reply_text(
            f"📝 <b>Exchanger বার্তা পরিবর্তন</b>\n\n"
            f"ব্যবহার: /set_exc_note &lt;exchanger&gt; &lt;bn/en&gt; &lt;বার্তা&gt;\n\n"
            f"উদাহরণ:\n"
            f"/set_exc_note binance bn আমাদের Binance UID-এ USDT পাঠান।\n"
            f"/set_exc_note binance en Send USDT to our Binance UID.",
            parse_mode='HTML'
        )
    exc_key = context.args[0].lower()
    lang_key = context.args[1].lower()
    note = ' '.join(context.args[2:])
    if exc_key not in config.EXCHANGERS:
        return await update.message.reply_text(f"❌ '{exc_key}' পাওয়া যায়নি।")
    if lang_key not in ('bn', 'en'):
        return await update.message.reply_text("❌ ভাষা হতে হবে: bn অথবা en")
    field = f'deposit_note_{lang_key}'
    config.EXCHANGERS[exc_key][field] = note
    await db.set_setting(f'exc_note_{exc_key}_{lang_key}', note)
    name = config.EXCHANGERS[exc_key]['name']
    await update.message.reply_text(f"✅ {name} ({lang_key}) বার্তা আপডেট:\n{note}")


@_admin_only
async def cmd_payment_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """সব payment info একসাথে দেখো"""
    # MFS info
    mfs_text = "📱 <b>MFS নম্বরসমূহ:</b>\n"
    for key, info in config.MOBILE_BANKING.items():
        mfs_text += f"  {info['emoji']} {info['name']}: <code>{info['number']}</code>\n"

    # Exchanger info
    exc_text = "\n🏦 <b>Exchanger UID সমূহ:</b>\n"
    for key, info in config.EXCHANGERS.items():
        uid_val = info.get('our_uid', '')
        status = f"<code>{uid_val}</code>" if uid_val else "❌ বন্ধ"
        exc_text += f"  {info['emoji']} {info['name']}: {status}\n"

    commands = (
        "\n⚙️ <b>Edit Commands:</b>\n"
        "/set_mfs_number bkash 01711223344\n"
        "/set_exc_uid binance 837755101\n"
        "/set_exc_note binance bn [বার্তা]\n"
        "/payment_info — এই তালিকা দেখো"
    )
    await update.message.reply_text(mfs_text + exc_text + commands, parse_mode='HTML')


@_admin_only
async def cmd_restore(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Telegram থেকে .db ফাইল পাঠিয়ে restore করো"""
    msg = update.message
    # reply করা message এ .db file আছে কিনা চেক
    doc = None
    if msg.reply_to_message and msg.reply_to_message.document:
        doc = msg.reply_to_message.document
    elif msg.document:
        doc = msg.document

    if not doc or not doc.file_name.endswith('.db'):
        return await msg.reply_text(
            "❌ ব্যবহার:\n"
            "1. .db backup ফাইলটা bot কে পাঠাও\n"
            "2. সেই ফাইলে reply করে /restore লেখো\n\n"
            "অথবা .db ফাইলের সাথে caption এ /restore লেখো।"
        )

    await msg.reply_text("⏳ Restore হচ্ছে...")
    try:
        import os
        file = await context.bot.get_file(doc.file_id)
        temp_path = f"restore_temp_{doc.file_name}"
        await file.download_to_drive(temp_path)

        # বর্তমান DB backup করো আগে
        from datetime import datetime
        safety_backup = f"pre_restore_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
        await db.safe_backup(safety_backup)

        # Replace করো
        import shutil
        shutil.copy2(temp_path, config.LOCAL_DB)
        os.remove(temp_path)

        await msg.reply_text(
            f"✅ Database restore সফল!\n"
            f"📁 ফাইল: {doc.file_name}\n"
            f"💾 Safety backup: {safety_backup}\n\n"
            f"Bot restart করুন নিশ্চিত হতে।"
        )
    except Exception as e:
        await msg.reply_text(f"❌ Restore ব্যর্থ: {e}")


# ════════════════════════════════════════════════════════════════════════════
#  TOURNAMENT ENHANCED FEATURES
# ════════════════════════════════════════════════════════════════════════════

@_admin_only
async def cmd_announce_tourney(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """টুর্নামেন্ট সুন্দরভাবে announce করো চ্যানেলে।
    Usage: /announce_tourney <tourney_id>"""
    if not context.args:
        return await update.message.reply_text("Usage: /announce_tourney <tourney_id>")
    try:
        tid = int(context.args[0])
        tourney = await db.get_tournament(tid)
        if not tourney:
            return await update.message.reply_text("❌ Tournament পাওয়া যায়নি।")
        players = await db.get_tourney_players(tid)
        joined = len(players)
        slots = tourney['slots']
        remaining = slots - joined

        announcement = (
            f"🏆 <b>eFootball Tournament!</b> 🏆\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"🎮 <b>{tourney['name']}</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"💰 Entry Fee: <b>{tourney['entry_fee']:.0f} TK</b>\n"
            f"🎁 Prize Pool: <b>{tourney['prize_pool']:.0f} TK</b>\n"
            f"👥 Slots: <b>{joined}/{slots}</b> filled\n"
            f"🔥 Remaining: <b>{remaining}</b> spots\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"✅ Join করতে Bot এ যাও → Tournament\n"
            f"⚡ Spots শেষ হওয়ার আগেই join করো!"
        )

        if config.LOBBY_CHANNEL_ID:
            await context.bot.send_message(
                config.LOBBY_CHANNEL_ID,
                announcement,
                parse_mode='HTML'
            )
        await update.message.reply_text(f"✅ Tournament #{tid} announce করা হয়েছে!")
    except Exception as e:
        await update.message.reply_text(f"❌ {e}")


@_admin_only
async def cmd_tourney_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """টুর্নামেন্টের সব players দেখো।
    Usage: /tourney_status <tourney_id>"""
    if not context.args:
        # সব open tournaments দেখাও
        tourneys = await db.get_open_tournaments()
        if not tourneys:
            return await update.message.reply_text("কোনো open tournament নেই।")
        text = "🏆 <b>Open Tournaments:</b>\n\n"
        for t in tourneys:
            players = await db.get_tourney_players(t['id'])
            text += f"#{t['id']} {t['name']} — {len(players)}/{t['slots']} joined\n"
        text += "\nDetails দেখতে: /tourney_status <id>"
        return await update.message.reply_text(text, parse_mode='HTML')

    try:
        tid = int(context.args[0])
        tourney = await db.get_tournament(tid)
        if not tourney:
            return await update.message.reply_text("❌ Tournament পাওয়া যায়নি।")
        players = await db.get_tourney_players(tid)
        active = [p for p in players if p.get('status') == 'ACTIVE']
        eliminated = [p for p in players if p.get('status') == 'ELIMINATED']

        text = (
            f"🏆 <b>{tourney['name']}</b> (#{tid})\n"
            f"Status: {tourney['status']}\n"
            f"💰 {tourney['entry_fee']:.0f} TK entry | 🎁 {tourney['prize_pool']:.0f} TK prize\n"
            f"━━━━━━━━━━━━━━━\n"
        )
        if active:
            text += f"\n✅ <b>Active ({len(active)}):</b>\n"
            for i, p in enumerate(active, 1):
                u = await db.get_user(p['user_id'])
                ign = esc(u.get('ingame_name') if u else str(p['user_id']))
                text += f"  {i}. {ign}\n"
        if eliminated:
            text += f"\n❌ <b>Eliminated ({len(eliminated)}):</b>\n"
            for p in eliminated:
                u = await db.get_user(p['user_id'])
                ign = esc(u.get('ingame_name') if u else str(p['user_id']))
                text += f"  • {ign}\n"

        kb = InlineKeyboardMarkup([[
            InlineKeyboardButton("🎮 Generate Round", callback_data=f"gen_round_{tid}"),
            InlineKeyboardButton("📢 Announce", callback_data=f"announce_t_{tid}"),
        ], [
            InlineKeyboardButton("🔴 Close Tournament", callback_data=f"close_t_{tid}"),
        ]])
        await update.message.reply_text(text, parse_mode='HTML', reply_markup=kb)
    except Exception as e:
        await update.message.reply_text(f"❌ {e}")


@_admin_only
async def cmd_close_tourney(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Tournament registration বন্ধ করে RUNNING করো।
    Usage: /close_tourney <tourney_id>"""
    if not context.args:
        return await update.message.reply_text("Usage: /close_tourney <tourney_id>")
    try:
        tid = int(context.args[0])
        tourney = await db.get_tournament(tid)
        if not tourney:
            return await update.message.reply_text("❌ Tournament পাওয়া যায়নি।")
        players = await db.get_tourney_players(tid)
        if len(players) < 2:
            return await update.message.reply_text("❌ কমপক্ষে ২ জন player লাগবে।")
        await db.update_tournament_status(tid, 'RUNNING')
        # সব players কে notify করো
        for p in players:
            u_lang = await db.get_user_lang(p['user_id'])
            try:
                await context.bot.send_message(
                    p['user_id'],
                    f"🏆 <b>{esc(tourney['name'])}</b> শুরু হতে চলেছে!\n"
                    f"👥 মোট {len(players)} জন player অংশ নিচ্ছে।\n"
                    f"⚔️ Round শুরু হবে শীঘ্রই, প্রস্তুত থাকুন!",
                    parse_mode='HTML'
                )
            except Exception:
                pass
        await update.message.reply_text(
            f"✅ Tournament #{tid} RUNNING!\n"
            f"👥 {len(players)} জন player notify করা হয়েছে।\n"
            f"এখন /generate_round {tid} দিয়ে round শুরু করুন।"
        )
    except Exception as e:
        await update.message.reply_text(f"❌ {e}")


# ════════════════════════════════════════════════════════════════════════════
#  ADMIN MANUAL FIX COMMANDS
# ════════════════════════════════════════════════════════════════════════════

@_admin_only
async def cmd_set_ign(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin user এর ingame name ঠিক করবে।
    Usage: /set_ign <user_id> <new_name>"""
    if len(context.args) < 2:
        return await update.message.reply_text("Usage: /set_ign <user_id> <new_ingame_name>")
    try:
        target_uid = int(context.args[0])
        new_name   = ' '.join(context.args[1:])
        user = await db.get_user(target_uid)
        if not user:
            return await update.message.reply_text("❌ User পাওয়া যায়নি।")
        old_name = user.get('ingame_name', '')
        await db.update_user(target_uid, ingame_name=new_name)
        await update.message.reply_text(
            f"✅ IGN আপডেট!\n"
            f"User: {target_uid}\n"
            f"আগে: {old_name}\n"
            f"এখন: {new_name}"
        )
        try:
            u_lang = await db.get_user_lang(target_uid)
            await context.bot.send_message(
                target_uid,
                f"✅ Admin আপনার Ingame Name আপডেট করেছে:\n<b>{esc(new_name)}</b>",
                parse_mode='HTML'
            )
        except Exception:
            pass
    except Exception as e:
        await update.message.reply_text(f"❌ {e}")


@_admin_only
async def cmd_cancel_match_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin যেকোনো match cancel করবে এবং refund দেবে।
    Usage: /cancel_match_admin <match_id>"""
    if not context.args:
        return await update.message.reply_text("Usage: /cancel_match_admin <match_id>")
    try:
        mid = context.args[0].upper()
        match = await db.get_match(mid)
        if not match:
            return await update.message.reply_text("❌ Match পাওয়া যায়নি।")
        if match['status'] != 'in_progress':
            return await update.message.reply_text(f"❌ Match status: {match['status']} — cancel করা যাবে না।")
        await db.cancel_match_refund(mid)
        for pid in (match['p1_id'], match['p2_id']):
            plang = await db.get_user_lang(pid)
            try:
                await context.bot.send_message(
                    pid,
                    f"⚠️ Admin ম্যাচ #{mid} cancel করেছে। Fee refund হয়েছে।"
                )
                await db.set_state(pid, None)
            except Exception:
                pass
        await update.message.reply_text(f"✅ Match #{mid} cancel করা হয়েছে। উভয় player কে refund দেওয়া হয়েছে।")
    except Exception as e:
        await update.message.reply_text(f"❌ {e}")


@_admin_only
async def cmd_force_win(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin manually winner declare করবে।
    Usage: /force_win <match_id> <winner_user_id>"""
    if len(context.args) < 2:
        return await update.message.reply_text("Usage: /force_win <match_id> <winner_user_id>")
    try:
        mid       = context.args[0].upper()
        winner_id = int(context.args[1])
        match = await db.get_match(mid)
        if not match:
            return await update.message.reply_text("❌ Match পাওয়া যায়নি।")
        if winner_id not in (match['p1_id'], match['p2_id']):
            return await update.message.reply_text("❌ এই user এই match এ নেই।")
        m = await db.resolve_match(mid, winner_id, update.effective_user.id)
        w = await db.get_user(winner_id)
        loser_id = m['p2_id'] if winner_id == m['p1_id'] else m['p1_id']
        prize = m['fee'] * 1.8
        w_lang = await db.get_user_lang(winner_id)
        l_lang = await db.get_user_lang(loser_id)
        try:
            await context.bot.send_message(winner_id, f"🏆 Admin আপনাকে Match #{mid} এর winner declare করেছে!\n💰 Prize: {prize:.0f} TK")
        except Exception:
            pass
        try:
            await context.bot.send_message(loser_id, f"❌ Admin Match #{mid} এ আপনার বিপক্ষে সিদ্ধান্ত দিয়েছে।")
        except Exception:
            pass
        w_ign = esc(w.get('ingame_name') if w else '?')
        await update.message.reply_text(f"✅ Match #{mid} — Winner: {w_ign} ({winner_id})\n💰 Prize: {prize:.0f} TK")
    except Exception as e:
        await update.message.reply_text(f"❌ {e}")


@_admin_only
async def cmd_reset_state(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """User এর stuck state reset করো।
    Usage: /reset_state <user_id>"""
    if not context.args:
        return await update.message.reply_text("Usage: /reset_state <user_id>")
    try:
        target_uid = int(context.args[0])
        await db.set_state(target_uid, None)
        await update.message.reply_text(f"✅ User {target_uid} এর state reset হয়েছে।")
        try:
            u_lang = await db.get_user_lang(target_uid)
            from utils import main_kb
            await context.bot.send_message(
                target_uid,
                "🔄 Admin আপনার session reset করেছে। আবার চেষ্টা করুন।",
                reply_markup=main_kb(u_lang)
            )
        except Exception:
            pass
    except Exception as e:
        await update.message.reply_text(f"❌ {e}")


@_admin_only
async def cmd_set_balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """User এর balance directly set করো।
    Usage: /set_balance <user_id> <amount>"""
    if len(context.args) < 2:
        return await update.message.reply_text("Usage: /set_balance <user_id> <amount>")
    try:
        target_uid = int(context.args[0])
        amount     = float(context.args[1])
        user = await db.get_user(target_uid)
        if not user:
            return await update.message.reply_text("❌ User পাওয়া যায়নি।")
        old_bal = user.get('available_bal', 0)
        diff = amount - old_bal
        await db.adjust_balance(target_uid, diff, 'admin_set', f'Set by admin to {amount}')
        await update.message.reply_text(
            f"✅ Balance set!\nUser: {target_uid}\nআগে: {old_bal:.2f} TK\nএখন: {amount:.2f} TK"
        )
    except Exception as e:
        await update.message.reply_text(f"❌ {e}")


@_admin_only
async def cmd_match_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Match এর বিস্তারিত তথ্য দেখো।
    Usage: /match_info <match_id>"""
    if not context.args:
        return await update.message.reply_text("Usage: /match_info <match_id>")
    try:
        mid = context.args[0].upper()
        match = await db.get_match(mid)
        if not match:
            return await update.message.reply_text("❌ Match পাওয়া যায়নি।")
        p1 = await db.get_user(match['p1_id'])
        p2 = await db.get_user(match['p2_id'])
        p1_ign = p1.get('ingame_name', '?') if p1 else '?'
        p2_ign = p2.get('ingame_name', '?') if p2 else '?'
        text = (
            f"🎮 <b>Match #{mid}</b>\n"
            f"Status: <b>{match['status']}</b>\n"
            f"Fee: {match['fee']} TK\n\n"
            f"P1: {esc(p1_ign)} ({match['p1_id']})\n"
            f"  Screenshot: {'✅' if match.get('p1_screenshot') else '❌'}\n\n"
            f"P2: {esc(p2_ign)} ({match['p2_id']})\n"
            f"  Screenshot: {'✅' if match.get('p2_screenshot') else '❌'}\n\n"
            f"Created: {str(match.get('created_at', ''))[:16]}"
        )
        kb = None
        if match['status'] == 'in_progress':
            kb = InlineKeyboardMarkup([[
                InlineKeyboardButton(f"🏆 {esc(p1_ign)} জিতেছে", callback_data=f"verify_{mid}_{match['p1_id']}"),
                InlineKeyboardButton(f"🏆 {esc(p2_ign)} জিতেছে", callback_data=f"verify_{mid}_{match['p2_id']}"),
            ], [
                InlineKeyboardButton("🔴 Match Cancel + Refund", callback_data=f"admin_cancel_{mid}"),
            ]])
        await update.message.reply_text(text, parse_mode='HTML', reply_markup=kb)
    except Exception as e:
        await update.message.reply_text(f"❌ {e}")


@_admin_only  
async def cmd_admin_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """সব admin commands এর তালিকা"""
    text = (
        "🛠 <b>Admin Commands</b>\n\n"
        "<b>👤 User Management:</b>\n"
        "/userinfo &lt;id&gt; — user তথ্য\n"
        "/set_ign &lt;id&gt; &lt;name&gt; — IGN ঠিক করো\n"
        "/banuser &lt;id&gt; — ban করো\n"
        "/unbanuser &lt;id&gt; — unban করো\n"
        "/reset_state &lt;id&gt; — stuck state fix\n"
        "/addbalance &lt;id&gt; &lt;amount&gt; — balance যোগ\n"
        "/deductbalance &lt;id&gt; &lt;amount&gt; — balance কাটো\n"
        "/set_balance &lt;id&gt; &lt;amount&gt; — balance directly set\n\n"
        "<b>🎮 Match Management:</b>\n"
        "/match_info &lt;mid&gt; — match details\n"
        "/force_win &lt;mid&gt; &lt;uid&gt; — winner declare\n"
        "/cancel_match_admin &lt;mid&gt; — match cancel + refund\n"
        "/pending_results — pending matches\n\n"
        "<b>🏆 Tournament:</b>\n"
        "/create_tourney name|slots|fee|prize\n"
        "/tourney_status &lt;id&gt; — players দেখো\n"
        "/announce_tourney &lt;id&gt; — চ্যানেলে announce\n"
        "/close_tourney &lt;id&gt; — registration বন্ধ\n"
        "/generate_round &lt;id&gt; — round শুরু\n\n"
        "<b>💰 Payment:</b>\n"
        "/payment_info — সব নম্বর/UID দেখো\n"
        "/set_mfs_number bkash 01711...\n"
        "/set_exc_uid binance 837755101\n"
        "/set_exc_note binance bn [বার্তা]\n"
        "/pending_deposits — pending deposits\n"
        "/pending_withdrawals — pending withdrawals\n\n"
        "<b>📢 Communication:</b>\n"
        "/broadcast &lt;msg&gt; — সবাইকে message\n"
        "/message_user &lt;id&gt; &lt;msg&gt; — একজনকে message\n\n"
        "<b>💾 Database:</b>\n"
        "/backup — DB backup Telegram এ পাঠাও\n"
        "/restore — .db ফাইল reply করে restore\n\n"
        "<b>⚙️ Settings:</b>\n"
        "/setdeprate &lt;rate&gt; — deposit rate\n"
        "/setwitrate &lt;rate&gt; — withdrawal rate\n"
        "/setrules — rules set\n"
        "/settutorial — tutorial video set\n"
        "/addmanager &lt;id&gt; — manager যোগ\n"
        "/removemanager &lt;id&gt; — manager সরাও\n"
        "/listmanagers — সব managers\n"
        "/report — daily report"
    )
    await update.message.reply_text(text, parse_mode='HTML')


# ════════════════════════════════════════════════════════════════════════════
#  FREE MODE & BROADCAST
# ════════════════════════════════════════════════════════════════════════════

@_admin_only
async def cmd_free_mode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Free match mode on/off করো — fee ছাড়াই খেলা যাবে।
    Usage: /free_mode on   অথবা   /free_mode off"""
    if not context.args:
        current = await db.get_setting('free_mode') or 'off'
        status = "✅ চালু" if current == 'on' else "❌ বন্ধ"
        return await update.message.reply_text(
            f"🆓 <b>Free Mode</b>: {status}\n\n"
            f"চালু করতে: /free_mode on\n"
            f"বন্ধ করতে: /free_mode off",
            parse_mode='HTML'
        )

    mode = context.args[0].lower()
    if mode not in ('on', 'off'):
        return await update.message.reply_text("❌ on অথবা off লেখো।")

    await db.set_setting('free_mode', mode)
    import config as cfg
    cfg.FREE_MODE = (mode == 'on')

    if mode == 'on':
        msg = (
            "🆓 <b>Free Mode চালু!</b>\n\n"
            "এখন সব user ফ্রিতে match খেলতে পারবে।\n"
            "বন্ধ করতে: /free_mode off"
        )
        # চ্যানেলে announce করো
        announce = (
            "🎉 <b>FREE MODE চালু!</b> 🎉\n\n"
            "এখন কোনো fee ছাড়াই eFootball match খেলো!\n"
            "⚡ Bot এ গিয়ে Play 1v1 চাপো!"
        )
        try:
            from handlers import _broadcast_chats
            for chat_id in _broadcast_chats():
                await context.bot.send_message(chat_id, announce, parse_mode='HTML')
        except Exception:
            pass
    else:
        msg = (
            "💰 <b>Free Mode বন্ধ!</b>\n\n"
            "এখন থেকে আবার fee দিয়ে match খেলতে হবে।"
        )

    await update.message.reply_text(msg, parse_mode='HTML')
