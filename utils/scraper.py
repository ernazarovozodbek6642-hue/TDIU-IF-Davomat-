"""
scraper.py — Edupage dan dars jadvalini yig'ish (Selenium Headless)
"""
import os
import glob
import logging
import re
from datetime import datetime, timedelta
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.common.exceptions import WebDriverException
from selenium.webdriver.support.ui import WebDriverWait
from data.edupage_catalog import TIMETABLE_NUM, COURSE_ID_RANGES, normalize_subject
from utils.timetable_weeks import day_bounds, cell_week_slot, filter_week_lessons
from data.constants import (
    DAYS_UZ, DAY_Y_RANGES, PERIOD_X_RANGES,
    ID_TO_NAME, GURUH_INFO, get_kafedra as default_get_kafedra, get_kurs
)


def find_chrome_binary() -> str | None:
    """Tizimda mavjud bo'lgan Chrome / Chromium binary faylini avtomatik topish"""
    custom_bin = os.environ.get('CHROME_BIN')
    if custom_bin and os.path.exists(custom_bin):
        return custom_bin

    user_home = os.path.expanduser('~')
    possible_paths = [
        r'C:\Program Files\Google\Chrome\Application\chrome.exe',
        r'C:\Program Files (x86)\Google\Chrome\Application\chrome.exe',
        os.path.join(user_home, r'AppData\Local\Google\Chrome\Application\chrome.exe'),
        os.path.join(user_home, r'AppData\Local\ms-playwright\chromium-1200\chrome-win64\chrome.exe'),
    ]

    playwright_chromes = glob.glob(os.path.join(user_home, r'AppData\Local\ms-playwright\chromium-*\chrome-win64\chrome.exe'))
    possible_paths.extend(playwright_chromes)

    for path in possible_paths:
        if os.path.exists(path):
            logging.info(f"Mavjud Chrome/Chromium binary topildi: {path}")
            return path

    return None


def get_driver():
    options = Options()
    options.add_argument('--headless=new')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--disable-gpu')
    options.add_argument('--disable-setuid-sandbox')
    options.add_argument('--disable-extensions')
    options.add_argument('--blink-settings=imagesEnabled=false')
    options.add_argument('--window-size=1920,1080')
    options.add_argument('--log-level=3')
    options.add_argument('--remote-debugging-pipe')
    options.add_argument('--lang=uz-UZ')
    # EduPage readiness is checked explicitly; renderer load events may stall.
    options.page_load_strategy = 'none'

    chrome_bin = find_chrome_binary()
    if chrome_bin:
        options.binary_location = chrome_bin

    driver_path = os.environ.get('CHROMEDRIVER_PATH', '').strip()
    if driver_path and os.path.isfile(driver_path):
        driver = webdriver.Chrome(service=Service(driver_path), options=options)
    else:
        # Local muhitda Selenium Manager mos drayverni topadi. Docker image esa
        # CHROMEDRIVER_PATH orqali apt bilan o'rnatilgan drayverni ishlatadi.
        driver = webdriver.Chrome(options=options)
    timeout = int(os.environ.get('SELENIUM_PAGE_LOAD_TIMEOUT', '45'))
    driver.set_page_load_timeout(timeout)
    driver.set_script_timeout(timeout)
    return driver


def load_timetable_page(driver, url: str):
    """Clear the previous group's DOM before waiting for the requested SVG."""
    timeout = int(os.environ.get('SELENIUM_PAGE_LOAD_TIMEOUT', '45'))
    driver.get('about:blank')
    WebDriverWait(driver, timeout).until(
        lambda d: d.current_url == 'about:blank'
        and not d.find_elements('css selector', 'svg')
    )
    driver.get(url)
    WebDriverWait(driver, timeout).until(
        lambda d: d.current_url == url
        and d.find_elements('css selector', 'svg g > text')
    )
    return driver.page_source


def _resolve_kafedra(subject_name: str, custom_kafedra_map: dict | None = None) -> str:
    if custom_kafedra_map:
        for k, v in custom_kafedra_map.items():
            if k.casefold() == subject_name.casefold():
                return v
        for k, v in sorted(custom_kafedra_map.items(), key=lambda item: len(item[0]), reverse=True):
            if k.lower() in subject_name.lower():
                return v
    return default_get_kafedra(subject_name)


def _period_numbers_for_rect(x: float, width: float) -> list[str]:
    """Return every timetable period covered by a lesson rectangle."""
    right = x + max(width, 0)
    periods = []
    for x_min, x_max, period_num in PERIOD_X_RANGES:
        # Ranges in constants are inclusive; one pixel closes the SVG boundary.
        overlap = min(right, x_max + 1) - max(x, x_min)
        if overlap > 1:
            periods.append(period_num)
    return periods


def _positioned_svg_texts(svg) -> list[tuple[float, float, str]]:
    result = []
    for tag in svg.find_all('text'):
        try:
            x = float(tag.get('x'))
            y = float(tag.get('y'))
        except (TypeError, ValueError):
            continue
        text = ' '.join(tag.get_text(' ', strip=True).split())
        if text:
            result.append((x, y, text))
    return result


def _displayed_teacher_for_rect(
    rect,
    positioned_texts: list[tuple[float, float, str]],
    fallback: str,
) -> str:
    """Use the teacher label printed at the top of the EduPage lesson cell."""
    x = float(rect.get('x', 0))
    y = float(rect.get('y', 0))
    width = float(rect.get('width', 0))
    height = float(rect.get('height', 0))
    top_band = max(20.0, height * 0.15)
    candidates = sorted(
        (text_y, text_x, text)
        for text_x, text_y, text in positioned_texts
        if x <= text_x <= x + width and y <= text_y <= y + top_band
    )
    if not candidates:
        return fallback
    first_y = candidates[0][0]
    labels = [text for text_y, _, text in candidates if abs(text_y - first_y) <= 1]
    return ' '.join(dict.fromkeys(labels)) or fallback


def _normalize_room(room: str) -> str:
    """Keep building/room only; remove capacity and room annotations."""
    normalized = []
    for part in re.split(r'\s+/\s+', room.strip()):
        value = re.sub(r'/+', '/', part.strip())
        value = re.sub(r'-\d+\b.*$', '', value).strip()
        normalized.append(value)
    return ' / '.join(value for value in normalized if value)


def scrape_one_group_with_driver(
    driver,
    group: dict,
    day_name: str | None,
    kafedra_map: dict | None = None,
    id_to_name_map: dict | None = None,
    cancel_event=None,
) -> list:
    lessons = []
    try:
        if cancel_event is not None and cancel_event.is_set():
            return []
        soup = BeautifulSoup(load_timetable_page(driver, group['url']), 'html.parser')
        svg = soup.find('svg')
        if not svg:
            raise WebDriverException('EduPage jadval SVG elementi topilmadi')

        resolved_name = (id_to_name_map or {}).get(group['id']) or ID_TO_NAME.get(group['id'], group['id'])
        group_name_svg = resolved_name
        heading = svg.select_one('g > text')
        if heading and heading.get_text(strip=True):
            group_name_svg = heading.get_text(strip=True)

        kurs = group.get('kurs') or get_kurs(group['id'])
        bounds_by_day = day_bounds(svg)
        positioned_texts = _positioned_svg_texts(svg)

        for rect in svg.find_all('rect'):
            if cancel_event is not None and cancel_event.is_set():
                return []
            title_tag = rect.find('title')
            if not title_tag:
                continue
            text = title_tag.get_text(strip=True)
            if not text or '\n' not in text:
                continue

            lines = text.split('\n')
            subject = lines[0].strip()
            title_teacher = lines[1].strip() if len(lines) > 1 else ''
            teacher = _displayed_teacher_for_rect(rect, positioned_texts, title_teacher)
            room = lines[2].strip() if len(lines) > 2 else ''

            x = float(rect.get('x', 0))
            width = float(rect.get('width', 0))
            y = float(rect.get('y', 0))

            day = None
            day_ranges = [(top, bottom, name) for name, (top, bottom) in bounds_by_day.items()]
            for y_min, y_max, d_name in day_ranges or DAY_Y_RANGES:
                if y_min <= y < y_max:
                    day = d_name
                    break
            if day is None or (day_name is not None and day != day_name):
                continue

            period_numbers = _period_numbers_for_rect(x, width)
            if not period_numbers:
                period_numbers = ['']

            lesson_type = ''
            if 'Jismoniy madaniyat' in subject and '(' in subject:
                room = 'Sport kompleksi'
                subject = 'Jismoniy madaniyat va Sport'
                lesson_type = 'Seminar'
            elif '(Ma)' in subject or '(ma)' in subject:
                lesson_type = "Ma'ruza"
                subject = subject.replace('(Ma)', '').replace('(ma)', '').strip()
            elif '(Sem)' in subject or '(sem)' in subject:
                lesson_type = "Seminar"
                subject = subject.replace('(Sem)', '').replace('(sem)', '').strip()
            elif '(Am)' in subject or '(am)' in subject:
                lesson_type = "Seminar"
                subject = subject.replace('(Am)', '').replace('(am)', '').strip()
            elif '(lab)' in subject.casefold():
                lesson_type = 'Laboratoriya'
            if not lesson_type:
                lesson_type = "Seminar"
            subject = normalize_subject(subject)
            room = _normalize_room(room)

            talaba_soni = GURUH_INFO.get(group_name_svg, {}).get('soni', '')

            gid_sort = int(group['id']) if group['id'].isdigit() else 0

            lesson = {
                'Filtr uchun': kurs,
                't/r': 0,
                'Guruh': group_name_svg,
                "Professor-o'qituvchining F.I.Sh": teacher,
                'Fan nomi': subject,
                'Kafedra': _resolve_kafedra(subject, kafedra_map),
                'Xona': room,
                'Talabalar soni': talaba_soni,
                'shundan, kelganlari': '',
                'kelmagan-lari': '',
                'Davomat, % da': '',
                "Darsda yo'q talabalarning F.I.Sh.": '',
                "Mashg'ulot turi": lesson_type,
                'Tyutor': '',  # Filled from current database assignments before upload.
                '_group_id': gid_sort,
                '_day': day,
                '_week_slot': cell_week_slot(rect, bounds_by_day.get(day)),
            }
            for period_num in period_numbers:
                lessons.append({**lesson, 'Juft-lik': period_num})

    except WebDriverException:
        raise
    except Exception as e:
        raise RuntimeError(f"EduPage jadvalini o‘qishda xato (guruh {group['id']})") from e
    return lessons


def _close_driver(driver):
    if driver is not None:
        try:
            driver.quit()
        except Exception:
            logging.warning('EduPage brauzerini yopishda xato', exc_info=True)


def scrape_timetable(
    target_date: datetime,
    progress_callback=None,
    kurs: str = "1",
    kafedra_map: dict | None = None,
    custom_edupage_groups: list | None = None,
    id_to_name_map: dict | None = None,
    whole_week: bool = False,
    cancel_event=None,
) -> list:
    day_name = None if whole_week else DAYS_UZ[target_date.weekday()]

    group_links = []
    if custom_edupage_groups:
        for eg in custom_edupage_groups:
            num_p = eg.num_param or TIMETABLE_NUM
            group_links.append({
                'id': str(eg.edupage_id),
                'name': eg.group_name,
                'kurs': eg.kurs,
                'url': f"https://tsue.edupage.org/timetable/view.php?num={num_p}&class=*{eg.edupage_id}"
            })
    else:
        course = str(kurs).removesuffix('-kurs')
        if course != 'all' and course not in COURSE_ID_RANGES:
            raise ValueError(f'Noma’lum kurs: {kurs}')
        courses = COURSE_ID_RANGES if course == 'all' else {course: COURSE_ID_RANGES[course]}
        group_ids = [gid for first, last in courses.values() for gid in range(first, last + 1)]
        num_param = TIMETABLE_NUM

        group_links = [
            {
                'id': str(gid),
                'kurs': get_kurs(str(gid)),
                'url': f"https://tsue.edupage.org/timetable/view.php?num={num_param}&class=*{gid}"
            }
            for gid in group_ids
        ]

    total = len(group_links)
    kurs_label = 'Barcha kurslar' if kurs == 'all' else f'{kurs}-kurs'
    period_label = (f"{target_date:%d.%m}–{target_date + timedelta(days=5):%d.%m.%Y}"
                    if whole_week else target_date.strftime('%d.%m.%Y'))
    all_lessons = []
    driver = get_driver()

    try:
        for i, group in enumerate(group_links, 1):
            if cancel_event is not None and cancel_event.is_set():
                break
            gname = (id_to_name_map or {}).get(group['id']) or ID_TO_NAME.get(group['id'], group['id'])
            if progress_callback:
                percent = int((i / total) * 100)
                filled = int(percent / 5)
                bar = "█" * filled + "░" * (20 - filled)
                progress_callback(
                    f"🕐 <b>{kurs_label} | {period_label}</b> jadvali yuklanmoqda...\n\n"
                    f"<b>Jarayon:</b> [{bar}] {percent}%\n"
                    f"⏳ [{i}/{total}] <b>{gname}</b> tekshirilmoqda..."
                )

            for attempt in range(1, 4):
                if cancel_event is not None and cancel_event.is_set():
                    break
                try:
                    if driver is None:
                        driver = get_driver()
                    result = scrape_one_group_with_driver(
                        driver, group, day_name, kafedra_map, id_to_name_map, cancel_event
                    )
                    break
                except WebDriverException as exc:
                    logging.warning(
                        'EduPage urinish %s/3 muvaffaqiyatsiz (guruh %s): %s: %s',
                        attempt, group['id'], type(exc).__name__, str(exc)[:1500],
                    )
                    _close_driver(driver)
                    driver = None
                    if cancel_event is not None and cancel_event.is_set():
                        break
                    if attempt == 3:
                        raise RuntimeError(
                            f'EduPage bilan ulanish tiklanmadi (guruh {group["id"]}). '
                            'Chala jadval yuklanmadi. Keyinroq qayta urinib ko‘ring.'
                        ) from exc
            if cancel_event is not None and cancel_event.is_set():
                break
            all_lessons.extend(filter_week_lessons(result, target_date))
    finally:
        _close_driver(driver)

    all_lessons.sort(key=lambda x: (x['Juft-lik'], x['_group_id']))
    for i, lesson in enumerate(all_lessons, 1):
        lesson['t/r'] = i

    return all_lessons


def scrape_week_timetable(
    target_date: datetime, progress_callback=None, kurs: str = 'all',
    kafedra_map: dict | None = None, custom_edupage_groups: list | None = None,
    id_to_name_map: dict | None = None, cancel_event=None,
) -> dict[datetime, list]:
    """Fetch each group once and split its weekly timetable into Monday–Saturday."""
    monday = target_date - timedelta(days=target_date.weekday())
    lessons = scrape_timetable(monday, progress_callback, kurs, kafedra_map,
                               custom_edupage_groups, id_to_name_map,
                               whole_week=True, cancel_event=cancel_event)
    result = {monday + timedelta(days=i): [] for i in range(6)}
    dates = {DAYS_UZ[day.weekday()]: day for day in result}
    for lesson in lessons:
        result[dates[lesson['_day']]].append(lesson)
    for daily_lessons in result.values():
        for index, lesson in enumerate(daily_lessons, 1):
            lesson['t/r'] = index
    return result
