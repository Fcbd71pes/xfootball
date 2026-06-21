# handlers.py
import json
import logging
import aiosqlite
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes
import db
import config
from lang import t
from utils import esc, main_kb, cancel_kb, ensure_user, staff_ids

logger = logging.getLogger(__name__)


# ════════════════════════════════════════════════════════════════════════════
#  TEXT HANDLER
# ════════════════════════════════════════════════════════════════════════════

async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = await ensure_user(update)
    if not user:
        return
    txt   = update.message.text.strip()
    state = user.get('state')
    sd    = user.get('state_data')
    lang  = user.get('lang', 'en')
    uid   = user['user_id']
    MKB   = main_kb(lang)
    CKB   = cancel_kb(lang)

    # ── Cancel ───────────────────────────────────────
    cancel_words = {t('btn_cancel', 'bn'), t('btn_cancel', 'en'), '❌ Cancel', '❌ বাতিল'}
    if txt in cancel_words:
        # if in queue, remove and refund
        q = await db.get_from_queue(uid)
        if q:
            await db.remove_from_queue(uid)
            try:
                await context.bot.delete_message(config.LOBBY_CHANNEL_ID, q['lobby_msg_id'])
            except Exception:
                pass
        await db.set_state(uid, None)
        return await update.message.reply_text(t('cancelled', lang), reply_markup=MKB)

    # ── Registration: IGN ─────────────────────────────
    if state == 'awaiting_ign':
        await db.update_user(uid, ingame_name=txt)
        await db.set_state(uid, 'awaiting_phone')
        return await update.message.reply_text(t('ask_phone', lang), reply_markup=CKB)

    # ── Registration: Phone ───────────────────────────
    if state == 'awaiting_phone':
        await db.update_user(uid, phone=txt, is_registered=1)
        if not user.get('welcome_given'):
            await db.update_user(uid, welcome_given=1)
        msg = t('reg_done', lang)
        await db.set_state(uid, None)
        await update.message.reply_text(msg, reply_markup=MKB)
        return

    # ── Room Code ─────────────────────────────────────
    if state == 'awaiting_room_code':
        match_id = sd
        match = await db.get_match(match_id)
        if match:
            opp_id   = match['p2_id'] if uid == match['p1_id'] else match['p1_id']
            opp_lang = await db.get_user_lang(opp_id)
            mins     = config.MATCH_TIMEOUT_MINUTES
            try:
                await context.bot.send_message(
                    opp_id,
                    t('room_code_fwd', opp_lang, code=esc(txt), mins=mins),
                    parse_mode='HTML',
                    reply_markup=main_kb(opp_lang)
                )
            except Exception:
                pass
            await update.message.reply_text(
                t('room_code_confirm', lang, mins=mins), reply_markup=MKB
            )
            # Schedule match jobs
            _schedule_match_jobs(context, match_id)
        await db.set_state(uid, None)
        return

    # ── MFS Deposit: TxID + Amount ────────────────────
    if state == 'awaiting_mfs_dep_txid':
        data = json.loads(sd or '{}')
        parts = txt.split()
        if len(parts) != 2:
            return await update.message.reply_text(t('mfs_wrong_fmt', lang), parse_mode='HTML', reply_markup=CKB)
        txid, amount_str = parts[0], parts[1]
        try:
            amount = float(amount_str)
        except ValueError:
            return await update.message.reply_text(t('mfs_wrong_fmt', lang), parse_mode='HTML', reply_markup=CKB)
        if amount < config.MINIMUM_DEPOSIT:
            return await update.message.reply_text(t('mfs_min_dep', lang, min=config.MINIMUM_DEPOSIT), reply_markup=CKB)
        data.update({'txid': txid, 'amount': amount})
        await db.set_state(uid, 'awaiting_mfs_dep_screenshot', json.dumps(data))
        return await update.message.reply_text(t('mfs_send_ss', lang), reply_markup=CKB)

    # ── MFS Withdrawal: Amount ────────────────────────
    if state == 'awaiting_mfs_wit_amount':
        data = json.loads(sd or '{}')
        try:
            amount = float(txt)
        except ValueError:
            return await update.message.reply_text(t('invalid_number', lang), reply_markup=CKB)
        if amount < config.MINIMUM_WITHDRAWAL:
            return await update.message.reply_text(t('wit_min', lang, min=config.MINIMUM_WITHDRAWAL), reply_markup=CKB)
        if amount > user['available_bal']:
            return await update.message.reply_text(t('insufficient_bal', lang), reply_markup=CKB)
        data['amount'] = amount
        method = data.get('method', '')
        await db.set_state(uid, 'awaiting_mfs_wit_account', json.dumps(data))
        return await update.message.reply_text(t('wit_ask_account', lang, method=method.upper()), reply_markup=CKB)

    # ── MFS Withdrawal: Account ───────────────────────
    if state == 'awaiting_mfs_wit_account':
        data   = json.loads(sd or '{}')
        amount = data['amount']
        method = data.get('method', '')
        req_id = await db.create_mfs_withdrawal(uid, method, txt, amount)
        await db.set_state(uid, None)
        await update.message.reply_text(
            t('wit_submitted', lang, amount=f"{amount:.2f} TK"), reply_markup=MKB
        )
        info = config.MOBILE_BANKING.get(method, {})
        admin_text = (
            f"💸 MFS Withdrawal #{req_id}\n"
            f"👤 {esc(user.get('ingame_name'))} ({uid})\n"
            f"📱 {info.get('name', method)}: {txt}\n"
            f"💰 {amount:.2f} TK\n\n"
            f"✅ /wit_approve_mfs {req_id}   ❌ /wit_reject_mfs {req_id}"
        )
        kb = InlineKeyboardMarkup([[
            InlineKeyboardButton(f"✅ Approve #{req_id}", callback_data=f"mwit_approve_{req_id}"),
            InlineKeyboardButton(f"❌ Reject #{req_id}",  callback_data=f"mwit_reject_{req_id}"),
        ]])
        for aid in staff_ids():
            try:
                await context.bot.send_message(aid, admin_text, reply_markup=kb)
            except Exception:
                pass
        return

    # ── Exchange Deposit: Amount ──────────────────────
    if state == 'awaiting_exc_dep_amount':
        data = json.loads(sd or '{}')
        try:
            usdt = float(txt)
        except ValueError:
            return await update.message.reply_text(t('invalid_number', lang), reply_markup=CKB)
        if usdt < config.MIN_USDT_DEPOSIT:
            return await update.message.reply_text(t('exc_min_usdt', lang, min=config.MIN_USDT_DEPOSIT), reply_markup=CKB)
        rate = await db.deposit_rate()
        data.update({'amount_usdt': usdt, 'amount_tk': round(usdt * rate, 2)})
        exc_key   = data.get('exchanger', '')
        info      = config.EXCHANGERS.get(exc_key, {})
        uid_label = info.get('uid_label', 'UID')
        await db.set_state(uid, 'awaiting_exc_dep_uid', json.dumps(data))
        return await update.message.reply_text(t('exc_ask_uid', lang, uid_label=uid_label), reply_markup=CKB)

    # ── Exchange Deposit: User UID ────────────────────
    if state == 'awaiting_exc_dep_uid':
        data = json.loads(sd or '{}')
        data['user_uid'] = txt.strip()
        await db.set_state(uid, 'awaiting_exc_dep_screenshot', json.dumps(data))
        return await update.message.reply_text(t('exc_ask_ss', lang), reply_markup=CKB)

    # ── Exchange Withdrawal: Amount ───────────────────
    if state == 'awaiting_exc_wit_amount':
        data = json.loads(sd or '{}')
        try:
            usdt = float(txt)
        except ValueError:
            return await update.message.reply_text(t('invalid_number', lang), reply_markup=CKB)
        if usdt < config.MIN_USDT_WITHDRAWAL:
            return await update.message.reply_text(t('wit_min_usdt', lang, min=config.MIN_USDT_WITHDRAWAL), reply_markup=CKB)
        rate     = await db.withdraw_rate()
        amount_tk = round(usdt * rate, 2)
        if amount_tk > user['available_bal']:
            return await update.message.reply_text(t('insufficient_bal', lang), reply_markup=CKB)
        exc_key  = data.get('exchanger', '')
        info     = config.EXCHANGERS.get(exc_key, {})
        uid_label = info.get('uid_label', 'UID')
        data.update({'amount_usdt': usdt, 'amount_tk': amount_tk})
        await db.set_state(uid, 'awaiting_exc_wit_uid', json.dumps(data))
        return await update.message.reply_text(t('wit_ask_account', lang, method=uid_label), reply_markup=CKB)

    # ── Exchange Withdrawal: User UID ─────────────────
    if state == 'awaiting_exc_wit_uid':
        data      = json.loads(sd or '{}')
        user_uid  = txt.strip()
        exc_key   = data.get('exchanger', '')
        info      = config.EXCHANGERS.get(exc_key, {})
        amount_usdt = data['amount_usdt']
        amount_tk   = data['amount_tk']
        req_id = await db.create_exc_withdrawal(uid, exc_key, user_uid, amount_usdt, amount_tk)
        await db.set_state(uid, None)
        await update.message.reply_text(
            t('wit_submitted', lang, amount=f"{amount_usdt:.4f} USDT ({amount_tk:.2f} TK)"),
            reply_markup=MKB
        )
        our_uid = info.get('our_uid', '?')
        admin_text = (
            f"💸 Exchange Withdrawal #{req_id}\n"
            f"👤 {esc(user.get('ingame_name'))} ({uid})\n"
            f"🏦 {info.get('name', exc_key)}\n"
            f"💵 {amount_usdt:.4f} USDT = {amount_tk:.2f} TK\n"
            f"📤 Their UID: {user_uid}\n"
            f"📥 Our UID: {our_uid}"
        )
        kb = InlineKeyboardMarkup([[
            InlineKeyboardButton(f"✅ Approve #{req_id}", callback_data=f"ewit_approve_{req_id}"),
            InlineKeyboardButton(f"❌ Reject #{req_id}",  callback_data=f"ewit_reject_{req_id}"),
        ]])
        for aid in staff_ids():
            try:
                await context.bot.send_message(aid, admin_text, reply_markup=kb)
            except Exception:
                pass
        return

    # ── Menu buttons ──────────────────────────────────
    from user_cmds import (cmd_wallet, cmd_profile, cmd_play,
                           cmd_leaderboard, cmd_share, cmd_tournaments,
                           cmd_language)
    play_btns = {t('btn_play', 'bn'), t('btn_play', 'en')}
    if txt in play_btns:
        return await cmd_play(update, context)
    wallet_btns = {t('btn_wallet', 'bn'), t('btn_wallet', 'en')}
    if txt in wallet_btns:
        return await cmd_wallet(update, context)
    profile_btns = {t('btn_profile', 'bn'), t('btn_profile', 'en')}
    if txt in profile_btns:
        return await cmd_profile(update, context)
    lb_btns = {t('btn_lb', 'bn'), t('btn_lb', 'en')}
    if txt in lb_btns:
        return await cmd_leaderboard(update, context)
    share_btns = {t('btn_share', 'bn'), t('btn_share', 'en')}
    if txt in share_btns:
        return await cmd_share(update, context)
    tourney_btns = {t('btn_tourney', 'bn'), t('btn_tourney', 'en')}
    if txt in tourney_btns:
        return await cmd_tournaments(update, context)
    lang_btns = {t('btn_lang', 'bn'), t('btn_lang', 'en')}
    if txt in lang_btns:
        return await cmd_language(update, context)
    rules_btns = {t('btn_rules', 'bn'), t('btn_rules', 'en')}
    if txt in rules_btns:
        rules = await db.get_setting('rules_text')
        return await update.message.reply_text(
            rules or ('No rules set.' if lang == 'en' else 'নিয়মাবলী সেট করা নেই।')
        )

    await update.message.reply_text(t('use_menu', lang), reply_markup=MKB)


# ════════════════════════════════════════════════════════════════════════════
#  PHOTO HANDLER
# ════════════════════════════════════════════════════════════════════════════

async def photo_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = await ensure_user(update)
    if not user:
        return
    state = user.get('state')
    sd    = user.get('state_data')
    lang  = user.get('lang', 'en')
    uid   = user['user_id']
    MKB   = main_kb(lang)
    file_id = update.message.photo[-1].file_id

    # ── Match screenshot ──────────────────────────────
    if state == 'awaiting_screenshot':
        match_id = sd
        match = await db.get_match(match_id)
        if not match or match['status'] != 'in_progress':
            return await update.message.reply_text(t('match_not_active', lang), reply_markup=MKB)
        if (uid == match['p1_id'] and match.get('p1_screenshot')) or \
           (uid == match['p2_id'] and match.get('p2_screenshot')):
            return await update.message.reply_text(t('already_submitted', lang), reply_markup=MKB)

        updated = await db.submit_screenshot(match_id, uid, file_id)
        await db.set_state(uid, None)
        await update.message.reply_text(t('ss_received', lang), reply_markup=MKB)

        opp_id = match['p2_id'] if uid == match['p1_id'] else match['p1_id']
        opp_lang = await db.get_user_lang(opp_id)
        try:
            await context.bot.send_message(opp_id, t('opp_submitted', opp_lang))
        except Exception:
            pass

        # Both submitted — send to admins for verification
        if updated.get('p1_screenshot') and updated.get('p2_screenshot'):
            await _send_to_admin_for_verify(context, updated)
        return

    # ── MFS Deposit screenshot ────────────────────────
    if state == 'awaiting_mfs_dep_screenshot':
        data = json.loads(sd or '{}')
        try:
            req_id = await db.create_mfs_deposit(
                uid, data.get('method', ''), data.get('txid', ''),
                data.get('amount', 0), file_id
            )
        except aiosqlite.IntegrityError:
            await db.set_state(uid, None)
            return await update.message.reply_text(
                '❌ TxID already used.' if lang == 'en' else '❌ এই TxID আগেই ব্যবহার হয়েছে।',
                reply_markup=MKB
            )
        await db.set_state(uid, None)
        await update.message.reply_text(t('dep_submitted', lang), reply_markup=MKB)
        info = config.MOBILE_BANKING.get(data.get('method', ''), {})
        caption = (
            f"🆕 MFS Deposit #{req_id}\n"
            f"👤 {esc(user.get('ingame_name'))} ({uid})\n"
            f"📱 {info.get('name', '')} | TxID: {data.get('txid')}\n"
            f"💰 {data.get('amount'):.2f} TK"
        )
        kb = InlineKeyboardMarkup([[
            InlineKeyboardButton(f"✅ Approve #{req_id}", callback_data=f"mdep_approve_{req_id}"),
            InlineKeyboardButton(f"❌ Reject #{req_id}",  callback_data=f"mdep_reject_{req_id}"),
        ]])
        for aid in staff_ids():
            try:
                await context.bot.send_photo(aid, file_id, caption=caption, reply_markup=kb)
            except Exception:
                pass
        return

    # ── Exchange Deposit screenshot ───────────────────
    if state == 'awaiting_exc_dep_screenshot':
        data = json.loads(sd or '{}')
        exc_key    = data.get('exchanger', '')
        info       = config.EXCHANGERS.get(exc_key, {})
        our_uid    = info.get('our_uid', '')
        user_uid   = data.get('user_uid', '')
        amount_usdt = data.get('amount_usdt', 0)
        amount_tk   = data.get('amount_tk', 0)
        req_id = await db.create_exc_deposit(
            uid, exc_key, our_uid, user_uid, amount_usdt, amount_tk, file_id
        )
        await db.set_state(uid, None)
        await update.message.reply_text(
            t('exc_dep_submitted', lang,
              name=info.get('name', exc_key),
              usdt=amount_usdt, bdt=amount_tk, user_uid=user_uid),
            reply_markup=MKB
        )
        caption = (
            f"🆕 Exchange Deposit #{req_id}\n"
            f"👤 {esc(user.get('ingame_name'))} ({uid})\n"
            f"🏦 {info.get('name', exc_key)}\n"
            f"💵 {amount_usdt:.4f} USDT = {amount_tk:.2f} TK\n"
            f"📥 Our UID: {our_uid}\n"
            f"📤 Their UID: {user_uid}"
        )
        kb = InlineKeyboardMarkup([[
            InlineKeyboardButton(f"✅ Approve #{req_id}", callback_data=f"edep_approve_{req_id}"),
            InlineKeyboardButton(f"❌ Reject #{req_id}",  callback_data=f"edep_reject_{req_id}"),
        ]])
        for aid in staff_ids():
            try:
                await context.bot.send_photo(aid, file_id, caption=caption, reply_markup=kb)
            except Exception:
                pass
        return


# ════════════════════════════════════════════════════════════════════════════
#  CALLBACK QUERY HANDLER
# ════════════════════════════════════════════════════════════════════════════

async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q    = update.callback_query
    await q.answer()
    data = q.data
    uid  = q.from_user.id
    lang = await db.get_user_lang(uid)
    user = await db.get_user(uid)
    MKB  = main_kb(lang)
    CKB  = cancel_kb(lang)

    if data == 'none':
        return

    # ── Language set ──────────────────────────────────
    if data.startswith('setlang_'):
        new_lang = data[8:]
        await db.update_user(uid, lang=new_lang)
        await q.message.reply_text(t('lang_set', new_lang), reply_markup=main_kb(new_lang))
        return

    # ── Deposit method ────────────────────────────────
    if data == 'deposit':
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton(t('btn_mfs', lang),      callback_data='dep_mfs')],
            [InlineKeyboardButton(t('btn_exchange', lang), callback_data='dep_exc')],
        ])
        await q.message.reply_text(t('choose_dep_method', lang), reply_markup=kb)
        return

    if data == 'dep_mfs':
        rows = [
            [InlineKeyboardButton(f"{i['emoji']} {i['name']}", callback_data=f"dep_mfs_{k}")]
            for k, i in config.MOBILE_BANKING.items()
        ]
        await q.message.reply_text(t('mfs_select', lang), reply_markup=InlineKeyboardMarkup(rows))
        return

    if data.startswith('dep_mfs_'):
        method = data[8:]
        info   = config.MOBILE_BANKING.get(method, {})
        await db.set_state(uid, 'awaiting_mfs_dep_txid', json.dumps({'method': method}))
        await q.message.reply_text(
            t('mfs_dep_inst', lang, name=info.get('name', ''), number=info.get('number', '')),
            parse_mode='HTML', reply_markup=CKB
        )
        return

    if data == 'dep_exc':
        rows = []
        for k, info in config.EXCHANGERS.items():
            our_uid = info.get('our_uid', '').strip()
            if not our_uid:
                continue
            rows.append([InlineKeyboardButton(
                f"{info['emoji']} {info['name']}",
                callback_data=f"dep_exc_{k}"
            )])
        if not rows:
            await q.message.reply_text(t('exc_none_configured', lang))
            return
        await q.message.reply_text(t('exc_select', lang), reply_markup=InlineKeyboardMarkup(rows))
        return

    if data.startswith('dep_exc_'):
        exc_key = data[8:]
        info    = config.EXCHANGERS.get(exc_key)
        if not info:
            return
        our_uid = info.get('our_uid', '').strip()
        if not our_uid:
            await q.message.reply_text(t('exc_uid_not_set', lang))
            return
        note = info.get(f'deposit_note_{lang}', info.get('deposit_note_en', ''))
        await db.set_state(uid, 'awaiting_exc_dep_amount', json.dumps({'exchanger': exc_key}))
        await q.message.reply_text(
            t('exc_dep_show_uid', lang,
              name=info['name'], uid_label=info.get('uid_label', 'UID'),
              our_uid=our_uid, note=note, min_dep=config.MIN_USDT_DEPOSIT),
            parse_mode='HTML', reply_markup=CKB
        )
        return

    # ── Withdraw method ───────────────────────────────
    if data == 'withdraw':
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton(t('btn_mfs', lang),      callback_data='wit_mfs')],
            [InlineKeyboardButton(t('btn_exchange', lang), callback_data='wit_exc')],
        ])
        await q.message.reply_text(t('choose_wit_method', lang), reply_markup=kb)
        return

    if data == 'wit_mfs':
        rows = [
            [InlineKeyboardButton(f"{i['emoji']} {i['name']}", callback_data=f"wit_mfs_{k}")]
            for k, i in config.MOBILE_BANKING.items()
        ]
        await q.message.reply_text(t('wit_mfs_select', lang), reply_markup=InlineKeyboardMarkup(rows))
        return

    if data.startswith('wit_mfs_'):
        method = data[8:]
        if not user:
            return
        avail = user.get('available_bal', 0)
        await db.set_state(uid, 'awaiting_mfs_wit_amount', json.dumps({'method': method}))
        await q.message.reply_text(
            t('wit_ask_amount_mfs', lang, avail=avail, min=config.MINIMUM_WITHDRAWAL),
            reply_markup=CKB
        )
        return

    if data == 'wit_exc':
        rows = []
        for k, info in config.EXCHANGERS.items():
            our_uid = info.get('our_uid', '').strip()
            if not our_uid:
                continue
            rows.append([InlineKeyboardButton(
                f"{info['emoji']} {info['name']}",
                callback_data=f"wit_exc_{k}"
            )])
        if not rows:
            await q.message.reply_text(t('exc_none_configured', lang))
            return
        await q.message.reply_text(t('wit_exc_select', lang), reply_markup=InlineKeyboardMarkup(rows))
        return

    if data.startswith('wit_exc_'):
        exc_key = data[8:]
        if not user:
            return
        info    = config.EXCHANGERS.get(exc_key, {})
        avail   = user.get('available_bal', 0)
        rate    = await db.withdraw_rate()
        await db.set_state(uid, 'awaiting_exc_wit_amount', json.dumps({'exchanger': exc_key}))
        await q.message.reply_text(
            t('wit_ask_amount_exc', lang,
              avail=avail, usdt_avail=avail / rate, min=config.MIN_USDT_WITHDRAWAL),
            reply_markup=CKB
        )
        return

    # ── Match play ────────────────────────────────────
    if data.startswith('play_fee_'):
        fee  = float(data.split('_')[-1])
        if not user:
            return
        if fee > 0 and user['available_bal'] < fee:
            return await q.message.reply_text(t('insufficient_bal', lang))
        if await db.get_from_queue(uid):
            return await q.message.reply_text(t('already_in_queue', lang))
        opponent = await db.find_opponent(fee, uid)
        if opponent:
            p2_id = opponent['user_id']
            await db.remove_from_queue(p2_id)
            match_id = await db.create_match(uid, p2_id, fee)
            p2 = await db.get_user(p2_id)
            p2_lang = p2.get('lang', 'en') if p2 else 'en'
            try:
                await context.bot.delete_message(config.LOBBY_CHANNEL_ID, opponent['lobby_msg_id'])
            except Exception:
                pass
            await context.bot.send_message(
                uid, t('match_found_p1', lang, opp=esc(p2.get('ingame_name') if p2 else '?')),
                reply_markup=CKB
            )
            await db.set_state(uid, 'awaiting_room_code', match_id)
            await context.bot.send_message(
                p2_id,
                t('match_found_p2', p2_lang, opp=esc(user.get('ingame_name'))),
                reply_markup=main_kb(p2_lang)
            )
            await q.message.edit_text(t('opponent_found_cb', lang))
        else:
            lobby = await context.bot.send_message(
                config.LOBBY_CHANNEL_ID,
                f"🔥 {esc(user.get('ingame_name'))} — {fee} TK"
            )
            await db.add_to_queue(uid, fee, lobby.message_id)
            kb = InlineKeyboardMarkup([[
                InlineKeyboardButton("❌ Cancel", callback_data=f"cancel_search_{uid}")
            ]])
            await q.message.edit_text(t('searching', lang), reply_markup=kb)
        return

    if data.startswith('cancel_search_'):
        target = int(data.split('_')[-1])
        if q.from_user.id != target:
            return await q.answer("Not yours.", show_alert=True)
        entry = await db.get_from_queue(target)
        if entry:
            await db.remove_from_queue(target)
            try:
                await context.bot.delete_message(config.LOBBY_CHANNEL_ID, entry['lobby_msg_id'])
            except Exception:
                pass
        tlang = await db.get_user_lang(target)
        await q.message.edit_text(t('cancelled', tlang))
        return

    # ── Admin: verify match ───────────────────────────
    if data.startswith('verify_'):
        if uid not in staff_ids():
            return
        parts     = data.split('_')
        match_id  = parts[1]
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
        tourney_id = m.get('tourney_id')
        if tourney_id:
            await db.eliminate_player(tourney_id, loser_id)
            active = await db.get_tourney_players(tourney_id, 'ACTIVE')
            if len(active) == 1:
                tourney = await db.get_tournament(tourney_id)
                if tourney:
                    await db.adjust_balance(winner_id, tourney['prize_pool'], 'tourney_prize')
                    await db.update_tournament_status(tourney_id, 'COMPLETED')
                    try:
                        await context.bot.send_message(winner_id, t('tourney_champion', w_lang, prize=tourney['prize_pool']))
                    except Exception:
                        pass
            else:
                try:
                    await context.bot.send_message(winner_id, t('match_won', w_lang, mid=match_id, prize=0))
                except Exception:
                    pass
        else:
            try:
                await context.bot.send_message(winner_id, t('match_won', w_lang, mid=match_id, prize=prize))
            except Exception:
                pass
        try:
            await context.bot.send_message(loser_id, t('match_lost', l_lang, mid=match_id))
        except Exception:
            pass
        try:
            await q.edit_message_caption(
                caption=f"✅ Verified by {esc(q.from_user.first_name)}\nWinner: {esc(w.get('ingame_name') if w else '?')}"
            )
        except Exception:
            pass
        return

    # ── Admin: MFS deposit approve/reject ─────────────
    if data.startswith('mdep_approve_') or data.startswith('mdep_reject_'):
        if uid not in staff_ids():
            return await q.answer("No permission.", show_alert=True)
        dep_id = int(data.split('_')[-1])
        action = 'approve' if 'approve' in data else 'reject'
        if action == 'approve':
            d = await db.approve_mfs_deposit(dep_id)
            if d:
                u_lang = await db.get_user_lang(d['user_id'])
                try:
                    await context.bot.send_message(d['user_id'], t('dep_approved', u_lang, amount=d['amount']))
                except Exception:
                    pass
                await _check_referral_bonus(context, d['user_id'], d['amount'])
        else:
            d = await db.reject_mfs_deposit(dep_id)
            if d:
                u_lang = await db.get_user_lang(d['user_id'])
                try:
                    await context.bot.send_message(d['user_id'], t('dep_rejected', u_lang))
                except Exception:
                    pass
        emoji = "✅" if action == 'approve' else "❌"
        try:
            cap = (q.message.caption or '') + f"\n\n{emoji} {action.upper()} by {esc(q.from_user.first_name)}"
            await q.edit_message_caption(caption=cap)
        except Exception:
            pass
        return

    # ── Admin: Exchange deposit approve/reject ─────────
    if data.startswith('edep_approve_') or data.startswith('edep_reject_'):
        if uid not in staff_ids():
            return await q.answer("No permission.", show_alert=True)
        dep_id = int(data.split('_')[-1])
        action = 'approve' if 'approve' in data else 'reject'
        if action == 'approve':
            d = await db.approve_exc_deposit(dep_id)
            if d:
                info   = config.EXCHANGERS.get(d['exchanger'], {})
                u_lang = await db.get_user_lang(d['user_id'])
                try:
                    await context.bot.send_message(
                        d['user_id'],
                        t('exc_dep_approved', u_lang,
                          name=info.get('name', ''),
                          usdt=d['amount_usdt'], bdt=d['amount_tk'])
                    )
                except Exception:
                    pass
                await _check_referral_bonus(context, d['user_id'], d['amount_tk'])
        else:
            d = await db.reject_exc_deposit(dep_id)
            if d:
                info   = config.EXCHANGERS.get(d['exchanger'], {})
                u_lang = await db.get_user_lang(d['user_id'])
                try:
                    await context.bot.send_message(
                        d['user_id'],
                        t('exc_dep_rejected', u_lang, name=info.get('name', ''))
                    )
                except Exception:
                    pass
        emoji = "✅" if action == 'approve' else "❌"
        try:
            cap = (q.message.caption or '') + f"\n\n{emoji} {action.upper()} by {esc(q.from_user.first_name)}"
            await q.edit_message_caption(caption=cap)
        except Exception:
            pass
        return

    # ── Admin: MFS withdrawal approve/reject ──────────
    if data.startswith('mwit_approve_') or data.startswith('mwit_reject_'):
        if uid not in staff_ids():
            return await q.answer("No permission.", show_alert=True)
        wid    = int(data.split('_')[-1])
        action = 'approve' if 'approve' in data else 'reject'
        if action == 'approve':
            w = await db.approve_mfs_withdrawal(wid)
            if w:
                u_lang = await db.get_user_lang(w['user_id'])
                try:
                    await context.bot.send_message(w['user_id'], t('wit_approved', u_lang, amount=f"{w['amount']:.2f} TK"))
                except Exception:
                    pass
        else:
            w = await db.reject_mfs_withdrawal(wid)
            if w:
                u_lang = await db.get_user_lang(w['user_id'])
                try:
                    await context.bot.send_message(w['user_id'], t('wit_rejected', u_lang))
                except Exception:
                    pass
        emoji = "✅" if action == 'approve' else "❌"
        try:
            txt_orig = q.message.text or ''
            await q.edit_message_text(txt_orig + f"\n\n{emoji} {action.upper()} by {esc(q.from_user.first_name)}")
        except Exception:
            pass
        return

    # ── Admin: Exchange withdrawal approve/reject ──────
    if data.startswith('ewit_approve_') or data.startswith('ewit_reject_'):
        if uid not in staff_ids():
            return await q.answer("No permission.", show_alert=True)
        wid    = int(data.split('_')[-1])
        action = 'approve' if 'approve' in data else 'reject'
        if action == 'approve':
            w = await db.approve_exc_withdrawal(wid)
            if w:
                info   = config.EXCHANGERS.get(w['exchanger'], {})
                u_lang = await db.get_user_lang(w['user_id'])
                try:
                    await context.bot.send_message(
                        w['user_id'],
                        t('wit_approved', u_lang,
                          amount=f"{w['amount_usdt']:.4f} USDT")
                    )
                except Exception:
                    pass
        else:
            w = await db.reject_exc_withdrawal(wid)
            if w:
                u_lang = await db.get_user_lang(w['user_id'])
                try:
                    await context.bot.send_message(w['user_id'], t('wit_rejected', u_lang))
                except Exception:
                    pass
        emoji = "✅" if action == 'approve' else "❌"
        try:
            txt_orig = q.message.text or ''
            await q.edit_message_text(txt_orig + f"\n\n{emoji} {action.upper()} by {esc(q.from_user.first_name)}")
        except Exception:
            pass
        return

    # ── Tournament join ───────────────────────────────
    if data.startswith('t_join_'):
        tid     = int(data[7:])
        tourney = await db.get_tournament(tid)
        if not tourney or tourney['status'] != 'OPEN':
            return await q.message.reply_text(t('tourney_closed', lang))
        players = await db.get_tourney_players(tid)
        if len(players) >= tourney['slots']:
            return await q.message.reply_text(t('tourney_full', lang))
        if not user or user['available_bal'] < tourney['entry_fee']:
            return await q.message.reply_text(t('insufficient_bal', lang))
        ok = await db.join_tournament(tid, uid, tourney['entry_fee'])
        await q.message.reply_text(t('tourney_joined' if ok else 'tourney_already', lang))
        return


# ════════════════════════════════════════════════════════════════════════════
#  MATCH JOB HELPERS
# ════════════════════════════════════════════════════════════════════════════

def _schedule_match_jobs(context, match_id: str):
    """Schedule warning at 10 min and auto-resolve at 15 min."""
    warn_secs    = config.MATCH_WARNING_MINUTES * 60
    timeout_secs = config.MATCH_TIMEOUT_MINUTES * 60
    context.job_queue.run_once(
        _match_warning_job, warn_secs,
        data=match_id, name=f"warn_{match_id}"
    )
    context.job_queue.run_once(
        _match_timeout_job, timeout_secs,
        data=match_id, name=f"timeout_{match_id}"
    )


async def _match_warning_job(context):
    match_id = context.job.data
    match = await db.get_match(match_id)
    if not match or match['status'] != 'in_progress':
        return
    remaining = config.MATCH_TIMEOUT_MINUTES - config.MATCH_WARNING_MINUTES
    for pid in (match['p1_id'], match['p2_id']):
        submitted = (pid == match['p1_id'] and match.get('p1_screenshot')) or \
                    (pid == match['p2_id'] and match.get('p2_screenshot'))
        if not submitted:
            plang = await db.get_user_lang(pid)
            try:
                await context.bot.send_message(
                    pid, t('warning_10min', plang, mid=match_id)
                )
            except Exception:
                pass


async def _match_timeout_job(context):
    match_id = context.job.data
    match = await db.get_match(match_id)
    if not match or match['status'] != 'in_progress':
        return

    p1_done = bool(match.get('p1_screenshot'))
    p2_done = bool(match.get('p2_screenshot'))

    if p1_done and not p2_done:
        winner_id = match['p1_id']
        loser_id  = match['p2_id']
        await db.autowin_match(match_id, winner_id)
        prize = match['fee'] * 1.8
        for pid, win in ((winner_id, True), (loser_id, False)):
            plang = await db.get_user_lang(pid)
            msg   = t('autowin', plang, prize=prize) if win else t('autolose', plang)
            try:
                await context.bot.send_message(pid, msg)
            except Exception:
                pass

    elif p2_done and not p1_done:
        winner_id = match['p2_id']
        loser_id  = match['p1_id']
        await db.autowin_match(match_id, winner_id)
        prize = match['fee'] * 1.8
        for pid, win in ((winner_id, True), (loser_id, False)):
            plang = await db.get_user_lang(pid)
            msg   = t('autowin', plang, prize=prize) if win else t('autolose', plang)
            try:
                await context.bot.send_message(pid, msg)
            except Exception:
                pass

    else:
        # Neither submitted — auto-cancel
        await db.cancel_match_refund(match_id)
        for pid in (match['p1_id'], match['p2_id']):
            plang = await db.get_user_lang(pid)
            try:
                await context.bot.send_message(pid, t('auto_cancel', plang, mid=match_id))
            except Exception:
                pass


async def _send_to_admin_for_verify(context, match: dict):
    p1 = await db.get_user(match['p1_id'])
    p2 = await db.get_user(match['p2_id'])
    mid = match['match_id']
    p1_ign = esc(p1.get('ingame_name') if p1 else '?')
    p2_ign = esc(p2.get('ingame_name') if p2 else '?')
    tag  = f" (Tourney #{match['tourney_id']})" if match.get('tourney_id') else ""
    msg  = (
        f"🎮 Match #{mid}{tag}\n"
        f"P1: {p1_ign}  vs  P2: {p2_ign}\n"
        f"Fee: {match['fee']} TK\n\n"
        f"⚠️ Verify IGNs in the screenshots match the names above."
    )
    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton(f"✅ {p1_ign} won", callback_data=f"verify_{mid}_{match['p1_id']}"),
        InlineKeyboardButton(f"✅ {p2_ign} won", callback_data=f"verify_{mid}_{match['p2_id']}"),
    ]])
    for aid in staff_ids():
        try:
            await context.bot.send_message(aid, msg)
            await context.bot.send_photo(aid, match['p1_screenshot'], caption=f"P1: {p1_ign}")
            await context.bot.send_photo(aid, match['p2_screenshot'], caption=f"P2: {p2_ign}", reply_markup=kb)
        except Exception:
            pass
