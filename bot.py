from dotenv import load_dotenv
from io import BytesIO
from datetime import datetime, timedelta
from telebot import TeleBot
from telebot.apihelper import ApiTelegramException
from telebot.types import InlineKeyboardMarkup as KeypadM, InlineKeyboardButton as KeypadB
import telebot.types as types
from telebot.util import quick_markup, extract_arguments
from os import getenv, path
import qrcode
import replies
from database import db, Judges
from competitions import lesson_by_time, mark_stand, mark_lesson, unmark_stand
from uuid import uuid4
from google_docs import sheet
from asyncio import run
from json import dump


def next_step(message, args: dict):
    user_id = message.from_user.id
    bot.delete_message(user_id, message.id)
    if message.text == '/start':
        bot.menu(message, args['m_id'])
        return
    elif message.text == '/invite':
        bot.send_invite(user_id)
    try:
        bot.edit_message_text(args['reply'] + "\n<b>В процессе обработки</b>", user_id, args['m_id'],
                              reply_markup=quick_markup({"В меню": {"callback_data": "menu"}}))
        success, reply, keypad, next_args = run(args['function'](message, args))
    except Exception as e:
        import traceback
        traceback.print_exc()
        success = next_args = None
        keypad = KeypadM().add(KeypadB('К старту', '', 'start'))
        reply = args['reply'] + f'\nПроизошла ошибка, попробуйте снова.\nОшибка: {e}'
    if next_args:
        bot.register_next_step_handler_by_chat_id(user_id, next_args)
    try:
        bot.edit_message_text(reply, user_id, args['m_id'], reply_markup=keypad)
    except ApiTelegramException:
        pass
    if not success:
        bot.register_next_step_handler_by_chat_id(user_id, args)

class Bot(TeleBot):
    def menu(self, message, m_id=None):
        keypad = None
        reply = ''
        user_id = message.from_user.id
        self.clear_step_handler_by_chat_id(user_id)
        if m_id is None and isinstance(message, types.CallbackQuery):
            m_id = message.message.id
        judges = Judges(db)
        if user_id not in judges.all:
            reply = 'Вы не являетесь судьёй, попросите пригласительный QR-код'
        elif user_id in judges.expired:
            reply = 'Похоже, что срок действия Ваших полномочий истёк'
        else:
            if lesson := lesson_by_time():
                reply = f"Вы судите на паре №{lesson}\n"
            if user_id not in judges.eternal:
                reply += f"Ваши полномочия активны до {judges.all[user_id].strftime('%H:%M %d.%m')}\n"
            else:
                reply += "Ваши полномочия не ограничены по времени"
            keypad = quick_markup({
                "Отметить на паре": {"callback_data": "mark_lesson"},
                "Отметить стенд": {"callback_data": "mark_stand"},
                "Убрать прохождение стенда": {"callback_data": "unmark_stand"},
            })
            if user_id in judges.eternal:
                keypad.add(KeypadB('Пригласить судью', '', 'invite'))
                keypad.add(KeypadB('Таблица', sheet.url))
        if m_id:
            self.edit_message_text(reply, user_id, m_id, reply_markup=keypad)
        else:
            self.send_message(user_id, reply, reply_markup=keypad)

    def delete_called_message(self, call):
        self.delete_message(call.from_user.id, call.message.message_id)

    def judge_validation(self, call):
        user_id = call.from_user.id
        m_id = call.message.id
        self.clear_step_handler_by_chat_id(user_id)
        judges = Judges(db)
        if user_id not in judges.actual:
            if user_id in judges.expired:
                reply = 'Похоже, что срок действия Ваших полномочий истёк'
            else:
                reply = 'Попросите пригласительную ссылку или QR-код'
            self.edit_message_text(reply, user_id, m_id)
            return 1
        return 0

    def stand_interaction(self, call):
        if self.judge_validation(call):
            return
        if call.data == 'mark_stand':
            reply = replies.mark_stand_instruction
            function = mark_stand
        else:
            reply = replies.unmark_stand_instruction
            function = unmark_stand
        keypad = quick_markup({"В меню": {"callback_data": "menu"}})
        self.edit_message_text(reply, call.from_user.id, call.message.message_id, reply_markup=keypad)
        args = {'function': function, 'm_id': call.message.message_id, 'reply': reply}
        self.register_next_step_handler_by_chat_id(call.from_user.id, args)

    def mark_lesson(self, call, lesson=lesson_by_time(), reply=replies.mark_lesson_instruction):
        self.judge_validation(call)
        keypad = KeypadM()
        args = {'function': mark_lesson, 'm_id': call.message.message_id, 'reply': reply, 'lesson': lesson}
        if lesson:
            reply += f"\n<b>Пара №{lesson}</b>"
            self.register_next_step_handler_by_chat_id(call.from_user.id, args)
        else:
            reply = f"\nНе удалось автоматически определить номер пары.\n<b>Выберите номер пары</b>"
            keypad.add(*[KeypadB(str(i), '', f'mark_lesson {i}') for i in range(1, 10)])
        keypad.add(KeypadB('Меню', '', 'menu'))
        self.edit_message_text(reply, call.from_user.id, call.message.message_id, reply_markup=keypad)

    def send_invite(self, call):
        user_id = call
        if isinstance(call, types.CallbackQuery):
            user_id = user_id.from_user.id
        expires = datetime.today() + timedelta(minutes=15)
        uuid = db.execute('INSERT INTO invites (invite_code, invited_by, expires) VALUES (?, ?, ?) RETURNING invite_code', (str(uuid4()), user_id, expires)).fetchone()[0]
        db.commit()
        url = f'https://t.me/{bot.get_me().username}?start=invite={uuid}'
        buf = BytesIO()
        qr = qrcode.make(url, box_size=5)
        qr.save(buf)
        buf.seek(0)
        reply = f'Приглашение действительно до {expires.strftime("%H:%M %d.%m")}\n'
        reply += f'Полномочия действительны до {(expires + timedelta(hours=2, minutes=15)).strftime("%H:%M %d.%m")}\n'
        reply += f'<a href="{url}">Ссылка</a>'
        keypad = quick_markup({'Удалить сообщение': {'callback_data': 'delete'}})
        self.send_photo(user_id, buf, reply, reply_markup=keypad)

    def table_link(self, message):
        user_id = message.from_user.id
        reply = f"<a href=\"{sheet.url}\">Ссылка на таблицу</a>"
        self.send_message(user_id, reply, reply_markup=quick_markup({'Удалить сообщение': {'callback_data': 'delete'}}))

    def register_next_step_handler_by_chat_id(self, chat_id: int, arguments, *args) -> None:
        super().register_next_step_handler_by_chat_id(chat_id, next_step, arguments)

    def infinity_polling(self, *args, **kwargs):
        self.enable_save_next_step_handlers(4, './handlers.save')
        if path.exists('./handlers.save'):
            self.load_next_step_handlers('./handlers.save', True)
        self.load_next_step_handlers()
        self.register_callback_query_handler(self.delete_called_message, lambda call: call.data == 'delete')
        self.register_callback_query_handler(self.menu, lambda call: call.data in ['start', 'menu'])
        self.register_callback_query_handler(self.stand_interaction, lambda call: call.data == 'mark_stand')
        self.register_callback_query_handler(self.stand_interaction, lambda call: call.data == 'unmark_stand')
        self.register_callback_query_handler(self.mark_lesson, lambda call: call.data == 'mark_lesson')
        self.register_callback_query_handler(self.send_invite, lambda call: call.data == 'invite')
        self.register_callback_query_handler(self.table_link, lambda call: call.data == 'export')
        print('Become eternal judge using next link:')
        print(f't.me/{self.get_me().username}?start={getenv('SECRET_PHRASE')}')
        print('Polling started')
        super().infinity_polling()


load_dotenv()
bot = Bot(str(getenv('TG_TOKEN')), num_threads=1, parse_mode='HTML', disable_web_page_preview=True)


def parse_arguments(data):
    data = extract_arguments(data)
    if not data:
        return {}
    return dict([arg if len(arg := argument.split('=')) > 1 else (arg[0], True) for argument in data.split('&')])


@bot.message_handler(commands=['start'])
def start_command(message):
    user_id = message.from_user.id
    bot.delete_message(user_id, message.message_id)
    arguments = parse_arguments(message.text)
    judges = Judges(db)
    if user_id not in judges.actual:
        if not arguments:
            bot.send_message(user_id, 'Похоже, что Вы не были добавлены как судья. Попросите другого судью пригласительный QR-код')
            return
        if 'invite' in arguments:
            invite_code = db.execute('SELECT * FROM invites WHERE invite_code = ? AND expires > ?', (arguments['invite'], datetime.today())).fetchone()
            if not invite_code:
                bot.send_message(user_id, 'Пригласительный код является недействительным')
                return
            if user_id not in judges.all:
                db.execute('INSERT INTO judges (user_id, expires) VALUES (?, ?)', (user_id, invite_code[3] + timedelta(hours=2, minutes=15)))
            else:
                db.execute('UPDATE judges SET expires = ? WHERE user_id = ?', (invite_code[3] + timedelta(hours=2, minutes=15), user_id))
            db.commit()
        elif str(getenv("SECRET_PHRASE")) in arguments:
            judges.eternal.append(user_id)
            dump(judges.eternal, open('eternal_judges.json', 'w'))
    bot.menu(message)


@bot.message_handler(commands=['invite'])
def invite(message):
    user_id = message.from_user.id
    bot.delete_message(user_id, message.message_id)
    judges = Judges(db)
    if user_id not in judges.eternal:
        return
    bot.send_invite(user_id)

@bot.callback_query_handler(func=lambda call: len(call.data.split()) == 2)
def mark_certain_lesson(call):
    bot.mark_lesson(call, call.data.split()[1])