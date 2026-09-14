from aiogram.fsm.state import State, StatesGroup


class TutorAttendanceState(StatesGroup):
    picking_group = State()
    picking_para = State()
    marking_absent = State()


class AdminTutorState(StatesGroup):
    entering_tutor_name = State()
    entering_tutor_id = State()
    picking_group = State()


class AddAdminState(StatesGroup):
    entering_telegram_id = State()


class SheetsSettingsState(StatesGroup):
    entering_spreadsheet_id = State()


class RoomRefreshSettingsState(StatesGroup):
    entering_interval = State()


class AdminEditState(StatesGroup):
    picking_date = State()
    picking_para = State()
    picking_groups = State()


class AdminHistState(StatesGroup):
    picking_date = State()
    picking_paras = State()
    picking_groups = State()


class ImportExportState(StatesGroup):
    waiting_student_file = State()
    waiting_replace_all_students_file = State()
    waiting_single_group_select = State()
    waiting_single_group_file = State()
    waiting_tutor_file = State()
    waiting_kafedra_file = State()
    waiting_edupage_group_file = State()
