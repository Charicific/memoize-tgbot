from aiogram import Router
from .common import router as common_router
from .daily import router as daily_router
from .srs import router as srs_router
from .srs_viewer import router as srs_viewer_router
from .ai import router as ai_router
from .community import router as community_router
from .streaks import router as streaks_router
from .admin import router as admin_router
from .visualize import router as visualize_router
from .chat import router as chat_router

def get_main_router() -> Router:
    main_router = Router()
    main_router.include_router(common_router)
    main_router.include_router(daily_router)
    main_router.include_router(srs_router)
    main_router.include_router(srs_viewer_router)
    main_router.include_router(ai_router)
    main_router.include_router(community_router)
    main_router.include_router(streaks_router)
    main_router.include_router(admin_router)
    main_router.include_router(visualize_router)
    
    # Chat fallback registered last to serve as catch-all
    main_router.include_router(chat_router)
    return main_router
