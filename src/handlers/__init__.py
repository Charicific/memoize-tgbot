from aiogram import Router
from .common import router as common_router
from .daily import router as daily_router
from .srs import router as srs_router
from .ai import router as ai_router
from .community import router as community_router

def get_main_router() -> Router:
    main_router = Router()
    main_router.include_router(common_router)
    main_router.include_router(daily_router)
    main_router.include_router(srs_router)
    main_router.include_router(ai_router)
    main_router.include_router(community_router)
    return main_router
