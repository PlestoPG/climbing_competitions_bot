from gspread_asyncio import AsyncioGspreadClientManager
from gspread import Cell
from google.oauth2.service_account import Credentials
from asyncio import run, sleep
import pandas as pd


def get_creds():
    creds = Credentials.from_service_account_file("./service_credentials.json")
    scoped = creds.with_scopes([
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ])
    return scoped


async def get_sheet():
    account_manager = AsyncioGspreadClientManager(get_creds)
    gc = await account_manager.authorize()
    sh = await gc.open('БОТ Боулдер 2025')
    return sh


sheet = run(get_sheet())


async def get_worksheet():
    account_manager = AsyncioGspreadClientManager(get_creds)
    gc = await account_manager.authorize()
    sh = await gc.open('БОТ Боулдер 2025')
    wks = await sh.get_worksheet(0)
    return wks


async def local_data():
    wks = await get_worksheet()
    table = await wks.get()
    dataframe = pd.DataFrame(table[1:], columns=table[0])
    dataframe.index += 1
    ids = dataframe['Стартовый номер']
    fcs = dataframe['Фамилия Имя '].str.lower()
    return dataframe, ids, fcs


df, id_column, fcs_column = run(local_data())


async def mark(wks, row, stand):
    await wks.update_cell(row, 7 + stand, 1)
    return 1


async def unmark(wks, row, stand):
    await wks.update_cell(row, 7 + stand, '')
    return 1


async def test():
    wks = await get_worksheet()
    stand = 5
    await wks.update_cells([Cell(int(row) + 1, stand + 7, '1') for row in id_column], 'USER_ENTERED')
    await sleep(3)
    await wks.update_cells([Cell(int(row) + 1, stand + 7, '') for row in id_column])


if __name__ == '__main__':
    run(test())
