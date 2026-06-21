# main.py
import logging
import asyncio
from datetime import time as dtime
from telegram import Update
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    filters, CallbackQueryHandler
)
from telegram.request import HTTPXRequest
from telegram.error import NetworkError, TimedOut

import config
import db
import user_cmds
import admin_cmds
import handlers

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(name)s %(levelname)s %(message)s'
)
logger = logging.getLogger(__name__)


# ── Error handler ─────────────────────────────────────────────────────────

async def error_handler(update: object, context):
    if isinstance(context.error, (NetworkError, TimedOut)):
        logger.warning(f"Network error (ignored): {context.error}")
        return
    logger.error(f"Unhandled error: {context.error}", exc_info=context.error)


# ── post_init: load managers from DB ──────────────────────────────────────

async def post_init(application: Application):
    await db.init_db()
    await db.load_payment_settings()  # DB থেকে MFS/Exchanger settings load
    mgrs = await db.get_managers()
    for m in mgrs:
        if m not in config.MANAGERS:
            config.MANAGERS.append(m)
    logger.info(f"✅ DB ready. Loaded {len(mgrs)} managers.")


# ── main ──────────────────────────────────────────────────────────────────

def main():
    req = HTTPXRequest(
        connection_pool_size=8,
        read_timeout=30.0,
        write_timeout=30.0,
        connect_timeout=30.0,
    )
    app = (
        Application.builder()
        .token(config.TOKEN)
        .request(req)
        .post_init(post_init)
        .build()
    )

    # ── User commands ──────────────────────────────────
    app.add_handler(CommandHandler('start',           user_cmds.cmd_start))
    app.add_handler(CommandHandler('result',          user_cmds.cmd_result))
    app.add_handler(CommandHandler('cancel_match',    user_cmds.cmd_cancel_match))
    app.add_handler(CommandHandler('wallet',          user_cmds.cmd_wallet))
    app.add_handler(CommandHandler('profile',         user_cmds.cmd_profile))
    app.add_handler(CommandHandler('stats',           user_cmds.cmd_stats))
    app.add_handler(CommandHandler('mymatches',       user_cmds.cmd_mymatches))
    app.add_handler(CommandHandler('withdraw_status', user_cmds.cmd_withdraw_status))
    app.add_handler(CommandHandler('support',         user_cmds.cmd_support))
    app.add_handler(CommandHandler('mytickets',       user_cmds.cmd_mytickets))
    app.add_handler(CommandHandler('treply',          user_cmds.cmd_treply))
    app.add_handler(CommandHandler('closeticket',     user_cmds.cmd_closeticket))
    app.add_handler(CommandHandler('language',        user_cmds.cmd_language))
    app.add_handler(CommandHandler('lang',            user_cmds.cmd_language))

    # ── Admin-only commands ────────────────────────────
    app.add_handler(CommandHandler('addmanager',      admin_cmds.cmd_addmanager))
    app.add_handler(CommandHandler('removemanager',   admin_cmds.cmd_removemanager))
    app.add_handler(CommandHandler('listmanagers',    admin_cmds.cmd_listmanagers))
    app.add_handler(CommandHandler('setdeprate',      admin_cmds.cmd_setdeprate))
    app.add_handler(CommandHandler('setwitrate',      admin_cmds.cmd_setwitrate))
    app.add_handler(CommandHandler('setrules',        admin_cmds.cmd_setrules))
    app.add_handler(CommandHandler('settutorial',     admin_cmds.cmd_settutorial))
    app.add_handler(CommandHandler('report',          admin_cmds.cmd_report))
    app.add_handler(CommandHandler('backup',          admin_cmds.cmd_backup))
    app.add_handler(CommandHandler('daily',           admin_cmds.cmd_report))
    app.add_handler(CommandHandler('userinfo',        admin_cmds.cmd_userinfo))
    app.add_handler(CommandHandler('banuser',         admin_cmds.cmd_banuser))
    app.add_handler(CommandHandler('unbanuser',       admin_cmds.cmd_unbanuser))
    app.add_handler(CommandHandler('addbalance',      admin_cmds.cmd_addbalance))
    app.add_handler(CommandHandler('deductbalance',   admin_cmds.cmd_deductbalance))
    app.add_handler(CommandHandler('broadcast',       admin_cmds.cmd_broadcast))
    app.add_handler(CommandHandler('message_user',    admin_cmds.cmd_message_user))

    # ── Staff commands ─────────────────────────────────
    app.add_handler(CommandHandler('pending_results',   admin_cmds.cmd_pending_results))
    app.add_handler(CommandHandler('pending_deposits',  admin_cmds.cmd_pending_deposits))
    app.add_handler(CommandHandler('pending_withdrawals', admin_cmds.cmd_pending_withdrawals))
    app.add_handler(CommandHandler('create_tourney',    admin_cmds.cmd_create_tourney))
    app.add_handler(CommandHandler('generate_round',    admin_cmds.cmd_generate_round))
    app.add_handler(CommandHandler('set_mfs_number',    admin_cmds.cmd_set_mfs_number))
    app.add_handler(CommandHandler('set_exc_uid',       admin_cmds.cmd_set_exc_uid))
    app.add_handler(CommandHandler('set_exc_note',      admin_cmds.cmd_set_exc_note))
    app.add_handler(CommandHandler('payment_info',      admin_cmds.cmd_payment_info))
    app.add_handler(CommandHandler('restore',           admin_cmds.cmd_restore))
    app.add_handler(CommandHandler('announce_tourney',  admin_cmds.cmd_announce_tourney))
    app.add_handler(CommandHandler('tourney_status',    admin_cmds.cmd_tourney_status))
    app.add_handler(CommandHandler('close_tourney',     admin_cmds.cmd_close_tourney))
    app.add_handler(CommandHandler('set_ign',           admin_cmds.cmd_set_ign))
    app.add_handler(CommandHandler('cancel_match_admin',admin_cmds.cmd_cancel_match_admin))
    app.add_handler(CommandHandler('force_win',         admin_cmds.cmd_force_win))
    app.add_handler(CommandHandler('reset_state',       admin_cmds.cmd_reset_state))
    app.add_handler(CommandHandler('set_balance',       admin_cmds.cmd_set_balance))
    app.add_handler(CommandHandler('match_info',        admin_cmds.cmd_match_info))
    app.add_handler(CommandHandler('admin_help',        admin_cmds.cmd_admin_help))
    app.add_handler(CommandHandler('free_mode',         admin_cmds.cmd_free_mode))
    app.add_handler(CommandHandler('edit_profile',      user_cmds.cmd_edit_profile))
    app.add_handler(MessageHandler(filters.Document.MimeType('application/x-sqlite3'), handlers.document_handler))
    app.add_handler(MessageHandler(filters.Document.ALL, handlers.document_handler))

    # ── Message & callback handlers ────────────────────
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handlers.text_handler))
    app.add_handler(MessageHandler(filters.PHOTO, handlers.photo_handler))
    app.add_handler(CallbackQueryHandler(handlers.callback_handler))
    app.add_error_handler(error_handler)

    # ── Background jobs ────────────────────────────────
    jq = app.job_queue
    if jq:
        # Daily backup at 3:00 AM
        jq.run_daily(admin_cmds.job_daily_backup, time=dtime(3, 0))
        logger.info("✅ JobQueue: daily backup scheduled.")

    logger.info("🚀 Bot starting...")
    app.run_polling(
        allowed_updates=["message", "callback_query"],
        drop_pending_updates=False,
    )


if __name__ == '__main__':
    main()
