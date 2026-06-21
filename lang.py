# lang.py  —  Bengali / English bilingual strings

STRINGS = {
    # ── Registration ──────────────────────────────────
    'choose_lang':        {'bn': '🌐 ভাষা বেছে নিন:', 'en': '🌐 Choose your language:'},
    'ask_ign':            {'bn': 'স্বাগতম! আপনার eFootball ইন-গেম নাম (IGN) পাঠান:', 'en': 'Welcome! Please send your eFootball in-game name (IGN):'},
    'ask_phone':          {'bn': '✅ এখন আপনার ফোন নম্বর পাঠান:', 'en': '✅ Now send your phone number:'},
    'reg_done_bonus':     {'bn': '✅ রেজিস্ট্রেশন সম্পন্ন! আপনি 10 TK বোনাস পেয়েছেন।', 'en': '✅ Registration complete! You got a 10 TK welcome bonus.'},
    'reg_done':           {'bn': '✅ রেজিস্ট্রেশন সম্পন্ন!', 'en': '✅ Registration complete!'},
    'welcome_back':       {'bn': '👋 আপনাকে স্বাগতম!', 'en': '👋 Welcome back!'},
    'banned':             {'bn': '❌ একাউন্ট ব্যান।', 'en': '❌ Account banned.'},
    'join_channel_msg':   {'bn': 'ব্যবহার করতে চ্যানেলে যোগ দিন।', 'en': 'Please join our channel to continue.'},
    'join_channel_btn':   {'bn': 'চ্যানেলে যোগ দিন', 'en': 'Join Channel'},
    'lang_set':           {'bn': '✅ ভাষা সেট হয়েছে।স্বাগতম! আপনার eFootball ইন-গেম নাম (IGN) পাঠান', 'en': '✅ Language updated.Welcome! Please send your eFootball in-game name (IGN)'},
    'register_first':     {'bn': '❌ /start করে রেজিস্ট্রেশন করুন।', 'en': '❌ Please /start and register first.'},

    # ── General ───────────────────────────────────────
    'cancelled':          {'bn': '✅ বাতিল হয়েছে।', 'en': '✅ Cancelled.'},
    'error':              {'bn': '❌ সমস্যা হয়েছে। আবার চেষ্টা করুন।', 'en': '❌ Something went wrong. Please try again.'},
    'invalid_number':     {'bn': '❌ সঠিক সংখ্যা দিন।', 'en': '❌ Please enter a valid number.'},
    'insufficient_bal':   {'bn': '❌ ব্যালেন্স অপর্যাপ্ত।', 'en': '❌ Insufficient balance.'},
    'use_menu':           {'bn': '❌ মেনু থেকে বেছে নিন।', 'en': '❌ Please use the menu.'},
    'no_permission':      {'bn': '❌ অনুমতি নেই।', 'en': '❌ No permission.'},

    # ── Wallet ────────────────────────────────────────
    'wallet_text':        {'bn': '💰 আপনার ওয়ালেট\n\n💵 উপলব্ধ: {avail:.2f} TK\n🔒 লক: {locked:.2f} TK\n📊 মোট: {total:.2f} TK',
                           'en': '💰 Your Wallet\n\n💵 Available: {avail:.2f} TK\n🔒 Locked: {locked:.2f} TK\n📊 Total: {total:.2f} TK'},
    'choose_dep_method':  {'bn': '💳 Deposit পদ্ধতি বেছে নিন:', 'en': '💳 Choose deposit method:'},
    'choose_wit_method':  {'bn': '💸 Withdrawal পদ্ধতি বেছে নিন:', 'en': '💸 Choose withdrawal method:'},
    'btn_mfs':            {'bn': '🇧🇩 Mobile Banking (BDT)', 'en': '🇧🇩 Mobile Banking (BDT)'},
    'btn_exchange':       {'bn': '🏦 Exchange (USDT)', 'en': '🏦 Exchange (USDT)'},

    # ── Mobile Banking Deposit ────────────────────────
    'mfs_select':         {'bn': '🇧🇩 কোন Mobile Banking?', 'en': '🇧🇩 Select Mobile Banking:'},
    'mfs_dep_inst':       {'bn': '💳 {name} Deposit\n\n📱 নম্বর: <code>{number}</code>\n\nউপরের নম্বরে {name} পাঠান।\nপরে TxID এবং পরিমাণ লিখুন:\n<code>TxID পরিমাণ</code>\nযেমন: <code>TX12345 500</code>',
                           'en': '💳 {name} Deposit\n\n📱 Number: <code>{number}</code>\n\nSend to the number above.\nThen reply: TxID Amount\nExample: <code>TX12345 500</code>'},
    'mfs_send_ss':        {'bn': '📸 এখন সফল লেনদেনের স্ক্রিনশট পাঠান:', 'en': '📸 Now send a screenshot of the transaction:'},
    'mfs_wrong_fmt':      {'bn': '❌ ফরম্যাট ভুল! TxID এবং পরিমাণ স্পেস দিয়ে লিখুন।\nযেমন: <code>TX12345 500</code>',
                           'en': '❌ Wrong format! Send: TxID Amount\nExample: <code>TX12345 500</code>'},
    'mfs_min_dep':        {'bn': '❌ সর্বনিম্ন {min:.0f} TK।', 'en': '❌ Minimum deposit is {min:.0f} TK.'},
    'dep_submitted':      {'bn': '✅ Deposit request জমা হয়েছে! Admin approve করবে।',
                           'en': '✅ Deposit request submitted! Admin will approve it.'},
    'dep_approved':       {'bn': '✅ {amount:.2f} TK আপনার ব্যালেন্সে যোগ হয়েছে!', 'en': '✅ {amount:.2f} TK added to your balance!'},
    'dep_rejected':       {'bn': '❌ Deposit request বাতিল হয়েছে। সমস্যা হলে /support দিন।',
                           'en': '❌ Deposit request rejected. Contact /support if needed.'},

    # ── Exchange Deposit ──────────────────────────────
    'exc_select':         {'bn': '🏦 কোন Exchange?', 'en': '🏦 Select Exchange:'},
    'exc_none_configured':{'bn': '❌ কোনো Exchange এখনো সেটআপ হয়নি। Admin-এ যোগাযোগ করুন।',
                           'en': '❌ No exchanges configured yet. Contact admin.'},
    'exc_dep_show_uid':   {'bn': '🏦 {name} Deposit\n\n🆔 আমাদের {uid_label}:\n<code>{our_uid}</code>\n\n📝 {note}\n\n💵 পরিমাণ লিখুন (USDT):\n📉 সর্বনিম্ন: {min_dep} USDT',
                           'en': '🏦 {name} Deposit\n\n🆔 Our {uid_label}:\n<code>{our_uid}</code>\n\n📝 {note}\n\nEnter amount (USDT):\n📉 Minimum: {min_dep} USDT'},
    'exc_ask_amount':     {'bn': '💵 কত USDT পাঠাচ্ছেন?', 'en': '💵 How much USDT are you sending?'},
    'exc_ask_uid':        {'bn': '✅ এখন আপনার {uid_label} লিখুন\n(যাচাইয়ের জন্য):',
                           'en': '✅ Now enter your {uid_label}\n(for verification):'},
    'exc_ask_ss':         {'bn': '📸 সফল লেনদেনের স্ক্রিনশট পাঠান:', 'en': '📸 Send a screenshot of the successful transaction:'},
    'exc_dep_submitted':  {'bn': '✅ Deposit request জমা হয়েছে!\n\n🏦 {name}\n💵 {usdt:.4f} USDT → {bdt:.2f} TK\n🆔 আপনার UID: {user_uid}\n\nAdmin verify করে approve করবে।',
                           'en': '✅ Deposit request submitted!\n\n🏦 {name}\n💵 {usdt:.4f} USDT → {bdt:.2f} TK\n🆔 Your UID: {user_uid}\n\nAdmin will verify and approve.'},
    'exc_dep_approved':   {'bn': '✅ {name} Deposit অনুমোদিত!\n💵 {usdt:.4f} USDT = {bdt:.2f} TK ব্যালেন্সে যোগ হয়েছে।',
                           'en': '✅ {name} deposit approved!\n💵 {usdt:.4f} USDT = {bdt:.2f} TK added to balance.'},
    'exc_dep_rejected':   {'bn': '❌ {name} Deposit বাতিল। সমস্যা হলে /support দিন।',
                           'en': '❌ {name} deposit rejected. Contact /support if needed.'},
    'exc_uid_not_set':    {'bn': '⚠️ এই Exchange এখনো সেটআপ হয়নি।', 'en': '⚠️ This exchange is not configured yet.'},
    'exc_min_usdt':       {'bn': '❌ সর্বনিম্ন {min} USDT।', 'en': '❌ Minimum {min} USDT.'},

    # ── Withdrawal ────────────────────────────────────
    'wit_mfs_select':     {'bn': '🇧🇩 কোন Mobile Banking-এ পাঠাবেন?', 'en': '🇧🇩 Which Mobile Banking to withdraw to?'},
    'wit_exc_select':     {'bn': '🏦 কোন Exchange-এ USDT পাঠাবেন?', 'en': '🏦 Which exchange to receive USDT?'},
    'wit_ask_amount_mfs': {'bn': 'কত টাকা Withdraw করতে চান?\n💰 উপলব্ধ: {avail:.2f} TK\n📉 সর্বনিম্ন: {min:.0f} TK',
                           'en': 'How much TK to withdraw?\n💰 Available: {avail:.2f} TK\n📉 Minimum: {min:.0f} TK'},
    'wit_ask_amount_exc': {'bn': 'কত USDT Withdraw করতে চান?\n💰 উপলব্ধ: {avail:.2f} TK ≈ {usdt_avail:.4f} USDT\n📉 সর্বনিম্ন: {min} USDT',
                           'en': 'How much USDT to withdraw?\n💰 Available: {avail:.2f} TK ≈ {usdt_avail:.4f} USDT\n📉 Minimum: {min} USDT'},
    'wit_ask_account':    {'bn': 'আপনার {method} নম্বর/UID লিখুন:', 'en': 'Enter your {method} number/UID:'},
    'wit_submitted':      {'bn': '✅ Withdraw request জমা হয়েছে!\n💰 {amount} লক করা হয়েছে। Admin পাঠিয়ে দেবে।',
                           'en': '✅ Withdrawal submitted!\n💰 {amount} locked. Admin will process it.'},
    'wit_approved':       {'bn': '✅ Withdrawal অনুমোদিত! {amount} পাঠানো হয়েছে।', 'en': '✅ Withdrawal approved! {amount} has been sent.'},
    'wit_rejected':       {'bn': '❌ Withdrawal বাতিল। টাকা ফেরত দেওয়া হয়েছে।', 'en': '❌ Withdrawal rejected. Amount refunded.'},
    'wit_min':            {'bn': '❌ সর্বনিম্ন {min} TK।', 'en': '❌ Minimum {min} TK.'},
    'wit_min_usdt':       {'bn': '❌ সর্বনিম্ন {min} USDT।', 'en': '❌ Minimum {min} USDT.'},

    # ── Match ─────────────────────────────────────────
    'match_select_fee':   {'bn': 'ম্যাচের ধরন বেছে নিন:', 'en': 'Select match fee:'},
    'searching':          {'bn': '⏳ প্রতিপক্ষ খোঁজা হচ্ছে...', 'en': '⏳ Searching for an opponent...'},
    'match_found_p1':     {'bn': '🔥 প্রতিপক্ষ পেয়েছেন! vs {opp}\n\n🎮 গেমে রুম তৈরি করুন এবং 8-ডিজিটের রুম কোড এখানে পাঠান।',
                           'en': '🔥 Opponent found! vs {opp}\n\n🎮 Create a room in-game and send the 8-digit room code here.'},
    'match_found_p2':     {'bn': '🔥 প্রতিপক্ষ পেয়েছেন! vs {opp}\n\n⏳ রুম কোডের জন্য অপেক্ষা করুন...',
                           'en': '🔥 Opponent found! vs {opp}\n\n⏳ Waiting for the room code...'},
    'room_code_fwd':      {'bn': '🎮 ম্যাচ শুরু!\n\n🔑 রুম কোড: <code>{code}</code>\n\n⚠️ আপনার কাছে সর্বোচ্চ {mins} মিনিট আছে স্ক্রিনশট জমা দিতে। জাল স্ক্রিনশট দিলে স্থায়ী ব্যান হবে।',
                           'en': '🎮 Match started!\n\n🔑 Room code: <code>{code}</code>\n\n⚠️ You have strictly {mins} minutes to finish and submit. Fake screenshots = permanent ban.'},
    'room_code_confirm':  {'bn': '✅ রুম কোড পাঠানো হয়েছে!\n\n⚠️ আপনার কাছে সর্বোচ্চ {mins} মিনিট আছে। জাল স্ক্রিনশট দিলে স্থায়ী ব্যান হবে।',
                           'en': '✅ Room code sent!\n\n⚠️ You have strictly {mins} minutes to finish. Fake screenshots = permanent ban.'},
    'ss_ask':             {'bn': '📸 ম্যাচ #{mid} — জয়ের স্পষ্ট স্ক্রিনশট পাঠান।', 'en': '📸 Match #{mid} — send a clear screenshot of your win.'},
    'ss_received':        {'bn': '✅ স্ক্রিনশট গৃহীত। Admin verify করছে...', 'en': '✅ Screenshot received. Admin is verifying...'},
    'opp_submitted':      {'bn': '📸 প্রতিপক্ষ স্ক্রিনশট জমা দিয়েছে। অপেক্ষা করুন...', 'en': '📸 Opponent submitted. Waiting for admin...'},
    'match_won':          {'bn': '🏆 ম্যাচ #{mid} জিতেছেন! পুরস্কার: {prize:.2f} TK', 'en': '🏆 You won match #{mid}! Prize: {prize:.2f} TK'},
    'match_lost':         {'bn': '😔 ম্যাচ #{mid} হেরেছেন।', 'en': '😔 You lost match #{mid}.'},
    'no_active_match':    {'bn': '❌ কোনো চলমান ম্যাচ নেই।', 'en': '❌ No active match found.'},
    'already_submitted':  {'bn': '❌ ইতিমধ্যে স্ক্রিনশট জমা দিয়েছেন।', 'en': '❌ You already submitted a screenshot.'},
    'match_not_active':   {'bn': '❌ এই ম্যাচ চলছে না।', 'en': '❌ This match is not active.'},
    'already_in_queue':   {'bn': '❌ ইতিমধ্যে ম্যাচ খুঁজছেন।', 'en': '❌ You are already searching.'},
    'opponent_found_cb':  {'bn': '✅ প্রতিপক্ষ পাওয়া গেছে! ইনবক্স চেক করুন।', 'en': '✅ Opponent found! Check your inbox.'},
    'warning_10min':      {'bn': '⚠️ ম্যাচ #{mid} — মাত্র 5 মিনিট বাকি! দ্রুত /result দিন।',
                           'en': '⚠️ Match #{mid} — only 5 minutes left! Submit /result now.'},
    'autowin':            {'bn': '🏆 Auto-Win! প্রতিপক্ষ সময়মতো স্ক্রিনশট দেয়নি। পুরস্কার: {prize:.2f} TK',
                           'en': '🏆 Auto-Win! Opponent missed the deadline. Prize: {prize:.2f} TK'},
    'autolose':           {'bn': '❌ সময়মতো স্ক্রিনশট না দেওয়ায় পরাজিত।', 'en': '❌ You lost — screenshot not submitted in time.'},
    'auto_cancel':        {'bn': '⚪ ম্যাচ #{mid} বাতিল (উভয়েই স্ক্রিনশট দেননি)। ফি ফেরত দেওয়া হয়েছে।',
                           'en': '⚪ Match #{mid} cancelled — no one submitted. Fee refunded.'},

    # ── Profile / Stats ───────────────────────────────
    'profile_text':       {'bn': '👤 প্রোফাইল\n\nIGN: {ign}\nফোন: {phone}\n\n💰 উপলব্ধ: {avail:.2f} TK\n🔒 লক: {locked:.2f} TK\n⭐ ELO: {elo}\n🏆 জয়: {wins} | ❌ পরাজয়: {losses}\n\n📅 যোগদান: {joined}',
                           'en': '👤 Profile\n\nIGN: {ign}\nPhone: {phone}\n\n💰 Available: {avail:.2f} TK\n🔒 Locked: {locked:.2f} TK\n⭐ ELO: {elo}\n🏆 Won: {wins} | ❌ Lost: {losses}\n\n📅 Joined: {joined}'},
    'stats_text':         {'bn': '📊 পরিসংখ্যান\n\n🎮 মোট: {total} | জয়: {wins} | পরাজয়: {losses}\n📈 জয়ের হার: {wr:.1f}%\n⭐ ELO: {elo}',
                           'en': '📊 Statistics\n\n🎮 Total: {total} | Won: {wins} | Lost: {losses}\n📈 Win rate: {wr:.1f}%\n⭐ ELO: {elo}'},
    'lb_title':           {'bn': '🏆 টপ ১০ লিডারবোর্ড\n\n', 'en': '🏆 Top 10 Leaderboard\n\n'},
    'history_title':      {'bn': '📋 শেষ ১০ ম্যাচ\n\n', 'en': '📋 Last 10 matches\n\n'},
    'no_history':         {'bn': '❌ এখনো কোনো ম্যাচ খেলেননি।', 'en': '❌ No matches played yet.'},
    'referral_text':      {'bn': '🔗 রেফার লিংক:\n{link}\nপ্রতি রেফারে {bonus} TK!', 'en': '🔗 Referral link:\n{link}\nEarn {bonus} TK per referral!'},
    'referral_bonus':     {'bn': '🎉 রেফার বোনাস: {bonus:.2f} TK পেয়েছেন!', 'en': '🎉 Referral bonus: earned {bonus:.2f} TK!'},

    # ── Support / Ticket ──────────────────────────────
    'support_help':       {'bn': '📞 সাপোর্ট\n\n/support <বিষয়> — টিকেট খুলুন\n/mytickets — টিকেট দেখুন',
                           'en': '📞 Support\n\n/support <issue> — open a ticket\n/mytickets — view tickets'},
    'ticket_opened':      {'bn': '✅ টিকেট #{id} খোলা হয়েছে। Admin রিপ্লাই করবে।', 'en': '✅ Ticket #{id} opened. Admin will reply.'},
    'ticket_reply_recv':  {'bn': '📨 টিকেট #{id} — Admin reply:\n\n{msg}\n\nReply: /treply {id} <বার্তা>',
                           'en': '📨 Ticket #{id} — Admin reply:\n\n{msg}\n\nReply: /treply {id} <message>'},
    'no_tickets':         {'bn': '❌ কোনো টিকেট নেই।', 'en': '❌ No tickets found.'},
    'ticket_sent':        {'bn': '✅ বার্তা পাঠানো হয়েছে।', 'en': '✅ Message sent.'},
    'ticket_closed':      {'bn': '✅ টিকেট বন্ধ করা হয়েছে।', 'en': '✅ Ticket closed.'},

    # ── Tournament ────────────────────────────────────
    'tourney_none':       {'bn': '❌ এখন কোনো টুর্নামেন্ট নেই।', 'en': '❌ No active tournaments.'},
    'tourney_joined':     {'bn': '✅ টুর্নামেন্টে যোগ দিয়েছেন!', 'en': '✅ Successfully joined the tournament!'},
    'tourney_full':       {'bn': '❌ স্লট ফুল।', 'en': '❌ Tournament is full.'},
    'tourney_closed':     {'bn': '❌ টুর্নামেন্ট বন্ধ।', 'en': '❌ Tournament is closed.'},
    'tourney_already':    {'bn': '❌ ইতিমধ্যে যোগ দিয়েছেন।', 'en': '❌ Already joined.'},
    'tourney_champion':   {'bn': '🏆 অভিনন্দন! চ্যাম্পিয়ন!\n\n💰 পুরস্কার: {prize:.2f} TK',
                           'en': '🏆 Congratulations! You are the Champion!\n\n💰 Prize: {prize:.2f} TK'},

    # ── Cancel match ──────────────────────────────────
    'cancel_req_sent':    {'bn': '✅ Cancel request পাঠানো হয়েছে।', 'en': '✅ Cancel request sent.'},
    'cancel_opp_notify':  {'bn': '⚠️ প্রতিপক্ষ ম্যাচ বাতিল করতে চাইছে।\n✅ /cancel_match — সম্মত হন\n❌ উপেক্ষা করুন — চালিয়ে যান',
                           'en': '⚠️ Opponent wants to cancel.\n✅ /cancel_match — agree\n❌ Ignore — keep playing'},
    'cancel_already':     {'bn': '⏳ আগেই request পাঠিয়েছেন।', 'en': '⏳ Already sent a cancel request.'},
    'match_cancelled_ok': {'bn': '✅ ম্যাচ বাতিল। ফি ফেরত দেওয়া হয়েছে।', 'en': '✅ Match cancelled. Fee refunded.'},

    # ── Menu buttons ──────────────────────────────────
    'btn_play':       {'bn': '🎮 Play 1v1', 'en': '🎮 Play 1v1'},
    'btn_wallet':     {'bn': '💰 Wallet', 'en': '💰 Wallet'},
    'btn_profile':    {'bn': '📋 Profile', 'en': '📋 Profile'},
    'btn_tourney':    {'bn': '⚔️ Tournaments', 'en': '⚔️ Tournaments'},
    'btn_lb':         {'bn': '🏆 Leaderboard', 'en': '🏆 Leaderboard'},
    'btn_share':      {'bn': '🔗 Share & Earn', 'en': '🔗 Share & Earn'},
    'btn_rules':      {'bn': '📜 Rules', 'en': '📜 Rules'},
    'btn_lang':       {'bn': '🌐 Language', 'en': '🌐 Language'},
    'btn_result':     {'bn': '📸 Result', 'en': '📸 Result'},
    'btn_cancel':     {'bn': '❌ Cancel', 'en': '❌ Cancel'},
    'btn_support':    {'bn': '📞 Support', 'en': '📞 Support'},
    'btn_daily':      {'bn': '🎁 Daily Bonus', 'en': '🎁 Daily Bonus'},
    'btn_tutorial':   {'bn': '📖 How to Play', 'en': '📖 How to Play'},
    'daily_claimed':  {'bn': '✅ আপনি আজকের {amount} TK বোনাস পেয়েছেন!', 'en': '✅ Daily bonus claimed: {amount} TK!'},
    'daily_already':  {'bn': '❌ আপনি আজ ইতিমধ্যে বোনাস নিয়েছেন। আগামীকাল চেষ্টা করুন।', 'en': '❌ Already claimed today. Try tomorrow.'},
    'mega_ref_bonus': {'bn': '🎉 মেগা বোনাস! ১০টি রেফার সম্পন্ন করায় এক্সট্রা ৫০ TK পেলেন!', 'en': '🎉 Mega Bonus! 50 TK added for 10 referrals!'},
    'tutorial_text':  {'bn': '🎮 <b>কীভাবে খেলবেন:</b>\n১. <b>Play 1v1</b> এ ক্লিক করে ফি সিলেক্ট করুন।\n২. প্রতিপক্ষ পেলে গেমে রুম বানিয়ে কোড দিন।\n৩. ম্যাচ শেষে <b>Result</b> এ ক্লিক করে জয়ের স্ক্রিনশট দিন।', 'en': '🎮 <b>How to Play:</b>\n1. Click <b>Play 1v1</b> & select fee.\n2. Share room code.\n3. Submit win screenshot in <b>Result</b>.'},
}


def t(key: str, lang: str = 'en', **kwargs) -> str:
    lang = lang if lang in ('bn', 'en') else 'en'
    entry = STRINGS.get(key, {})
    text = entry.get(lang) or entry.get('en') or f'[{key}]'
    if kwargs:
        try:
            text = text.format(**kwargs)
        except (KeyError, ValueError):
            pass
    return text
