"""Alternate the upper/lower half of timetable cells on consecutive weeks."""
from datetime import date, datetime

# User-defined reference: upper lessons start in the week of 14 September 2026.
UPPER_WEEK_MONDAY = date(2026, 9, 14)
DAY_LABELS = {'Mn': 'Dushanba', 'Tu': 'Seshanba', 'Wed': 'Chorshanba',
              'Thu': 'Payshanba', 'Fri': 'Juma', 'Sat': 'Shanba'}


def active_week_slot(target_date: date | datetime) -> int:
    day = target_date.date() if isinstance(target_date, datetime) else target_date
    return ((day - UPPER_WEEK_MONDAY).days // 7) % 2


def day_bounds(svg) -> dict[str, tuple[float, float]]:
    """Use the actual day-label rectangles, independent of SVG scaling."""
    rectangles = [r for r in svg.find_all('rect') if not r.find('title')]
    result = {}
    for label in svg.find_all('text'):
        day = DAY_LABELS.get(label.get_text(strip=True))
        if not day:
            continue
        lx, ly = float(label.get('x', 0)), float(label.get('y', 0))
        candidates = []
        for rect in rectangles:
            x, y = float(rect.get('x', 0)), float(rect.get('y', 0))
            width, height = float(rect.get('width', 0)), float(rect.get('height', 0))
            if width > 0 and height > 0 and x <= lx <= x + width and y <= ly <= y + height:
                candidates.append((width * height, y, height))
        if candidates:
            _, top, height = min(candidates)
            result[day] = (top, top + height)
    return result


def cell_week_slot(rect, bounds: tuple[float, float] | None) -> int | None:
    """Full-height and horizontally split cells repeat every week."""
    if bounds is None:
        return None
    top, bottom = bounds
    height = bottom - top
    cell_height = float(rect.get('height', 0))
    cell_top = float(rect.get('y', 0))
    tolerance = height * 0.01
    if abs(cell_height - height / 2) > tolerance:
        return None
    if abs(cell_top - top) <= tolerance:
        return 0
    if abs(cell_top - (top + height / 2)) <= tolerance:
        return 1
    return None


def filter_week_lessons(lessons: list[dict], target_date: date | datetime) -> list[dict]:
    active = active_week_slot(target_date)
    return [lesson for lesson in lessons if lesson.get('_week_slot') in (None, active)]
