from fastapi import APIRouter, Body, HTTPException, Request
from fastapi.concurrency import run_in_threadpool

from api.workspace_context import request_project_path
from core.services.capability_service import CapabilityService


def create_capability_router():
    router = APIRouter(tags=['能力函数'])

    @router.get('/api/capabilities')
    async def list_capabilities(request: Request, reload: bool = False):
        project_path = request_project_path(request)
        discovered = await run_in_threadpool(
            lambda: CapabilityService.discover(project_path, force=bool(reload))
        )
        errors = []
        capabilities = []
        for item in discovered:
            if item.get('id') == '__discovery_errors__':
                errors.extend(item.get('errors') or [])
            else:
                capabilities.append(item)
        return {'capabilities': capabilities, 'errors': errors}

    @router.post('/api/capabilities/packages')
    async def create_capability_package(request: Request, payload: dict = Body(...)):
        project_path = request_project_path(request, writable=True)
        try:
            return await run_in_threadpool(
                lambda: CapabilityService.create_package(
                    project_path,
                    scope=payload.get('scope') or 'project',
                    package_id=payload.get('package_id') or '',
                    function_name=payload.get('function_name') or 'run',
                    display_name=payload.get('display_name') or '',
                    description=payload.get('description') or '',
                )
            )
        except Exception as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    return router
