from datetime import date, datetime
from sqlite3 import register_adapter, register_converter, PARSE_DECLTYPES, Connection
from os import path
from json import load


class Database(Connection):
    def __init__(self, db_file):
        super().__init__(db_file, detect_types=PARSE_DECLTYPES, check_same_thread=False)
        self.create_function("CL_LIKE", 2, lambda x, y: x and y.strip().lower() in x.strip().lower())
        register_adapter(date, lambda x: x.isoformat())
        register_adapter(datetime, lambda x: x.isoformat())
        register_adapter(list, lambda x: str(x))
        register_adapter(dict, lambda x: str(x))
        register_converter('date', lambda x: date.fromisoformat(x.decode()))
        register_converter('datetime', lambda x: datetime.fromisoformat(x.decode()))
        self.execute('CREATE TABLE IF NOT EXISTS judges (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INT, expires DATETIME)')
        self.execute('CREATE TABLE IF NOT EXISTS invites (id INTEGER PRIMARY KEY AUTOINCREMENT, invite_code TEXT, invited_by INT, expires DATETIME)')
        self.commit()


class Judges:
    def __init__(self, db_connection):
        self.eternal = load(open(f'{path.dirname(path.abspath(__file__))}/eternal_judges.json')) if path.exists(f'{path.dirname(path.abspath(__file__))}/eternal_judges.json') else []
        users = db_connection.execute("SELECT * FROM judges").fetchall()
        all_judges = [user[1:3] for user in users]
        self.all = dict(all_judges) if all_judges else {}
        actual_judges = [user[1:3] for user in users if user[2] > datetime.today()]
        self.actual = dict(actual_judges) if actual_judges else {}
        for eternal in self.eternal:
            self.all[eternal] = True
            self.actual[eternal] = True
        expired_judges = [user[1:3] for user in users if user[2] <= datetime.today()]
        self.expired = dict(expired_judges) if expired_judges else {}

db = Database('db.sqlite')