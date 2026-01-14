import asyncio
import logging
import gspread
import json
from telegram import Update, ReplyKeyboardRemove, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, ConversationHandler, CallbackQueryHandler
from telegram.error import TelegramError, BadRequest
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from datetime import datetime
import os


# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Conversation states
(NAME, LASTNAME, GROUP, FACULTY, MEETING, DATE, GROUP_MEMBERS, WERE, WHY_NOT, HANDMAN, ORGANIZATIONS, WHERE_1, DOPS_1,
 MOMENTS, WHERE_2, TOTALITY, DOPS_2, COORD_1, DOING1, SANTA, DOPS_3, COORD_2, DOING2,
 PLUSES, MINUSES, TOTAL, COMMENTS, PHOTOS) = range(28)


# Google Sheets setup
SCOPES = [
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/drive'
]


class GoogleSheetsManager:
    def __init__(self, credentials_file='credentials.json', spreadsheet_name='Telegram Bot Data'):
        self.credentials_file = credentials_file
        self.spreadsheet_name = spreadsheet_name
        self.sheet = None
        self.headers = []
        self.setup_sheets()

    def setup_sheets(self):
        """Initialize Google Sheets connection"""
        try:
            if not os.path.exists(self.credentials_file):
                self.create_credentials_template()
                raise FileNotFoundError(
                    f"Credentials file '{self.credentials_file}' not found. "
                    f"A template has been created. Please fill it with your Google Service Account credentials."
                )

            creds = Credentials.from_service_account_file(self.credentials_file, scopes=SCOPES)
            client = gspread.authorize(creds)

            # Try to open existing spreadsheet or create new one
            try:
                self.spreadsheet = client.open(self.spreadsheet_name)
                logger.info(f"Opened existing spreadsheet: {self.spreadsheet_name}")
            except gspread.SpreadsheetNotFound:
                # Create new spreadsheet
                self.spreadsheet = client.create(self.spreadsheet_name)
                logger.info(f"Created new spreadsheet: {self.spreadsheet_name}")

            # Get the first worksheet
            try:
                self.sheet = self.spreadsheet.sheet1
            except gspread.WorksheetNotFound:
                self.sheet = self.spreadsheet.add_worksheet(title="Main Data", rows=1000, cols=20)
                logger.info("Created new worksheet")

            # Set headers if sheet is empty
            existing_data = self.sheet.get_all_values()
            if not existing_data:
                self.headers = [
                    "Время заполнения", "ID", "username", "Имя", "Фамилия", "Группа", "Факультет", "Вид встречи",
                    "Дата проведения встречи","Сколько первокурсников в группе?", "Сколько пришло?", "Причины отсутствия",
                    #1 cентября
                    "Выбрали ли старосту на встрече?",
                    #Информационная
                    "Про какие организации, клубы, внеучебные возможности ты рассказал(а) своей группе? Что было наиболее интересно первокурсникам?", "Задали ли первокурсники доп. вопросы не по теме встречи?_ИНФО",
                    #На сплочение
                    "Где проходила встреча? Была ли она в стенах университета?", "Использовали ли вы Коордбокс на встрече? Если да, то в какие игры играли? "
                    "(варианты ответа: Не использовали, «Детектив», «Отчислено»,"
                    "«Тик-Так-Бум», «ФинЭлиас», «Координариум», «Шпион»)", "Чем вы занимались на встрече с первокурсниками?",
                    #Новогодняя предсессионная
                    "Задали ли первокурсники доп. вопросы не по теме встречи?_НГ", "Играли ли вы в Тайного Санту с группой? Если нет, то почему?",
                    #Информационная онлайн
                    "Какие моменты ты осветил(а) на встрече? Что из этого было наиболее полезно первокурсникам?", "Задали ли первокурсники доп. вопросы не по теме встречи?_ОНЛАЙН",
                    #Неформальная
                    "Где проходила встреча? Была ли она в стенах университета?_НЕФОР", "Использовали ли вы Коордбокс на встрече? Если да, то в какие игры играли? "
                    "(варианты ответа: Не использовали, «Детектив», «Отчислено»,"
                    "«Тик-Так-Бум», «ФинЭлиас», «Координариум», «Шпион»)_НЕФОР", "Чем вы занимались на встрече с первокурсниками?_НЕФОР",
                    #Итоговая
                    "Какое было наполнение у твоей встречи с группой?",
                    "Плюсы встречи", "Минусы встречи", "Общие впечатления","Доп. инфа", "Фото"
                ]
                self.sheet.append_row(self.headers)
            else:
                self.headers = existing_data[0]

        except Exception as e:
            logger.error(f"Error setting up Google Sheets: {e}")
            raise

    def create_credentials_template(self):
        """Create a template credentials.json file with instructions"""
        template = {
            "type": "service_account",
            "project_id": "koordbook",
            "private_key_id": "62b0955e8b768bff5a7f298def701e5f11994a57",
            "private_key": "MIIEvgIBADANBgkqhkiG9w0BAQEFAASCBKgwggSkAgEAAoIBAQC+ID+C6YHt8ABE\nwikt0l3n+9gyjKheWnGtxH867lCGwnLhu7p/g6NqEIJ7mvXPEosvKaVs8J2JttpD\nXbQKu2tdhsrw89bjXWBPO38o+tc7rRqG5TbGf+l9N62H7UJROOT593k+HO5uWlHi\nX8vbQ5IhS5Jpqb+g74L+f5iB806kF9ucn+1gjN0bsxYLEjeQZESWrpH8tBbGiIQv\nVWI3+1CUuvqZ0DOGnul4GCiqM27HgfeBpdrHXhPld1mLdDdRQaj4gBNYrbRkn6GD\ny6y657RU3b73ggNpBAlUoEzzXVoNcBhAin5F0C3qGM9pKt4ZJy3lfijk9JXDAlXa\nEE/HaQzfAgMBAAECggEAXcDPMMHu1SL9LurDnZnXvrZ8tOiRef2FgxebWbb8tIcc\nWV3WKF0Ebx/3B/aw8cyGH9qcfWzlcmxdksyZJJWo6vS2DD1hoLqB7HA9UzrmecHx\ni8VpzlZzD9Et3BJOGnlAyFaVTeC8XmRhboyonNXkMFDwwPP4z+ZrpQ3MaYBOLjHP\nDIn6429i2NCtN8YCW+LVrqAc6cl++OFWCDfu8y4MsARynRCM3M216QVjPWeKSTUG\n7vGQjtqo5cnX5jo7RnJMQxSUc+C6IC+cRu/lMfAkWcPyibc1xyjHTkPf9ilh43lW\np1GhU8tjtdnvFj0f3pnWkRxJVHXWTlz1A5isfFdNcQKBgQDyOJIoyZ6zBFPLEdYB\nZ3oktkdQQe52el8nuiuqgChNCIxU1fSed/xKRoEw6xuybF+SjTTKdVcjxpm8p0UA\nq8JpO0IULpC2QnQVYxoJDLyALqWnyuVyGB0CaO74VXzfegAevmgiNj8J/bkW85dn\naHMto85c/xLGWxuh3UlSoOj9iQKBgQDI8QZp0ki+roTNELRzjW/sK0uLASbJHTld\nBAUie8dzEPpF90p57lm46Luqh3AUP1HDk+Xm/ZDov//gPVcWIZNI6tLqz3tMaCKX\npjGsibYS3ycYsKA3LpT87miJrsdX6ZcTBLPXXSshfVEhLC5whYRsSGnKWvP32gI6\nNptfTlDFJwKBgQDbo4aNa733MG5XDpZS8aTlU1A5K3/zeSV93ago1Es3BxBRAS3u\n4HgqVeJiHF8iHHlRZ6++AkcBDt5rHfZJFHaWe4CA0nSwgHPIzPNXz2/CgAoAq9AA\n9HKhs8s17jbsYjFnr1q34x6ojaTfdgUNZL5EXWwMEdPRf93/mawaPATpmQKBgQCB\n42MM5lQFhhPr5l9uzj9Jvxa+zMjAebaJzL5w8ugTFidhMJ+gv5SZtT8R1Sh6vg9h\nR+n1bXTNLsb8sUno0V0+ZiReii2eTzYFJvW3HPFns323NPzrjp3Z/VXvod3TkvgH\n4CNMFDp8FGBr+/4s1/GoeQqBNle7n92OuZuneJ03QwKBgASYzsvCtgm1oQ3nvk84\nR8nKGxjM2RDmKcNboD4F5tCBxhsWiBANlsH5XMiCO3rzcjTuEWcMqwkBq9/WYNA9\nsUhiru6/pyiDMFTCxOU2RXg7NWSaH2AGqEcCGXQybGZ7gY6jqx9MUzU3fYnrhF1U\n+YG4wdBHKPD3oknIW3J1nz+5",
            "client_email": "telegram-bot-sheets@koordbook.iam.gserviceaccount.com",
            "client_id": "103772447748404966704",
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
            "client_x509_cert_url": "https://www.googleapis.com/robot/v1/metadata/x509/telegram-bot-sheets%40koordbook.iam.gserviceaccount.com",
            "universe_domain": "googleapis.com"
        }

        with open(self.credentials_file, 'w') as f:
            json.dump(template, f, indent=2)

        logger.info(f"Created credentials template at {self.credentials_file}")

    async def add_data(self, user_data: dict):
        """Add data to Google Sheets asynchronously"""
        try:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, self._add_data_sync, user_data)
            return True
        except Exception as e:
            logger.error(f"Error adding data to sheets: {e}")
            return False

    def _add_data_sync(self, user_data: dict):
        """Synchronous method to add data to sheets"""
        row_data = ['' for _ in range(len(self.headers))]
        column_mapping = {
            'Время заполнения':datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            'ID':user_data.get('ID', ''),
            'username':user_data.get('username', ''),
            'Имя':user_data.get('Имя', ''),
            'Фамилия':user_data.get('Фамилия', ''),
            'Группа':user_data.get('Группа', ''),
            'Факультет':user_data.get('Факультет', ''),
            'Вид встречи':user_data.get('Вид встречи', ''),
            'Дата проведения встречи': user_data.get('Дата проведения встречи', ''),
            'Сколько первокурсников в группе?':user_data.get('Сколько первокурсников в группе?', ''),
            'Сколько пришло?':user_data.get('Сколько пришло?', ''),
            'Причины отсутствия':user_data.get('Причины отсутствия', ''),
            'Выбрали ли старосту на встрече?': user_data.get('Выбор старосты', ''),
            'Про какие организации, клубы, внеучебные возможности ты рассказал(а) своей группе? Что было наиболее интересно первокурсникам?': user_data.get('Организации', ''),
            'Где проходила встреча? Была ли она в стенах университета?': user_data.get('Где была встреча1', ''),
            'Задали ли первокурсники доп. вопросы не по теме встречи?_НГ': user_data.get('Вопросы не по теме1', ''),
            'Какие моменты осветили?': user_data.get('Какие моменты осветили?', ''),
            'Где проходила встреча? Была ли она в стенах университета?_НЕФОР': user_data.get('Где была встреча2', ''),
            'Какое было наполнение у твоей встречи с группой?': user_data.get('Что обсуждали?', ''),
            'Задали ли первокурсники доп. вопросы не по теме встречи?_ИНФО': user_data.get('Вопросы не по теме2', ''),
            'Использовали ли вы Коордбокс на встрече? Если да, то в какие игры играли? (варианты ответа: Не использовали, «Детектив», «Отчислено»,«Тик-Так-Бум», «ФинЭлиас», «Координариум», «Шпион»)': user_data.get('Использовали Коордбокс?1', ''),
            'Играли ли вы в Тайного Санту с группой? Если нет, то почему?': user_data.get('Тайный Санта', ''),
            'Задали ли первокурсники доп. вопросы не по теме встречи?_ОНЛАЙН': user_data.get('Вопросы не по теме3', ''),
            'Использовали ли вы Коордбокс на встрече? Если да, то в какие игры играли? (варианты ответа: Не использовали, «Детектив», «Отчислено»,«Тик-Так-Бум», «ФинЭлиас», «Координариум», «Шпион»)_НЕФОР': user_data.get('Использовали Коордбокс?2', ''),
            'Чем занимались?1': user_data.get('Чем занимались?1', ''),
            'Чем занимались?2': user_data.get('Чем занимались?2', ''),
            'Плюсы встречи':user_data.get('Плюсы встречи', ''),
            'Минусы встречи':user_data.get('Минусы встречи', ''),
            'Общие впечатления':user_data.get('Общие впечатления', ''),
            'Доп. инфа':user_data.get('Доп. инфа', ''),
            'Фото':user_data.get('Фото', ''),
        }

        for i, header in enumerate(self.headers):
            if header in column_mapping:
                row_data[i] = column_mapping[header]

        self.sheet.append_row(row_data)
        logger.info(f"Data added to Google Sheets for user {user_data.get('ID')}")


# Bot functions
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Start the conversation"""
    context.user_data.clear()
    user = update.message.from_user
    context.user_data.update({
        'ID': user.id,
        'username': user.username or '',
    })

    await update.message.reply_text(
        "Привет! Я твой личный дневник Координатора!\n\nНапиши своё имя:",
        reply_markup=ReplyKeyboardRemove()
    )

    return NAME


async def get_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Get user's name"""
    context.user_data['Имя'] = update.message.text

    await update.message.reply_text(
        "Супер! А теперь наши свою фамилию:"
    )

    return LASTNAME


async def get_lastname(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Get user's lastname"""
    context.user_data['Фамилия'] = update.message.text

    await update.message.reply_text(
        "Записал! Напиши группу, у которой проводилась встреча:"
    )

    return GROUP


async def get_group(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Get user's group"""
    context.user_data['Группа'] = update.message.text

    # Клавиатура для выбора факультета
    faculty_kb = [
        [InlineKeyboardButton(text='СНиМК', callback_data='СНиМК')],
        [InlineKeyboardButton(text='ФЭБ', callback_data='ФЭБ')],
        [InlineKeyboardButton(text='МЭО', callback_data='МЭО')],
        [InlineKeyboardButton(text='ФинФак', callback_data='ФинФак')],
        [InlineKeyboardButton(text='ЮрФак', callback_data='ЮрФак')],
        [InlineKeyboardButton(text='НАБ', callback_data='НАБ')],
        [InlineKeyboardButton(text='ИТиАБД', callback_data='ИТиАБД')],
        [InlineKeyboardButton(text='ВШУ', callback_data='ВШУ')]]

    reply_markup = InlineKeyboardMarkup(faculty_kb)
    await update.message.reply_text(
        "Класс! Какой это факультет:", reply_markup=reply_markup, parse_mode='Markdown'
    )
    return FACULTY


async def get_faculty(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Get user's faculty"""
    query = update.callback_query
    await query.answer()

    option_type = query.data
    context.user_data['Факультет'] = option_type
    # Клавиатура для выбора вида встречи
    meeting_kb = [
        [InlineKeyboardButton(text='1 сентября', callback_data='1 сентября')],
        [InlineKeyboardButton(text='Информационная встреча', callback_data='Информационная встреча')],
        [InlineKeyboardButton(text='Встреча на сплочение', callback_data='Встреча на сплочение')],
        [InlineKeyboardButton(text='Новогодняя предсессионная встреча', callback_data='Новогодняя предсессионная встреча')],
        [InlineKeyboardButton(text='Информационная онлайн-встреча', callback_data='Информационная онлайн-встреча')],
        [InlineKeyboardButton(text='Неформальная встреча', callback_data='Неформальная встреча')],
        [InlineKeyboardButton(text='Итоговая встреча', callback_data='Итоговая встреча')]]

    reply_markup = InlineKeyboardMarkup(meeting_kb)
    await query.message.reply_text(
        "Давай определимся с видом встречи:", reply_markup=reply_markup, parse_mode='Markdown'
    )

    return MEETING

async def get_meeting(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Get user's meeting"""
    query = update.callback_query
    await query.answer()

    option_type = query.data
    context.user_data['Вид встречи'] = option_type

    await query.message.reply_text(
        "Напиши дату, когда прошла ваша встреча (в формате 01.09.2025)"
    )

    return DATE

async def get_date(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Get user's meeting"""
    context.user_data['Дата проведения встречи'] = update.message.text

    await update.message.reply_text(
        "Сколько первокурсников в группе? (отправь сообщение числом)"
    )

    return GROUP_MEMBERS

async def get_amount(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Get user's pluses"""
    context.user_data['Сколько первокурсников в группе?'] = update.message.text

    await update.message.reply_text(
        "Сколько пришло первокурсников на встречу? (отправь сообщение числом)"
    )

    return WERE

async def get_were(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Get user's pluses"""
    context.user_data['Сколько пришло?'] = update.message.text

    await update.message.reply_text(
        " Если кто-то не пришёл на встречу, то по какой причине? Возможные варианты: никто не пропустил, болезнь, "
        "важные дела, неудобное время или место, не видят актуальность встречи для себя, предупредили и не "
        "пришли в последний момент, другое"
    )

    return WHY_NOT

async def get_why_not(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Get user's pluses"""
    context.user_data['Причины отсутствия'] = update.message.text

    variant = context.user_data.get('Вид встречи')

    if variant == '1 сентября':
        await update.message.reply_text(
            "Выбрали ли старосту на встрече?"
        )
        return HANDMAN

    elif variant == 'Информационная встреча':
        await update.message.reply_text(
            "Про какие организации, клубы, внеучебные возможности ты рассказал(а) своей группе? "
            "Что было наиболее интересно первокурсникам?"
        )
        return ORGANIZATIONS

    elif variant == 'Встреча на сплочение':
        await update.message.reply_text(
            "Где проходила встреча? Была ли она в стенах университета?"
        )
        return WHERE_1

    elif variant == 'Новогодняя предсессионная встреча':
        await update.message.reply_text(
            "Задали ли первокурсники доп. вопросы не по теме встречи?"
        )
        return DOPS_1

    elif variant == 'Информационная онлайн-встреча':
        await update.message.reply_text(
            "Какие моменты ты осветил(а) на встрече? Что из этого было наиболее полезно первокурсникам?"
        )
        return MOMENTS
    elif variant == 'Неформальная встреча':
        await update.message.reply_text(
            "Где проходила встреча? Была ли она в стенах университета?"
        )
        return WHERE_2

    else:
        await update.message.reply_text(
            "Какое было наполнение у твоей встречи с группой?"
        )
        return TOTALITY


async def pull_1(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Get user's pluses"""
    variant = context.user_data.get('Вид встречи')

    if variant == '1 сентября':
        context.user_data['Выбор старосты'] = update.message.text
        await update.message.reply_text(
            "Что тебе понравилось по итогам встречи? Какие плюсы можешь выделить?"
        )
        return PLUSES

    elif variant == 'Информационная встреча':
        context.user_data['Организации'] = update.message.text
        await update.message.reply_text(
            "Задали ли первокурсники доп. вопросы не по теме встречи?"
        )
        return DOPS_2

    elif variant == 'Встреча на сплочение':
        context.user_data['Где была встреча1'] = update.message.text
        await update.message.reply_text(
            "Использовали ли вы Коордбокс на встрече? Если да, то в какие игры играли? "
            "(варианты ответа: Не использовали, «Детектив», «Отчислено», "
            "«Тик-Так-Бум», «ФинЭлиас», «Координариум», «Шпион»)"
        )
        return COORD_1

    elif variant == 'Новогодняя предсессионная встреча':
        context.user_data['Вопросы не по теме1'] = update.message.text
        await update.message.reply_text(
            "Играли ли вы в Тайного Санту с группой? Если нет, то почему?"
        )
        return SANTA

    elif variant == 'Информационная онлайн-встреча':
        context.user_data['Какие моменты осветили?'] = update.message.text
        await update.message.reply_text(
            "Задали ли первокурсники доп. вопросы не по теме встречи? "
        )
        return DOPS_3

    elif variant == 'Неформальная встреча':
        context.user_data['Где была встреча2'] = update.message.text
        await update.message.reply_text(
            "Использовали ли вы Коордбокс на встрече? Если да, то в какие игры играли? "
            "(варианты ответа: Не использовали, «Детектив», «Отчислено», "
            "«Тик-Так-Бум», «ФинЭлиас», «Координариум», «Шпион»)"
        )
        return COORD_2

    else:
        context.user_data['Что обсуждали?'] = update.message.text
        await update.message.reply_text(
            "Что тебе понравилось по итогам встречи? Какие плюсы можешь выделить?"
        )
        return PLUSES


async def pull_2(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Get user's pluses"""
    variant = context.user_data.get('Вид встречи')

    if variant == 'Информационная встреча':
        context.user_data['Вопросы не по теме2'] = update.message.text
        await update.message.reply_text(
            "Что тебе понравилось по итогам встречи? Какие плюсы можешь выделить?"
        )
        return PLUSES

    elif variant == 'Встреча на сплочение':
        context.user_data['Использовали Коордбокс?1'] = update.message.text
        await update.message.reply_text(
            "Чем вы занимались на встрече с первокурсниками?"
        )
        return DOING1

    elif variant == 'Новогодняя предсессионная встреча':
        context.user_data['Тайный Санта'] = update.message.text
        await update.message.reply_text(
            "Что тебе понравилось по итогам встречи? Какие плюсы можешь выделить?"
        )
        return PLUSES

    elif variant == 'Информационная онлайн-встреча':
        context.user_data['Вопросы не по теме3'] = update.message.text
        await update.message.reply_text(
            "Что тебе понравилось по итогам встречи? Какие плюсы можешь выделить?"
        )
        return PLUSES

    elif variant == 'Неформальная встреча':
        context.user_data['Использовали Коордбокс?2'] = update.message.text
        await update.message.reply_text(
            "Чем вы занимались на встрече с первокурсниками?"
        )
        return DOING2

    else:
        pass

async def pull_3(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Get user's pluses"""
    variant = context.user_data.get('Вид встречи')

    if variant == 'Встреча на сплочение':
        context.user_data['Чем занимались?1'] = update.message.text
        await update.message.reply_text(
            "Что тебе понравилось по итогам встречи? Какие плюсы можешь выделить?"
        )
        return PLUSES

    elif variant == 'Неформальная встреча':
        context.user_data['Чем занимались?2'] = update.message.text
        await update.message.reply_text(
            "Что тебе понравилось по итогам встречи? Какие плюсы можешь выделить?"
        )
        return PLUSES

    else:
        pass

async def get_pluses(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Get user's pluses"""
    context.user_data['Плюсы встречи'] = update.message.text

    await update.message.reply_text(
        "Что тебе не понравилось во встрече? Что бы ты хотел(а) исправить к следующей встрече"
    )

    return MINUSES

async def get_minuses(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Get user's minuses"""
    context.user_data['Минусы встречи'] = update.message.text

    await update.message.reply_text(
        "Какие у тебя общие впечатления от встречи?"
    )

    return TOTAL

async def get_total(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Get user's total"""
    context.user_data['Общие впечатления'] = update.message.text

    await update.message.reply_text(
        "Если хочешь что-то ещё сказать, то напиши тут!\n\n"
        "(отправь сообщение, а если нечего добавить, напиши любой текст)"
    )

    return COMMENTS


async def get_comments(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Get user's comments and save to Google Sheets"""
    context.user_data['Доп. инфа'] = update.message.text

    # Get sheets manager from context
    sheets_manager = context.application.sheets_manager

    # Save to Google Sheets
    success = await sheets_manager.add_data(context.user_data)

    if success:
        await update.message.reply_text(
            "Спасибо огромное! Я всё успешно записал)\n\nТеперь отправь сюда одну фотографию со встречи с первашами. Если фотки нет, то отправь любую"
        )

    else:
        await update.message.reply_text(
            "Please try again later."
        )
        return ConversationHandler.END
        
    return PHOTOS

# async def send_tele(update: Update, context: ContextTypes.DEFAULT_TYPE):
#     list = []
#     list_upd = []
#     list.add(context.user_data.get('ID', ''), context.user_data.get('username', ''), context.user_data.get('Имя', ''), context.user_data.get('Фамилия', ''),
#             context.user_data.get('Группа', ''), context.user_data.get('Факультет', ''), context.user_data.get('Вид встречи', ''), context.user_data.get('Дата проведения встречи', ''),
#             context.user_data.get('Сколько первокурсников в группе?', ''),context.user_data.get('Сколько пришло?', ''),context.user_data.get('Причины отсутствия', ''),
#             context.user_data.get('Выбор старосты', ''),context.user_data.get('Организации', ''),context.user_data.get('Где была встреча1', ''),context.user_data.get('Вопросы не по теме1', ''),
#             context.user_data.get('Какие моменты осветили?', ''),context.user_data.get('Где была встреча2', ''),context.user_data.get('Что обсуждали?', ''),
#             context.user_data.get('Вопросы не по теме2', ''),context.user_data.get('Использовали Коордбокс?1', ''),context.user_data.get('Тайный Санта', ''),
#             context.user_data.get('Вопросы не по теме3', ''),context.user_data.get('Использовали Коордбокс?2', ''),context.user_data.get('Чем занимались?1', ''),
#             context.user_data.get('Чем занимались?2', ''),context.user_data.get('Плюсы встречи', ''),context.user_data.get('Минусы встречи', ''),
#             context.user_data.get('Общие впечатления', ''),context.user_data.get('Доп. инфа', '')
#             )
            
#     list.length() = i
#     while i >= 0:
#         if list[i] != '':
#             list_upd.add(list[i])
#         i--
#         else:
#             pass
    
    
async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    
    context.user_data['Фото'] = "Смотри чат в тг"
    # Получаем файл
    try:
            photo = update.message.photo[-1]
            
            # Сохраняем file_id в базу данных или файл (опционально)
            print(f"File ID сохранен: {photo.file_id}")
            print(f"Unique File ID: {photo.file_unique_id}")
            
            # await context.bot.send_photo(
            #     chat_id=-4615608029,
            #     text=f"Координатор факультета {context.user_data.get('Факультет', '')} и группы {context.user_data.get('Группа', '')}"  
            #       f"{context.user_data.get('Имя', '')} {context.user_data.get('Фамилия', '')} (@{context.user_data.get('username', '')} заполнил дневник о встрече '{context.user_data.get('Вид встречи', '')}'\n"
            #       f"Дата проведения - {context.user_data.get('Дата проведения встречи', '')}\n"
            #       f"Факультет: {context.user_data.get('Факультет', '')}\n"
            #       f"Встреча: {context.user_data.get('Вид встречи', '')}"
            #)
            # Пересылаем используя file_id
            await context.bot.send_photo(
                chat_id=-1003088757586,
                photo=photo.file_id,
                caption=f"Координатор факультета {context.user_data.get('Факультет', '')} и группы {context.user_data.get('Группа', '')}"  
                   f"{context.user_data.get('Имя', '')} {context.user_data.get('Фамилия', '')} (@{context.user_data.get('username', '')}) заполнил дневник о встрече '{context.user_data.get('Вид встречи', '')}'\n"
                   f"Дата проведения - {context.user_data.get('Дата проведения встречи', '')}"
            )
            
            await update.message.reply_text("Какие красавчики!\n\nДля записи следующей встречи сначала нажми /again!")
            
    except Exception as e:
        logger.error(f"Error handling photo: {e}")
        await update.message.reply_text(f"❌ Ошибка: {e}")
        
    return PHOTOS
    


   
async def again(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    
    await update.message.reply_text(
        'Прошла новая встреча с первашами?\n\nНажимай /start и мы всё запишем!',
        reply_markup=ReplyKeyboardRemove()
    )

    return ConversationHandler.END
        
        
async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancel the conversation"""
    await update.message.reply_text(
        'Начнём заново!\n\nНажимай /again и мы начнём заново!',
        reply_markup=ReplyKeyboardRemove()
    )

    return ConversationHandler.END

async def id(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:

    chat_id = update.effective_chat.id
    await update.message.reply_text(f"Айди этого чата => {chat_id}",
                                        reply_to_message_id=None,)



async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send a help message"""
    await update.message.reply_text(
        "Я твой личный дневник. Вот что я умею:\n\n/start - Нажимай и мы запишем твою встречу с первашами\n"
        "/cancel - Если что-то пошло не так, то я перезапишу твои данные"
        "\n/again - Когда заполнишь встречу, используй, чтобы записать новую"
    )


async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle errors"""
    logger.error(f"Update {update} caused error {context.error}")


def main():
    # Configuration
    TELEGRAM_TOKEN = "8000295961:AAHGzRkWxj7E24ZJGwAbm4aK4rJMIKggQX8"  # Replace with your token from @BotFather
    CREDENTIALS_FILE = "credentials.json"
    SPREADSHEET_NAME = "Данные дневника Координаторов'25"

    print("🔧 Setting up Telegram Bot with Google Sheets...")

    # Initialize Google Sheets manager
    try:
        sheets_manager = GoogleSheetsManager(
            credentials_file=CREDENTIALS_FILE,
            spreadsheet_name=SPREADSHEET_NAME
        )
        logger.info("✅ Google Sheets connection established successfully")
    except FileNotFoundError as e:
        print(f"❌ {e}")
        return
    except Exception as e:
        logger.error(f"❌ Failed to initialize Google Sheets: {e}")
        print(f"❌ Error: {e}")
        return

    # Create Application
    try:
        application = Application.builder().token(TELEGRAM_TOKEN).build()
        application.sheets_manager = sheets_manager
    except Exception as e:
        logger.error(f"❌ Ошибка создания приложения: {e}")
        print(f"❌ Ошибка Telegram: {e}")
        return

    # Setup conversation handler
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={
            NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_name)],
            LASTNAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_lastname)],
            GROUP: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_group)],
            FACULTY: [CallbackQueryHandler(get_faculty)],
            MEETING: [CallbackQueryHandler(get_meeting)],
            DATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_date)],
            GROUP_MEMBERS: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_amount)],
            WERE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_were)],
            WHY_NOT:[MessageHandler(filters.TEXT & ~filters.COMMAND, get_why_not)],
            HANDMAN: [MessageHandler(filters.TEXT & ~filters.COMMAND, pull_1)],
            ORGANIZATIONS: [MessageHandler(filters.TEXT & ~filters.COMMAND, pull_1)],
            WHERE_1: [MessageHandler(filters.TEXT & ~filters.COMMAND, pull_1)],
            DOPS_1: [MessageHandler(filters.TEXT & ~filters.COMMAND, pull_1)],
            MOMENTS: [MessageHandler(filters.TEXT & ~filters.COMMAND, pull_1)],
            WHERE_2: [MessageHandler(filters.TEXT & ~filters.COMMAND, pull_1)],
            TOTALITY: [MessageHandler(filters.TEXT & ~filters.COMMAND, pull_1)],
            DOPS_2: [MessageHandler(filters.TEXT & ~filters.COMMAND, pull_2)],
            COORD_1: [MessageHandler(filters.TEXT & ~filters.COMMAND, pull_2)],
            DOING1: [MessageHandler(filters.TEXT & ~filters.COMMAND, pull_3)],
            SANTA: [MessageHandler(filters.TEXT & ~filters.COMMAND, pull_2)],
            DOPS_3: [MessageHandler(filters.TEXT & ~filters.COMMAND, pull_2)],
            COORD_2: [MessageHandler(filters.TEXT & ~filters.COMMAND, pull_2)],
            DOING2: [MessageHandler(filters.TEXT & ~filters.COMMAND, pull_3)],
            PLUSES: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_pluses)],
            MINUSES: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_minuses)],
            TOTAL: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_total)],
            COMMENTS: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_comments)],
            PHOTOS: [MessageHandler(filters.PHOTO, handle_photo)],
        },
        fallbacks=[CommandHandler('again', again)],
    )

    # Add handlers
    application.add_handler(conv_handler)
    application.add_handler(CommandHandler('help', help_command))
    application.add_handler(CommandHandler('cancel', cancel))
    application.add_handler(CommandHandler('id', id))
    application.add_error_handler(error_handler)

    # Start the bot
    logger.info("✅ Telegram bot starting...")
    print("🤖 Bot is running! Press Ctrl+C to stop.")

    try:
        application.run_polling()
    except TelegramError as e:
        logger.error(f"Telegram error: {e}")
        print(f"❌ Telegram error: {e}")
    except Exception as e:
        logger.error(f"Bot stopped with error: {e}")
        print(f"❌ Bot stopped: {e}")


if __name__ == "__main__":
    main()



