#!/usr/bin/env python3
# keepalive.py — main bot + admin bot + HTTP server
import subprocess, time, logging, threading, os, sys
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger(__name__)

RESTART_DELAY = 5

class PingHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b'eFootball Bot is running!')
    def log_message(self, *args):
        pass

def start_http_server():
    port = int(os.environ.get('PORT', 10000))
    server = HTTPServer(('0.0.0.0', port), PingHandler)
    logger.info(f"🌐 HTTP server on port {port}")
    server.serve_forever()

def run_subprocess(script, label):
    """আলাদা subprocess হিসেবে bot চালাও — crash হলে restart করো"""
    while True:
        logger.info(f"🚀 Starting {label}...")
        try:
            proc = subprocess.Popen(
                [sys.executable, '-u', script],
                stdout=sys.stdout,
                stderr=sys.stderr
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

    # HTTP server (Render port scan এর জন্য)
    threading.Thread(target=start_http_server, daemon=True).start()

    # Admin bot আলাদা thread এ subprocess হিসেবে
    threading.Thread(
        target=run_subprocess,
        args=('admin_bot.py', 'Admin Bot'),
        daemon=True
    ).start()

    # Main bot main thread এ
    run_subprocess('main.py', 'Main Bot')
