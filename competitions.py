from datetime import datetime, time
from google_docs import get_worksheet, id_column, fcs_column, df
from gspread import Cell
from bot import KeypadM, KeypadB
import replies


def lesson_by_time():
    t = datetime.today()
    if t.year == 2025 and t.month == 4 and t.day in (21, 22):
        if t.day == 21:
            if time(8) < t.time() < time(9, 30):
                return 1
            elif time(9, 50) < t.time() < time(11, 20):
                return 2
            elif time(11, 40) < t.time() < time(13, 10):
                return 3
            elif time(13, 40) < t.time() < time(15, 10):
                return 4
            elif time(15, 30) < t.time() < time(17):
                return 5
        else:
            if time(9, 50) < t.time() < time(11, 20):
                return 6
            elif time(11, 40) < t.time() < time(13, 10):
                return 7
            elif time(13, 40) < t.time() < time(15, 10):
                return 8
            elif time(15, 30) < t.time() < time(17):
                return 9
    return None


class Climber:
    def __init__(self, uid):
        self.row = None
        if isinstance(uid, str):
            if not uid:
                raise KeyError("Не указан номер лазающего")
            uid = uid.strip()
            if uid.isdigit():
                if uid in id_column.values:
                    self.row = int(uid) + 1
            else:
                uid = uid.lower()
                if any([uid in fcs for fcs in fcs_column]):
                    self.row = [uid in fcs for fcs in fcs_column].index(True) + 2
            if self.row is None:
                raise KeyError("Не удалось найти лазающего " + (f"с номером <b>{uid}</b>" if uid.isdigit() else f"с ФИО <b>{uid}</b>"))
            climber = df.loc[self.row - 1]
        else:
            climber = uid
            self.row = climber[0] + 1
        self.id = climber[0]
        self.lesson = climber[1]
        self.name = climber[2]
        self.sex = climber[3]
        self.group = climber[4]
        self.course = climber[5]
        self.faculty = climber[6]
        self.stands = list(climber[7:57])
        self.result = int(climber[57])

    async def mark_lesson(self, lesson=None):
        self.lesson = lesson
        wks = await get_worksheet()
        await wks.update_cell(self.row, 2, self.lesson)


    async def mark_stand(self, number):
        if not (number.isdigit() and 1 <= (number := int(number)) <= 50):
            raise ValueError("Номер стенда должен быть в диапазоне от 1 до 50")
        wks = await get_worksheet()
        await wks.update_cell(self.row, 7 + number, 1)
        self.stands[number - 1] = 1
        self.result += 1

    async def unmark_stand(self, number):
        if not (number.isdigit() and 1 <= (number := int(number)) <= 50):
            raise ValueError("Номер стенда должен быть в диапазоне от 1 до 50")
        wks = await get_worksheet()
        await wks.update_cell(self.row, 7 + number, '')
        self.stands[number - 1] = ''
        self.result -= 1

    def __str__(self):
        reply = f"{self.id}. {self.name}\n"
        if self.lesson:
            reply += f"Отмечен{'a' if self.sex == 'ж' else ''} на паре №{int(self.lesson)}\n"
        else:
            reply += f"<b>Не был{'a' if self.sex == 'ж' else ''} отмечен{'a' if self.sex == 'ж' else ''}!</b>\n"
        if any(self.stands):
            reply += f"Отмеченные трассы: {', '.join([str(i + 1) for i in range(len(self.stands)) if self.stands[i]])}\n"
        return reply


async def mark_stand(message, args):
    climber = Climber(message.text.split('-')[0])
    number = message.text.split('-')[1].strip()
    await climber.mark_stand(number)
    reply = f'Отлично! Лазающий №{climber.id} {climber.name} {"прошёл" if climber.sex == "м" else "прошла"} трассу №{number}\n\n'
    reply += replies.mark_stand_instruction
    keypad = KeypadM().add(KeypadB('В меню', '', 'menu'))
    new_args = {'function': mark_stand, 'm_id': args["m_id"], 'reply': replies.mark_stand_instruction}
    return True, reply, keypad, new_args


async def unmark_stand(message, args):
    climber = Climber(message.text.split('-')[0])
    number = message.text.split('-')[1].strip()
    await climber.unmark_stand(number)
    reply = f'Отметка о прохождении трассы №{number} у лазающего №{climber.id} {climber.name} была убрана\n\n'
    reply += replies.unmark_stand_instruction
    keypad = KeypadM().add(KeypadB('В меню', '', 'menu'))
    new_args = {'function': unmark_stand, 'm_id': args["m_id"], 'reply': replies.unmark_stand_instruction}
    return True, reply, keypad, new_args


async def mark_lesson(message, args):
    lesson = args["lesson"]
    uids = map(lambda x: x.strip(), message.text.split())
    marked_climbers = []
    unsuccessful_marks = []
    climbers =[]
    for climber in uids:
        try:
            climber = Climber(climber)
            marked_climbers.append(climber.id)
            climbers.append(climber)
        except KeyError:
            import traceback
            traceback.print_exc()
            unsuccessful_marks.append(str(climber))
    marked_climbers.sort()
    wks = await get_worksheet()
    if climbers:
        await wks.update_cells([Cell(climber.row, 2, lesson) for climber in climbers], 'USER_ENTERED')
    if len(unsuccessful_marks) == 0:
        reply = 'Все лазающие были успешно отмечены'
    else:
        reply = f'Отмечены следующие лазающие: {", ".join(map(str, marked_climbers))}\n'
        reply += f'Следующие не найдены в списке: {", ".join(map(str, unsuccessful_marks))}\n'
    keypad = KeypadM().add(KeypadB('В меню', '', 'menu'))
    return True, reply, keypad, None
