from bot import bot
from os import getenv
from dotenv import load_dotenv


if __name__ == '__main__':
    load_dotenv()
    if not str(getenv("TG_TOKEN")) or not str(getenv("SECRET_PHRASE")):
        print('TG_TOKEN or SECRET_PHRASE environment variables not set')
        exit(1)
    bot.infinity_polling()
