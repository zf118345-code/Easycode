import logging
import os
import sys
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Body, HTTPException, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse
from api.workspace_context import assert_matching_legacy_path

logger = logging.getLogger(__name__)


def _service_unavailable(name):
    raise HTTPException(status_code=503, detail=f'服务不可用: {name} 模块未加载')


def create_build_router(export_service, compiler_service, player_service):
    router = APIRouter(tags=['导出、打包与播放器'])

    # ====== 导出与编译 ======

    @router.get('/api/exporter/schema')
    async def get_exporter_schema(request: Request, project_path: str | None = None):
        if export_service is None:
            _service_unavailable('ExportService')
        return await run_in_threadpool(export_service.get_form_schema, assert_matching_legacy_path(request, project_path))

    @router.post('/api/exporter/schema')
    async def save_exporter_schema(request: Request, data: dict = Body(...)):
        if export_service is None:
            _service_unavailable('ExportService')
        project_path = assert_matching_legacy_path(request, data.get('project_path'), writable=True)
        schema_data = data.get('schema_data')
        return await run_in_threadpool(export_service.save_form_schema, project_path, schema_data)

    @router.post('/api/exporter/build')
    async def build_export_bundle(request: Request, data: dict = Body(...)):
        if export_service is None:
            _service_unavailable('ExportService')
        project_path = assert_matching_legacy_path(request, data.get('project_path'), writable=True)
        form_schema = data.get('form_schema')
        return await run_in_threadpool(
            export_service.build_export_bundle,
            project_path,
            form_schema,
            bool(data.get('acknowledge_warnings', False)),
        )

    @router.post('/api/exporter/preflight')
    async def run_exporter_preflight(request: Request, data: dict = Body(...)):
        from core.services.preflight_service import PreflightService

        return await run_in_threadpool(
            PreflightService.check,
            assert_matching_legacy_path(request, data.get('project_path')),
            data.get('form_schema'),
            data.get('entry_task_id'),
            data.get('entry_node_id'),
            data.get('scope', 'publish'),
        )

    @router.post('/api/exporter/config')
    async def export_project_config(request: Request, data: dict = Body(...)):
        if export_service is None:
            _service_unavailable('ExportService')
        project_path = assert_matching_legacy_path(request, data.get('project_path'), writable=True)
        return await run_in_threadpool(export_service.export_project_config, project_path)

    @router.post('/api/exporter/compile-exe')
    async def compile_player_executable(request: Request, data: dict = Body(...)):
        if compiler_service is None:
            _service_unavailable('CompilerService')
        project_path = assert_matching_legacy_path(request, data.get('project_path'), writable=True)
        return await run_in_threadpool(compiler_service.compile_player_exe, project_path)

    # ====== Player 运行端 ======

    @router.get('/api/player/init')
    async def player_init_session():
        if player_service is None:
            _service_unavailable('PlayerService')
        configured = str(os.environ.get('EASYCODE_PLAYER_BUNDLE') or '').strip()
        if configured:
            ebp_path = str(Path(configured).resolve())
        elif getattr(sys, 'frozen', False):
            ebp_path = str(Path(sys.executable).resolve().parent / 'release' / 'assets.ebp')
        else:
            raise HTTPException(
                status_code=409,
                detail='开发模式必须显式设置 EASYCODE_PLAYER_BUNDLE，Player 不会扫描工作目录或其他项目',
            )
        if not os.path.isfile(ebp_path):
            raise HTTPException(status_code=404, detail=f'Player 资源包不存在: {ebp_path}')
        return await run_in_threadpool(player_service.init_session, ebp_path, None)

    @router.get('/api/player/providers')
    async def get_player_provider_options(provider: str):
        if player_service is None:
            _service_unavailable('PlayerService')
        options = await run_in_threadpool(player_service.get_provider_options, provider)
        return {'status': 'success', 'options': options}

    @router.post('/api/player/screen-snipping')
    async def open_player_screen_snipping():
        if player_service is None:
            _service_unavailable('PlayerService')
        return await run_in_threadpool(player_service.open_screen_snipping)

    @router.post('/api/player/config')
    async def save_player_user_config(data: dict = Body(...), config_path: str | None = None):
        if player_service is None:
            _service_unavailable('PlayerService')
        user_config = data.get('user_config')
        return await run_in_threadpool(
            player_service.save_user_config,
            user_config,
            config_path,
            data.get('instance_id') or 'instance-1',
        )

    @router.post('/api/player/run')
    async def run_player_script(background_tasks: BackgroundTasks, data: dict = Body(default={})):
        if player_service is None:
            _service_unavailable('PlayerService')
        return player_service.run_script(
            background_tasks,
            data.get('instance_id') or 'instance-1',
            bool(data.get('resume', False)),
        )

    @router.post('/api/player/stop')
    async def stop_player_script(data: dict = Body(default={})):
        if player_service is None:
            _service_unavailable('PlayerService')
        return await run_in_threadpool(player_service.stop_script, data.get('instance_id') or 'instance-1')

    @router.get('/api/player/status')
    async def get_player_status(instance_id: str = 'instance-1'):
        if player_service is None:
            _service_unavailable('PlayerService')
        return await run_in_threadpool(player_service.get_status, instance_id)

    @router.get('/api/player/environment')
    async def get_player_environment(instance_id: str = 'instance-1'):
        if player_service is None:
            _service_unavailable('PlayerService')
        return await run_in_threadpool(player_service.environment_check, instance_id)

    @router.get('/api/player/instances')
    async def list_player_instances():
        if player_service is None:
            _service_unavailable('PlayerService')
        return {'instances': await run_in_threadpool(player_service.list_instances)}

    @router.delete('/api/player/instances/{instance_id}')
    async def delete_player_instance(instance_id: str):
        if player_service is None:
            _service_unavailable('PlayerService')
        return await run_in_threadpool(player_service.remove_instance, instance_id)

    @router.get('/api/player/profiles')
    async def list_player_profiles():
        if player_service is None:
            _service_unavailable('PlayerService')
        return {'profiles': await run_in_threadpool(player_service.list_profiles)}

    @router.post('/api/player/profiles')
    async def save_player_profile(data: dict = Body(...)):
        if player_service is None:
            _service_unavailable('PlayerService')
        return await run_in_threadpool(player_service.save_profile, data.get('name'), data.get('user_config') or {})

    @router.post('/api/player/profiles/{name}/apply')
    async def apply_player_profile(name: str, data: dict = Body(default={})):
        if player_service is None:
            _service_unavailable('PlayerService')
        return await run_in_threadpool(player_service.apply_profile, name, data.get('instance_id') or 'instance-1')

    @router.delete('/api/player/profiles/{name}')
    async def delete_player_profile(name: str):
        if player_service is None:
            _service_unavailable('PlayerService')
        return await run_in_threadpool(player_service.delete_profile, name)

    @router.get('/api/player/diagnostics')
    async def download_player_diagnostics(instance_id: str = 'instance-1'):
        if player_service is None:
            _service_unavailable('PlayerService')
        path = await run_in_threadpool(player_service.create_diagnostic_package, instance_id)
        return FileResponse(path, filename=os.path.basename(path), media_type='application/zip')

    return router
