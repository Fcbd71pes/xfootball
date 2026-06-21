import os

def add_backup_command():
    print("🚀 /backup কমান্ড যুক্ত করা হচ্ছে...\n")
    
    # --- ১. admin_cmds.py তে ফাংশন যোগ করা ---
    admin_file = 'admin_cmds.py'
    if os.path.exists(admin_file):
        with open(admin_file, 'r', encoding='utf-8') as f:
            admin_content = f.read()
        
        backup_cmd_code = """
@_admin_only
async def cmd_backup(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("⏳ ডাটাবেজ ব্যাকআপ তৈরি হচ্ছে, দয়া করে অপেক্ষা করুন...")
    from datetime import datetime
    dest = f"manual_backup_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.db"
    try:
        await db.safe_backup(dest)
        import os
        with open(dest, 'rb') as doc:
            await context.bot.send_document(
                chat_id=update.effective_user.id,
                document=doc,
                filename=dest,
                caption="✅ আপনার ডাটাবেজ ব্যাকআপ সফলভাবে সম্পন্ন হয়েছে!"
            )
        os.remove(dest)  # সেন্ড করার পর সার্ভার থেকে মুছে ফেলবে যাতে স্টোরেজ না ভরে
    except Exception as e:
        await update.message.reply_text(f"❌ ব্যাকআপ নিতে সমস্যা হয়েছে: {e}")
"""
        if "async def cmd_backup" not in admin_content:
            admin_content += "\n" + backup_cmd_code
            with open(admin_file, 'w', encoding='utf-8') as f:
                f.write(admin_content)
            print("✅ admin_cmds.py তে ব্যাকআপ ফাংশন যুক্ত হয়েছে।")
        else:
            print("⚠️ ব্যাকআপ ফাংশন আগে থেকেই আছে।")
    else:
        print("❌ admin_cmds.py ফাইলটি পাওয়া যায়নি!")

    # --- ২. main.py তে কমান্ড হ্যান্ডলার যোগ করা ---
    main_file = 'main.py'
    if os.path.exists(main_file):
        with open(main_file, 'r', encoding='utf-8') as f:
            main_content = f.read()

        handler_code = "app.add_handler(CommandHandler('backup',          admin_cmds.cmd_backup))"
        target_line = "app.add_handler(CommandHandler('report',          admin_cmds.cmd_report))"

        if "CommandHandler('backup'" not in main_content and target_line in main_content:
            main_content = main_content.replace(target_line, target_line + "\n    " + handler_code)
            with open(main_file, 'w', encoding='utf-8') as f:
                f.write(main_content)
            print("✅ main.py তে ব্যাকআপ হ্যান্ডলার যুক্ত হয়েছে।")
        else:
            print("⚠️ main.py তে ব্যাকআপ হ্যান্ডলার আগে থেকেই আছে বা সঠিক জায়গা পাওয়া যায়নি।")
    else:
        print("❌ main.py ফাইলটি পাওয়া যায়নি!")

    print("\n🎉 কাজ শেষ! এখন আপনি যেকোনো সময় /backup কমান্ড ব্যবহার করতে পারবেন।")

if __name__ == "__main__":
    add_backup_command()
    