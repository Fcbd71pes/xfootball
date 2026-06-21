import asyncio
import logging
import db
from utils import esc

logger = logging.getLogger(__name__)

async def get_ai_response(user_input: str, user_id: int, is_admin: bool) -> str:
    """
    tgpt কে ডাটাবেজের রিয়েল-টাইম তথ্য সহ কল করবে।
    """
    
    # ব্যাকগ্রাউন্ডে ডাটাবেজ থেকে তথ্য সংগ্রহ
    context_data = ""
    
    if is_admin:
        # এডমিনদের জন্য রিয়েল-টাইম রিপোর্ট
        report = await db.get_daily_report()
        pending_matches = await db.get_pending_matches()
        pending_mfs_dep = await db.get_pending_mfs_deposits()
        pending_exc_dep = await db.get_pending_exc_deposits()
        pending_mfs_wit = await db.get_pending_mfs_withdrawals()
        pending_exc_wit = await db.get_pending_exc_withdrawals()
        
        context_data = f"""
[LIVE SYSTEM DATA FOR ADMIN]
- Today's Matches Played: {report['matches']} (Completed: {report['completed']})
- Today's Total Income (Fees): {report['fees']} TK
- Pending Match Verifications: {len(pending_matches)}
- Pending Deposits: {len(pending_mfs_dep)} (MFS) & {len(pending_exc_dep)} (Crypto)
- Pending Withdrawals: {len(pending_mfs_wit)} (MFS) & {len(pending_exc_wit)} (Crypto)
- Total Users: {report['total_users']} (New today: {report['new_users']})
"""
        system_prompt = "You are the intelligent System Manager AI of an eFootball Telegram Bot. Answer the Admin's questions based on the [LIVE SYSTEM DATA] provided. Speak nicely in Bengali or English."
        
    else:
        # সাধারণ ইউজারদের জন্য তথ্য (টুর্নামেন্ট ইত্যাদি)
        tournaments = await db.get_open_tournaments()
        tourney_text = "No open tournaments right now."
        if tournaments:
            tourney_text = "\n".join([f"- {t['name']} (Entry: {t['entry_fee']} TK, Prize: {t['prize_pool']} TK, Slots: {t['slots']})" for t in tournaments])
            
        context_data = f"""
[LIVE DATA FOR USER]
- Available Tournaments:\n{tourney_text}
"""
        system_prompt = "You are a helpful and polite customer support AI for an eFootball Esports Bot. Answer the user's questions based on the [LIVE DATA]. If they ask about tournaments, tell them the available ones. Keep answers short, friendly, and in Bengali or English."

    # tgpt এর জন্য ফুল প্রম্পট তৈরি
    full_prompt = f"{system_prompt}\n\n{context_data}\n\nUser: {user_input}\nAssistant:"

    try:
        process = await asyncio.create_subprocess_exec(
            "tgpt", "-q", "--provider", "pollinations", full_prompt,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=30.0)
        
        if process.returncode == 0:
            reply = stdout.decode('utf-8').strip()
            return reply if reply else "দুঃখিত, আমি বুঝতে পারিনি। আবার বলুন।"
        else:
            error_msg = stderr.decode('utf-8')
            logger.error(f"tgpt error: {error_msg}")
            return "দুঃখিত, এআই সার্ভারে এই মুহূর্তে সমস্যা হচ্ছে।"

    except asyncio.TimeoutError:
        try:
            process.kill()
        except:
            pass
        return "সার্ভারে লোড বেশি থাকায় উত্তর দিতে দেরি হচ্ছে। একটু পর আবার চেষ্টা করুন।"
    except FileNotFoundError:
        return "সিস্টেমে tgpt ইন্সটল করা নেই।"
    except Exception as e:
        logger.error(f"AI processing error: {e}")
        return "একটি অজানা সমস্যা হয়েছে।"
