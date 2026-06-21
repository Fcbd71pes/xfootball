# utils.py
import html
from telegram import ReplyKeyboardMarkup, InlineKeyboardMarkup, InlineKeyboardButton, Update
from telegram.ext import ContextTypes
import db
import config
from lang import t


def esc(text) -> str:
    return html.escape(str(text)) if text else 'N/A'


def main_kb(lang: str = 'en') -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup([
        [t('btn_play', lang),    t('btn_wallet', lang)],
        [t('btn_profile', lang), t('btn_tourney', lang)],
        [t('btn_lb', lang),      t('btn_share', lang)],
        [t('btn_rules', lang),   t('btn_result', lang)],
        [t('btn_daily', lang), t('btn_tutorial', lang)],
    ], resize_keyboard=True)


def cancel_kb(lang: str = 'en') -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup([[t('btn_cancel', lang)]], resize_keyboard=True)


async def ensure_user(update: Update, referrer_id=None):
    obj = update.effective_user
    if not obj:
        return None
    await db.create_user(obj.id, obj.username or obj.first_name, referrer_id)
    u = await db.get_user(obj.id)
    if u and u.get('is_banned'):
        return None
    return u


async def check_channel(update: Update, context: ContextTypes.DEFAULT_TYPE, lang='en') -> bool:
    uid = update.effective_user.id
    if uid in config.ADMINS:
        return True
    try:
        m = await context.bot.get_chat_member(config.CHANNEL_ID, uid)
        if m.status in ('left', 'kicked'):
            kb = InlineKeyboardMarkup([[InlineKeyboardButton(
                t('join_channel_btn', lang),
                url=f'https://t.me/{config.CHANNEL_USERNAME}'
            )]])
            await update.effective_message.reply_text(t('join_channel_msg', lang), reply_markup=kb)
            return False
    except Exception:
        pass
    return True


def staff_ids() -> set:
    """All admin + manager IDs."""
    return set(config.ADMINS) | set(config.MANAGERS)
