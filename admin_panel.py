# admin_panel.py
import os
import logging
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List
try:
    import uvicorn
except ImportError:
    uvicorn = None
import asyncio
from telegram import Bot
import json

import db
import config
from lang import t

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("admin_panel")

app = FastAPI(title="eFootball Bot Local Admin Panel")

# Enable CORS for local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize Telegram Bot for sending notifications
tg_bot = Bot(token=config.TOKEN)

async def notify_user(user_id: int, message: str):
    """Send Telegram notification to a user."""
    try:
        await tg_bot.send_message(chat_id=user_id, text=message, parse_mode="HTML")
        logger.info(f"Notification sent to user {user_id}")
    except Exception as e:
        logger.error(f"Failed to send notification to user {user_id}: {e}")

# Serve the static Admin Dashboard UI
@app.get("/", response_class=HTMLResponse)
async def get_index():
    index_path = os.path.join(os.path.dirname(__file__), "templates", "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return "<h1>Admin Dashboard Template Not Found</h1><p>Please create templates/index.html first.</p>"

# ── API ENDPOINTS ──────────────────────────────────────────────────────────

@app.get("/api/stats")
async def get_stats():
    try:
        report = await db.get_daily_report()
        # Add active queue count from memory
        queue_count = len(db.MATCH_QUEUE)
        report['queue_count'] = queue_count
        return report
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/users")
async def get_users(query: Optional[str] = None):
    try:
        async with db.aiosqlite.connect(db.DB) as conn:
            conn.row_factory = db.aiosqlite.Row
            if query:
                q_str = f"%{query}%"
                async with conn.execute(
                    "SELECT * FROM users WHERE username LIKE ? OR ingame_name LIKE ? OR phone LIKE ? OR user_id = ? ORDER BY created_at DESC",
                    (q_str, q_str, q_str, query if query.isdigit() else -1)
                ) as cur:
                    return [dict(r) for r in await cur.fetchall()]
            else:
                async with conn.execute("SELECT * FROM users ORDER BY created_at DESC LIMIT 100") as cur:
                    return [dict(r) for r in await cur.fetchall()]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

class BalanceAdjustRequest(BaseModel):
    amount: float
    note: str

@app.post("/api/users/{uid}/balance")
async def adjust_user_balance(uid: int, req: BalanceAdjustRequest):
    try:
        user = await db.get_user(uid)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        await db.admin_adjust_balance(uid, req.amount, req.note)
        
        # Notify user via Telegram
        u_lang = await db.get_user_lang(uid)
        if req.amount > 0:
            msg = f"✅ <b>{req.amount:.2f} TK</b> has been added to your balance. (Note: {req.note})" if u_lang == 'en' else f"✅ <b>{req.amount:.2f} TK</b> আপনার ব্যালেন্সে যোগ করা হয়েছে। (নোট: {req.note})"
        else:
            msg = f"❌ <b>{abs(req.amount):.2f} TK</b> has been deducted from your balance. (Note: {req.note})" if u_lang == 'en' else f"❌ <b>{abs(req.amount):.2f} TK</b> আপনার ব্যালেন্স থেকে কেটে নেওয়া হয়েছে। (নোট: {req.note})"
        
        await notify_user(uid, msg)
        return {"status": "success", "message": f"Balance adjusted by {req.amount:.2f} TK"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/users/{uid}/ban")
async def toggle_user_ban(uid: int):
    try:
        user = await db.get_user(uid)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        new_ban_status = 0 if user.get('is_banned') else 1
        await db.update_user(uid, is_banned=new_ban_status)
        
        # Notify user
        u_lang = await db.get_user_lang(uid)
        if new_ban_status:
            msg = "❌ Your account has been banned." if u_lang == 'en' else "❌ আপনার একাউন্টটি ব্যান করা হয়েছে।"
        else:
            msg = "✅ Your account has been unbanned." if u_lang == 'en' else "✅ আপনার একাউন্টটি আনব্যান করা হয়েছে।"
            
        await notify_user(uid, msg)
        return {"status": "success", "is_banned": bool(new_ban_status)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/matches")
async def get_matches(status: Optional[str] = None):
    try:
        async with db.aiosqlite.connect(db.DB) as conn:
            conn.row_factory = db.aiosqlite.Row
            if status:
                async with conn.execute(
                    "SELECT m.*, u1.ingame_name p1_ign, u2.ingame_name p2_ign FROM matches m JOIN users u1 ON m.p1_id=u1.user_id JOIN users u2 ON m.p2_id=u2.user_id WHERE m.status=? ORDER BY m.created_at DESC",
                    (status,)
                ) as cur:
                    return [dict(r) for r in await cur.fetchall()]
            else:
                async with conn.execute(
                    "SELECT m.*, u1.ingame_name p1_ign, u2.ingame_name p2_ign FROM matches m JOIN users u1 ON m.p1_id=u1.user_id JOIN users u2 ON m.p2_id=u2.user_id ORDER BY m.created_at DESC LIMIT 50"
                ) as cur:
                    return [dict(r) for r in await cur.fetchall()]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

class MatchResolveRequest(BaseModel):
    winner_id: Optional[int] = None # If None, match is cancelled and refunded

@app.post("/api/matches/{mid}/resolve")
async def resolve_match_dispute(mid: str, req: MatchResolveRequest):
    try:
        match = await db.get_match(mid)
        if not match:
            raise HTTPException(status_code=404, detail="Match not found")
        if match['status'] != 'in_progress':
            raise HTTPException(status_code=400, detail="Match is already resolved")
            
        if req.winner_id is not None:
            # Resolve with winner
            m = await db.resolve_match(mid, req.winner_id, 0) # verified_by 0 means admin dashboard
            
            # Send notifications
            w_lang = await db.get_user_lang(req.winner_id)
            loser_id = match['p2_id'] if req.winner_id == match['p1_id'] else match['p1_id']
            l_lang = await db.get_user_lang(loser_id)
            prize = match['fee'] * 1.8
            
            # Notify winner
            await notify_user(req.winner_id, t('match_won', w_lang, mid=mid, prize=prize))
            # Notify loser
            await notify_user(loser_id, t('match_lost', l_lang, mid=mid))
            
            # Live Match Broadcast
            try:
                w = await db.get_user(req.winner_id)
                w_ign = esc(w.get('ingame_name') if w else '?')
                if prize > 0 and config.LOBBY_CHANNEL_ID:
                    await tg_bot.send_message(
                        config.LOBBY_CHANNEL_ID,
                        f"🔥 <b>LIVE MATCH UPDATE</b>\n\n🏆 <b>{w_ign}</b> জিতেছে একটি ম্যাচ!\n💰 পুরস্কার: <b>{prize:.0f} TK</b>\n🎮 আপনিও জয়েন করুন!",
                        parse_mode='HTML'
                    )
            except Exception:
                pass
                
            return {"status": "success", "resolved_as": "winner", "winner_id": req.winner_id}
        else:
            # Cancel and refund match
            await db.cancel_match_refund(mid)
            p1_lang = await db.get_user_lang(match['p1_id'])
            p2_lang = await db.get_user_lang(match['p2_id'])
            
            await notify_user(match['p1_id'], t('match_cancelled_ok', p1_lang))
            await notify_user(match['p2_id'], t('match_cancelled_ok', p2_lang))
            
            return {"status": "success", "resolved_as": "cancelled"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/deposits")
async def get_deposits():
    try:
        mfs = await db.get_pending_mfs_deposits()
        exc = await db.get_pending_exc_deposits()
        # Add user ingame names
        for d in mfs:
            user = await db.get_user(d['user_id'])
            d['username'] = user.get('username') if user else ''
            d['ingame_name'] = user.get('ingame_name') if user else ''
        for d in exc:
            user = await db.get_user(d['user_id'])
            d['username'] = user.get('username') if user else ''
            d['ingame_name'] = user.get('ingame_name') if user else ''
        return {"mfs": mfs, "exc": exc}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

class ActionRequest(BaseModel):
    action: str # 'approve' or 'reject'

@app.post("/api/deposits/mfs/{dep_id}/resolve")
async def resolve_mfs_deposit(dep_id: int, req: ActionRequest):
    try:
        dep = await db.get_mfs_deposit(dep_id)
        if not dep:
            raise HTTPException(status_code=404, detail="Deposit not found")
        if dep['status'] != 'PENDING':
            raise HTTPException(status_code=400, detail="Deposit already processed")
            
        if req.action == 'approve':
            d = await db.approve_mfs_deposit(dep_id)
            if d:
                u_lang = await db.get_user_lang(d['user_id'])
                await notify_user(d['user_id'], t('dep_approved', u_lang, amount=d['amount']))
            return {"status": "success", "action": "approved"}
        else:
            d = await db.reject_mfs_deposit(dep_id)
            if d:
                u_lang = await db.get_user_lang(d['user_id'])
                await notify_user(d['user_id'], t('dep_rejected', u_lang))
            return {"status": "success", "action": "rejected"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/deposits/exc/{dep_id}/resolve")
async def resolve_exc_deposit(dep_id: int, req: ActionRequest):
    try:
        dep = await db.get_exc_deposit(dep_id)
        if not dep:
            raise HTTPException(status_code=404, detail="Deposit not found")
        if dep['status'] != 'PENDING':
            raise HTTPException(status_code=400, detail="Deposit already processed")
            
        if req.action == 'approve':
            d = await db.approve_exc_deposit(dep_id)
            if d:
                info = config.EXCHANGERS.get(d['exchanger'], {})
                u_lang = await db.get_user_lang(d['user_id'])
                await notify_user(
                    d['user_id'],
                    t('exc_dep_approved', u_lang, name=info.get('name', ''), usdt=d['amount_usdt'], bdt=d['amount_tk'])
                )
            return {"status": "success", "action": "approved"}
        else:
            d = await db.reject_exc_deposit(dep_id)
            if d:
                info = config.EXCHANGERS.get(d['exchanger'], {})
                u_lang = await db.get_user_lang(d['user_id'])
                await notify_user(d['user_id'], t('exc_dep_rejected', u_lang, name=info.get('name', '')))
            return {"status": "success", "action": "rejected"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/withdrawals")
async def get_withdrawals():
    try:
        mfs = await db.get_pending_mfs_withdrawals()
        exc = await db.get_pending_exc_withdrawals()
        # Add user details
        for w in mfs:
            user = await db.get_user(w['user_id'])
            w['username'] = user.get('username') if user else ''
            w['ingame_name'] = user.get('ingame_name') if user else ''
        for w in exc:
            user = await db.get_user(w['user_id'])
            w['username'] = user.get('username') if user else ''
            w['ingame_name'] = user.get('ingame_name') if user else ''
        return {"mfs": mfs, "exc": exc}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/withdrawals/mfs/{wid}/resolve")
async def resolve_mfs_withdrawal(wid: int, req: ActionRequest):
    try:
        w_data = await db.get_mfs_withdrawal(wid)
        if not w_data:
            raise HTTPException(status_code=404, detail="Withdrawal not found")
        if w_data['status'] != 'PENDING':
            raise HTTPException(status_code=400, detail="Withdrawal already processed")
            
        if req.action == 'approve':
            w = await db.approve_mfs_withdrawal(wid)
            if w:
                u_lang = await db.get_user_lang(w['user_id'])
                await notify_user(w['user_id'], t('wit_approved', u_lang, amount=f"{w['amount']:.2f} TK"))
            return {"status": "success", "action": "approved"}
        else:
            w = await db.reject_mfs_withdrawal(wid)
            if w:
                u_lang = await db.get_user_lang(w['user_id'])
                await notify_user(w['user_id'], t('wit_rejected', u_lang))
            return {"status": "success", "action": "rejected"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/withdrawals/exc/{wid}/resolve")
async def resolve_exc_withdrawal(wid: int, req: ActionRequest):
    try:
        w_data = await db.get_exc_withdrawal(wid)
        if not w_data:
            raise HTTPException(status_code=404, detail="Withdrawal not found")
        if w_data['status'] != 'PENDING':
            raise HTTPException(status_code=400, detail="Withdrawal already processed")
            
        if req.action == 'approve':
            w = await db.approve_exc_withdrawal(wid)
            if w:
                u_lang = await db.get_user_lang(w['user_id'])
                await notify_user(w['user_id'], t('wit_approved', u_lang, amount=f"{w['amount_usdt']:.4f} USDT"))
            return {"status": "success", "action": "approved"}
        else:
            w = await db.reject_exc_withdrawal(wid)
            if w:
                u_lang = await db.get_user_lang(w['user_id'])
                await notify_user(w['user_id'], t('wit_rejected', u_lang))
            return {"status": "success", "action": "rejected"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/settings")
async def get_settings():
    try:
        rate_dep = await db.deposit_rate()
        rate_wit = await db.withdraw_rate()
        rules = await db.get_setting('rules_text')
        
        # Load config details
        bkash_num = config.MOBILE_BANKING.get('bkash', {}).get('number', '')
        nagad_num = config.MOBILE_BANKING.get('nagad', {}).get('number', '')
        rocket_num = config.MOBILE_BANKING.get('rocket', {}).get('number', '')
        upay_num = config.MOBILE_BANKING.get('upay', {}).get('number', '')
        
        return {
            "usdt_deposit_rate": rate_dep,
            "usdt_withdraw_rate": rate_wit,
            "rules_text": rules or '',
            "bkash_number": bkash_num,
            "nagad_number": nagad_num,
            "rocket_number": rocket_num,
            "upay_number": upay_num,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

class SettingsUpdateRequest(BaseModel):
    usdt_deposit_rate: float
    usdt_withdraw_rate: float
    rules_text: str
    bkash_number: str
    nagad_number: str
    rocket_number: str
    upay_number: str

@app.post("/api/settings")
async def update_settings(req: SettingsUpdateRequest):
    try:
        await db.set_setting('usdt_deposit_rate', str(req.usdt_deposit_rate))
        await db.set_setting('usdt_withdraw_rate', str(req.usdt_withdraw_rate))
        await db.set_setting('rules_text', req.rules_text)
        
        # Save numbers into config dictionary (in memory)
        if 'bkash' in config.MOBILE_BANKING:
            config.MOBILE_BANKING['bkash']['number'] = req.bkash_number
        if 'nagad' in config.MOBILE_BANKING:
            config.MOBILE_BANKING['nagad']['number'] = req.nagad_number
        if 'rocket' in config.MOBILE_BANKING:
            config.MOBILE_BANKING['rocket']['number'] = req.rocket_number
        if 'upay' in config.MOBILE_BANKING:
            config.MOBILE_BANKING['upay']['number'] = req.upay_number
            
        return {"status": "success", "message": "Settings and payment numbers updated successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/logs")
async def get_system_logs():
    try:
        async with db.aiosqlite.connect(db.DB) as conn:
            conn.row_factory = db.aiosqlite.Row
            async with conn.execute("SELECT * FROM logs ORDER BY created_at DESC LIMIT 30") as cur:
                return [dict(r) for r in await cur.fetchall()]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/transactions")
async def get_ledger_transactions():
    try:
        async with db.aiosqlite.connect(db.DB) as conn:
            conn.row_factory = db.aiosqlite.Row
            async with conn.execute(
                "SELECT t.*, u.ingame_name FROM transactions t JOIN users u ON t.user_id=u.user_id ORDER BY t.created_at DESC LIMIT 50"
            ) as cur:
                return [dict(r) for r in await cur.fetchall()]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Function helper for HTML escaping
def esc(text):
    import html
    return html.escape(str(text)) if text else 'N/A'


def run_async(coro):
    import asyncio
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    
    if loop.is_running():
        import concurrent.futures
        future = asyncio.run_coroutine_threadsafe(coro, loop)
        return future.result()
    else:
        return loop.run_until_complete(coro)


def handle_request(path: str, args_json: str) -> str:
    import json
    import urllib.parse
    try:
        # Resolve query parameters if any
        query_params = {}
        if "?" in path:
            path, query_str = path.split("?", 1)
            for pair in query_str.split("&"):
                if "=" in pair:
                    k, v = pair.split("=", 1)
                    query_params[k] = urllib.parse.unquote(v)

        data = {}
        if args_json:
            try:
                data = json.loads(args_json)
            except Exception:
                pass

        parts = [p for p in path.split("/") if p]
        if len(parts) < 2 or parts[0] != "api":
            return json.dumps({"status": "error", "detail": "Invalid API path"})

        endpoint = parts[1]

        # 1. /api/stats
        if endpoint == "stats" and len(parts) == 2:
            async def _stats():
                report = await db.get_daily_report()
                report['queue_count'] = len(db.MATCH_QUEUE)
                return report
            return json.dumps(run_async(_stats()))

        # 2. /api/users
        elif endpoint == "users" and len(parts) == 2:
            q = query_params.get("query")
            async def _users():
                async with db.aiosqlite.connect(db.DB) as conn:
                    conn.row_factory = db.aiosqlite.Row
                    if q:
                        q_str = f"%{q}%"
                        async with conn.execute(
                            "SELECT * FROM users WHERE username LIKE ? OR ingame_name LIKE ? OR phone LIKE ? OR user_id = ? ORDER BY created_at DESC",
                            (q_str, q_str, q_str, int(q) if q.isdigit() else -1)
                        ) as cur:
                            return [dict(r) for r in await cur.fetchall()]
                    else:
                        async with conn.execute("SELECT * FROM users ORDER BY created_at DESC LIMIT 100") as cur:
                            return [dict(r) for r in await cur.fetchall()]
            return json.dumps(run_async(_users()))

        # 3. /api/users/{uid}/balance
        elif endpoint == "users" and len(parts) == 4 and parts[3] == "balance":
            uid = int(parts[2])
            async def _balance():
                user = await db.get_user(uid)
                if not user:
                    return {"status": "error", "detail": "User not found"}
                amount = float(data.get("amount", 0.0))
                note = data.get("note", "")
                await db.admin_adjust_balance(uid, amount, note)
                u_lang = await db.get_user_lang(uid)
                if amount > 0:
                    msg = f"✅ <b>{amount:.2f} TK</b> has been added to your balance. (Note: {note})" if u_lang == 'en' else f"✅ <b>{amount:.2f} TK</b> আপনার ব্যালেন্সে যোগ করা হয়েছে। (নোট: {note})"
                else:
                    msg = f"❌ <b>{abs(amount):.2f} TK</b> has been deducted from your balance. (Note: {note})" if u_lang == 'en' else f"❌ <b>{abs(amount):.2f} TK</b> আপনার ব্যালেন্স থেকে কেটে নেওয়া হয়েছে। (নোট: {note})"
                await notify_user(uid, msg)
                return {"status": "success", "message": f"Balance adjusted by {amount:.2f} TK"}
            return json.dumps(run_async(_balance()))

        # 4. /api/users/{uid}/ban
        elif endpoint == "users" and len(parts) == 4 and parts[3] == "ban":
            uid = int(parts[2])
            async def _ban():
                user = await db.get_user(uid)
                if not user:
                    return {"status": "error", "detail": "User not found"}
                new_ban_status = 0 if user.get('is_banned') else 1
                await db.update_user(uid, is_banned=new_ban_status)
                u_lang = await db.get_user_lang(uid)
                if new_ban_status:
                    msg = "❌ Your account has been banned." if u_lang == 'en' else "❌ আপনার একাউন্টটি ব্যান করা হয়েছে।"
                else:
                    msg = "✅ Your account has been unbanned." if u_lang == 'en' else "✅ আপনার একাউন্টটি আনব্যান করা হয়েছে।"
                await notify_user(uid, msg)
                return {"status": "success", "is_banned": bool(new_ban_status)}
            return json.dumps(run_async(_ban()))

        # 5. /api/matches
        elif endpoint == "matches" and len(parts) == 2:
            status = query_params.get("status")
            async def _matches():
                async with db.aiosqlite.connect(db.DB) as conn:
                    conn.row_factory = db.aiosqlite.Row
                    if status:
                        async with conn.execute(
                            "SELECT m.*, u1.ingame_name p1_ign, u2.ingame_name p2_ign FROM matches m JOIN users u1 ON m.p1_id=u1.user_id JOIN users u2 ON m.p2_id=u2.user_id WHERE m.status=? ORDER BY m.created_at DESC",
                            (status,)
                        ) as cur:
                            return [dict(r) for r in await cur.fetchall()]
                    else:
                        async with conn.execute(
                            "SELECT m.*, u1.ingame_name p1_ign, u2.ingame_name p2_ign FROM matches m JOIN users u1 ON m.p1_id=u1.user_id JOIN users u2 ON m.p2_id=u2.user_id ORDER BY m.created_at DESC LIMIT 50"
                        ) as cur:
                            return [dict(r) for r in await cur.fetchall()]
            return json.dumps(run_async(_matches()))

        # 6. /api/matches/{mid}/resolve
        elif endpoint == "matches" and len(parts) == 4 and parts[3] == "resolve":
            mid = parts[2]
            async def _resolve():
                match = await db.get_match(mid)
                if not match:
                    return {"status": "error", "detail": "Match not found"}
                if match['status'] != 'in_progress':
                    return {"status": "error", "detail": "Match is already resolved"}
                winner_id = data.get("winner_id")
                if winner_id is not None:
                    winner_id = int(winner_id)
                    m = await db.resolve_match(mid, winner_id, 0)
                    w_lang = await db.get_user_lang(winner_id)
                    loser_id = match['p2_id'] if winner_id == match['p1_id'] else match['p1_id']
                    l_lang = await db.get_user_lang(loser_id)
                    prize = match['fee'] * 1.8
                    await notify_user(winner_id, t('match_won', w_lang, mid=mid, prize=prize))
                    await notify_user(loser_id, t('match_lost', l_lang, mid=mid))
                    try:
                        w = await db.get_user(winner_id)
                        w_ign = esc(w.get('ingame_name') if w else '?')
                        if prize > 0 and config.LOBBY_CHANNEL_ID:
                            await tg_bot.send_message(
                                config.LOBBY_CHANNEL_ID,
                                f"🔥 <b>LIVE MATCH UPDATE</b>\n\n🏆 <b>{w_ign}</b> জিতেছে একটি ম্যাচ!\n💰 পুরস্কার: <b>{prize:.0f} TK</b>\n🎮 আপনিও জয়েন করুন!",
                                parse_mode='HTML'
                            )
                    except Exception:
                        pass
                    return {"status": "success", "resolved_as": "winner", "winner_id": winner_id}
                else:
                    await db.cancel_match_refund(mid)
                    p1_lang = await db.get_user_lang(match['p1_id'])
                    p2_lang = await db.get_user_lang(match['p2_id'])
                    await notify_user(match['p1_id'], t('match_cancelled_ok', p1_lang))
                    await notify_user(match['p2_id'], t('match_cancelled_ok', p2_lang))
                    return {"status": "success", "resolved_as": "cancelled"}
            return json.dumps(run_async(_resolve()))

        # 7. /api/deposits
        elif endpoint == "deposits" and len(parts) == 2:
            async def _deposits():
                mfs = await db.get_pending_mfs_deposits()
                exc = await db.get_pending_exc_deposits()
                for d in mfs:
                    user = await db.get_user(d['user_id'])
                    d['username'] = user.get('username') if user else ''
                    d['ingame_name'] = user.get('ingame_name') if user else ''
                for d in exc:
                    user = await db.get_user(d['user_id'])
                    d['username'] = user.get('username') if user else ''
                    d['ingame_name'] = user.get('ingame_name') if user else ''
                return {"mfs": mfs, "exc": exc}
            return json.dumps(run_async(_deposits()))

        # 8. /api/deposits/mfs/{dep_id}/resolve
        elif endpoint == "deposits" and len(parts) == 5 and parts[2] == "mfs" and parts[4] == "resolve":
            dep_id = int(parts[3])
            async def _res_mfs_dep():
                dep = await db.get_mfs_deposit(dep_id)
                if not dep:
                    return {"status": "error", "detail": "Deposit not found"}
                if dep['status'] != 'PENDING':
                    return {"status": "error", "detail": "Deposit already processed"}
                if data.get("action") == "approve":
                    d = await db.approve_mfs_deposit(dep_id)
                    if d:
                        u_lang = await db.get_user_lang(d['user_id'])
                        await notify_user(d['user_id'], t('dep_approved', u_lang, amount=d['amount']))
                    return {"status": "success", "action": "approved"}
                else:
                    d = await db.reject_mfs_deposit(dep_id)
                    if d:
                        u_lang = await db.get_user_lang(d['user_id'])
                        await notify_user(d['user_id'], t('dep_rejected', u_lang))
                    return {"status": "success", "action": "rejected"}
            return json.dumps(run_async(_res_mfs_dep()))

        # 9. /api/deposits/exc/{dep_id}/resolve
        elif endpoint == "deposits" and len(parts) == 5 and parts[2] == "exc" and parts[4] == "resolve":
            dep_id = int(parts[3])
            async def _res_exc_dep():
                dep = await db.get_exc_deposit(dep_id)
                if not dep:
                    return {"status": "error", "detail": "Deposit not found"}
                if dep['status'] != 'PENDING':
                    return {"status": "error", "detail": "Deposit already processed"}
                if data.get("action") == "approve":
                    d = await db.approve_exc_deposit(dep_id)
                    if d:
                        info = config.EXCHANGERS.get(d['exchanger'], {})
                        u_lang = await db.get_user_lang(d['user_id'])
                        await notify_user(
                            d['user_id'],
                            t('exc_dep_approved', u_lang, name=info.get('name', ''), usdt=d['amount_usdt'], bdt=d['amount_tk'])
                        )
                    return {"status": "success", "action": "approved"}
                else:
                    d = await db.reject_exc_deposit(dep_id)
                    if d:
                        info = config.EXCHANGERS.get(d['exchanger'], {})
                        u_lang = await db.get_user_lang(d['user_id'])
                        await notify_user(d['user_id'], t('exc_dep_rejected', u_lang, name=info.get('name', '')))
                    return {"status": "success", "action": "rejected"}
            return json.dumps(run_async(_res_exc_dep()))

        # 10. /api/withdrawals
        elif endpoint == "withdrawals" and len(parts) == 2:
            async def _withdrawals():
                mfs = await db.get_pending_mfs_withdrawals()
                exc = await db.get_pending_exc_withdrawals()
                for w in mfs:
                    user = await db.get_user(w['user_id'])
                    w['username'] = user.get('username') if user else ''
                    w['ingame_name'] = user.get('ingame_name') if user else ''
                for w in exc:
                    user = await db.get_user(w['user_id'])
                    w['username'] = user.get('username') if user else ''
                    w['ingame_name'] = user.get('ingame_name') if user else ''
                return {"mfs": mfs, "exc": exc}
            return json.dumps(run_async(_withdrawals()))

        # 11. /api/withdrawals/mfs/{wid}/resolve
        elif endpoint == "withdrawals" and len(parts) == 5 and parts[2] == "mfs" and parts[4] == "resolve":
            wid = int(parts[3])
            async def _res_mfs_wit():
                w_data = await db.get_mfs_withdrawal(wid)
                if not w_data:
                    return {"status": "error", "detail": "Withdrawal not found"}
                if w_data['status'] != 'PENDING':
                    return {"status": "error", "detail": "Withdrawal already processed"}
                if data.get("action") == "approve":
                    w = await db.approve_mfs_withdrawal(wid)
                    if w:
                        u_lang = await db.get_user_lang(w['user_id'])
                        await notify_user(w['user_id'], t('wit_approved', u_lang, amount=f"{w['amount']:.2f} TK"))
                    return {"status": "success", "action": "approved"}
                else:
                    w = await db.reject_mfs_withdrawal(wid)
                    if w:
                        u_lang = await db.get_user_lang(w['user_id'])
                        await notify_user(w['user_id'], t('wit_rejected', u_lang))
                    return {"status": "success", "action": "rejected"}
            return json.dumps(run_async(_res_mfs_wit()))

        # 12. /api/withdrawals/exc/{wid}/resolve
        elif endpoint == "withdrawals" and len(parts) == 5 and parts[2] == "exc" and parts[4] == "resolve":
            wid = int(parts[3])
            async def _res_exc_wit():
                w_data = await db.get_exc_withdrawal(wid)
                if not w_data:
                    return {"status": "error", "detail": "Withdrawal not found"}
                if w_data['status'] != 'PENDING':
                    return {"status": "error", "detail": "Withdrawal already processed"}
                if data.get("action") == "approve":
                    w = await db.approve_exc_withdrawal(wid)
                    if w:
                        u_lang = await db.get_user_lang(w['user_id'])
                        await notify_user(w['user_id'], t('wit_approved', u_lang, amount=f"{w['amount_usdt']:.4f} USDT"))
                    return {"status": "success", "action": "approved"}
                else:
                    w = await db.reject_exc_withdrawal(wid)
                    if w:
                        u_lang = await db.get_user_lang(w['user_id'])
                        await notify_user(w['user_id'], t('wit_rejected', u_lang))
                    return {"status": "success", "action": "rejected"}
            return json.dumps(run_async(_res_exc_wit()))

        # 13. /api/settings
        elif endpoint == "settings" and len(parts) == 2:
            if not data:  # GET
                async def _get_settings():
                    rate_dep = await db.deposit_rate()
                    rate_wit = await db.withdraw_rate()
                    rules = await db.get_setting('rules_text')
                    bkash_num = config.MOBILE_BANKING.get('bkash', {}).get('number', '')
                    nagad_num = config.MOBILE_BANKING.get('nagad', {}).get('number', '')
                    rocket_num = config.MOBILE_BANKING.get('rocket', {}).get('number', '')
                    upay_num = config.MOBILE_BANKING.get('upay', {}).get('number', '')
                    return {
                        "usdt_deposit_rate": rate_dep,
                        "usdt_withdraw_rate": rate_wit,
                        "rules_text": rules or '',
                        "bkash_number": bkash_num,
                        "nagad_number": nagad_num,
                        "rocket_number": rocket_num,
                        "upay_number": upay_num,
                    }
                return json.dumps(run_async(_get_settings()))
            else:  # POST
                async def _update_settings():
                    await db.set_setting('usdt_deposit_rate', str(data.get("usdt_deposit_rate", 0.0)))
                    await db.set_setting('usdt_withdraw_rate', str(data.get("usdt_withdraw_rate", 0.0)))
                    await db.set_setting('rules_text', data.get("rules_text", ""))
                    if 'bkash' in config.MOBILE_BANKING:
                        config.MOBILE_BANKING['bkash']['number'] = data.get("bkash_number", "")
                    if 'nagad' in config.MOBILE_BANKING:
                        config.MOBILE_BANKING['nagad']['number'] = data.get("nagad_number", "")
                    if 'rocket' in config.MOBILE_BANKING:
                        config.MOBILE_BANKING['rocket']['number'] = data.get("rocket_number", "")
                    if 'upay' in config.MOBILE_BANKING:
                        config.MOBILE_BANKING['upay']['number'] = data.get("upay_number", "")
                    return {"status": "success", "message": "Settings and payment numbers updated successfully"}
                return json.dumps(run_async(_update_settings()))

        # 14. /api/logs
        elif endpoint == "logs" and len(parts) == 2:
            async def _logs():
                async with db.aiosqlite.connect(db.DB) as conn:
                    conn.row_factory = db.aiosqlite.Row
                    async with conn.execute("SELECT * FROM logs ORDER BY created_at DESC LIMIT 30") as cur:
                        return [dict(r) for r in await cur.fetchall()]
            return json.dumps(run_async(_logs()))

        # 15. /api/transactions
        elif endpoint == "transactions" and len(parts) == 2:
            async def _transactions():
                async with db.aiosqlite.connect(db.DB) as conn:
                    conn.row_factory = db.aiosqlite.Row
                    async with conn.execute(
                        "SELECT t.*, u.ingame_name FROM transactions t JOIN users u ON t.user_id=u.user_id ORDER BY t.created_at DESC LIMIT 50"
                    ) as cur:
                        return [dict(r) for r in await cur.fetchall()]
            return json.dumps(run_async(_transactions()))

        else:
            return json.dumps({"status": "error", "detail": f"Path not found: {path}"})

    except Exception as e:
        return json.dumps({"status": "error", "detail": str(e)})


if __name__ == "__main__" and uvicorn is not None:
    # Ensure templates directory exists
    os.makedirs(os.path.join(os.path.dirname(__file__), "templates"), exist_ok=True)
    # Start the server using configured host and port
    uvicorn.run(app, host=config.ADMIN_PANEL_HOST, port=config.ADMIN_PANEL_PORT)
