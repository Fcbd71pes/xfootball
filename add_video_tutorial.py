import os
import re

def add_video_tutorial():
    print("🎥 ভিডিও টিউটোরিয়াল সিস্টেম ইনস্টল করা হচ্ছে...\n")

    # --- ১. user_cmds.py আপডেট করা (ভিডিও সেন্ড করার লজিক) ---
    user_file = 'user_cmds.py'
    if os.path.exists(user_file):
        with open(user_file, 'r', encoding='utf-8') as f:
            content = f.read()

        new_tutorial_cmd = """async def cmd_tutorial(update, context):
    from utils import ensure_user
    from lang import t
    import db
    user = await ensure_user(update)
    if not user: return
    lang = user.get('lang', 'en')
    text = t('tutorial_text', lang)
    
    # ডাটাবেজ থেকে ভিডিও আইডি নেওয়া
    video_id = await db.get_setting('tutorial_video_id')
    
    if video_id:
        try:
            await context.bot.send_video(
                chat_id=update.effective_chat.id, 
                video=video_id, 
                caption=text, 
                parse_mode='HTML'
            )
            return
        except Exception as e:
            pass # ভিডিও পাঠাতে সমস্যা হলে শুধু টেক্সট পাঠাবে
            
    await update.message.reply_text(text, parse_mode='HTML')
"""

        # আগের cmd_tutorial রিপ্লেস করা (যদি থাকে)
        if "async def cmd_tutorial" in content:
            content = re.sub(r"async def cmd_tutorial\(update, context\):.*?(?=\n\n|$)", new_tutorial_cmd, content, flags=re.DOTALL)
        else:
            content += "\n" + new_tutorial_cmd

        with open(user_file, 'w', encoding='utf-8') as f:
            f.write(content)
        print("✅ ইউজারদের ভিডিও সেন্ড করার অপশন যুক্ত হয়েছে।")

    # --- ২. admin_cmds.py আপডেট করা (ভিডিও সেভ করার কমান্ড) ---
    admin_file = 'admin_cmds.py'
    if os.path.exists(admin_file):
        with open(admin_file, 'r', encoding='utf-8') as f:
            admin_content = f.read()

        admin_tut_cmd = """
@_admin_only
async def cmd_settutorial(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.reply_to_message or not update.message.reply_to_message.video:
        return await update.message.reply_text("❌ আপনাকে প্রথমে বটকে একটি ভিডিও পাঠাতে হবে, তারপর সেই ভিডিওতে রিপ্লাই করে /settutorial লিখতে হবে।")
    
    file_id = update.message.reply_to_message.video.file_id
    await db.set_setting('tutorial_video_id', file_id)
    await update.message.reply_text("✅ চমৎকার! টিউটোরিয়াল ভিডিও সফলভাবে ডাটাবেজে সেভ হয়েছে। এখন ইউজাররা 'How to Play' তে ক্লিক করলেই এই ভিডিওটি দেখতে পাবে।")
"""
        if "cmd_settutorial" not in admin_content:
            admin_content += "\n" + admin_tut_cmd
            with open(admin_file, 'w', encoding='utf-8') as f:
                f.write(admin_content)
            print("✅ এডমিন কমান্ড /settutorial যুক্ত হয়েছে।")

    # --- ৩. main.py আপডেট করা (কমান্ড হ্যান্ডলার) ---
    main_file = 'main.py'
    if os.path.exists(main_file):
        with open(main_file, 'r', encoding='utf-8') as f:
            main_content = f.read()

        if "'settutorial'" not in main_content:
            main_content = main_content.replace(
                "app.add_handler(CommandHandler('setrules',        admin_cmds.cmd_setrules))",
                "app.add_handler(CommandHandler('setrules',        admin_cmds.cmd_setrules))\n    app.add_handler(CommandHandler('settutorial',     admin_cmds.cmd_settutorial))"
            )
            with open(main_file, 'w', encoding='utf-8') as f:
                f.write(main_content)
            print("✅ মেইন ফাইলে কমান্ড হ্যান্ডলার অ্যাক্টিভ করা হয়েছে।")

    print("\n🎉 কাজ শেষ! এখন আপনি নিজেই ভিডিও আপলোড করে সেট করতে পারবেন।")

if __name__ == "__main__":
    add_video_tutorial()