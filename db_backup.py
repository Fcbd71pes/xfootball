# db.py  —  aiosqlite database layer
import aiosqlite
import logging
import uuid
from datetime import datetime, timedelta
from typing import Optional, Dict, List

import config

logger = logging.getLogger(__name__)
DB = config.LOCAL_DB


async def init_db():
    async with aiosqlite.connect(DB) as conn:
        conn.row_factory = aiosqlite.Row
        await conn.execute("PRAGMA journal_mode=WAL")
        await conn.execute("PRAGMA foreign_keys=ON")

        await conn.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            user_id       INTEGER PRIMARY KEY,
            username      TEXT,
            ingame_name   TEXT,
            phone         TEXT,
            lang          TEXT    DEFAULT 'en',
            available_bal REAL    DEFAULT 0,
            locked_bal    REAL    DEFAULT 0,
            elo           INTEGER DEFAULT 1000,
            wins          INTEGER DEFAULT 0,
            losses        INTEGER DEFAULT 0,
            is_registered INTEGER DEFAULT 0,
            is_banned     INTEGER DEFAULT 0,
            welcome_given INTEGER DEFAULT 0,
            referrer_id   INTEGER,
            state         TEXT,
            state_data    TEXT,
            created_at    TEXT    DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS match_queue (
            user_id          INTEGER PRIMARY KEY,
            fee              REAL,
            lobby_msg_id     INTEGER,
            queued_at        TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS matches (
            match_id         TEXT PRIMARY KEY,
            p1_id            INTEGER,
            p2_id            INTEGER,
            fee              REAL,
            status           TEXT DEFAULT 'in_progress',
            p1_screenshot    TEXT,
            p2_screenshot    TEXT,
            winner_id        INTEGER,
            verified_by      INTEGER,
            tourney_id       INTEGER,
            started_at       TEXT DEFAULT (datetime('now')),
            created_at       TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS cancel_requests (
            match_id      TEXT PRIMARY KEY,
            requested_by  INTEGER,
            agreed_by     INTEGER,
            status        TEXT DEFAULT 'PENDING',
            created_at    TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS mfs_deposits (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id     INTEGER,
            method      TEXT,
            txid        TEXT UNIQUE,
            amount      REAL,
            screenshot  TEXT,
            status      TEXT DEFAULT 'PENDING',
            created_at  TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS exc_deposits (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id       INTEGER,
            exchanger     TEXT,
            our_uid       TEXT,
            user_uid      TEXT,
            amount_usdt   REAL,
            amount_tk     REAL,
            screenshot    TEXT,
            status        TEXT DEFAULT 'PENDING',
            created_at    TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS mfs_withdrawals (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id     INTEGER,
            method      TEXT,
            account     TEXT,
            amount      REAL,
            status      TEXT DEFAULT 'PENDING',
            created_at  TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS exc_withdrawals (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id     INTEGER,
            exchanger   TEXT,
            user_uid    TEXT,
            amount_usdt REAL,
            amount_tk   REAL,
            status      TEXT DEFAULT 'PENDING',
            created_at  TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS tournaments (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            name        TEXT,
            slots       INTEGER,
            entry_fee   REAL,
            prize_pool  REAL,
            status      TEXT DEFAULT 'OPEN',
            created_at  TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS tourney_players (
            tourney_id  INTEGER,
            user_id     INTEGER,
            status      TEXT DEFAULT 'ACTIVE',
            PRIMARY KEY (tourney_id, user_id)
        );

        CREATE TABLE IF NOT EXISTS support_tickets (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id     INTEGER,
            subject     TEXT,
            status      TEXT DEFAULT 'OPEN',
            created_at  TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS ticket_messages (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            ticket_id   INTEGER,
            sender_id   INTEGER,
            role        TEXT,
            message     TEXT,
            created_at  TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS managers (
            user_id   INTEGER PRIMARY KEY,
            added_by  INTEGER,
            added_at  TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS settings (
            key   TEXT PRIMARY KEY,
            value TEXT
        );

        CREATE TABLE IF NOT EXISTS logs (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id    INTEGER,
            role       TEXT,
            action     TEXT,
            detail     TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        );
        """)
        # seed default settings
        for k, v in [
            ('usdt_deposit_rate',  str(config.USDT_DEPOSIT_RATE_DEFAULT)),
            ('usdt_withdraw_rate', str(config.USDT_WITHDRAW_RATE_DEFAULT)),
        ]:
            await conn.execute(
                "INSERT OR IGNORE INTO settings(key,value) VALUES(?,?)", (k, v)
            )
        await conn.commit()


# ── helpers ─────────────────────────────────────────────────────────────────

def _row(r) -> Optional[Dict]:
    return dict(r) if r else None


async def get_setting(key: str) -> Optional[str]:
    async with aiosqlite.connect(DB) as conn:
        conn.row_factory = aiosqlite.Row
        async with conn.execute("SELECT value FROM settings WHERE key=?", (key,)) as cur:
            r = await cur.fetchone()
            return r['value'] if r else None


async def set_setting(key: str, value: str):
    async with aiosqlite.connect(DB) as conn:
        await conn.execute(
            "INSERT OR REPLACE INTO settings(key,value) VALUES(?,?)", (key, value)
        )
        await conn.commit()


async def deposit_rate() -> float:
    v = await get_setting('usdt_deposit_rate')
    return float(v) if v else config.USDT_DEPOSIT_RATE_DEFAULT


async def withdraw_rate() -> float:
    v = await get_setting('usdt_withdraw_rate')
    return float(v) if v else config.USDT_WITHDRAW_RATE_DEFAULT


async def log(user_id: int, role: str, action: str, detail: str = ''):
    async with aiosqlite.connect(DB) as conn:
        await conn.execute(
            "INSERT INTO logs(user_id,role,action,detail) VALUES(?,?,?,?)",
            (user_id, role, action, detail)
        )
        await conn.commit()


# ── users ─────────────────────────────────────────────────────────────────

async def get_user(uid: int) -> Optional[Dict]:
    async with aiosqlite.connect(DB) as conn:
        conn.row_factory = aiosqlite.Row
        async with conn.execute("SELECT * FROM users WHERE user_id=?", (uid,)) as cur:
            return _row(await cur.fetchone())


async def create_user(uid: int, username: str, referrer_id: Optional[int] = None):
    async with aiosqlite.connect(DB) as conn:
        await conn.execute(
            "INSERT OR IGNORE INTO users(user_id,username,referrer_id) VALUES(?,?,?)",
            (uid, username, referrer_id)
        )
        await conn.commit()


async def update_user(uid: int, **fields):
    if not fields:
        return
    cols = ', '.join(f"{k}=?" for k in fields)
    vals = list(fields.values()) + [uid]
    async with aiosqlite.connect(DB) as conn:
        await conn.execute(f"UPDATE users SET {cols} WHERE user_id=?", vals)
        await conn.commit()


async def set_state(uid: int, state: Optional[str], data: Optional[str] = None):
    async with aiosqlite.connect(DB) as conn:
        await conn.execute(
            "UPDATE users SET state=?, state_data=? WHERE user_id=?",
            (state, data, uid)
        )
        await conn.commit()


async def adjust_balance(uid: int, amount: float, action: str, detail: str = ''):
    """Add (positive) or deduct (negative) from available_balance."""
    async with aiosqlite.connect(DB) as conn:
        await conn.execute(
            "UPDATE users SET available_bal = available_bal + ? WHERE user_id=?",
            (amount, uid)
        )
        await conn.commit()
    await log(uid, 'system', action, detail)


async def lock_balance(uid: int, amount: float):
    """Move amount from available → locked."""
    async with aiosqlite.connect(DB) as conn:
        await conn.execute(
            "UPDATE users SET available_bal=available_bal-?, locked_bal=locked_bal+? WHERE user_id=?",
            (amount, amount, uid)
        )
        await conn.commit()


async def unlock_balance(uid: int, amount: float, restore: bool = True):
    """Remove amount from locked. If restore=True also add back to available."""
    async with aiosqlite.connect(DB) as conn:
        if restore:
            await conn.execute(
                "UPDATE users SET locked_bal=locked_bal-?, available_bal=available_bal+? WHERE user_id=?",
                (amount, amount, uid)
            )
        else:
            await conn.execute(
                "UPDATE users SET locked_bal=locked_bal-? WHERE user_id=?",
                (amount, uid)
            )
        await conn.commit()


async def get_user_lang(uid: int) -> str:
    u = await get_user(uid)
    return (u or {}).get('lang', 'en')


async def get_top_elo(limit: int = 10) -> List[Dict]:
    async with aiosqlite.connect(DB) as conn:
        conn.row_factory = aiosqlite.Row
        async with conn.execute(
            "SELECT * FROM users WHERE is_registered=1 ORDER BY elo DESC LIMIT ?", (limit,)
        ) as cur:
            return [dict(r) for r in await cur.fetchall()]


# ── managers ─────────────────────────────────────────────────────────────

async def get_managers() -> List[int]:
    async with aiosqlite.connect(DB) as conn:
        conn.row_factory = aiosqlite.Row
        async with conn.execute("SELECT user_id FROM managers") as cur:
            return [r['user_id'] for r in await cur.fetchall()]


async def add_manager(uid: int, added_by: int):
    async with aiosqlite.connect(DB) as conn:
        await conn.execute(
            "INSERT OR IGNORE INTO managers(user_id, added_by) VALUES(?,?)", (uid, added_by)
        )
        await conn.commit()


async def remove_manager(uid: int) -> bool:
    async with aiosqlite.connect(DB) as conn:
        cur = await conn.execute("DELETE FROM managers WHERE user_id=?", (uid,))
        await conn.commit()
        return cur.rowcount > 0


async def is_manager(uid: int) -> bool:
    if uid in config.ADMINS:
        return True
    mgrs = await get_managers()
    return uid in mgrs


# ── match queue ──────────────────────────────────────────────────────────

async def add_to_queue(uid: int, fee: float, lobby_msg_id: int):
    async with aiosqlite.connect(DB) as conn:
        await conn.execute(
            "INSERT OR REPLACE INTO match_queue(user_id,fee,lobby_msg_id) VALUES(?,?,?)",
            (uid, fee, lobby_msg_id)
        )
        await conn.commit()


async def get_from_queue(uid: int) -> Optional[Dict]:
    async with aiosqlite.connect(DB) as conn:
        conn.row_factory = aiosqlite.Row
        async with conn.execute("SELECT * FROM match_queue WHERE user_id=?", (uid,)) as cur:
            return _row(await cur.fetchone())


async def find_opponent(fee: float, exclude: int) -> Optional[Dict]:
    async with aiosqlite.connect(DB) as conn:
        conn.row_factory = aiosqlite.Row
        async with conn.execute(
            "SELECT * FROM match_queue WHERE fee=? AND user_id!=? LIMIT 1",
            (fee, exclude)
        ) as cur:
            return _row(await cur.fetchone())


async def remove_from_queue(uid: int):
    async with aiosqlite.connect(DB) as conn:
        await conn.execute("DELETE FROM match_queue WHERE user_id=?", (uid,))
        await conn.commit()


# ── matches ──────────────────────────────────────────────────────────────

async def create_match(p1: int, p2: int, fee: float,
                       tourney_id: Optional[int] = None) -> str:
    mid = str(uuid.uuid4())[:8].upper()
    async with aiosqlite.connect(DB) as conn:
        await conn.execute(
            "INSERT INTO matches(match_id,p1_id,p2_id,fee,tourney_id) VALUES(?,?,?,?,?)",
            (mid, p1, p2, fee, tourney_id)
        )
        if fee > 0:
            await conn.execute(
                "UPDATE users SET available_bal=available_bal-? WHERE user_id=?", (fee, p1)
            )
            await conn.execute(
                "UPDATE users SET available_bal=available_bal-? WHERE user_id=?", (fee, p2)
            )
        await conn.commit()
    return mid


async def get_match(mid: str) -> Optional[Dict]:
    async with aiosqlite.connect(DB) as conn:
        conn.row_factory = aiosqlite.Row
        async with conn.execute("SELECT * FROM matches WHERE match_id=?", (mid,)) as cur:
            return _row(await cur.fetchone())


async def get_active_match(uid: int) -> Optional[Dict]:
    async with aiosqlite.connect(DB) as conn:
        conn.row_factory = aiosqlite.Row
        async with conn.execute(
            "SELECT * FROM matches WHERE (p1_id=? OR p2_id=?) AND status='in_progress' ORDER BY created_at DESC LIMIT 1",
            (uid, uid)
        ) as cur:
            return _row(await cur.fetchone())


async def submit_screenshot(mid: str, uid: int, file_id: str) -> Dict:
    async with aiosqlite.connect(DB) as conn:
        conn.row_factory = aiosqlite.Row
        async with conn.execute("SELECT * FROM matches WHERE match_id=?", (mid,)) as cur:
            m = dict(await cur.fetchone())
        if uid == m['p1_id']:
            await conn.execute("UPDATE matches SET p1_screenshot=? WHERE match_id=?", (file_id, mid))
        else:
            await conn.execute("UPDATE matches SET p2_screenshot=? WHERE match_id=?", (file_id, mid))
        await conn.commit()
        async with conn.execute("SELECT * FROM matches WHERE match_id=?", (mid,)) as cur:
            return dict(await cur.fetchone())


async def resolve_match(mid: str, winner_id: int, manager_id: int):
    async with aiosqlite.connect(DB) as conn:
        conn.row_factory = aiosqlite.Row
        async with conn.execute("SELECT * FROM matches WHERE match_id=?", (mid,)) as cur:
            m = dict(await cur.fetchone())
        loser_id = m['p2_id'] if winner_id == m['p1_id'] else m['p1_id']
        prize = m['fee'] * 1.8
        if prize > 0:
            await conn.execute(
                "UPDATE users SET available_bal=available_bal+?, wins=wins+1, elo=elo+15 WHERE user_id=?",
                (prize, winner_id)
            )
        await conn.execute(
            "UPDATE users SET losses=losses+1, elo=MAX(800,elo-15) WHERE user_id=?", (loser_id,)
        )
        await conn.execute(
            "UPDATE matches SET status='completed',winner_id=?,verified_by=? WHERE match_id=?",
            (winner_id, manager_id, mid)
        )
        await conn.commit()
    return m


async def cancel_match_refund(mid: str):
    """Cancel match and refund fees to both players."""
    async with aiosqlite.connect(DB) as conn:
        conn.row_factory = aiosqlite.Row
        async with conn.execute("SELECT * FROM matches WHERE match_id=?", (mid,)) as cur:
            m = _row(await cur.fetchone())
        if not m:
            return
        if m['fee'] > 0:
            await conn.execute(
                "UPDATE users SET available_bal=available_bal+? WHERE user_id=?",
                (m['fee'], m['p1_id'])
            )
            await conn.execute(
                "UPDATE users SET available_bal=available_bal+? WHERE user_id=?",
                (m['fee'], m['p2_id'])
            )
        await conn.execute(
            "UPDATE matches SET status='cancelled' WHERE match_id=?", (mid,)
        )
        await conn.commit()


async def autowin_match(mid: str, winner_id: int):
    """Auto-resolve: winner gets prize, loser marked."""
    async with aiosqlite.connect(DB) as conn:
        conn.row_factory = aiosqlite.Row
        async with conn.execute("SELECT * FROM matches WHERE match_id=?", (mid,)) as cur:
            m = _row(await cur.fetchone())
        if not m or m['status'] != 'in_progress':
            return m
        loser_id = m['p2_id'] if winner_id == m['p1_id'] else m['p1_id']
        prize = m['fee'] * 1.8
        if prize > 0:
            await conn.execute(
                "UPDATE users SET available_bal=available_bal+?, wins=wins+1, elo=elo+15 WHERE user_id=?",
                (prize, winner_id)
            )
        await conn.execute(
            "UPDATE users SET losses=losses+1, elo=MAX(800,elo-15) WHERE user_id=?", (loser_id,)
        )
        await conn.execute(
            "UPDATE matches SET status='completed',winner_id=?,verified_by=0 WHERE match_id=?",
            (winner_id, mid)
        )
        await conn.commit()
    return m


async def get_stale_matches(minutes: int) -> List[Dict]:
    cutoff = (datetime.now() - timedelta(minutes=minutes)).strftime('%Y-%m-%d %H:%M:%S')
    async with aiosqlite.connect(DB) as conn:
        conn.row_factory = aiosqlite.Row
        async with conn.execute(
            "SELECT * FROM matches WHERE status='in_progress' AND started_at<=?", (cutoff,)
        ) as cur:
            return [dict(r) for r in await cur.fetchall()]


async def get_pending_matches() -> List[Dict]:
    async with aiosqlite.connect(DB) as conn:
        conn.row_factory = aiosqlite.Row
        async with conn.execute(
            "SELECT * FROM matches WHERE p1_screenshot IS NOT NULL AND p2_screenshot IS NOT NULL AND status='in_progress'"
        ) as cur:
            return [dict(r) for r in await cur.fetchall()]


async def get_match_history(uid: int, limit: int = 10) -> List[Dict]:
    async with aiosqlite.connect(DB) as conn:
        conn.row_factory = aiosqlite.Row
        async with conn.execute(
            """SELECT m.*, u1.ingame_name p1_ign, u2.ingame_name p2_ign
               FROM matches m
               JOIN users u1 ON m.p1_id=u1.user_id
               JOIN users u2 ON m.p2_id=u2.user_id
               WHERE (m.p1_id=? OR m.p2_id=?) AND m.status='completed'
               ORDER BY m.created_at DESC LIMIT ?""",
            (uid, uid, limit)
        ) as cur:
            return [dict(r) for r in await cur.fetchall()]


# ── cancel requests ──────────────────────────────────────────────────────

async def create_cancel_req(mid: str, uid: int) -> bool:
    async with aiosqlite.connect(DB) as conn:
        try:
            await conn.execute(
                "INSERT INTO cancel_requests(match_id,requested_by) VALUES(?,?)", (mid, uid)
            )
            await conn.commit()
            return True
        except Exception:
            return False


async def get_cancel_req(mid: str) -> Optional[Dict]:
    async with aiosqlite.connect(DB) as conn:
        conn.row_factory = aiosqlite.Row
        async with conn.execute(
            "SELECT * FROM cancel_requests WHERE match_id=? AND status='PENDING'", (mid,)
        ) as cur:
            return _row(await cur.fetchone())


async def agree_cancel(mid: str, uid: int):
    await cancel_match_refund(mid)
    async with aiosqlite.connect(DB) as conn:
        await conn.execute(
            "UPDATE cancel_requests SET agreed_by=?,status='AGREED' WHERE match_id=?",
            (uid, mid)
        )
        await conn.commit()


# ── MFS deposits ─────────────────────────────────────────────────────────

async def create_mfs_deposit(uid: int, method: str, txid: str,
                              amount: float, screenshot: str) -> int:
    async with aiosqlite.connect(DB) as conn:
        cur = await conn.execute(
            "INSERT INTO mfs_deposits(user_id,method,txid,amount,screenshot) VALUES(?,?,?,?,?)",
            (uid, method, txid, amount, screenshot)
        )
        await conn.commit()
        return cur.lastrowid


async def get_mfs_deposit(dep_id: int) -> Optional[Dict]:
    async with aiosqlite.connect(DB) as conn:
        conn.row_factory = aiosqlite.Row
        async with conn.execute("SELECT * FROM mfs_deposits WHERE id=?", (dep_id,)) as cur:
            return _row(await cur.fetchone())


async def get_pending_mfs_deposits() -> List[Dict]:
    async with aiosqlite.connect(DB) as conn:
        conn.row_factory = aiosqlite.Row
        async with conn.execute(
            "SELECT * FROM mfs_deposits WHERE status='PENDING' ORDER BY created_at"
        ) as cur:
            return [dict(r) for r in await cur.fetchall()]


async def approve_mfs_deposit(dep_id: int):
    async with aiosqlite.connect(DB) as conn:
        conn.row_factory = aiosqlite.Row
        async with conn.execute("SELECT * FROM mfs_deposits WHERE id=?", (dep_id,)) as cur:
            d = _row(await cur.fetchone())
        if not d:
            return None
        await conn.execute(
            "UPDATE users SET available_bal=available_bal+? WHERE user_id=?",
            (d['amount'], d['user_id'])
        )
        await conn.execute(
            "UPDATE mfs_deposits SET status='APPROVED' WHERE id=?", (dep_id,)
        )
        await conn.commit()
    return d


async def reject_mfs_deposit(dep_id: int):
    async with aiosqlite.connect(DB) as conn:
        await conn.execute(
            "UPDATE mfs_deposits SET status='REJECTED' WHERE id=?", (dep_id,)
        )
        await conn.commit()
    return await get_mfs_deposit(dep_id)


# ── Exchange deposits ─────────────────────────────────────────────────────

async def create_exc_deposit(uid: int, exchanger: str, our_uid: str,
                              user_uid: str, amount_usdt: float,
                              amount_tk: float, screenshot: str) -> int:
    async with aiosqlite.connect(DB) as conn:
        cur = await conn.execute(
            "INSERT INTO exc_deposits(user_id,exchanger,our_uid,user_uid,amount_usdt,amount_tk,screenshot) VALUES(?,?,?,?,?,?,?)",
            (uid, exchanger, our_uid, user_uid, amount_usdt, amount_tk, screenshot)
        )
        await conn.commit()
        return cur.lastrowid


async def get_exc_deposit(dep_id: int) -> Optional[Dict]:
    async with aiosqlite.connect(DB) as conn:
        conn.row_factory = aiosqlite.Row
        async with conn.execute("SELECT * FROM exc_deposits WHERE id=?", (dep_id,)) as cur:
            return _row(await cur.fetchone())


async def get_pending_exc_deposits() -> List[Dict]:
    async with aiosqlite.connect(DB) as conn:
        conn.row_factory = aiosqlite.Row
        async with conn.execute(
            "SELECT * FROM exc_deposits WHERE status='PENDING' ORDER BY created_at"
        ) as cur:
            return [dict(r) for r in await cur.fetchall()]


async def approve_exc_deposit(dep_id: int):
    async with aiosqlite.connect(DB) as conn:
        conn.row_factory = aiosqlite.Row
        async with conn.execute("SELECT * FROM exc_deposits WHERE id=?", (dep_id,)) as cur:
            d = _row(await cur.fetchone())
        if not d:
            return None
        await conn.execute(
            "UPDATE users SET available_bal=available_bal+? WHERE user_id=?",
            (d['amount_tk'], d['user_id'])
        )
        await conn.execute(
            "UPDATE exc_deposits SET status='APPROVED' WHERE id=?", (dep_id,)
        )
        await conn.commit()
    return d


async def reject_exc_deposit(dep_id: int):
    async with aiosqlite.connect(DB) as conn:
        await conn.execute(
            "UPDATE exc_deposits SET status='REJECTED' WHERE id=?", (dep_id,)
        )
        await conn.commit()
    return await get_exc_deposit(dep_id)


# ── MFS withdrawals ──────────────────────────────────────────────────────

async def create_mfs_withdrawal(uid: int, method: str,
                                 account: str, amount: float) -> int:
    async with aiosqlite.connect(DB) as conn:
        await conn.execute(
            "UPDATE users SET available_bal=available_bal-?, locked_bal=locked_bal+? WHERE user_id=?",
            (amount, amount, uid)
        )
        cur = await conn.execute(
            "INSERT INTO mfs_withdrawals(user_id,method,account,amount) VALUES(?,?,?,?)",
            (uid, method, account, amount)
        )
        await conn.commit()
        return cur.lastrowid


async def get_mfs_withdrawal(wid: int) -> Optional[Dict]:
    async with aiosqlite.connect(DB) as conn:
        conn.row_factory = aiosqlite.Row
        async with conn.execute("SELECT * FROM mfs_withdrawals WHERE id=?", (wid,)) as cur:
            return _row(await cur.fetchone())


async def get_pending_mfs_withdrawals() -> List[Dict]:
    async with aiosqlite.connect(DB) as conn:
        conn.row_factory = aiosqlite.Row
        async with conn.execute(
            "SELECT * FROM mfs_withdrawals WHERE status='PENDING' ORDER BY created_at"
        ) as cur:
            return [dict(r) for r in await cur.fetchall()]


async def approve_mfs_withdrawal(wid: int):
    async with aiosqlite.connect(DB) as conn:
        conn.row_factory = aiosqlite.Row
        async with conn.execute("SELECT * FROM mfs_withdrawals WHERE id=?", (wid,)) as cur:
            w = _row(await cur.fetchone())
        if not w:
            return None
        await conn.execute(
            "UPDATE users SET locked_bal=locked_bal-? WHERE user_id=?",
            (w['amount'], w['user_id'])
        )
        await conn.execute(
            "UPDATE mfs_withdrawals SET status='APPROVED' WHERE id=?", (wid,)
        )
        await conn.commit()
    return w


async def reject_mfs_withdrawal(wid: int):
    async with aiosqlite.connect(DB) as conn:
        conn.row_factory = aiosqlite.Row
        async with conn.execute("SELECT * FROM mfs_withdrawals WHERE id=?", (wid,)) as cur:
            w = _row(await cur.fetchone())
        if not w:
            return None
        await conn.execute(
            "UPDATE users SET locked_bal=locked_bal-?, available_bal=available_bal+? WHERE user_id=?",
            (w['amount'], w['amount'], w['user_id'])
        )
        await conn.execute(
            "UPDATE mfs_withdrawals SET status='REJECTED' WHERE id=?", (wid,)
        )
        await conn.commit()
    return w


# ── Exchange withdrawals ─────────────────────────────────────────────────

async def create_exc_withdrawal(uid: int, exchanger: str, user_uid: str,
                                 amount_usdt: float, amount_tk: float) -> int:
    async with aiosqlite.connect(DB) as conn:
        await conn.execute(
            "UPDATE users SET available_bal=available_bal-?, locked_bal=locked_bal+? WHERE user_id=?",
            (amount_tk, amount_tk, uid)
        )
        cur = await conn.execute(
            "INSERT INTO exc_withdrawals(user_id,exchanger,user_uid,amount_usdt,amount_tk) VALUES(?,?,?,?,?)",
            (uid, exchanger, user_uid, amount_usdt, amount_tk)
        )
        await conn.commit()
        return cur.lastrowid


async def get_exc_withdrawal(wid: int) -> Optional[Dict]:
    async with aiosqlite.connect(DB) as conn:
        conn.row_factory = aiosqlite.Row
        async with conn.execute("SELECT * FROM exc_withdrawals WHERE id=?", (wid,)) as cur:
            return _row(await cur.fetchone())


async def get_pending_exc_withdrawals() -> List[Dict]:
    async with aiosqlite.connect(DB) as conn:
        conn.row_factory = aiosqlite.Row
        async with conn.execute(
            "SELECT * FROM exc_withdrawals WHERE status='PENDING' ORDER BY created_at"
        ) as cur:
            return [dict(r) for r in await cur.fetchall()]


async def approve_exc_withdrawal(wid: int):
    async with aiosqlite.connect(DB) as conn:
        conn.row_factory = aiosqlite.Row
        async with conn.execute("SELECT * FROM exc_withdrawals WHERE id=?", (wid,)) as cur:
            w = _row(await cur.fetchone())
        if not w:
            return None
        await conn.execute(
            "UPDATE users SET locked_bal=locked_bal-? WHERE user_id=?",
            (w['amount_tk'], w['user_id'])
        )
        await conn.execute(
            "UPDATE exc_withdrawals SET status='APPROVED' WHERE id=?", (wid,)
        )
        await conn.commit()
    return w


async def reject_exc_withdrawal(wid: int):
    async with aiosqlite.connect(DB) as conn:
        conn.row_factory = aiosqlite.Row
        async with conn.execute("SELECT * FROM exc_withdrawals WHERE id=?", (wid,)) as cur:
            w = _row(await cur.fetchone())
        if not w:
            return None
        await conn.execute(
            "UPDATE users SET locked_bal=locked_bal-?, available_bal=available_bal+? WHERE user_id=?",
            (w['amount_tk'], w['amount_tk'], w['user_id'])
        )
        await conn.execute(
            "UPDATE exc_withdrawals SET status='REJECTED' WHERE id=?", (wid,)
        )
        await conn.commit()
    return w


# ── tournaments ───────────────────────────────────────────────────────────

async def create_tournament(name: str, slots: int,
                             entry_fee: float, prize_pool: float) -> int:
    async with aiosqlite.connect(DB) as conn:
        cur = await conn.execute(
            "INSERT INTO tournaments(name,slots,entry_fee,prize_pool) VALUES(?,?,?,?)",
            (name, slots, entry_fee, prize_pool)
        )
        await conn.commit()
        return cur.lastrowid


async def get_open_tournaments() -> List[Dict]:
    async with aiosqlite.connect(DB) as conn:
        conn.row_factory = aiosqlite.Row
        async with conn.execute(
            "SELECT * FROM tournaments WHERE status='OPEN' ORDER BY id"
        ) as cur:
            return [dict(r) for r in await cur.fetchall()]


async def get_tournament(tid: int) -> Optional[Dict]:
    async with aiosqlite.connect(DB) as conn:
        conn.row_factory = aiosqlite.Row
        async with conn.execute("SELECT * FROM tournaments WHERE id=?", (tid,)) as cur:
            return _row(await cur.fetchone())


async def get_tourney_players(tid: int, status: Optional[str] = None) -> List[Dict]:
    async with aiosqlite.connect(DB) as conn:
        conn.row_factory = aiosqlite.Row
        if status:
            async with conn.execute(
                "SELECT * FROM tourney_players WHERE tourney_id=? AND status=?", (tid, status)
            ) as cur:
                return [dict(r) for r in await cur.fetchall()]
        async with conn.execute(
            "SELECT * FROM tourney_players WHERE tourney_id=?", (tid,)
        ) as cur:
            return [dict(r) for r in await cur.fetchall()]


async def join_tournament(tid: int, uid: int, fee: float) -> bool:
    async with aiosqlite.connect(DB) as conn:
        try:
            await conn.execute(
                "INSERT INTO tourney_players(tourney_id,user_id) VALUES(?,?)", (tid, uid)
            )
            if fee > 0:
                await conn.execute(
                    "UPDATE users SET available_bal=available_bal-? WHERE user_id=?", (fee, uid)
                )
            await conn.commit()
            return True
        except Exception:
            return False


async def eliminate_player(tid: int, uid: int):
    async with aiosqlite.connect(DB) as conn:
        await conn.execute(
            "UPDATE tourney_players SET status='ELIMINATED' WHERE tourney_id=? AND user_id=?",
            (tid, uid)
        )
        await conn.commit()


async def update_tournament_status(tid: int, status: str):
    async with aiosqlite.connect(DB) as conn:
        await conn.execute(
            "UPDATE tournaments SET status=? WHERE id=?", (status, tid)
        )
        await conn.commit()


# ── support tickets ───────────────────────────────────────────────────────

async def create_ticket(uid: int, subject: str) -> int:
    async with aiosqlite.connect(DB) as conn:
        cur = await conn.execute(
            "INSERT INTO support_tickets(user_id,subject) VALUES(?,?)", (uid, subject)
        )
        await conn.commit()
        return cur.lastrowid


async def add_ticket_msg(ticket_id: int, sender: int, role: str, msg: str):
    async with aiosqlite.connect(DB) as conn:
        await conn.execute(
            "INSERT INTO ticket_messages(ticket_id,sender_id,role,message) VALUES(?,?,?,?)",
            (ticket_id, sender, role, msg)
        )
        await conn.commit()


async def get_ticket(ticket_id: int) -> Optional[Dict]:
    async with aiosqlite.connect(DB) as conn:
        conn.row_factory = aiosqlite.Row
        async with conn.execute(
            "SELECT * FROM support_tickets WHERE id=?", (ticket_id,)
        ) as cur:
            return _row(await cur.fetchone())


async def get_user_tickets(uid: int) -> List[Dict]:
    async with aiosqlite.connect(DB) as conn:
        conn.row_factory = aiosqlite.Row
        async with conn.execute(
            "SELECT * FROM support_tickets WHERE user_id=? ORDER BY created_at DESC LIMIT 5",
            (uid,)
        ) as cur:
            return [dict(r) for r in await cur.fetchall()]


async def get_open_tickets() -> List[Dict]:
    async with aiosqlite.connect(DB) as conn:
        conn.row_factory = aiosqlite.Row
        async with conn.execute(
            "SELECT * FROM support_tickets WHERE status='OPEN' ORDER BY created_at"
        ) as cur:
            return [dict(r) for r in await cur.fetchall()]


async def get_ticket_msgs(ticket_id: int) -> List[Dict]:
    async with aiosqlite.connect(DB) as conn:
        conn.row_factory = aiosqlite.Row
        async with conn.execute(
            "SELECT * FROM ticket_messages WHERE ticket_id=? ORDER BY created_at",
            (ticket_id,)
        ) as cur:
            return [dict(r) for r in await cur.fetchall()]


async def close_ticket(ticket_id: int):
    async with aiosqlite.connect(DB) as conn:
        await conn.execute(
            "UPDATE support_tickets SET status='CLOSED' WHERE id=?", (ticket_id,)
        )
        await conn.commit()


# ── admin / reports ───────────────────────────────────────────────────────

async def get_daily_report() -> Dict:
    today = datetime.now().strftime('%Y-%m-%d')
    async with aiosqlite.connect(DB) as conn:
        conn.row_factory = aiosqlite.Row

        async def scalar(sql, *params):
            async with conn.execute(sql, params) as cur:
                r = await cur.fetchone()
                return list(r)[0] if r else 0

        return {
            'date':              today,
            'total_users':       await scalar("SELECT COUNT(*) FROM users"),
            'new_users':         await scalar("SELECT COUNT(*) FROM users WHERE DATE(created_at)=?", today),
            'matches':           await scalar("SELECT COUNT(*) FROM matches WHERE DATE(created_at)=?", today),
            'completed':         await scalar("SELECT COUNT(*) FROM matches WHERE DATE(created_at)=? AND status='completed'", today),
            'fees':              await scalar("SELECT COALESCE(SUM(fee),0) FROM matches WHERE DATE(created_at)=? AND status='completed'", today),
            'mfs_dep_count':     await scalar("SELECT COUNT(*) FROM mfs_deposits WHERE DATE(created_at)=? AND status='APPROVED'", today),
            'mfs_dep_amount':    await scalar("SELECT COALESCE(SUM(amount),0) FROM mfs_deposits WHERE DATE(created_at)=? AND status='APPROVED'", today),
            'exc_dep_count':     await scalar("SELECT COUNT(*) FROM exc_deposits WHERE DATE(created_at)=? AND status='APPROVED'", today),
            'exc_dep_usdt':      await scalar("SELECT COALESCE(SUM(amount_usdt),0) FROM exc_deposits WHERE DATE(created_at)=? AND status='APPROVED'", today),
            'exc_dep_tk':        await scalar("SELECT COALESCE(SUM(amount_tk),0) FROM exc_deposits WHERE DATE(created_at)=? AND status='APPROVED'", today),
            'mfs_wit_amount':    await scalar("SELECT COALESCE(SUM(amount),0) FROM mfs_withdrawals WHERE DATE(created_at)=? AND status='APPROVED'", today),
            'exc_wit_usdt':      await scalar("SELECT COALESCE(SUM(amount_usdt),0) FROM exc_withdrawals WHERE DATE(created_at)=? AND status='APPROVED'", today),
            'pending_mfs_dep':   await scalar("SELECT COUNT(*) FROM mfs_deposits WHERE status='PENDING'"),
            'pending_exc_dep':   await scalar("SELECT COUNT(*) FROM exc_deposits WHERE status='PENDING'"),
            'pending_mfs_wit':   await scalar("SELECT COUNT(*) FROM mfs_withdrawals WHERE status='PENDING'"),
            'pending_exc_wit':   await scalar("SELECT COUNT(*) FROM exc_withdrawals WHERE status='PENDING'"),
            'dep_rate':          await scalar("SELECT value FROM settings WHERE key='usdt_deposit_rate'"),
            'wit_rate':          await scalar("SELECT value FROM settings WHERE key='usdt_withdraw_rate'"),
        }


async def admin_adjust_balance(uid: int, amount: float, note: str):
    await adjust_balance(uid, amount, 'admin_adjust', note)


async def safe_backup(dest_path: str):
    """Safe SQLite backup using native backup API."""
    async with aiosqlite.connect(DB) as src:
        async with aiosqlite.connect(dest_path) as dst:
            await src.backup(dst)
