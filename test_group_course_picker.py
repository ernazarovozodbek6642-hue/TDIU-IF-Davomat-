import unittest

from data.constants import ALL_GROUPS
from keyboards.inline.attendance import get_course_picker_keyboard, get_groups_keyboard
from utils.group_courses import groups_by_course


class GroupCoursePickerTests(unittest.TestCase):
    def test_current_catalog_is_split_into_four_courses(self):
        courses = groups_by_course(ALL_GROUPS)
        self.assertEqual(
            {course: len(courses[course]) for course in ("1", "2", "3", "4")},
            {"1": 44, "2": 30, "3": 25, "4": 33},
        )
        self.assertEqual(sum(len(groups) for groups in courses.values()), 132)

    def test_unknown_legacy_group_is_inferred_from_admission_year(self):
        courses = groups_by_course(["TEST-1/26", "TEST-2/25", "NO-YEAR"])
        self.assertEqual(courses["1"], ["TEST-1/26"])
        self.assertEqual(courses["2"], ["TEST-2/25"])
        self.assertEqual(courses["other"], ["NO-YEAR"])

    def test_course_then_group_callbacks_keep_navigation(self):
        course_keyboard = get_course_picker_keyboard(
            {"1": 44, "2": 30, "3": 25, "4": 33}, prefix="att_course"
        )
        callbacks = [
            button.callback_data
            for row in course_keyboard.inline_keyboard
            for button in row
        ]
        self.assertTrue(all(f"att_course:{course}" in callbacks for course in "1234"))

        group_keyboard = get_groups_keyboard(
            ["I-900/26"], prefix="att_grp", back_cb="att_courses"
        )
        callbacks = [
            button.callback_data
            for row in group_keyboard.inline_keyboard
            for button in row
        ]
        self.assertIn("att_grp:I-900|26", callbacks)
        self.assertIn("att_courses", callbacks)


if __name__ == "__main__":
    unittest.main()
