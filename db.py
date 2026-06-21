# db.py  —  aiosqlite database layer
import aiosqlite
import logging
import asyncio
import uuid
from datetime import datetime, timedelta
from typing import Optional, Dict, List

import config

logger = logging.getLogger(__name__)
DB = config.LOCAL_DB

# ── Turso Libsql Compatibility Layer ──────────────────────────────────────
import base64
import httpx
import sqlite3

class LibsqlRow:
    def __init__(self, keys, values):
        self._dict = {k: v for k, v in zip(keys, values)}
        self._list = list(values)
        
    def __getitem__(self, key):
        if isinstance(key, int):
            return self._list[key]
        return self._dict[key]
        
    def get(self, key, default=None):
        return self._dict.get(key, default)
        
    def keys(self):
        return list(self._dict.keys())
        
    def __repr__(self):
        return f"<Row {self._dict}>"

class LibsqlCursor:
    def __init__(self, result_set):
        self.rows = []
        self.rowcount = 0
        self.lastrowid = None
        
        if result_set:
            self.rowcount = result_set.get("affected_row_count", 0)
            last_id_str = result_set.get("last_insert_rowid")
            if last_id_str is not None:
                try:
                    self.lastrowid = int(last_id_str)
                except ValueError:
                    self.lastrowid = last_id_str
                    
            cols = result_set.get("cols", [])
            col_names = [c.get("name") if isinstance(c, dict) else c for c in cols]
            for r in result_set.get("rows", []):
                row_vals = []
                for cell in r:
                    val = cell.get("value")
                    cell_type = cell.get("type")
                    if cell_type == "integer" and val is not None:
                        val = int(val)
                    elif cell_type == "float" and val is not None:
                        val = float(val)
                    elif cell_type == "blob" and cell.get("base64") is not None:
                        try:
                            val = base64.b64decode(cell.get("base64"))
                        except Exception:
                            val = None
                    elif cell_type == "null":
                        val = None
                    row_vals.append(val)
                self.rows.append(LibsqlRow(col_names, row_vals))
        self.index = 0
        
    async def fetchone(self):
        if self.index < len(self.rows):
            r = self.rows[self.index]
            self.index += 1
            return r
        return None
        
    async def fetchall(self):
        rows = self.rows[self.index:]
        self.index = len(self.rows)
        return rows
        
    async def __aenter__(self):
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass

class LibsqlConnection:
    def __init__(self, url, token):
        if url.startswith("libsql://"):
            self.url = url.replace("libsql://", "https://")
        elif url.startswith("wss://"):
            self.url = url.replace("wss://", "https://")
        else:
            self.url = url
        self.token = token
        self.row_factory = None
        
    async def __aenter__(self):
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass
        
    def _serialize_arg(self, arg):
        if arg is None:
            return {"type": "null"}
        elif isinstance(arg, int):
            return {"type": "integer", "value": str(arg)}
        elif isinstance(arg, float):
            return {"type": "float", "value": arg}
        elif isinstance(arg, bytes):
            return {"type": "blob", "base64": base64.b64encode(arg).decode('utf-8')}
        else:
            return {"type": "text", "value": str(arg)}

    async def execute(self, sql, params=None):
        sql_upper = sql.upper().strip()
        if sql_upper.startswith("PRAGMA "):
            return LibsqlCursor({"cols": [], "rows": []})

        args = []
        if params is not None:
            if isinstance(params, (list, tuple)):
                args = [self._serialize_arg(a) for a in params]
            else:
                args = [self._serialize_arg(params)]

        payload = {
            "requests": [
                {
                    "type": "execute",
                    "stmt": {
                        "sql": sql,
                        "args": args
                    }
                },
                {
                    "type": "close"
                }
            ]
        }
        
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json"
        }
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(f"{self.url}/v2/pipeline", json=payload, headers=headers)
            response.raise_for_status()
            res_data = response.json()
            
            results = res_data.get("results", [])
            if results and results[0].get("type") == "error":
                error_msg = results[0].get("error", {}).get("message", "Unknown Turso Error")
                if "UNIQUE constraint failed" in error_msg:
                    raise sqlite3.IntegrityError(error_msg)
                raise Exception(f"Turso Error: {error_msg}")
                
            exec_res = results[0].get("response", {}).get("result", {})
            return LibsqlCursor(exec_res)
            
    async def executescript(self, script):
        # Basic statement splitter (simple semicolon split)
        # Note: if query contains semicolons inside strings, a regex parser would be safer,
        # but in our DB setup, SQL scripts are straightforward.
        for stmt in script.split(';'):
            stmt = stmt.strip()
            if stmt:
                await self.execute(stmt)
                
    async def commit(self):
        pass

# Override aiosqlite.connect to route connection to Turso if configured
if getattr(config, 'USE_TURSO', False):
    def connect_mock(database=None, **kwargs):
        return LibsqlConnection(config.TURSO_DB_URL, config.TURSO_AUTH_TOKEN)
    aiosqlite.connect = connect_mock
    aiosqlite.IntegrityError = sqlite3.IntegrityError



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
            last_daily    TEXT,
            total_refs    INTEGER DEFAULT 0,
            created_at    TEXT    DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS transactions (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id     INTEGER,
            amount      REAL,
            type        TEXT,
            status      TEXT DEFAULT 'COMPLETED',
            detail      TEXT,
            created_at  TEXT DEFAULT (datetime('now'))
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


async def increment_referrals(ref_id: int) -> int:
    async with aiosqlite.connect(DB) as conn:
        conn.row_factory = aiosqlite.Row
        await conn.execute("UPDATE users SET total_refs=total_refs+1 WHERE user_id=?", (ref_id,))
        await conn.commit()
        async with conn.execute("SELECT total_refs FROM users WHERE user_id=?", (ref_id,)) as cur:
            r = await cur.fetchone()
            return r['total_refs'] if r else 0


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


async def record_transaction(uid: int, amount: float, type_: str, detail: str = '', status: str = 'COMPLETED'):
    async with aiosqlite.connect(DB) as conn:
        await conn.execute(
            "INSERT INTO transactions(user_id, amount, type, detail, status) VALUES (?,?,?,?,?)",
            (uid, amount, type_, detail, status)
        )
        await conn.commit()


async def update_transaction_status(uid: int, type_: str, detail: str, new_status: str):
    async with aiosqlite.connect(DB) as conn:
        await conn.execute(
            "UPDATE transactions SET status=? WHERE user_id=? AND type=? AND detail=? AND status='PENDING'",
            (new_status, uid, type_, detail)
        )
        await conn.commit()


async def claim_daily_bonus(uid: int, amount: float, today: str) -> bool:
    async with aiosqlite.connect(DB) as conn:
        conn.row_factory = aiosqlite.Row
        async with conn.execute("SELECT last_daily FROM users WHERE user_id=?", (uid,)) as cur:
            r = await cur.fetchone()
            if r and r['last_daily'] == today:
                return False
        await conn.execute(
            "UPDATE users SET available_bal=available_bal+?, last_daily=? WHERE user_id=?",
            (amount, today, uid)
        )
        await conn.commit()
    await record_transaction(uid, amount, 'daily_bonus', f'Claimed daily bonus on {today}')
    return True


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
    await record_transaction(uid, amount, action, detail, 'COMPLETED')


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

MATCH_QUEUE = {}  # user_id -> {user_id, fee, lobby_msg_id, queued_at}
QUEUE_LOCK = asyncio.Lock()


async def add_to_queue(uid: int, fee: float, lobby_msg_id: int, extra_data: str = '[]'):
    async with QUEUE_LOCK:
        MATCH_QUEUE[uid] = {
            'user_id': uid,
            'fee': fee,
            'lobby_msg_id': lobby_msg_id,
            'extra_data': extra_data,
            'queued_at': datetime.now()
        }


async def get_from_queue(uid: int) -> Optional[Dict]:
    async with QUEUE_LOCK:
        return MATCH_QUEUE.get(uid)


async def find_opponent(fee: float, exclude: int) -> Optional[Dict]:
    async with QUEUE_LOCK:
        # Find first opponent who matches
        candidates = [v for k, v in MATCH_QUEUE.items() if k != exclude]
        if not candidates:
            return None
        candidates.sort(key=lambda x: x['queued_at'])
        return candidates[0]


async def remove_from_queue(uid: int):
    async with QUEUE_LOCK:
        if uid in MATCH_QUEUE:
            del MATCH_QUEUE[uid]


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
    if fee > 0:
        await record_transaction(p1, -fee, 'match_fee', f'Match #{mid}')
        await record_transaction(p2, -fee, 'match_fee', f'Match #{mid}')
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
    if prize > 0:
        await record_transaction(winner_id, prize, 'match_win', f'Match #{mid}')
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
    if m and m['fee'] > 0:
        await record_transaction(m['p1_id'], m['fee'], 'match_refund', f'Match #{mid}')
        await record_transaction(m['p2_id'], m['fee'], 'match_refund', f'Match #{mid}')


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
    if prize > 0:
        await record_transaction(winner_id, prize, 'match_win', f'Auto-win Match #{mid}')
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
    await record_transaction(d['user_id'], d['amount'], 'mfs_deposit', f'TxID: {d["txid"]}')
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
    await record_transaction(d['user_id'], d['amount_tk'], 'exc_deposit', f'Exchanger: {d["exchanger"]}, USDT: {d["amount_usdt"]}')
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
        wid = cur.lastrowid
    await record_transaction(uid, -amount, 'mfs_withdrawal', f'Withdrawal #{wid} ({method}: {account})', 'PENDING')
    return wid


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
    await update_transaction_status(w['user_id'], 'mfs_withdrawal', f'Withdrawal #{wid} ({w["method"]}: {w["account"]})', 'COMPLETED')
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
    await update_transaction_status(w['user_id'], 'mfs_withdrawal', f'Withdrawal #{wid} ({w["method"]}: {w["account"]})', 'REJECTED')
    await record_transaction(w['user_id'], w['amount'], 'withdrawal_refund', f'Refund for Withdrawal #{wid}')
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
        wid = cur.lastrowid
    await record_transaction(uid, -amount_tk, 'exc_withdrawal', f'Withdrawal #{wid} ({exchanger}: {user_uid}, USDT: {amount_usdt})', 'PENDING')
    return wid


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
    await update_transaction_status(w['user_id'], 'exc_withdrawal', f'Withdrawal #{wid} ({w["exchanger"]}: {w["user_uid"]}, USDT: {w["amount_usdt"]})', 'COMPLETED')
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
    await update_transaction_status(w['user_id'], 'exc_withdrawal', f'Withdrawal #{wid} ({w["exchanger"]}: {w["user_uid"]}, USDT: {w["amount_usdt"]})', 'REJECTED')
    await record_transaction(w['user_id'], w['amount_tk'], 'withdrawal_refund', f'Refund for Withdrawal #{wid}')
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
            success = True
        except Exception:
            success = False
    if success and fee > 0:
        await record_transaction(uid, -fee, 'tourney_fee', f'Tournament #{tid}')
    return success


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
            'new_users':         await scalar("SELECT COUNT(*) FROM users WHERE DATE(datetime(created_at, 'localtime'))=?", today),
            'matches':           await scalar("SELECT COUNT(*) FROM matches WHERE DATE(datetime(created_at, 'localtime'))=?", today),
            'completed':         await scalar("SELECT COUNT(*) FROM matches WHERE DATE(datetime(created_at, 'localtime'))=? AND status='completed'", today),
            'fees':              await scalar("SELECT COALESCE(SUM(fee),0) FROM matches WHERE DATE(datetime(created_at, 'localtime'))=? AND status='completed'", today),
            'mfs_dep_count':     await scalar("SELECT COUNT(*) FROM mfs_deposits WHERE DATE(datetime(created_at, 'localtime'))=? AND status='APPROVED'", today),
            'mfs_dep_amount':    await scalar("SELECT COALESCE(SUM(amount),0) FROM mfs_deposits WHERE DATE(datetime(created_at, 'localtime'))=? AND status='APPROVED'", today),
            'exc_dep_count':     await scalar("SELECT COUNT(*) FROM exc_deposits WHERE DATE(datetime(created_at, 'localtime'))=? AND status='APPROVED'", today),
            'exc_dep_usdt':      await scalar("SELECT COALESCE(SUM(amount_usdt),0) FROM exc_deposits WHERE DATE(datetime(created_at, 'localtime'))=? AND status='APPROVED'", today),
            'exc_dep_tk':        await scalar("SELECT COALESCE(SUM(amount_tk),0) FROM exc_deposits WHERE DATE(datetime(created_at, 'localtime'))=? AND status='APPROVED'", today),
            'mfs_wit_amount':    await scalar("SELECT COALESCE(SUM(amount),0) FROM mfs_withdrawals WHERE DATE(datetime(created_at, 'localtime'))=? AND status='APPROVED'", today),
            'exc_wit_usdt':      await scalar("SELECT COALESCE(SUM(amount_usdt),0) FROM exc_withdrawals WHERE DATE(datetime(created_at, 'localtime'))=? AND status='APPROVED'", today),
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
    """Safe database backup. Downloads Turso tables to a local SQLite file if Turso is active, or does a native SQLite backup if local."""
    if getattr(config, 'USE_TURSO', False):
        import aiosqlite
        # 1. Create a local SQLite DB and initialize tables
        async with aiosqlite.connect(dest_path) as local_conn:
            await local_conn.executescript("""
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
                last_daily    TEXT,
                total_refs    INTEGER DEFAULT 0,
                created_at    TEXT    DEFAULT (datetime('now'))
            );
            CREATE TABLE IF NOT EXISTS transactions (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id     INTEGER,
                amount      REAL,
                type        TEXT,
                status      TEXT DEFAULT 'COMPLETED',
                detail      TEXT,
                created_at  TEXT DEFAULT (datetime('now'))
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
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id       INTEGER,
                method        TEXT,
                number        TEXT,
                amount        REAL,
                status        TEXT DEFAULT 'PENDING',
                created_at    TEXT DEFAULT (datetime('now'))
            );
            CREATE TABLE IF NOT EXISTS exc_withdrawals (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id       INTEGER,
                exchanger     TEXT,
                user_uid      TEXT,
                amount_usdt   REAL,
                amount_tk     REAL,
                status        TEXT DEFAULT 'PENDING',
                created_at    TEXT DEFAULT (datetime('now'))
            );
            CREATE TABLE IF NOT EXISTS settings (
                key           TEXT PRIMARY KEY,
                value         TEXT
            );
            CREATE TABLE IF NOT EXISTS logs (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id       INTEGER,
                action        TEXT,
                detail        TEXT,
                role          TEXT,
                created_at    TEXT DEFAULT (datetime('now'))
            );
            """)
            
            # 2. Query each table from Turso and write to local DB
            tables = [
                "users", "transactions", "matches", "cancel_requests",
                "mfs_deposits", "exc_deposits", "mfs_withdrawals",
                "exc_withdrawals", "settings", "logs"
            ]
            
            async with LibsqlConnection(config.TURSO_DB_URL, config.TURSO_AUTH_TOKEN) as remote_conn:
                for table in tables:
                    cur = await remote_conn.execute(f"SELECT * FROM {table}")
                    rows = await cur.fetchall()
                    if rows:
                        keys = list(rows[0].keys())
                        placeholders = ", ".join(["?"] * len(keys))
                        cols_str = ", ".join(keys)
                        
                        val_tuples = []
                        for r in rows:
                            val_tuples.append(tuple(r[k] for k in keys))
                            
                        await local_conn.executemany(
                            f"INSERT OR REPLACE INTO {table} ({cols_str}) VALUES ({placeholders})",
                            val_tuples
                        )
            await local_conn.commit()
    else:
        async with aiosqlite.connect(DB) as src:
            async with aiosqlite.connect(dest_path) as dst:
                await src.backup(dst)


async def load_payment_settings():
    """DB থেকে MFS number ও Exchanger UID load করো config এ"""
    import config as cfg
    for key in cfg.MOBILE_BANKING:
        val = await get_setting(f'mfs_number_{key}')
        if val:
            cfg.MOBILE_BANKING[key]['number'] = val
    for key in cfg.EXCHANGERS:
        uid_val = await get_setting(f'exc_uid_{key}')
        if uid_val is not None:
            cfg.EXCHANGERS[key]['our_uid'] = uid_val
        for lang in ('bn', 'en'):
            note = await get_setting(f'exc_note_{key}_{lang}')
            if note:
                cfg.EXCHANGERS[key][f'deposit_note_{lang}'] = note
