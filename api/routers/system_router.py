import logging
from fastapi import APIRouter

logger = logging.getLogger(__name__)


def create_system_router(all_params):
    router = APIRouter(tags=['系统'])

    @router.get('/api/params')
    async def get_params():
        return all_params

    return router
