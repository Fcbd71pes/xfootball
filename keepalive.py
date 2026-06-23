#!/usr/bin/env python3
import subprocess, time, logging, threading, sys
from datetime import datetime

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger(__name__)
RESTART_DELAY = 5

def run_subprocess(script, label):
    while True:
        logger.info(f"🚀 Starting {label}...")
        try:
            proc = subprocess.Popen(
                [sys.executable, '-u', script],
                stdout=sys.stdout, stderr=sys.stderr
            )
            proc.wait()
        except Exception as e:
            logger.error(f"❌ {label} error: {e}")
        logger.warning(f"⚠️ {label} stopped. Restarting in {RESTART_DELAY}s...")
        time.sleep(RESTART_DELAY)

if __name__ == '__main__':
    logger.info("=" * 40)
    logger.info(f"eFootball Suite — {datetime.now():%Y-%m-%d %H:%M}")
    logger.info("=" * 40)

    # Admin bot thread এ
    threading.Thread(target=run_subprocess, args=('admin_bot.py', 'Admin Bot'), daemon=True).start()

    # Main bot thread এ
    threading.Thread(target=run_subprocess, args=('main.py', 'Main Bot'), daemon=True).start()

    # Web server main thread এ — Render port bind এটাই করবে
    run_subprocess('admin_panel.py', 'Web Server')
