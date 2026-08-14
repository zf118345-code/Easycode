import logging
import os

from fastapi import APIRouter, BackgroundTasks, Body, HTTPException
from fastapi.concurrency import run_in_threadpool

logger = logging.getLogger(__name__)


def _service_unavailable(name):
    raise HTTPException(status_code=503, detail=f'服务不可用: {name} 模块未加载')


def create_build_router(export_service, compiler_service, player_service):
    router = APIRouter(tags=['导出、打包与播放器'])

    # ====== 导出与编译 ======

    @router.get('/api/exporter/schema')
    async def get_exporter_schema(project_path: str):
        if export_service is None:
            _service_unavailable('ExportService')
        return await run_in_threadpool(export_service.get_form_schema, project_path)

    @router.post('/api/exporter/schema')
    async def save_exporter_schema(data: dict = Body(...)):
        if export_service is None:
            _service_unavailable('ExportService')
        project_path = data.get('project_path')
        schema_data = data.get('schema_data')
        return await run_in_threadpool(export_service.save_form_schema, project_path, schema_data)

    @router.post('/api/exporter/build')
    async def build_export_bundle(data: dict = Body(...)):
        if export_service is None:
            _service_unavailable('ExportService')
        project_path = data.get('project_path')
        form_schema = data.get('form_schema')
        return await run_in_threadpool(export_service.build_export_bundle, project_path, form_schema)

    @router.post('/api/exporter/compile-exe')
    async def compile_player_executable(data: dict = Body(...)):
        if compiler_service is None:
            _service_unavailable('CompilerService')
        project_path = data.get('project_path')
        return await run_in_threadpool(compiler_service.compile_player_exe, project_path)

    # ====== Player 运行端 ======

    @router.get('/api/player/init')
    async def player_init_session(project_path: str = None):
        if player_service is None:
            _service_unavailable('PlayerService')
        ebp_path = None
        config_path = None

        if project_path and os.path.exists(project_path):
            ebp_path = os.path.join(project_path, 'release', 'assets.ebp')
            config_path = os.path.join(project_path, 'release', 'user_config.json')

        if not ebp_path or not os.path.exists(ebp_path):
            projects_root = os.path.join(os.getcwd(), 'projects')
            if os.path.exists(projects_root):
                for sub_p in os.listdir(projects_root):
                    candidate_ebp = os.path.join(projects_root, sub_p, 'release', 'assets.ebp')
                    if os.path.exists(candidate_ebp):
                        ebp_path = candidate_ebp
                        config_path = os.path.join(projects_root, sub_p, 'release', 'user_config.json')
                        break

        if not ebp_path or not os.path.exists(ebp_path):
            ebp_path = os.path.join(os.getcwd(), 'release', 'assets.ebp')
            config_path = os.path.join(os.getcwd(), 'release', 'user_config.json')

        return await run_in_threadpool(player_service.init_session, ebp_path, config_path)

    @router.get('/api/player/providers')
    async def get_player_provider_options(provider: str):
        if player_service is None:
            _service_unavailable('PlayerService')
        options = await run_in_threadpool(player_service.get_provider_options, provider)
        return {'status': 'success', 'options': options}

    @router.post('/api/player/config')
    async def save_player_user_config(data: dict = Body(...), config_path: str = 'release/user_config.json'):
        if player_service is None:
            _service_unavailable('PlayerService')
        user_config = data.get('user_config')
        return await run_in_threadpool(player_service.save_user_config, user_config, config_path)

    @router.post('/api/player/run')
    async def run_player_script(background_tasks: BackgroundTasks):
        if player_service is None:
            _service_unavailable('PlayerService')
        return player_service.run_script(background_tasks)

    @router.post('/api/player/stop')
    async def stop_player_script():
        if player_service is None:
            _service_unavailable('PlayerService')
        return await run_in_threadpool(player_service.stop_script)

    return router
