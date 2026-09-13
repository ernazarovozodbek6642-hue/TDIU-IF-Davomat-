"""Shared course grouping for every group picker in the bot."""
import re
from datetime import date
from collections.abc import Iterable

from data.edupage_catalog import catalog_groups


COURSES = ("1", "2", "3", "4")


def _infer_course(group_name: str) -> str:
    match = re.search(r"/(\d{2})(?:\D.*)?$", group_name)
    if not match:
        return "other"
    admission_year = 2000 + int(match.group(1))
    current_year = date.today().year
    course = current_year - admission_year + 1
    return str(course) if 1 <= course <= 4 else "other"


def groups_by_course(group_names: Iterable[str] | None = None) -> dict[str, list[str]]:
    catalog = catalog_groups()
    course_by_name = {
        group["name"]: str(group["kurs"]).removesuffix("-kurs")
        for group in catalog
    }
    names = list(dict.fromkeys(
        group_names if group_names is not None else (group["name"] for group in catalog)
    ))
    result = {course: [] for course in COURSES}
    for name in names:
        course = course_by_name.get(name) or _infer_course(name)
        result.setdefault(course, []).append(name)
    for groups in result.values():
        groups.sort(key=str.casefold)
    return result
