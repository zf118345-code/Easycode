import os
import logging
from fastapi import APIRouter, HTTPException

logger = logging.getLogger(__name__)


def create_system_router(all_params):
    router = APIRouter(tags=["系统"])

    @router.get("/api/params")
    async def get_params():
        return all_params

    @router.get("/api/projects/verify")
    async def verify_project(project_path: str):
        if not os.path.exists(project_path):
            raise HTTPException(status_code=404, detail="项目路径不存在")
        return {
            "exists": True,
            "has_project_json": os.path.exists(os.path.join(project_path, "project.json")),
            "has_tasks_dir": os.path.exists(os.path.join(project_path, "tasks")),
            "name": os.path.basename(project_path),
        }

    return router
