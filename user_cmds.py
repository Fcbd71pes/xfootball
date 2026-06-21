# user_cmds.py
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes
import db
import config
from lang import t
from utils import esc, main_kb, cancel_kb, ensure_user, check_channel


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    obj  = update.effective_user
    args = context.args
    ref  = None

    # চ্যানেল/গ্রুপ থেকে tournament join: /start tjoin_tid
    if args and args[0].startswith('tjoin_'):
        try:
            tid = int(args[0][6:])
            user = await ensure_user(update)
            if not user:
                return
            lang = user.get('lang', 'en')
            uid  = user['user_id']
            MKB  = main_kb(lang)

            if not user.get('is_registered'):
                return await update.message.reply_text("❌ আগে register করুন।", reply_markup=MKB)

            tourney = await db.get_tournament(tid)
            if not tourney or tourney['status'] != 'OPEN':
                return await update.message.reply_text("❌ Tournament আর open নেই।", reply_markup=MKB)

            players = await db.get_tourney_players(tid)
            if len(players) >= tourney['slots']:
                return await update.message.reply_text("❌ Tournament full হয়ে গেছে!", reply_markup=MKB)

            if user['available_bal'] < tourney['entry_fee']:
                return await update.message.reply_text(t('insufficient_bal', lang), reply_markup=MKB)

            ok = await db.join_tournament(tid, uid, tourney['entry_fee'])
            if ok:
                new_count = len(players) + 1
                remaining = tourney['slots'] - new_count
                await update.message.reply_text(
                    f"✅ <b>{esc(tourney['name'])}</b> এ join হয়েছে!\n"
                    f"👥 {new_count}/{tourney['slots']} joined | 🎁 Prize: {tourney['prize_pool']:.0f} TK",
                    parse_mode='HTML', reply_markup=MKB
                )
                # channel/group এ notify
                from handlers import _broadcast_chats
                u_ign = esc(user.get('ingame_name', '?'))
                for chat_id in _broadcast_chats():
                    try:
                        new_kb = InlineKeyboardMarkup([[
                            InlineKeyboardButton(
                                f"{'🔴 FULL' if remaining <= 0 else '🟢 Join করো'} ({new_count}/{tourney['slots']}){'' if remaining <= 0 else f' — {remaining} বাকি'}",
                                url=f"https://t.me/{config.BOT_USERNAME}?start=tjoin_{tid}" if remaining > 0 else None,
                                callback_data='none' if remaining <= 0 else None
                            )
                        ]])
                        await context.bot.send_message(
                            chat_id,
                            f"🏆 <b>{esc(tourney['name'])}</b>\n✅ <b>{u_ign}</b> join করেছে!\n👥 {new_count}/{tourney['slots']}",
                            parse_mode='HTML'
                        )
                    except Exception:
                        pass
            else:
                await update.message.reply_text("❌ আপনি ইতিমধ্যে join করেছেন!", reply_markup=MKB)
            return
        except (ValueError, IndexError):
            pass
    if args and args[0].startswith('join_'):
        parts = args[0].split('_')
        if len(parts) == 3:
            try:
                searcher_uid = int(parts[1])
                fee          = float(parts[2])
                user = await ensure_user(update)
                if not user:
                    return
                joiner_uid = user['user_id']
                lang = user.get('lang', 'en')
                MKB  = main_kb(lang)

                if joiner_uid == searcher_uid:
                    return await update.message.reply_text("❌ নিজের match এ join করা যাবে না!", reply_markup=MKB)
                if not user.get('is_registered'):
                    return await update.message.reply_text("❌ আগে register করুন।", reply_markup=MKB)
                if fee > 0 and user['available_bal'] < fee:
                    return await update.message.reply_text(t('insufficient_bal', lang), reply_markup=MKB)

                entry = await db.get_from_queue(searcher_uid)
                if not entry:
                    return await update.message.reply_text("❌ এই match আর available নেই।", reply_markup=MKB)

                # Match তৈরি করো
                await db.remove_from_queue(searcher_uid)
                final_fee = min(fee, entry['fee'])
                match_id  = await db.create_match(searcher_uid, joiner_uid, final_fee)

                # Lobby messages মুছো
                try:
                    await context.bot.delete_message(config.LOBBY_CHANNEL_ID, entry['lobby_msg_id'])
                except Exception:
                    pass
                try:
                    extra_msgs = json.loads(entry.get('extra_data') or '[]')
                    for cid, mid in extra_msgs:
                        try:
                            await context.bot.delete_message(cid, mid)
                        except Exception:
                            pass
                except Exception:
                    pass

                # উভয়কে notify করো
                p1 = await db.get_user(searcher_uid)
                p1_lang = p1.get('lang', 'en') if p1 else 'en'
                p2_lang = lang
                p1_ign  = esc(p1.get('ingame_name', '?') if p1 else '?')
                p2_ign  = esc(user.get('ingame_name', '?'))

                fee_text = f"\n💰 Fee: <b>{final_fee:.0f} TK</b>"
                await context.bot.send_message(
                    searcher_uid,
                    t('match_found_p1', p1_lang, opp=p2_ign) + fee_text,
                    parse_mode='HTML', reply_markup=cancel_kb(p1_lang)
                )
                await db.set_state(searcher_uid, 'awaiting_room_code', match_id)

                await update.message.reply_text(
                    t('match_found_p2', p2_lang, opp=p1_ign) + fee_text,
                    parse_mode='HTML', reply_markup=MKB
                )

                # চ্যানেলে notification
                from handlers import _broadcast_chats
                for chat_id in _broadcast_chats():
                    try:
                        await context.bot.send_message(
                            chat_id,
                            f"⚔️ <b>ম্যাচ শুরু!</b>\n🎮 <b>{p1_ign}</b> vs <b>{p2_ign}</b>\n💰 Fee: <b>{final_fee:.0f} TK</b>",
                            parse_mode='HTML'
                        )
                    except Exception:
                        pass
                return
            except (ValueError, IndexError):
                pass

    if args and args[0].startswith('ref_'):
        try:
            ref = int(args[0][4:])
        except ValueError:
            pass
    user = await ensure_user(update, ref)
    if not user:
        return await update.message.reply_text("❌ Account banned.")
    lang = user.get('lang', 'en')
    if not await check_channel(update, context, lang):
        return

    if user.get('is_registered'):
        await update.message.reply_text(t('welcome_back', lang), reply_markup=main_kb(lang))
    else:
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("🇧🇩 বাংলা",   callback_data="setlang_bn"),
             InlineKeyboardButton("🇬🇧 English", callback_data="setlang_en")],
        ])
        await update.message.reply_text(t('choose_lang', 'en'), reply_markup=kb)
        await db.set_state(user['user_id'], 'awaiting_ign')


async def cmd_wallet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = await ensure_user(update)
    if not user:
        return
    lang  = user.get('lang', 'en')
    avail = user.get('available_bal', 0)
    locked = user.get('locked_bal', 0)
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ Deposit",  callback_data='deposit'),
         InlineKeyboardButton("➖ Withdraw", callback_data='withdraw')],
    ])
    await update.effective_message.reply_text(
        t('wallet_text', lang, avail=avail, locked=locked, total=avail + locked),
        reply_markup=kb
    )


async def cmd_play(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = await ensure_user(update)
    if not user or not user.get('is_registered'):
        lang = (user or {}).get('lang', 'en')
        return await update.effective_message.reply_text(t('register_first', lang))
    lang = user.get('lang', 'en')
    rate = await db.deposit_rate()

    def label(fee):
        return f"{fee} TK"

    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton(label(f), callback_data=f"play_fee_{f}") for f in [20, 30, 50]],
        [InlineKeyboardButton(label(f), callback_data=f"play_fee_{f}") for f in [100, 200, 500]],
    ])
    await update.effective_message.reply_text(t('match_select_fee', lang), reply_markup=kb)


async def cmd_result(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = await ensure_user(update)
    if not user:
        return
    lang = user.get('lang', 'en')
    uid  = user['user_id']

    if context.args:
        match = await db.get_match(context.args[0].upper())
        if not match or uid not in (match['p1_id'], match['p2_id']):
            return await update.message.reply_text(t('no_active_match', lang))
    else:
        match = await db.get_active_match(uid)
        if not match:
            return await update.message.reply_text(t('no_active_match', lang))

    if match['status'] != 'in_progress':
        return await update.message.reply_text(t('match_not_active', lang))

    submitted = (uid == match['p1_id'] and match.get('p1_screenshot')) or \
                (uid == match['p2_id'] and match.get('p2_screenshot'))
    if submitted:
        return await update.message.reply_text(t('already_submitted', lang))

    await db.set_state(uid, 'awaiting_screenshot', match['match_id'])
    await update.message.reply_text(
        t('ss_ask', lang, mid=match['match_id']),
        reply_markup=cancel_kb(lang)
    )


async def cmd_cancel_match(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = await ensure_user(update)
    if not user:
        return
    lang  = user.get('lang', 'en')
    uid   = user['user_id']
    match = await db.get_active_match(uid)
    if not match:
        return await update.message.reply_text(t('no_active_match', lang))

    mid       = match['match_id']
    opp_id    = match['p2_id'] if uid == match['p1_id'] else match['p1_id']
    cancel_req = await db.get_cancel_req(mid)

    if cancel_req:
        if cancel_req['requested_by'] == uid:
            return await update.message.reply_text(t('cancel_already', lang))
        await db.agree_cancel(mid, uid)
        opp_lang = await db.get_user_lang(opp_id)
        try:
            await context.bot.send_message(opp_id, t('match_cancelled_ok', opp_lang))
        except Exception:
            pass
        return await update.message.reply_text(t('match_cancelled_ok', lang), reply_markup=main_kb(lang))

    await db.create_cancel_req(mid, uid)
    opp_lang = await db.get_user_lang(opp_id)
    try:
        await context.bot.send_message(opp_id, t('cancel_opp_notify', opp_lang))
    except Exception:
        pass
    await update.message.reply_text(t('cancel_req_sent', lang))


async def cmd_profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = await ensure_user(update)
    if not user:
        return
    lang   = user.get('lang', 'en')
    wins   = user.get('wins', 0)
    losses = user.get('losses', 0)
    await update.effective_message.reply_text(
        t('profile_text', lang,
          ign=esc(user.get('ingame_name')),
          phone=esc(user.get('phone')),
          avail=user.get('available_bal', 0),
          locked=user.get('locked_bal', 0),
          elo=user.get('elo', 1000),
          wins=wins, losses=losses,
          joined=str(user.get('created_at', ''))[:10])
    )


async def cmd_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = await ensure_user(update)
    if not user:
        return
    lang   = user.get('lang', 'en')
    wins   = user.get('wins', 0)
    losses = user.get('losses', 0)
    total  = wins + losses
    wr     = (wins / total * 100) if total > 0 else 0
    await update.message.reply_text(
        t('stats_text', lang, wins=wins, losses=losses, total=total, wr=wr, elo=user.get('elo', 1000))
    )


async def cmd_mymatches(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = await ensure_user(update)
    if not user:
        return
    lang = user.get('lang', 'en')
    uid  = user['user_id']
    history = await db.get_match_history(uid)
    if not history:
        return await update.message.reply_text(t('no_history', lang))
    text = t('history_title', lang)
    for m in history:
        won     = m.get('winner_id') == uid
        opp_ign = m['p2_ign'] if uid == m['p1_id'] else m['p1_ign']
        result  = "🏆" if won else "❌"
        text   += f"{result} vs {esc(opp_ign)} | {m['fee']:.0f} TK | {str(m['created_at'])[:10]}\n"
    await update.message.reply_text(text)


async def cmd_leaderboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = await ensure_user(update)
    if not user:
        return
    lang = user.get('lang', 'en')
    rows = await db.get_top_elo()
    text = t('lb_title', lang)
    for i, r in enumerate(rows, 1):
        text += f"{i}. {esc(r['ingame_name'])} — ⭐ {r['elo']}\n"
    await update.effective_message.reply_text(text, parse_mode='HTML')


async def cmd_share(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = await ensure_user(update)
    if not user:
        return
    lang = user.get('lang', 'en')
    uid  = user['user_id']
    link = f"https://t.me/{config.BOT_USERNAME}?start=ref_{uid}"
    await update.effective_message.reply_text(
        t('referral_text', lang, link=link, bonus=config.REFERRAL_BONUS)
    )


async def cmd_tournaments(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = await ensure_user(update)
    if not user:
        return
    lang     = user.get('lang', 'en')
    uid      = user['user_id']
    tourneys = await db.get_open_tournaments()
    if not tourneys:
        return await update.effective_message.reply_text(t('tourney_none', lang))
    for tk in tourneys:
        players  = await db.get_tourney_players(tk['id'])
        joined   = len(players)
        is_in    = any(p['user_id'] == uid for p in players)
        text     = (
            f"🏆 <b>{esc(tk['name'])}</b>\n"
            f"💰 Entry: {tk['entry_fee']:.0f} TK\n"
            f"🎁 Prize: {tk['prize_pool']:.0f} TK\n"
            f"👥 {joined}/{tk['slots']}"
        )
        kb_rows = []
        if is_in:
            kb_rows.append([InlineKeyboardButton("✅ Joined", callback_data="none")])
        elif tk['status'] == 'OPEN' and joined < tk['slots']:
            kb_rows.append([InlineKeyboardButton("⚔️ Join", url=f"https://t.me/{config.BOT_USERNAME}?start=tjoin_{tk['id']}")])
        else:
            kb_rows.append([InlineKeyboardButton("🚫 Full", callback_data="none")])
        await update.effective_message.reply_text(
            text, parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup(kb_rows) if kb_rows else None
        )


async def cmd_support(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = await ensure_user(update)
    if not user:
        return
    lang = user.get('lang', 'en')
    uid  = user['user_id']
    if not context.args:
        return await update.message.reply_text(t('support_help', lang))
    subject   = ' '.join(context.args)
    ticket_id = await db.create_ticket(uid, subject)
    await db.add_ticket_msg(ticket_id, uid, 'user', subject)
    from utils import staff_ids
    for aid in staff_ids():
        try:
            await context.bot.send_message(
                aid,
                f"🎫 Ticket #{ticket_id}\n"
                f"👤 {esc(user.get('ingame_name'))} ({uid})\n"
                f"📝 {esc(subject)}\n\n"
                f"Reply: /treply {ticket_id} <message>"
            )
        except Exception:
            pass
    await update.message.reply_text(t('ticket_opened', lang, id=ticket_id))


async def cmd_mytickets(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = await ensure_user(update)
    if not user:
        return
    lang    = user.get('lang', 'en')
    tickets = await db.get_user_tickets(user['user_id'])
    if not tickets:
        return await update.message.reply_text(t('no_tickets', lang))
    text = ''
    for tk in tickets:
        status_e = "🟢" if tk['status'] == 'OPEN' else "⚫"
        msgs     = await db.get_ticket_msgs(tk['id'])
        last_msg = msgs[-1]['message'] if msgs else tk['subject']
        who      = "Admin" if (msgs and msgs[-1]['role'] == 'admin') else ("You" if lang == 'en' else "আপনি")
        text    += f"{status_e} #{tk['id']}: {esc(str(tk['subject'])[:40])}\n   {who}: {esc(str(last_msg)[:50])}\n\n"
    await update.message.reply_text(text or t('no_tickets', lang))


async def cmd_treply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """User reply to a ticket (also used by admin — role determined by is_staff)."""
    user = await ensure_user(update)
    if not user:
        return
    lang = user.get('lang', 'en')
    uid  = user['user_id']
    if not context.args or len(context.args) < 2:
        return await update.message.reply_text("/treply <ticket_id> <message>")
    try:
        tid = int(context.args[0])
        msg = ' '.join(context.args[1:])
    except ValueError:
        return await update.message.reply_text("❌ Invalid ticket ID.")
    ticket = await db.get_ticket(tid)
    if not ticket:
        return await update.message.reply_text("❌ Ticket not found.")

    from utils import staff_ids
    is_staff = uid in staff_ids()
    if not is_staff and ticket['user_id'] != uid:
        return await update.message.reply_text(t('no_permission', lang))

    role = 'admin' if is_staff else 'user'
    await db.add_ticket_msg(tid, uid, role, msg)

    if is_staff:
        # Notify user
        u_lang = await db.get_user_lang(ticket['user_id'])
        try:
            await context.bot.send_message(
                ticket['user_id'],
                t('ticket_reply_recv', u_lang, id=tid, msg=esc(msg))
            )
        except Exception:
            pass
        await update.message.reply_text(t('ticket_sent', lang))
    else:
        # Notify staff
        for aid in staff_ids():
            try:
                await context.bot.send_message(
                    aid,
                    f"💬 Ticket #{tid} — {esc(user.get('ingame_name'))}: {esc(msg)}\n"
                    f"Reply: /treply {tid} <message>"
                )
            except Exception:
                pass
        await update.message.reply_text(t('ticket_sent', lang))


async def cmd_closeticket(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = await ensure_user(update)
    if not user:
        return
    lang = user.get('lang', 'en')
    if not context.args:
        return await update.message.reply_text("/closeticket <ticket_id>")
    try:
        tid = int(context.args[0])
    except ValueError:
        return await update.message.reply_text("❌ Invalid ID.")
    ticket = await db.get_ticket(tid)
    if not ticket:
        return await update.message.reply_text("❌ Not found.")
    from utils import staff_ids
    if user['user_id'] not in staff_ids() and ticket['user_id'] != user['user_id']:
        return await update.message.reply_text(t('no_permission', lang))
    await db.close_ticket(tid)
    await update.message.reply_text(t('ticket_closed', lang, id=tid))


async def cmd_language(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = await ensure_user(update)
    if not user:
        return
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🇧🇩 বাংলা",   callback_data="setlang_bn"),
         InlineKeyboardButton("🇬🇧 English", callback_data="setlang_en")],
    ])
    await update.effective_message.reply_text(t('choose_lang', 'en'), reply_markup=kb)


async def cmd_withdraw_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = await ensure_user(update)
    if not user:
        return
    lang  = user.get('lang', 'en')
    uid   = user['user_id']
    mfs_w = await db.get_pending_mfs_withdrawals()
    exc_w = await db.get_pending_exc_withdrawals()
    mine  = [w for w in (mfs_w + exc_w) if w['user_id'] == uid]
    if not mine:
        msg = "No pending withdrawals." if lang == 'en' else "কোনো পেন্ডিং উইথড্র নেই।"
    else:
        msg = ("Pending withdrawals:\n\n" if lang == 'en' else "পেন্ডিং উইথড্র:\n\n")
        for w in mine:
            amt = w.get('amount') or w.get('amount_tk', 0)
            msg += f"#{w['id']} | {amt:.2f} TK | {w['status']}\n"
    await update.message.reply_text(msg)

async def cmd_tutorial(update, context):
    from utils import ensure_user
    from lang import t
    import db
    user = await ensure_user(update)
    if not user: return
    lang = user.get('lang', 'en')
    text = t('tutorial_text', lang)
    
    # ডাটাবেজ থেকে ভিডিও আইডি নেওয়া
    video_id = await db.get_setting('tutorial_video_id')
    
    if video_id:
        try:
            await context.bot.send_video(
                chat_id=update.effective_chat.id, 
                video=video_id, 
                caption=text, 
                parse_mode='HTML'
            )
            return
        except Exception as e:
            pass # ভিডিও পাঠাতে সমস্যা হলে শুধু টেক্সট পাঠাবে
            
    await update.message.reply_text(text, parse_mode='HTML')

async def cmd_daily(update, context):
    from utils import ensure_user
    from lang import t
    user = await ensure_user(update)
    if not user: return
    lang = user.get('lang', 'en')
    uid = user['user_id']
    import datetime
    today = datetime.datetime.now().strftime('%Y-%m-%d')
    last_daily = user.get('last_daily')
    if last_daily == today:
        return await update.message.reply_text(t('daily_already', lang))
    
    success = await db.claim_daily_bonus(uid, 2.0, today)
    if not success:
        return await update.message.reply_text(t('daily_already', lang))
        
    await update.message.reply_text(t('daily_claimed', lang, amount=2))


async def cmd_edit_profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """User নিজের ingame name ও phone edit করতে পারবে"""
    user = await ensure_user(update)
    if not user:
        return
    lang = user.get('lang', 'en')
    uid  = user['user_id']
    MKB  = main_kb(lang)

    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("✏️ Ingame Name পরিবর্তন", callback_data='edit_ign')],
        [InlineKeyboardButton("📱 Phone পরিবর্তন",       callback_data='edit_phone')],
    ])
    await update.effective_message.reply_text(
        f"✏️ <b>Profile Edit</b>\n\n"
        f"বর্তমান নাম: <b>{esc(user.get('ingame_name', '?'))}</b>\n"
        f"Phone: <code>{esc(user.get('phone', '?'))}</code>\n\n"
        f"কী পরিবর্তন করতে চাও?",
        parse_mode='HTML',
        reply_markup=kb
    )
