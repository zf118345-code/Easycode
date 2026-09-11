import logging
import os
import sys
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Body, Header, HTTPException, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse

from api.contracts.operations import (
    ExporterBuildRequest,
    ExporterPreflightRequest,
    ExporterSchemaRequest,
    PlayerConfigRequest,
    PlayerInstanceRequest,
    PlayerProfileApplyRequest,
    PlayerProfileRequest,
    PlayerRunRequest,
    ProjectPathRequest,
)
from api.idempotency import execute_idempotent
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
    async def save_exporter_schema(
        request: Request,
        payload: ExporterSchemaRequest,
        idempotency_key: str = Header(default='', alias='Idempotency-Key'),
    ):
        if export_service is None:
            _service_unavailable('ExportService')
        project_path = assert_matching_legacy_path(request, payload.project_path, writable=True)
        async def produce():
            return await run_in_threadpool(export_service.save_form_schema, project_path, payload.schema_data)

        return await execute_idempotent(
            idempotency_key,
            'legacy.exporter.schema.save',
            payload.model_dump(mode='json'),
            produce,
        )

    @router.post('/api/exporter/build')
    async def build_export_bundle(
        request: Request,
        payload: ExporterBuildRequest,
        idempotency_key: str = Header(default='', alias='Idempotency-Key'),
    ):
        if export_service is None:
            _service_unavailable('ExportService')
        project_path = assert_matching_legacy_path(request, payload.project_path, writable=True)
        async def produce():
            return await run_in_threadpool(
                export_service.build_export_bundle,
                project_path,
                payload.form_schema,
                payload.acknowledge_warnings,
            )

        return await execute_idempotent(
            idempotency_key,
            'legacy.exporter.build',
            payload.model_dump(mode='json'),
            produce,
        )

    @router.post('/api/exporter/preflight')
    async def run_exporter_preflight(request: Request, payload: ExporterPreflightRequest):
        from core.services.preflight_service import PreflightService

        return await run_in_threadpool(
            PreflightService.check,
            assert_matching_legacy_path(request, payload.project_path),
            payload.form_schema,
            payload.entry_task_id,
            payload.entry_node_id,
            payload.scope,
        )

    @router.post('/api/exporter/config')
    async def export_project_config(request: Request, payload: ProjectPathRequest):
        if export_service is None:
            _service_unavailable('ExportService')
        project_path = assert_matching_legacy_path(request, payload.project_path, writable=True)
        return await run_in_threadpool(export_service.export_project_config, project_path)

    @router.post('/api/exporter/compile-exe')
    async def compile_player_executable(
        request: Request,
        payload: ProjectPathRequest,
        idempotency_key: str = Header(default='', alias='Idempotency-Key'),
    ):
        if compiler_service is None:
            _service_unavailable('CompilerService')
        project_path = assert_matching_legacy_path(request, payload.project_path, writable=True)
        async def produce():
            return await run_in_threadpool(compiler_service.compile_player_exe, project_path)

        return await execute_idempotent(
            idempotency_key,
            'legacy.exporter.compile_exe',
            payload.model_dump(mode='json'),
            produce,
            timeout=900,
        )

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
    async def save_player_user_config(payload: PlayerConfigRequest, config_path: str | None = None):
        if player_service is None:
            _service_unavailable('PlayerService')
        return await run_in_threadpool(
            player_service.save_user_config,
            payload.user_config,
            config_path,
            payload.instance_id,
        )

    @router.post('/api/player/run')
    async def run_player_script(
        background_tasks: BackgroundTasks,
        payload: PlayerRunRequest = Body(default_factory=PlayerRunRequest),
        idempotency_key: str = Header(default='', alias='Idempotency-Key'),
    ):
        if player_service is None:
            _service_unavailable('PlayerService')
        async def produce():
            return player_service.run_script(
                background_tasks,
                payload.instance_id,
                payload.resume,
            )

        return await execute_idempotent(
            idempotency_key,
            'legacy.player.run',
            payload.model_dump(mode='json'),
            produce,
        )

    @router.post('/api/player/stop')
    async def stop_player_script(payload: PlayerInstanceRequest = Body(default_factory=PlayerInstanceRequest)):
        if player_service is None:
            _service_unavailable('PlayerService')
        return await run_in_threadpool(player_service.stop_script, payload.instance_id)

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
    async def save_player_profile(payload: PlayerProfileRequest):
        if player_service is None:
            _service_unavailable('PlayerService')
        return await run_in_threadpool(player_service.save_profile, payload.name, payload.user_config)

    @router.post('/api/player/profiles/{name}/apply')
    async def apply_player_profile(
        name: str,
        payload: PlayerProfileApplyRequest = Body(default_factory=PlayerProfileApplyRequest),
    ):
        if player_service is None:
            _service_unavailable('PlayerService')
        return await run_in_threadpool(player_service.apply_profile, name, payload.instance_id)

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
