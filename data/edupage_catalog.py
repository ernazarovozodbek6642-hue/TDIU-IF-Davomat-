"""Verified public EduPage catalog, shared by scraping and import templates."""
import json
import re
from pathlib import Path

TIMETABLE_NUM = '94'
COURSE_ID_RANGES = {'1': (254, 297), '2': (305, 334), '3': (341, 365), '4': (372, 404)}


def normalize_subject(subject: str) -> str:
    subject = ' '.join(subject.split())
    if 'Jismoniy madaniyat' in subject and '(' in subject:
        return 'Jismoniy madaniyat va Sport'
    subject = re.sub(r'\((?:ma|sem|am|lab)\)', '', subject, flags=re.IGNORECASE).strip()
    # The lecture and seminar use two spellings of the same name in num=94.
    return {'Inson taraqiyoti': 'Inson taraqqiyoti'}.get(subject, subject)


def load_catalog() -> dict:
    return json.loads(Path(__file__).with_name('edupage_94.json').read_text(encoding='utf-8'))


def catalog_groups() -> list[dict]:
    return load_catalog()['groups']


def catalog_subjects() -> list[str]:
    return sorted({normalize_subject(subject) for group in catalog_groups()
                   for subject in group['raw_subjects'] if normalize_subject(subject)}, key=str.casefold)
