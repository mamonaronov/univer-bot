from aiogram import Router

from handlers.catalog import router as catalog_router
from handlers.search import router as search_router

__all__ = ["router", "setup_routers"]


def setup_routers() -> Router:
    root = Router()
    root.include_router(search_router)   # первым: иначе any_text перехватит
    root.include_router(catalog_router)
    return root


router = catalog_router  # обратная совместимость с bot.py