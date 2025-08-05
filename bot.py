import logging
from typing import Dict

from openai import OpenAI
from sqlalchemy.orm import sessionmaker, Session
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ConversationHandler, ContextTypes

from config import settings
from db import Program, engine

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

client = OpenAI(api_key=settings.OPEN_AI_KEY)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)

CHOOSING, BACKGROUND, INTERESTS, ASK = range(4)


def get_programs() -> Dict[str, Program]:
    session: Session = SessionLocal()
    try:
        slugs = settings.PROGRAM_SLUGS
        progs = session.query(Program).filter(Program.slug.in_(slugs)).all()
        return {p.slug: p for p in progs}
    finally:
        session.close()


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    keyboard = [["Рекомендовать программу"], ["Спросить о программе"]]
    await update.message.reply_text(
        "Привет! Выберите действие:",
        reply_markup=ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
    )
    return CHOOSING


async def recommendation_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data.clear()
    await update.message.reply_text(
        "Расскажите, пожалуйста, о вашем академическом фоне:",
        reply_markup=ReplyKeyboardRemove()
    )
    return BACKGROUND


async def background(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data['background'] = update.message.text
    await update.message.reply_text("Какие темы и направления вас интересуют, какие цели после магистратуры?")
    return INTERESTS


async def interests(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data['interests'] = update.message.text
    programs = get_programs()
    bg = context.user_data['background']
    interests_text = context.user_data['interests']
    messages = [{"role": "system", "content": "Вы эксперт по магистерским программам ITMO."},
                {"role": "user",
                 "content": f"Академический фон абитуриента: {bg}\nИнтересы и цели: {interests_text}\n"}]
    for prog in programs.values():
        attrs = {
            'slug': prog.slug,
            'id': prog.id,
            'title': prog.title,
            'exam_dates': prog.exam_dates,
            'admission_quotas': prog.admission_quotas,
            'study_plan_text': prog.study_plan_text[:-2000] or ''
        }
        info = '\n'.join(f"{k}: {v}" for k, v in attrs.items())
        messages.append({"role": "user", "content": info})
    messages.append({"role": "user", "content": "Порекомендуй программу и предложи ключевые элективы."})
    try:
        resp = client.chat.completions.create(model="gpt-4", messages=messages)
        answer = resp.choices[0].message.content.strip()
    except Exception as e:
        logger.error("OpenAI error: %s", e)
        await update.message.reply_text("Ошибка при получении рекомендации. Попробуйте позже.")
        return ConversationHandler.END
    await update.message.reply_text(answer)
    keyboard = [["Рекомендовать программу"], ["Спросить о программе"]]
    await update.message.reply_text(
        "Выберите действие:",
        reply_markup=ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
    )
    return CHOOSING


async def ask_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data.clear()
    await update.message.reply_text("Введите ваш вопрос по программе:", reply_markup=ReplyKeyboardRemove())
    return ASK


async def ask_question(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    question = update.message.text
    programs = get_programs()
    info = ''
    for prog in programs.values():
        attrs = {
            'slug': prog.slug,
            'id': prog.id,
            'title': prog.title,
            'exam_dates': prog.exam_dates,
            'admission_quotas': prog.admission_quotas,
            'study_plan_url': prog.study_plan_url,
        }
        info += '\n'.join(f"{k}: {v}" for k, v in attrs.items()) + "\n---\n"
    prompt = f"{info}Вопрос: {question}"
    messages = [{"role": "system",
                 "content": "Вы эксперт по магистерским программам ITMO. Если вопрос не связан с программой, скажите об этом."},
                {"role": "user", "content": prompt}]
    try:
        resp = client.chat.completions.create(model="gpt-4", messages=messages)
        answer = resp.choices[0].message.content.strip()
    except Exception as e:
        logger.error("OpenAI error: %s", e)
        await update.message.reply_text("Ошибка при обработке вопроса. Попробуйте позже.")
        return ConversationHandler.END
    await update.message.reply_text(answer)
    keyboard = [["Рекомендовать программу"], ["Спросить о программе"]]
    await update.message.reply_text(
        "Выберите действие:",
        reply_markup=ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
    )
    return CHOOSING


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("Всего доброго!", reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END


def main():
    app = ApplicationBuilder().token(settings.TELEGRAM_BOT_TOKEN).build()
    conv = ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={
            CHOOSING: [
                MessageHandler(filters.Regex('^Рекомендовать программу$'), recommendation_start),
                MessageHandler(filters.Regex('^Спросить о программе$'), ask_start)
            ],
            BACKGROUND: [MessageHandler(filters.TEXT & ~filters.COMMAND, background)],
            INTERESTS: [MessageHandler(filters.TEXT & ~filters.COMMAND, interests)],
            ASK: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_question)]
        },
        fallbacks=[CommandHandler('cancel', cancel)]
    )
    app.add_handler(conv)
    app.run_polling()


if __name__ == '__main__':
    main()
