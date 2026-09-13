"""
sheets.py — Google Sheets API bilan ishlash
"""
import os
import logging
from datetime import datetime
import gspread
from gspread.http_client import BackOffHTTPClient
from googleapiclient.discovery import build

from data.config import SPREADSHEET_ID
from data.constants import DAYS_UZ, HEADERS, shorten_name
from utils.google_credentials import load_google_credentials

SCOPES = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/spreadsheets"
]

SHEET_HEADERS = [
    'Filtr uchun', 't/r', 'Guruh',
    "Professor-o'qituvchining F.I.SH", 'Fan nomi', 'Kafedrasi',
    'Xona', 'Juft-lik', 'Talabalar soni', 'shundan, kelganlari',
    'kelmagan-lari', 'Davomat, % da',
    "Darsda yo‘q talabalarning F.I.Sh.", "Mashg'ulot turi", 'Tyutor',
]


def _academic_year(target_date: datetime) -> str:
    start_year = target_date.year if target_date.month >= 9 else target_date.year - 1
    return f"{start_year}-{start_year + 1}"


def _course_sort_key(course: str) -> tuple[int, str]:
    prefix = str(course).split('-', 1)[0]
    return (int(prefix) if prefix.isdigit() else 99, str(course))


def _get_gspread_client():
    creds = load_google_credentials(SCOPES)
    return (
        gspread.authorize(creds, http_client=BackOffHTTPClient),
        build("sheets", "v4", credentials=creds, cache_discovery=False),
    )


def sheets_service_account_email() -> str:
    creds = load_google_credentials(SCOPES)
    return creds.service_account_email


def validate_spreadsheet_access(spreadsheet_id: str) -> str:
    """Read-only validation: ensure the bot can edit the selected spreadsheet."""
    creds = load_google_credentials(SCOPES)
    service = build('drive', 'v3', credentials=creds, cache_discovery=False)
    metadata = service.files().get(
        fileId=spreadsheet_id, fields='name,mimeType,capabilities(canEdit)',
        supportsAllDrives=True
    ).execute(num_retries=3)
    if metadata.get('mimeType') != 'application/vnd.google-apps.spreadsheet':
        raise ValueError('Tanlangan fayl Google Sheets jadvali emas.')
    if not metadata.get('capabilities', {}).get('canEdit'):
        raise ValueError('Botga ushbu fayl uchun Editor (tahrirlash) ruxsatini bering.')
    return metadata.get('name', spreadsheet_id)


def daily_sheet_exists(target_date: datetime, spreadsheet_id: str | None = None) -> bool:
    """Return whether the dated timetable sheet already exists."""
    return bool(existing_daily_sheet_names([target_date], spreadsheet_id))


def existing_daily_sheet_names(
    target_dates: list[datetime],
    spreadsheet_id: str | None = None,
) -> set[str]:
    """Return target timetable sheet names that are already present."""
    client, _ = _get_gspread_client()
    spreadsheet = client.open_by_key(spreadsheet_id or SPREADSHEET_ID)
    targets = {
        f"{target_date.strftime('%d.%m')} {DAYS_UZ[target_date.weekday()]}"
        for target_date in target_dates
    }
    return targets & {sheet.title for sheet in spreadsheet.worksheets()}


def upload_to_sheets(lessons: list, target_date: datetime, spreadsheet_id: str | None = None) -> tuple[str, str]:
    """Dars jadvalini tasdiqlangan fakultet shablonida Google Sheets ga yuklash."""
    client, service = _get_gspread_client()
    spreadsheet_id = spreadsheet_id or SPREADSHEET_ID

    day_name = DAYS_UZ[target_date.weekday()]
    sheet_name = f"{target_date.strftime('%d.%m')} {day_name}"
    spreadsheet = client.open_by_key(spreadsheet_id)
    try:
        sheet = spreadsheet.worksheet(sheet_name)
        sheet.clear()
    except gspread.WorksheetNotFound:
        sheet = spreadsheet.add_worksheet(title=sheet_name, rows=500, cols=20)

    sheet_id = sheet._properties["sheetId"]

    # Juftlik ichida kurs bo'yicha alohida bo'limlar.
    sections = {}
    for lesson in lessons:
        para = str(lesson.get("Juft-lik") or "0")
        course = str(lesson.get("Filtr uchun") or "1-kurs").split('.', 1)[0]
        sections.setdefault((para, course), []).append(lesson)

    roman = {1: "I", 2: "II", 3: "III", 4: "IV", 5: "V", 6: "VI", 7: "VII", 8: "VIII"}
    all_rows = [[
        "Iqtisodiyot fakultetida dars jarayonining borishi va talabalar davomati toʻgʻrisida maʼlumot",
        "", "", "", "", "", "", "", "", "", "", "",
        _academic_year(target_date), "", "",
    ], SHEET_HEADERS]
    row_meta = ["title", "header"]

    ordered_sections = sorted(
        sections.items(),
        key=lambda item: (
            int(item[0][0]) if item[0][0].isdigit() else 99,
            _course_sort_key(item[0][1]),
        ),
    )

    counter = 1
    for section_index, ((para, course), section_lessons) in enumerate(ordered_sections):
        para_int = int(para) if str(para).isdigit() else 1
        para_roman = roman.get(para_int, str(para))

        for source_lesson in section_lessons:
            lesson = dict(source_lesson)
            lesson['t/r'] = counter
            lesson['Filtr uchun'] = f"{course}. {para_roman}"
            row = [lesson.get(h, "") for h in HEADERS]
            for column_index in (8, 9, 10, 11, 14):
                row[column_index] = ""
            all_rows.append(row)
            row_meta.append("data")
            counter += 1

        jami = [
            f"{course}. {para_roman}", f"{course}, JAMI", "", "", "", "", "", "",
            "", "", "", "",
            "", "", ""
        ]
        all_rows.append(jami)
        row_meta.append("jami")

        if section_index < len(ordered_sections) - 1:
            all_rows.append([""] * len(SHEET_HEADERS))
            row_meta.append("separator")

    if len(all_rows) > sheet.row_count:
        sheet.resize(rows=len(all_rows))

    # Oldingi yuklashdan qolgan birlashtirish va formatlarni olib tashlash.
    service.spreadsheets().batchUpdate(
        spreadsheetId=spreadsheet_id,
        body={"requests": [
            {"unmergeCells": {"range": {
                "sheetId": sheet_id, "startRowIndex": 0, "endRowIndex": max(sheet.row_count, len(all_rows)),
                "startColumnIndex": 0, "endColumnIndex": 20,
            }}},
            {"repeatCell": {
                "range": {"sheetId": sheet_id, "startRowIndex": 0,
                          "endRowIndex": max(sheet.row_count, len(all_rows)),
                          "startColumnIndex": 0, "endColumnIndex": 20},
                "cell": {"userEnteredFormat": {}},
                "fields": "userEnteredFormat",
            }},
        ]},
    ).execute(num_retries=3)
    sheet.update(range_name="A1", values=all_rows, value_input_option="USER_ENTERED")

    total_rows = len(all_rows)
    total_cols = len(SHEET_HEADERS)
    border_s = {"style": "SOLID", "width": 1, "color": {"red": 0, "green": 0, "blue": 0}}
    requests = [{"updateSheetProperties": {
        "properties": {"sheetId": sheet_id, "gridProperties": {"frozenRowCount": 2}},
        "fields": "gridProperties.frozenRowCount",
    }}]

    col_widths = [63, 44, 92, 238, 222, 193, 81, 68, 105, 107, 110, 106, 250, 122, 146]
    for i, w in enumerate(col_widths):
        requests.append({"updateDimensionProperties": {
            "range": {"sheetId": sheet_id, "dimension": "COLUMNS", "startIndex": i, "endIndex": i + 1},
            "properties": {"pixelSize": w}, "fields": "pixelSize"
        }})

    for row_i, meta in enumerate(row_meta):
        if meta == "title":
            requests.append({"mergeCells": {
                "range": {"sheetId": sheet_id, "startRowIndex": row_i, "endRowIndex": row_i + 1,
                          "startColumnIndex": 0, "endColumnIndex": 12},
                "mergeType": "MERGE_ALL"
            }})
            requests.append({"repeatCell": {
                "range": {"sheetId": sheet_id, "startRowIndex": row_i, "endRowIndex": row_i + 1,
                          "startColumnIndex": 0, "endColumnIndex": 12},
                "cell": {"userEnteredFormat": {
                    "backgroundColor": {"red": 0.9882353, "green": 0.89411765, "blue": 0.8392157},
                    "textFormat": {"bold": True, "fontSize": 22, "fontFamily": "Times New Roman"},
                    "horizontalAlignment": "CENTER", "verticalAlignment": "MIDDLE",
                    "borders": {"bottom": border_s},
                }},
                "fields": "userEnteredFormat"
            }})
            requests.append({"repeatCell": {
                "range": {"sheetId": sheet_id, "startRowIndex": row_i, "endRowIndex": row_i + 1,
                          "startColumnIndex": 12, "endColumnIndex": 13},
                "cell": {"userEnteredFormat": {
                    "textFormat": {"bold": True, "fontSize": 14, "fontFamily": "Times New Roman"},
                    "horizontalAlignment": "CENTER", "verticalAlignment": "MIDDLE", "wrapStrategy": "WRAP",
                }},
                "fields": "userEnteredFormat",
            }})
            requests.append({"updateDimensionProperties": {
                "range": {"sheetId": sheet_id, "dimension": "ROWS", "startIndex": row_i, "endIndex": row_i + 1},
                "properties": {"pixelSize": 57}, "fields": "pixelSize",
            }})

        elif meta == "header":
            header_base = {
                "horizontalAlignment": "CENTER", "verticalAlignment": "MIDDLE", "wrapStrategy": "WRAP",
                "textFormat": {"bold": True, "fontSize": 14, "fontFamily": "Times New Roman"},
                "borders": {"top": border_s, "bottom": border_s, "left": border_s, "right": border_s},
            }
            requests.append({"repeatCell": {
                "range": {"sheetId": sheet_id, "startRowIndex": row_i, "endRowIndex": row_i + 1,
                          "startColumnIndex": 0, "endColumnIndex": 12},
                "cell": {"userEnteredFormat": {**header_base,
                    "backgroundColor": {"red": 1.0, "green": 0.7529412, "blue": 0.0}}},
                "fields": "userEnteredFormat"
            }})
            requests.append({"repeatCell": {
                "range": {"sheetId": sheet_id, "startRowIndex": row_i, "endRowIndex": row_i + 1,
                          "startColumnIndex": 12, "endColumnIndex": 15},
                "cell": {"userEnteredFormat": {**header_base,
                    "backgroundColor": {"red": 0.7882353, "green": 0.85490197, "blue": 0.972549}}},
                "fields": "userEnteredFormat",
            }})
            requests.append({"repeatCell": {
                "range": {"sheetId": sheet_id, "startRowIndex": row_i, "endRowIndex": row_i + 1,
                          "startColumnIndex": 0, "endColumnIndex": 1},
                "cell": {"userEnteredFormat": {"textFormat": {"fontSize": 10}}},
                "fields": "userEnteredFormat.textFormat.fontSize",
            }})
            requests.append({"repeatCell": {
                "range": {"sheetId": sheet_id, "startRowIndex": row_i, "endRowIndex": row_i + 1,
                          "startColumnIndex": 1, "endColumnIndex": 2},
                "cell": {"userEnteredFormat": {"textFormat": {"fontSize": 16}}},
                "fields": "userEnteredFormat.textFormat.fontSize",
            }})

        elif meta == "data":
            requests.append({"repeatCell": {
                "range": {"sheetId": sheet_id, "startRowIndex": row_i, "endRowIndex": row_i + 1,
                          "startColumnIndex": 0, "endColumnIndex": 15},
                "cell": {"userEnteredFormat": {
                    "backgroundColor": {"red": 1, "green": 1, "blue": 1},
                    "textFormat": {"fontSize": 12, "fontFamily": "Times New Roman"},
                    "horizontalAlignment": "CENTER", "verticalAlignment": "MIDDLE", "wrapStrategy": "WRAP",
                    "borders": {"top": border_s, "bottom": border_s, "left": border_s, "right": border_s},
                }},
                "fields": "userEnteredFormat"
            }})
            for start, end, size in ((0, 1, 9), (1, 3, 14), (7, 11, 14)):
                requests.append({"repeatCell": {
                    "range": {"sheetId": sheet_id, "startRowIndex": row_i, "endRowIndex": row_i + 1,
                              "startColumnIndex": start, "endColumnIndex": end},
                    "cell": {"userEnteredFormat": {"textFormat": {
                        "fontSize": size, "fontFamily": "Times New Roman",
                    }}},
                    "fields": "userEnteredFormat.textFormat",
                }})
            requests.append({"repeatCell": {
                "range": {"sheetId": sheet_id, "startRowIndex": row_i, "endRowIndex": row_i + 1,
                          "startColumnIndex": 11, "endColumnIndex": 12},
                "cell": {"userEnteredFormat": {
                    "numberFormat": {"type": "NUMBER", "pattern": "0.0"},
                    "textFormat": {"fontSize": 14, "fontFamily": "Times New Roman", "bold": True},
                }},
                "fields": "userEnteredFormat(numberFormat,textFormat)",
            }})
            requests.append({"repeatCell": {
                "range": {"sheetId": sheet_id, "startRowIndex": row_i, "endRowIndex": row_i + 1,
                          "startColumnIndex": 14, "endColumnIndex": 15},
                "cell": {"userEnteredFormat": {"horizontalAlignment": "LEFT"}},
                "fields": "userEnteredFormat.horizontalAlignment",
            }})

        elif meta == "jami":
            requests.append({"mergeCells": {
                "range": {"sheetId": sheet_id, "startRowIndex": row_i, "endRowIndex": row_i + 1,
                          "startColumnIndex": 1, "endColumnIndex": 8},
                "mergeType": "MERGE_ALL"
            }})
            requests.append({"repeatCell": {
                "range": {"sheetId": sheet_id, "startRowIndex": row_i, "endRowIndex": row_i + 1,
                          "startColumnIndex": 1, "endColumnIndex": 12},
                "cell": {"userEnteredFormat": {
                    "backgroundColor": {"red": 1.0, "green": 0.7529412, "blue": 0.0},
                    "textFormat": {"bold": True, "fontSize": 14, "fontFamily": "Times New Roman"},
                    "horizontalAlignment": "CENTER", "verticalAlignment": "MIDDLE",
                    "borders": {"top": border_s, "bottom": border_s, "left": border_s, "right": border_s},
                }},
                "fields": "userEnteredFormat"
            }})
            requests.append({"repeatCell": {
                "range": {"sheetId": sheet_id, "startRowIndex": row_i, "endRowIndex": row_i + 1,
                          "startColumnIndex": 0, "endColumnIndex": 1},
                "cell": {"userEnteredFormat": {
                    "textFormat": {"fontSize": 9, "fontFamily": "Times New Roman"},
                    "horizontalAlignment": "CENTER", "verticalAlignment": "MIDDLE", "wrapStrategy": "WRAP",
                }},
                "fields": "userEnteredFormat",
            }})
            requests.append({"repeatCell": {
                "range": {"sheetId": sheet_id, "startRowIndex": row_i, "endRowIndex": row_i + 1,
                          "startColumnIndex": 1, "endColumnIndex": 2},
                "cell": {"userEnteredFormat": {"textFormat": {"fontSize": 16, "bold": True}}},
                "fields": "userEnteredFormat.textFormat",
            }})
            requests.append({"repeatCell": {
                "range": {"sheetId": sheet_id, "startRowIndex": row_i, "endRowIndex": row_i + 1,
                          "startColumnIndex": 11, "endColumnIndex": 12},
                "cell": {"userEnteredFormat": {"numberFormat": {"type": "NUMBER", "pattern": "0.0"}}},
                "fields": "userEnteredFormat.numberFormat",
            }})

        elif meta == "separator":
            requests.append({"mergeCells": {
                "range": {"sheetId": sheet_id, "startRowIndex": row_i, "endRowIndex": row_i + 1,
                          "startColumnIndex": 0, "endColumnIndex": total_cols},
                "mergeType": "MERGE_ALL",
            }})
            requests.append({"repeatCell": {
                "range": {"sheetId": sheet_id, "startRowIndex": row_i, "endRowIndex": row_i + 1,
                          "startColumnIndex": 0, "endColumnIndex": total_cols},
                "cell": {"userEnteredFormat": {
                    "backgroundColor": {"red": 0.91764706, "green": 0.81960785, "blue": 0.8627451},
                    "horizontalAlignment": "CENTER", "verticalAlignment": "MIDDLE", "wrapStrategy": "WRAP",
                    "borders": {"bottom": border_s, "right": border_s},
                }},
                "fields": "userEnteredFormat",
            }})

        if row_i > 0:
            requests.append({"updateDimensionProperties": {
                "range": {"sheetId": sheet_id, "dimension": "ROWS", "startIndex": row_i, "endIndex": row_i + 1},
                "properties": {"pixelSize": 21}, "fields": "pixelSize",
            }})

    if requests:
        service.spreadsheets().batchUpdate(
            spreadsheetId=spreadsheet_id,
            body={"requests": requests}
        ).execute(num_retries=3)

    sheets_url = f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}"
    return sheets_url, sheet_name


def update_sheets_attendance(
    group_name: str,
    para: int,
    absent_students: list[str],
    target_date: datetime,
    total_students: int = 0,
    spreadsheet_id: str | None = None
) -> bool:
    """Sheets dagi mavjud varaqda kelmagan talabalarni yangilash"""
    try:
        client, _ = _get_gspread_client()
        sheet_name = f"{target_date.strftime('%d.%m')} {DAYS_UZ[target_date.weekday()]}"

        spreadsheet = client.open_by_key(spreadsheet_id or SPREADSHEET_ID)
        sheet = spreadsheet.worksheet(sheet_name)
    except Exception as e:
        logging.warning(f"update_sheets_attendance varaq ochishda xato: {e}")
        return False

    all_values = sheet.get_all_values()
    if len(all_values) < 2:
        return False

    headers = all_values[1]
    try:
        guruh_col = headers.index('Guruh')
        para_col = headers.index('Juft-lik')
        absent_col = next(
            headers.index(name)
            for name in ("Darsda yo‘q talabalarning F.I.Sh.", "Darsda yo'q talabalarning F.I.Sh.")
            if name in headers
        )
    except (ValueError, StopIteration):
        return False

    updates = []
    for row_i, row in enumerate(all_values):
        if row_i < 2:
            continue
        if (len(row) > guruh_col and row[guruh_col] == group_name and
                len(row) > para_col and row[para_col] == str(para)):

            short_names = [shorten_name(s) for s in absent_students]
            absent_text = "; ".join(short_names) if short_names else ""

            r = row_i + 1
            updates.append({"range": gspread.utils.rowcol_to_a1(r, absent_col + 1), "values": [[absent_text]]})

    if updates:
        sheet.batch_update(updates, value_input_option="USER_ENTERED")
        logging.info(f"✅ Sheets yangilandi: {group_name}, {para}-para")
        return True
    return False
