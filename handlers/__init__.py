from aiogram import Router

from handlers.start import router as start_router
from handlers.jadval import router as jadval_router
from handlers.attendance import router as attendance_router
from handlers.admin import router as admin_router
from handlers.import_export import router as import_export_router
from handlers.history import router as history_router
from handlers.rooms import router as rooms_router


def setup_message_routers() -> Router:
    main_router = Router()

    # Routerlarni qo'shish tartibi
    main_router.include_router(start_router)
    main_router.include_router(jadval_router)
    main_router.include_router(rooms_router)
    main_router.include_router(admin_router)
    main_router.include_router(import_export_router)
    main_router.include_router(history_router)
    main_router.include_router(attendance_router)

    return main_router
