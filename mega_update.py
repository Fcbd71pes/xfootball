import os
import sqlite3
import re

def apply_mega_features():
    print("🚀 প্রিমিয়াম ফিচারগুলো বটের ভেতরে ইন্সটল করা হচ্ছে...\n")

    # --- ১. Database Update (নতুন কলাম যুক্ত করা) ---
    print("⏳ ডাটাবেজ আপডেট করা হচ্ছে...")
    try:
        conn = sqlite3.connect('efootball.db')
        cur = conn.cursor()
        cur.execute("ALTER TABLE users ADD COLUMN last_daily TEXT;")
        cur.execute("ALTER TABLE users ADD COLUMN total_refs INTEGER DEFAULT 0;")
        conn.commit()
        conn.close()
    except Exception as e:
        # কলাম আগে থেকেই থাকলে এরর ইগনোর করবে
        pass

    # --- ২. lang.py আপডেট ---
    print("⏳ ভাষা এবং বাটন যুক্ত করা হচ্ছে...")
    with open('lang.py', 'r', encoding='utf-8') as f:
        lang_data = f.read()
        
    if "'btn_daily'" not in lang_data:
        lang_data = lang_data.replace(
            "'btn_support':    {'bn': '📞 Support', 'en': '📞 Support'},",
            """'btn_support':    {'bn': '📞 Support', 'en': '📞 Support'},
    'btn_daily':      {'bn': '🎁 Daily Bonus', 'en': '🎁 Daily Bonus'},
    'btn_tutorial':   {'bn': '📖 How to Play', 'en': '📖 How to Play'},
    'daily_claimed':  {'bn': '✅ আপনি আজকের {amount} TK বোনাস পেয়েছেন!', 'en': '✅ Daily bonus claimed: {amount} TK!'},
    'daily_already':  {'bn': '❌ আপনি আজ ইতিমধ্যে বোনাস নিয়েছেন। আগামীকাল চেষ্টা করুন।', 'en': '❌ Already claimed today. Try tomorrow.'},
    'mega_ref_bonus': {'bn': '🎉 মেগা বোনাস! ১০টি রেফার সম্পন্ন করায় এক্সট্রা ৫০ TK পেলেন!', 'en': '🎉 Mega Bonus! 50 TK added for 10 referrals!'},
    'tutorial_text':  {'bn': '🎮 <b>কীভাবে খেলবেন:</b>\\n১. <b>Play 1v1</b> এ ক্লিক করে ফি সিলেক্ট করুন।\\n২. প্রতিপক্ষ পেলে গেমে রুম বানিয়ে কোড দিন।\\n৩. ম্যাচ শেষে <b>Result</b> এ ক্লিক করে জয়ের স্ক্রিনশট দিন।', 'en': '🎮 <b>How to Play:</b>\\n1. Click <b>Play 1v1</b> & select fee.\\n2. Share room code.\\n3. Submit win screenshot in <b>Result</b>.'},"""
        )
        with open('lang.py', 'w', encoding='utf-8') as f:
            f.write(lang_data)

    # --- ৩. utils.py আপডেট (কীবোর্ডে বাটন বসানো) ---
    with open('utils.py', 'r', encoding='utf-8') as f:
        utils_data = f.read()
        
    if "t('btn_daily'" not in utils_data:
        utils_data = utils_data.replace(
            "[t('btn_rules', lang),   t('btn_result', lang)],",
            "[t('btn_rules', lang),   t('btn_result', lang)],\n        [t('btn_daily', lang), t('btn_tutorial', lang)],"
        )
        with open('utils.py', 'w', encoding='utf-8') as f:
            f.write(utils_data)

    # --- ৪. user_cmds.py আপডেট ---
    print("⏳ কমান্ড ফাংশন তৈরি করা হচ্ছে...")
    with open('user_cmds.py', 'r', encoding='utf-8') as f:
        user_cmds_data = f.read()
        
    if "async def cmd_daily" not in user_cmds_data:
        new_cmds = """
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
    import aiosqlite, config
    async with aiosqlite.connect(config.LOCAL_DB) as conn:
        await conn.execute("UPDATE users SET available_bal=available_bal+2, last_daily=? WHERE user_id=?", (today, uid))
        await conn.commit()
    await update.message.reply_text(t('daily_claimed', lang, amount=2))

async def cmd_tutorial(update, context):
    from utils import ensure_user
    from lang import t
    user = await ensure_user(update)
    if not user: return
    lang = user.get('lang', 'en')
    await update.message.reply_text(t('tutorial_text', lang), parse_mode='HTML')
"""
        with open('user_cmds.py', 'a', encoding='utf-8') as f:
            f.write(new_cmds)

    # --- ৫. handlers.py আপডেট ---
    print("⏳ লজিক ও লাইভ ফিড যুক্ত করা হচ্ছে...")
    with open('handlers.py', 'r', encoding='utf-8') as f:
        handlers_data = f.read()

    modified = False

    # Daily ও Tutorial বাটন ক্লিক করলে ফাংশন কল করা
    if "cmd_daily" not in handlers_data:
        import re
        handlers_data = re.sub(
            r"rules_btns = \{t\('btn_rules', 'bn'\), t\('btn_rules', 'en'\)\}",
            """daily_btns = {t('btn_daily', 'bn'), t('btn_daily', 'en')}
    if txt in daily_btns:
        from user_cmds import cmd_daily
        return await cmd_daily(update, context)
        
    tut_btns = {t('btn_tutorial', 'bn'), t('btn_tutorial', 'en')}
    if txt in tut_btns:
        from user_cmds import cmd_tutorial
        return await cmd_tutorial(update, context)

    rules_btns = {t('btn_rules', 'bn'), t('btn_rules', 'en')}""",
            handlers_data
        )
        modified = True

    # মেগা রেফারেল বোনাস লজিক
    if "total_refs=total_refs+1" not in handlers_data:
        handlers_data = handlers_data.replace(
            "await db.update_user(user_id, referrer_id=0)",
            """await db.update_user(user_id, referrer_id=0)
        # Mega Referral Logic
        async with aiosqlite.connect(config.LOCAL_DB) as conn:
            conn.row_factory = aiosqlite.Row
            await conn.execute("UPDATE users SET total_refs=total_refs+1 WHERE user_id=?", (ref_id,))
            await conn.commit()
            async with conn.execute("SELECT total_refs FROM users WHERE user_id=?", (ref_id,)) as cur:
                r = await cur.fetchone()
                if r and r['total_refs'] > 0 and r['total_refs'] % 10 == 0:
                    await db.adjust_balance(ref_id, 50.0, 'mega_ref_bonus')
                    try:
                        await context.bot.send_message(ref_id, t('mega_ref_bonus', rlang))
                    except: pass"""
        )
        modified = True

    # লাইভ ম্যাচ চ্যানেল আপডেট
    if "Live Match Result" not in handlers_data:
        handlers_data = handlers_data.replace(
            "m = await db.resolve_match(match_id, winner_id, uid)",
            """m = await db.resolve_match(match_id, winner_id, uid)
        # Live Match Broadcast
        try:
            w_ign = esc(w.get('ingame_name') if w else '?')
            prize_pool = m['fee'] * 1.8
            if prize_pool > 0 and config.LOBBY_CHANNEL_ID:
                await context.bot.send_message(
                    config.LOBBY_CHANNEL_ID,
                    f"🔥 <b>LIVE MATCH UPDATE</b>\\n\\n🏆 <b>{w_ign}</b> জিতেছে একটি ম্যাচ!\\n💰 পুরস্কার: <b>{prize_pool:.0f} TK</b>\\n🎮 আপনিও জয়েন করুন!",
                    parse_mode='HTML'
                )
        except Exception as e:
            pass"""
        )
        modified = True

    if modified:
        with open('handlers.py', 'w', encoding='utf-8') as f:
            f.write(handlers_data)

    print("\n🎉 চমৎকার! সবগুলো ফিচার বটের ভেতরে বসে গেছে।")
    print("এখন বট স্টপ করে আবার রিস্টার্ট করুন: python main.py")

if __name__ == "__main__":
    apply_mega_features()