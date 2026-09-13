"""Validate user-supplied Google Sheets links and IDs."""
import re
from urllib.parse import urlparse


def parse_spreadsheet_id(value: str) -> str:
    value = value.strip()
    if '://' in value:
        url = urlparse(value)
        if url.scheme != 'https' or url.hostname != 'docs.google.com':
            raise ValueError('Google Sheets havolasini yoki ID raqamini yuboring.')
        match = re.fullmatch(r'/spreadsheets/(?:u/\d+/)?d/([A-Za-z0-9_-]+)(?:/.*)?', url.path)
        if not match:
            raise ValueError('Google Sheets havolasi noto‘g‘ri.')
        value = match.group(1)
    if not re.fullmatch(r'[A-Za-z0-9_-]{20,200}', value):
        raise ValueError('Google Sheets ID noto‘g‘ri. To‘liq havolani yuborishingiz ham mumkin.')
    return value
