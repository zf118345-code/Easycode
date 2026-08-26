# core/services/player_service.py
# P0 修复：停止机制（实际下发停止信号）、线程安全缓存（加锁）

import json
import os
import threading
import hashlib
import base64
import tempfile
import time
import zipfile
import platform
import sys
from datetime import datetime, timezone
from typing import Any

from fastapi import BackgroundTasks, HTTPException

from core.player.loader import PlayerAssetLoader
from core.player.providers import SystemDataProvider
from core.player.schema import build_user_config, normalize_form_schema, split_target, validate_user_config
from core.security.crypto import SecureAssetCrypto
from core.security.licensing import LicenseManager
from core.services.execution_service import ExecutionService


class PlayerService:
    """
    Player 客户端解密与运行期管理服务
    P0 修复：线程安全缓存、停止机制
    """

    _MEMORY_CACHE: dict[str, Any] = {
        'blueprint': None,
        'form_schema': None,
        'user_config': None,
        'templates': {},
        'context': {},
        'license_info': {},
        'ebp_path': '',
        'config_path': '',
        'bundle_hash': '',
        'project_id': '',
        'engine_path': '',
    }

    # P0 修复：缓存读写锁
    _cache_lock = threading.Lock()

    # P0 修复：当前运行的 execution_id
    _current_execution_id: str = None
    _instances: dict[str, dict[str, Any]] = {}
    _state_lock = threading.Lock()

    @staticmethod
    def _runtime_graphs(blueprint: dict[str, Any], *, include_page_map: bool = True) -> list[dict[str, Any]]:
        """Return every v3 graph that may contain Player-overridable nodes."""
        graphs: list[dict[str, Any]] = []
        main_graph = blueprint.get('main_graph')
        if isinstance(main_graph, dict):
            graphs.append(main_graph)
        for function in blueprint.get('functions') or []:
            if isinstance(function, dict) and isinstance(function.get('graph'), dict):
                graphs.append(function['graph'])
        page_map = blueprint.get('page_map')
        if include_page_map and isinstance(page_map, dict):
            graphs.append(page_map)
        return graphs

    @staticmethod
    def _runtime_entries(blueprint: dict[str, Any]) -> list[dict[str, Any]]:
        """Expose execution graphs in the compact shape used by status/UI code.

        Player release entry remains the main graph. Functions are referenced
        callables and cannot be launched as a root frame because their parameter
        and return contracts require a caller.
        """
        main_graph = blueprint.get('main_graph')
        if not isinstance(main_graph, dict):
            return []
        return [{
            'task_id': 'main',
            'task_name': '主流程',
            'nodes': main_graph.get('nodes') or [],
            'edges': main_graph.get('edges') or [],
        }]

    @classmethod
    def get_machine_code(cls) -> str:
        return LicenseManager.get_machine_code()

    @classmethod
    def _runtime_root(cls) -> str:
        base = os.environ.get('LOCALAPPDATA') or tempfile.gettempdir()
        with cls._cache_lock:
            bundle_hash = cls._MEMORY_CACHE.get('bundle_hash') or 'uninitialized'
            project_id = cls._MEMORY_CACHE.get('project_id') or str(bundle_hash)[:16]
        safe_project_id = ''.join(ch for ch in str(project_id) if ch.isalnum() or ch in '-_') or 'uninitialized'
        root = os.path.join(base, 'EasyCode', 'Player', safe_project_id)
        try:
            os.makedirs(root, exist_ok=True)
        except OSError:
            root = os.path.join(tempfile.gettempdir(), 'EasyCode', 'Player', safe_project_id)
            os.makedirs(root, exist_ok=True)
        return root

    @classmethod
    def _materialize_runtime_files(
        cls,
        runtime_files: dict[str, bytes],
        bundle_hash: str,
        project_id: str,
    ) -> str:
        base = os.environ.get('LOCALAPPDATA') or tempfile.gettempdir()
        safe_project_id = ''.join(ch for ch in str(project_id) if ch.isalnum() or ch in '-_') or f'bundle_{bundle_hash[:16]}'
        root = os.path.join(base, 'EasyCode', 'Player', safe_project_id, 'bundles', bundle_hash[:24], 'engine')
        os.makedirs(root, exist_ok=True)
        root_abs = os.path.abspath(root)
        for archive_name, payload in (runtime_files or {}).items():
            normalized = str(archive_name or '').replace('\\', '/').lstrip('/')
            if not normalized.startswith(('capabilities/', 'scripts/')):
                continue
            target = os.path.abspath(os.path.join(root_abs, *normalized.split('/')))
            if os.path.commonpath([root_abs, target]) != root_abs:
                raise HTTPException(status_code=422, detail=f'密包代码路径越界: {archive_name}')
            os.makedirs(os.path.dirname(target), exist_ok=True)
            temp_target = target + '.tmp'
            with open(temp_target, 'wb') as stream:
                stream.write(payload)
            os.replace(temp_target, target)
        return root_abs

    @classmethod
    def _ensure_instance(cls, instance_id: str) -> dict:
        clean_id = ''.join(ch for ch in str(instance_id or 'instance-1') if ch.isalnum() or ch in '-_')[:64]
        clean_id = clean_id or 'instance-1'
        if clean_id not in cls._instances:
            cls._instances[clean_id] = {
                'instance_id': clean_id,
                'state': 'ready' if cls._MEMORY_CACHE.get('blueprint') else 'initializing',
                'message': '就绪' if cls._MEMORY_CACHE.get('blueprint') else '等待初始化',
                'execution_id': None,
                'updated_at': time.time(),
            }
        return cls._instances[clean_id]

    @classmethod
    def _set_state(cls, instance_id: str, state: str, message: str = '', **extra) -> dict:
        with cls._state_lock:
            instance = cls._ensure_instance(instance_id)
            instance.update({'state': state, 'message': message, 'updated_at': time.time(), **extra})
            return dict(instance)

    @classmethod
    def get_status(cls, instance_id: str = 'instance-1') -> dict:
        with cls._state_lock:
            instance = dict(cls._ensure_instance(instance_id))
        execution_id = instance.get('execution_id')
        if execution_id:
            try:
                execution = ExecutionService.get_execution_status(execution_id)
                instance['runtime_metrics'] = execution.get('runtime_metrics') or {}
                raw_state = execution.get('status', {}).get('status')
                mapping = {
                    'running': 'running', 'success': 'success', 'error': 'error',
                    'stopped': 'stopped',
                }
                if raw_state in mapping and raw_state != instance.get('state'):
                    instance = cls._set_state(
                        instance_id,
                        mapping[raw_state],
                        execution.get('status', {}).get('message', ''),
                        failure_screenshot=execution.get('status', {}).get('failure_screenshot'),
                        latest_frame=execution.get('status', {}).get('latest_frame'),
                        runtime_metrics=execution.get('runtime_metrics') or {},
                    )
            except HTTPException:
                pass
        checkpoint_path = os.path.join(cls._runtime_root(), 'checkpoints', f'{instance["instance_id"]}.json')
        instance['can_resume'] = os.path.isfile(checkpoint_path) and instance.get('state') in {'error', 'stopped', 'ready'}
        return instance

    @classmethod
    def environment_check(cls, instance_id: str = 'instance-1') -> dict:
        checks = []

        def add(code, label, status, message):
            checks.append({'code': code, 'label': label, 'status': status, 'message': message})

        with cls._cache_lock:
            blueprint = cls._MEMORY_CACHE.get('blueprint') or {}
            schema = cls._MEMORY_CACHE.get('form_schema') or {}
            config = cls._MEMORY_CACHE.get('user_config') or {}
            templates = cls._MEMORY_CACHE.get('templates') or {}
            license_info = cls._MEMORY_CACHE.get('license_info') or {}
            engine_path = cls._MEMORY_CACHE.get('engine_path') or ''
        with cls._state_lock:
            instance = cls._ensure_instance(instance_id)
            config = instance.get('user_config') or config
        add('bundle', '脚本资源包', 'pass' if blueprint else 'error', '已加载并解密' if blueprint else '尚未初始化')
        tasks = cls._runtime_entries(blueprint)
        function_count = len([item for item in blueprint.get('functions') or [] if isinstance(item, dict)])
        add(
            'tasks', '运行入口', 'pass' if tasks and tasks[0].get('nodes') else 'error',
            f'主流程 + {function_count} 个引用函数' if tasks and tasks[0].get('nodes') else '主流程没有可执行节点',
        )
        errors = validate_user_config(schema, config) if schema else []
        add('config', '运行参数', 'pass' if not errors else 'error', '参数有效' if not errors else errors[0]['message'])
        add('templates', '视觉资产', 'pass', f'已加载 {len(templates)} 个模板')
        try:
            from core.services.capture_capability_service import CaptureCapabilityService

            capture_env = CaptureCapabilityService.environment()
            wgc = capture_env['windows_graphics_capture']
            add(
                'windows_capture', 'Windows 后台截图', 'pass' if wgc['available'] else 'warning',
                wgc['detail'],
            )
        except Exception as exc:
            add('windows_capture', 'Windows 后台截图', 'warning', str(exc))
        try:
            from core.services.capability_packaging_service import CapabilityPackagingService
            from core.services.capability_service import CapabilityService

            capability_ids = CapabilityPackagingService.references(blueprint)
            CapabilityService.discover(engine_path or None, force=True)
            missing = sorted(capability_id for capability_id in capability_ids if CapabilityService.resolve(engine_path or None, capability_id) is None)
            add(
                'capabilities', '能力运行时', 'error' if missing else 'pass',
                f'缺少: {", ".join(missing)}' if missing else f'{len(capability_ids)} 个能力可用',
            )
        except Exception as exc:
            add('capabilities', '能力运行时', 'error', str(exc))
        try:
            root = cls._runtime_root()
            probe = os.path.join(root, '.write-test')
            with open(probe, 'w', encoding='utf-8') as stream:
                stream.write('ok')
            os.unlink(probe)
            add('storage', '运行目录', 'pass', root)
        except Exception as exc:
            add('storage', '运行目录', 'error', f'不可写: {exc}')

        window_options = SystemDataProvider.get_window_list()
        windows = {item['value'] for item in window_options}
        title_counts = {}
        for item in window_options:
            title_counts[item.get('title')] = title_counts.get(item.get('title'), 0) + 1
        for group in schema.get('groups', []):
            for field in group.get('fields', []):
                if field.get('provider') != 'sys.window_list':
                    continue
                target = str(field.get('target') or '')
                slot, key = split_target(target)
                title = config.get(slot, {}).get(key) if slot else None
                if not title:
                    add('window', '目标窗口', 'error' if field.get('required') else 'warning', '未选择目标窗口')
                else:
                    add(
                        'window', '目标窗口',
                        'pass' if title in windows or title_counts.get(title) == 1 else 'error',
                        f'已找到: {title}' if title in windows or title_counts.get(title) == 1 else f'未找到或存在同名歧义: {title}',
                    )

        expires_at = license_info.get('expires_at') or license_info.get('expiry')
        if expires_at:
            try:
                expires = datetime.fromisoformat(str(expires_at).replace('Z', '+00:00'))
                if expires.tzinfo is None:
                    expires = expires.replace(tzinfo=timezone.utc)
                valid = expires > datetime.now(timezone.utc)
                add('license', '授权有效期', 'pass' if valid else 'error', str(expires_at))
            except ValueError:
                add('license', '授权有效期', 'warning', f'无法解析: {expires_at}')
        elif license_info:
            add('license', '授权信息', 'pass', '授权已加载')
        else:
            add('license', '授权信息', 'warning', '当前包未启用授权证书')

        counts = {status: sum(1 for check in checks if check['status'] == status) for status in ('error', 'warning', 'pass')}
        return {'status': 'error' if counts['error'] else ('warning' if counts['warning'] else 'pass'), 'counts': counts, 'checks': checks}

    @classmethod
    def init_session(
        cls, ebp_path: str, config_path: str, license_path: str = None, public_key_pem: str = None
    ) -> dict:
        if not ebp_path or not os.path.exists(ebp_path):
            raise HTTPException(
                status_code=404, detail=f'Player 内存解密失败: 未在目标路径找到脚本资源密包: {ebp_path}'
            )

        if not license_path:
            license_path = os.path.join(os.path.dirname(ebp_path), 'license.lic')

        license_payload = {}
        if os.path.exists(license_path) and public_key_pem:
            try:
                with open(license_path, encoding='utf-8') as f:
                    lic_str = f.read().strip()
                is_valid, err_msg, payload = LicenseManager.verify_license_payload(lic_str, public_key_pem)
                if not is_valid:
                    raise HTTPException(status_code=403, detail=f'卡密授权校验失败: {err_msg}')
                license_payload = payload
            except HTTPException:
                raise
            except Exception as e:
                raise HTTPException(status_code=403, detail=f'解析授权证书失败: {e}') from e

        machine_code = cls.get_machine_code()
        derived_key = SecureAssetCrypto.derive_key_from_machine(PlayerAssetLoader.DEFAULT_MASTER_KEY, machine_code)

        try:
            blueprint_data, form_schema, user_config, templates, context_data = PlayerAssetLoader.load_bundle_from_ebp(
                ebp_path, config_path, key=derived_key
            )
        except Exception:
            try:
                blueprint_data, form_schema, user_config, templates, context_data = PlayerAssetLoader.load_bundle_from_ebp(
                    ebp_path, config_path, key=PlayerAssetLoader.DEFAULT_MASTER_KEY
                )
            except Exception as e:
                raise HTTPException(status_code=500, detail=f'Player 内存解密失败: {e}') from e

        runtime_files = context_data.pop('_runtime_files', {}) if isinstance(context_data, dict) else {}
        form_schema = normalize_form_schema(form_schema)

        # P0 修复：加锁写入缓存
        with open(ebp_path, 'rb') as bundle_stream:
            bundle_hash = hashlib.sha256(bundle_stream.read()).hexdigest()
        project_id = str(blueprint_data.get('project_id') or f'bundle_{bundle_hash[:16]}')
        # 本地配置中的 secret 字段按当前密包/项目隔离密钥解密。普通字段保持
        # JSON 可读，秘密字段在磁盘上始终是 DPAPI/Fernet 密文。
        with cls._cache_lock:
            cls._MEMORY_CACHE['bundle_hash'] = bundle_hash
            cls._MEMORY_CACHE['project_id'] = project_id
        from core.services.player_secret_service import PlayerSecretService

        user_config = PlayerSecretService.transform_config(
            form_schema, user_config, decrypt=True, storage_root=cls._runtime_root(),
        )
        user_config = build_user_config(form_schema, user_config)
        blueprint_data.setdefault('variables', {}).update(user_config.get('vars') or {})
        for context_key, context_value in (user_config.get('ctx') or {}).items():
            blueprint_data['variables'][f'$ctx.{context_key}'] = context_value
        engine_path = cls._materialize_runtime_files(runtime_files, bundle_hash, project_id)
        with cls._cache_lock:
            cls._MEMORY_CACHE['blueprint'] = blueprint_data
            cls._MEMORY_CACHE['form_schema'] = form_schema
            cls._MEMORY_CACHE['user_config'] = user_config
            cls._MEMORY_CACHE['templates'] = templates
            cls._MEMORY_CACHE['context'] = context_data or {}
            cls._MEMORY_CACHE['license_info'] = license_payload
            cls._MEMORY_CACHE['ebp_path'] = os.path.abspath(ebp_path)
            cls._MEMORY_CACHE['config_path'] = os.path.abspath(config_path) if config_path else ''
            cls._MEMORY_CACHE['bundle_hash'] = bundle_hash
            cls._MEMORY_CACHE['project_id'] = project_id
            cls._MEMORY_CACHE['engine_path'] = engine_path
        with cls._state_lock:
            cls._instances = {}
            cls._ensure_instance('instance-1')
        from core.services.platform_runtime_service import platform_runtime_service

        platform_runtime_service.register_player(cls._runtime_root())

        return {
            'status': 'success',
            'machine_code': machine_code,
            'form_schema': form_schema,
            'user_config': user_config,
            'templates_count': len(templates),
            'license_info': license_payload,
            'environment': cls.environment_check('instance-1'),
            'runtime_status': cls.get_status('instance-1'),
        }

    @classmethod
    def get_provider_options(cls, provider_key: str) -> list[dict[str, str]]:
        return SystemDataProvider.resolve_provider(provider_key)

    @staticmethod
    def open_screen_snipping() -> dict:
        """Invoke Windows' native snipping UI; the result is returned via clipboard."""
        if os.name != 'nt':
            raise HTTPException(status_code=409, detail='当前系统不支持 Windows 截图工具')
        try:
            os.startfile('ms-screenclip:')  # type: ignore[attr-defined]
        except OSError as exc:
            raise HTTPException(status_code=500, detail=f'无法启动系统截图工具: {exc}') from exc
        return {'status': 'success'}

    @classmethod
    def _apply_runtime_overrides(
        cls,
        runtime_blueprint: dict,
        form_schema: dict,
        user_config: dict,
        memory_templates: dict,
    ) -> dict:
        """Apply only developer-declared settings/node bindings to a runtime copy."""
        templates = dict(memory_templates or {})
        node_index: dict[str, dict] = {}
        for graph in cls._runtime_graphs(runtime_blueprint):
            for node in graph.get('nodes') or []:
                if isinstance(node, dict) and node.get('node_id'):
                    node_index[str(node['node_id'])] = node

        overrides = user_config.get('overrides') or {}
        for group in form_schema.get('groups') or []:
            for field in group.get('fields') or []:
                target = str(field.get('target') or '')
                if target not in overrides:
                    continue
                value = overrides[target]
                if field.get('ui_type') == 'image_asset' and isinstance(value, str) and value.startswith('data:image/'):
                    try:
                        encoded = value.split(',', 1)[1]
                        raw = base64.b64decode(encoded, validate=True)
                        if len(raw) > 16 * 1024 * 1024:
                            raise ValueError('截图不能超过 16MB')
                        import cv2
                        import numpy as np

                        matrix = cv2.imdecode(np.frombuffer(raw, np.uint8), cv2.IMREAD_COLOR)
                        if matrix is None:
                            raise ValueError('图片解码失败')
                        template_key = f'player_override://{hashlib.sha256(raw).hexdigest()[:24]}'
                        templates[template_key] = matrix
                        value = template_key
                    except (ValueError, IndexError) as exc:
                        raise HTTPException(status_code=422, detail=f'Player 截图无效: {exc}') from exc

                if target.startswith('$settings.'):
                    setting_key = target[10:]
                    if not setting_key:
                        raise HTTPException(status_code=422, detail=f'项目设置绑定无效: {target}')
                    runtime_blueprint.setdefault('settings', {})[setting_key] = value
                    continue

                if target.startswith('$node.'):
                    parts = target.split('.', 2)
                    if len(parts) != 3:
                        raise HTTPException(status_code=422, detail=f'节点属性绑定无效: {target}')
                    node = node_index.get(parts[1])
                    if node is None:
                        raise HTTPException(status_code=422, detail=f'Player 绑定的节点不存在: {parts[1]}')
                    property_path = parts[2]
                    if property_path in {'delay_before', 'loop_count'}:
                        node[property_path] = value
                        continue
                    if not property_path.startswith('params.'):
                        raise HTTPException(status_code=422, detail=f'不允许在 Player 修改该节点字段: {property_path}')
                    keys = [key for key in property_path[7:].split('.') if key]
                    if not keys:
                        raise HTTPException(status_code=422, detail=f'节点参数绑定无效: {target}')
                    try:
                        cls._assign_existing_runtime_path(node.setdefault('params', {}), keys, value)
                    except (KeyError, IndexError, TypeError, ValueError):
                        raise HTTPException(status_code=422, detail=f'Player 绑定的节点参数不存在: {target}')
        return templates

    @staticmethod
    def _assign_existing_runtime_path(root: Any, keys: list[str], value: Any) -> None:
        """Write one preflight-approved dict/list leaf without changing structure."""
        if not keys:
            raise KeyError('empty path')
        cursor = root
        for key in keys[:-1]:
            if isinstance(cursor, dict) and key in cursor:
                cursor = cursor[key]
            elif isinstance(cursor, list) and key.isdigit() and 0 <= int(key) < len(cursor):
                cursor = cursor[int(key)]
            else:
                raise KeyError(key)
        leaf = keys[-1]
        if isinstance(cursor, dict) and leaf in cursor:
            cursor[leaf] = value
            return
        if isinstance(cursor, list) and leaf.isdigit() and 0 <= int(leaf) < len(cursor):
            cursor[int(leaf)] = value
            return
        raise KeyError(leaf)

    @classmethod
    def save_user_config(
        cls,
        user_config: dict,
        config_path: str | None = None,
        instance_id: str = 'instance-1',
    ) -> dict:
        if not user_config:
            raise HTTPException(status_code=400, detail='缺少 user_config 数据')

        with cls._cache_lock:
            form_schema = cls._MEMORY_CACHE.get('form_schema') or {}
        normalized_config = build_user_config(form_schema, user_config)
        errors = validate_user_config(form_schema, normalized_config)
        if errors:
            raise HTTPException(status_code=422, detail={'message': '运行参数校验失败', 'fields': errors})

        with cls._cache_lock:
            cls._MEMORY_CACHE['user_config'] = normalized_config
            configured_path = cls._MEMORY_CACHE.get('config_path')

        with cls._state_lock:
            cls._ensure_instance(instance_id)['user_config'] = normalized_config

        config_path = config_path or configured_path or os.path.join(cls._runtime_root(), 'user_config.json')

        config_dir = os.path.dirname(os.path.abspath(config_path))
        if not os.path.isdir(config_dir) or not os.access(config_dir, os.W_OK):
            config_path = os.path.join(cls._runtime_root(), 'user_config.json')

        try:
            temp_path = config_path + '.tmp'
            from core.services.player_secret_service import PlayerSecretService

            protected_config = PlayerSecretService.transform_config(
                form_schema, normalized_config, storage_root=cls._runtime_root(),
            )
            with open(temp_path, 'w', encoding='utf-8') as f:
                json.dump(protected_config, f, ensure_ascii=False, indent=2)
            os.replace(temp_path, config_path)
            return {'status': 'success', 'instance_id': instance_id}
        except Exception as e:
            raise HTTPException(status_code=500, detail=f'保存 user_config 失败: {e}') from e

    @classmethod
    def run_script(
        cls,
        background_tasks: BackgroundTasks,
        instance_id: str = 'instance-1',
        resume: bool = False,
    ) -> dict:
        """从解密后的内存对象倒灌参数并将内存模板打包注入给引擎。"""
        with cls._cache_lock:
            blueprint_data = cls._MEMORY_CACHE.get('blueprint')
            default_user_config = cls._MEMORY_CACHE.get('user_config') or {}
            memory_templates = cls._MEMORY_CACHE.get('templates') or {}
            form_schema = cls._MEMORY_CACHE.get('form_schema') or {}
            ebp_context = cls._MEMORY_CACHE.get('context') or {}

        with cls._state_lock:
            instance = cls._ensure_instance(instance_id)
            if instance.get('state') in {'starting', 'running', 'stopping'}:
                raise HTTPException(status_code=409, detail=f'实例 {instance_id} 已在运行')
            user_config = instance.get('user_config') or default_user_config

        cls._set_state(instance_id, 'validating', '正在校验环境与参数')

        if not blueprint_data:
            cls._set_state(instance_id, 'error', 'Player Session 未初始化')
            raise HTTPException(status_code=400, detail='Player Session 未初始化，请先调用 init_session')

        config_errors = validate_user_config(form_schema, user_config)
        if config_errors:
            cls._set_state(instance_id, 'error', config_errors[0]['message'])
            raise HTTPException(status_code=422, detail={'message': '运行参数校验失败', 'fields': config_errors})

        environment = cls.environment_check(instance_id)
        if environment['counts']['error']:
            cls._set_state(instance_id, 'error', '环境自检未通过')
            raise HTTPException(status_code=422, detail={'message': '环境自检未通过', 'environment': environment})

        # 1. 深度拷贝蓝图数据
        runtime_blueprint = json.loads(json.dumps(blueprint_data))
        if 'variables' not in runtime_blueprint:
            runtime_blueprint['variables'] = {}

        # 2. 执行三阶参数倒灌
        for vk, vv in user_config.get('vars', {}).items():
            runtime_blueprint['variables'][vk] = vv

        # 3. 应用开发者在 Schema 中明确开放的项目设置/节点属性；
        # 图片截图会解码为当前实例的内存模板，不修改密包原件。
        memory_templates = cls._apply_runtime_overrides(
            runtime_blueprint, form_schema, user_config, memory_templates
        )
        runtime_blueprint['_memory_templates'] = memory_templates

        # ⚡ 4. 上下文链路：密包内置 context（窗口预热默认值）+ 客户在表单里配置的 ctx 覆盖
        user_ctx = user_config.get('ctx') or {}
        merged_context = {**ebp_context}
        for k, v in user_ctx.items():
            if v not in (None, ''):
                merged_context[k] = v
        selected_window = str(merged_context.get('window_title') or '').strip()
        if selected_window.startswith('window:'):
            try:
                import win32gui
                import win32process

                hwnd = int(selected_window.split(':', 1)[1])
                if not win32gui.IsWindow(hwnd):
                    raise ValueError('窗口句柄已失效，请刷新列表后重新选择')
                _, pid = win32process.GetWindowThreadProcessId(hwnd)
                merged_context.update({
                    'work_mode': 'window',
                    'window_title': win32gui.GetWindowText(hwnd),
                    'window_hwnd': hwnd,
                    'window_process_id': int(pid),
                    'window_class_name': win32gui.GetClassName(hwnd),
                })
            except Exception as exc:
                cls._set_state(instance_id, 'error', f'目标窗口绑定失效: {exc}')
                raise HTTPException(status_code=409, detail=f'目标窗口绑定失效: {exc}') from exc
        if merged_context:
            runtime_blueprint['_player_context'] = merged_context

        # ⚡ 5. 运行入口：v3 Player 只能从主流程中的明确节点开始。
        tasks = cls._runtime_entries(runtime_blueprint)
        if not tasks or not tasks[0].get('nodes'):
            raise HTTPException(status_code=400, detail='密包中不包含有效主流程')

        entry = form_schema.get('entry') or {}
        entry_task_id = entry.get('task_id')
        entry_node_id = entry.get('node_id')
        if not entry_task_id or not entry_node_id:
            raise HTTPException(status_code=422, detail='密包未配置明确的 Player 运行入口')
        if entry_task_id != 'main':
            raise HTTPException(status_code=422, detail='Player 运行入口必须位于主流程；函数只能通过调用函数节点进入')
        entry_nodes = {str(item.get('node_id')): item for item in tasks[0].get('nodes') or [] if isinstance(item, dict)}
        if str(entry_node_id) not in entry_nodes:
            raise HTTPException(status_code=422, detail='Player 运行入口节点不在主流程中')

        checkpoint_dir = os.path.join(cls._runtime_root(), 'checkpoints')
        checkpoint_path = os.path.join(checkpoint_dir, f'{cls._ensure_instance(instance_id)["instance_id"]}.json')
        if resume:
            cls._set_state(instance_id, 'recovering', '正在从最近恢复点继续')
            if not os.path.isfile(checkpoint_path):
                cls._set_state(instance_id, 'error', '没有可用的恢复点')
                raise HTTPException(status_code=404, detail='没有可用的恢复点')
            try:
                with open(checkpoint_path, encoding='utf-8') as stream:
                    checkpoint_document = json.load(stream)
                from core.services.player_secret_service import PlayerSecretService

                checkpoint = PlayerSecretService.unprotect_document(
                    checkpoint_document, storage_root=cls._runtime_root(),
                )
                entry_task_id = checkpoint.get('task_id') or entry_task_id
                entry_node_id = checkpoint.get('node_id') or entry_node_id
                if entry_task_id != 'main' or str(entry_node_id) not in entry_nodes:
                    raise ValueError('恢复点引用了当前版本中不存在的主流程节点')
                runtime_blueprint['variables'].update(checkpoint.get('variables') or {})
            except Exception as exc:
                cls._set_state(instance_id, 'error', f'恢复点损坏: {exc}')
                raise HTTPException(status_code=422, detail=f'恢复点损坏: {exc}') from exc

        with cls._cache_lock:
            project_path = cls._MEMORY_CACHE.get('engine_path')
        if not project_path:
            project_path = os.path.join(cls._runtime_root(), 'engine')
        os.makedirs(project_path, exist_ok=True)

        cls._set_state(instance_id, 'starting', '正在创建执行实例')

        from core.services.player_secret_service import PlayerSecretService

        exec_result = ExecutionService.run_task(
            project_path,
            entry_task_id,
            entry_node_id,
            runtime_blueprint,
            background_tasks,
            persist_blueprint=False,
            runtime_dir=os.path.join(cls._runtime_root(), 'diagnostics'),
            checkpoint_path=checkpoint_path,
            instance_id=instance_id,
            isolate_process=True,
            checkpoint_storage_root=cls._runtime_root(),
            redact_values=PlayerSecretService.secret_values(form_schema, user_config),
        )

        if isinstance(exec_result, dict):
            exec_id = exec_result.get('execution_id') or exec_result.get('data', {}).get('execution_id')
            if exec_id:
                exec_result['execution_id'] = exec_id
                # P0 修复：记录当前 execution_id 供 stop_script 使用
                cls._current_execution_id = exec_id
                cls._set_state(instance_id, 'running', '自动化正在运行', execution_id=exec_id)
                # ⚡ 返回入口信息供前端展示（组名/节点名）
                entry_name = entry.get('node_name') or ''
                task_name = ''
                task_name = '主流程'
                exec_result['entry'] = {'task_name': task_name, 'node_name': entry_name}

        return exec_result

    @classmethod
    def stop_script(cls, instance_id: str = 'instance-1') -> dict:
        """P0 修复：实际下发停止信号"""
        with cls._state_lock:
            instance = cls._ensure_instance(instance_id)
            exec_id = instance.get('execution_id')
        if exec_id:
            cls._set_state(instance_id, 'stopping', '正在停止执行器')
            result = ExecutionService.stop_execution(exec_id)
            cls._set_state(instance_id, 'stopped', '用户主动停止', execution_id=exec_id)
            if cls._current_execution_id == exec_id:
                cls._current_execution_id = None
            return result
        return {'status': 'warning', 'message': '当前没有正在运行的脚本'}

    @classmethod
    def list_instances(cls) -> list[dict]:
        with cls._state_lock:
            ids = list(cls._instances) or ['instance-1']
        return [cls.get_status(instance_id) for instance_id in ids]

    @classmethod
    def remove_instance(cls, instance_id: str) -> dict:
        status = cls.get_status(instance_id)
        if status.get('state') in {'starting', 'running', 'stopping'}:
            raise HTTPException(status_code=409, detail='运行中的实例不能删除，请先停止')
        with cls._state_lock:
            if instance_id == 'instance-1':
                raise HTTPException(status_code=400, detail='默认实例不能删除')
            cls._instances.pop(instance_id, None)
        return {'status': 'success'}

    @classmethod
    def _profiles_path(cls) -> str:
        return os.path.join(cls._runtime_root(), 'profiles.json')

    @classmethod
    def _load_profiles(cls) -> dict:
        path = cls._profiles_path()
        if not os.path.isfile(path):
            return {}
        try:
            with open(path, encoding='utf-8-sig') as stream:
                value = json.load(stream)
            return value if isinstance(value, dict) else {}
        except (OSError, ValueError):
            return {}

    @classmethod
    def list_profiles(cls) -> list[dict]:
        return [
            {'name': name, 'updated_at': item.get('updated_at')}
            for name, item in sorted(cls._load_profiles().items())
            if isinstance(item, dict)
        ]

    @classmethod
    def save_profile(cls, name: str, user_config: dict) -> dict:
        clean_name = str(name or '').strip()
        if not clean_name or len(clean_name) > 64:
            raise HTTPException(status_code=400, detail='方案名称必须为 1-64 个字符')
        with cls._cache_lock:
            schema = cls._MEMORY_CACHE.get('form_schema') or {}
        normalized = build_user_config(schema, user_config)
        errors = validate_user_config(schema, normalized)
        if errors:
            raise HTTPException(status_code=422, detail={'message': '方案参数无效', 'fields': errors})
        profiles = cls._load_profiles()
        from core.services.player_secret_service import PlayerSecretService

        protected = PlayerSecretService.transform_config(schema, normalized, storage_root=cls._runtime_root())
        profiles[clean_name] = {'updated_at': datetime.now(timezone.utc).isoformat(), 'user_config': protected}
        path = cls._profiles_path()
        temp_path = path + '.tmp'
        with open(temp_path, 'w', encoding='utf-8') as stream:
            json.dump(profiles, stream, ensure_ascii=False, indent=2)
        os.replace(temp_path, path)
        return {'status': 'success', 'name': clean_name}

    @classmethod
    def apply_profile(cls, name: str, instance_id: str = 'instance-1') -> dict:
        profile = cls._load_profiles().get(name)
        if not isinstance(profile, dict):
            raise HTTPException(status_code=404, detail='配置方案不存在')
        with cls._cache_lock:
            schema = cls._MEMORY_CACHE.get('form_schema') or {}
        from core.services.player_secret_service import PlayerSecretService

        config = PlayerSecretService.transform_config(
            schema, profile.get('user_config') or {}, decrypt=True, storage_root=cls._runtime_root(),
        )
        with cls._state_lock:
            cls._ensure_instance(instance_id)['user_config'] = config
        return {'status': 'success', 'name': name, 'user_config': config}

    @classmethod
    def delete_profile(cls, name: str) -> dict:
        profiles = cls._load_profiles()
        if name not in profiles:
            raise HTTPException(status_code=404, detail='配置方案不存在')
        profiles.pop(name)
        path = cls._profiles_path()
        temp_path = path + '.tmp'
        with open(temp_path, 'w', encoding='utf-8') as stream:
            json.dump(profiles, stream, ensure_ascii=False, indent=2)
        os.replace(temp_path, path)
        return {'status': 'success'}

    @classmethod
    def create_diagnostic_package(cls, instance_id: str = 'instance-1') -> str:
        status = cls.get_status(instance_id)
        environment = cls.environment_check(instance_id)
        execution_id = status.get('execution_id')
        execution = {'status': {}, 'logs': []}
        if execution_id:
            try:
                execution = ExecutionService.get_execution_status(execution_id)
            except HTTPException:
                pass
        with cls._cache_lock:
            schema = cls._MEMORY_CACHE.get('form_schema') or {}
            config = json.loads(json.dumps(cls._MEMORY_CACHE.get('user_config') or {}))
            bundle_hash = cls._MEMORY_CACHE.get('bundle_hash') or ''
            engine_path = cls._MEMORY_CACHE.get('engine_path') or ''
        with cls._state_lock:
            instance_config = cls._ensure_instance(instance_id).get('user_config')
        if instance_config:
            config = json.loads(json.dumps(instance_config))
        secret_targets = {
            field.get('target')
            for group in schema.get('groups', [])
            for field in group.get('fields', [])
            if field.get('ui_type') == 'secret'
        }
        secret_values = []
        for target in secret_targets:
            slot, key = split_target(str(target or ''))
            if slot and key in config.get(slot, {}):
                if config[slot][key] not in (None, ''):
                    secret_values.append(config[slot][key])
                config[slot][key] = '***REDACTED***'
        from core.services.player_secret_service import PlayerSecretService

        redacted_logs = PlayerSecretService.redact((execution.get('logs') or [])[-500:], secret_values)
        redacted_status = PlayerSecretService.redact(status, secret_values)
        redacted_environment = PlayerSecretService.redact(environment, secret_values)

        diag_dir = os.path.join(cls._runtime_root(), 'diagnostics')
        os.makedirs(diag_dir, exist_ok=True)
        stamp = datetime.now().strftime('%Y%m%d-%H%M%S')
        output = os.path.join(diag_dir, f'diagnostic-{instance_id}-{stamp}.zip')
        with zipfile.ZipFile(output, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
            archive.writestr('status.json', json.dumps(redacted_status, ensure_ascii=False, indent=2))
            archive.writestr('environment.json', json.dumps(redacted_environment, ensure_ascii=False, indent=2))
            archive.writestr('config.redacted.json', json.dumps(config, ensure_ascii=False, indent=2))
            archive.writestr('logs.json', json.dumps(redacted_logs, ensure_ascii=False, indent=2))
            archive.writestr('runtime-metrics.json', json.dumps(
                redacted_status.get('runtime_metrics') or {}, ensure_ascii=False, indent=2,
            ))
            archive.writestr('manifest.json', json.dumps({
                'created_at': datetime.now(timezone.utc).isoformat(),
                'instance_id': instance_id,
                'execution_id': execution_id,
                'bundle_hash': bundle_hash,
                'python_version': sys.version,
                'platform': platform.platform(),
            }, ensure_ascii=False, indent=2))
            screenshot = execution.get('status', {}).get('failure_screenshot') or status.get('failure_screenshot')
            if screenshot and os.path.isfile(screenshot):
                archive.write(screenshot, 'failure-screenshot.png')
            latest_frame = execution.get('status', {}).get('latest_frame') or status.get('latest_frame')
            if latest_frame and os.path.isfile(latest_frame):
                archive.write(latest_frame, 'last-frame.png')
            capability_profile = os.path.join(
                str(engine_path), '.easycode', 'target-capabilities.json',
            )
            if os.path.isfile(capability_profile):
                archive.write(capability_profile, 'target-capabilities.json')
        return output
