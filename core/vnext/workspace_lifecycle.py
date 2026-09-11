"""Workspace inspection and initialization application service."""

from __future__ import annotations

import os
import uuid
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from .program_repository import ProgramDocumentRepository
from .program_serialization import content_revision
from .extension_schema_v6 import ExtensionSchemaError, load_easycode_lock
from .pure_operations_v6 import PURE_OPERATION_REGISTRY_VERSION, pure_operation_registry_hash
from .program_types import create_program_document
from .target_service import TargetConfiguration
from .workspace_context import VNextWorkspaceError


class VNextWorkspaceLifecycleService:
    def __init__(
        self,
        *,
        read_json: Callable[[str], dict[str, Any]],
        write_json: Callable[[str, Any], None],
        project_file: str,
        lock_file: str,
        format_version: int,
        required_directories: tuple[str, ...],
    ) -> None:
        self._read_json = read_json
        self._write_json = write_json
        self._project_file = project_file
        self._lock_file = lock_file
        self._format_version = format_version
        self._required_directories = required_directories

    @staticmethod
    def canonicalize(path: str) -> str:
        value = os.path.expandvars(os.path.expanduser(str(path or '').strip().strip('"')))
        if not value:
            raise VNextWorkspaceError('项目路径不能为空')
        return os.path.realpath(os.path.abspath(value))

    def inspect(self, raw_path: str) -> dict[str, Any]:
        path = self.canonicalize(raw_path)
        result: dict[str, Any] = {'project_path': path, 'status': 'missing', 'errors': [], 'warnings': []}
        if not os.path.exists(path):
            return result
        if not os.path.isdir(path):
            return {**result, 'status': 'not_directory', 'errors': ['项目路径必须是文件夹']}
        entries = sorted(os.listdir(path), key=str.casefold)
        project_path = os.path.join(path, self._project_file)
        if not os.path.isfile(project_path):
            return {**result, 'status': 'empty' if not entries else 'uninitialized', 'entries': entries}
        try:
            project = self._read_json(project_path)
            version = project.get('format_version')
            if version != self._format_version:
                shown = '旧节点版' if project.get('schema_version') else repr(version)
                return {
                    **result,
                    'status': 'unsupported',
                    'valid': False,
                    'format_version': version,
                    'errors': [
                        f'此项目版本不受支持（{shown}）；请新建格式 {self._format_version} 项目'
                    ],
                }
            for field in ('project_id', 'name', 'entry_function_id', 'program_model_version'):
                if not str(project.get(field) or '').strip():
                    raise VNextWorkspaceError(f'project.json 缺少 {field}')
            try:
                TargetConfiguration.model_validate({
                    'schema_version': project.get('targets_schema_version', 1),
                    'targets': project.get('targets', []),
                    'default_target_id': project.get('default_target_id'),
                })
            except ValidationError as exc:
                raise VNextWorkspaceError(f'目标配置损坏：{exc}') from exc
            missing = [
                name for name in self._required_directories
                if not os.path.isdir(os.path.join(path, *name.split('/')))
            ]
            if missing:
                raise VNextWorkspaceError(f'项目缺少目录：{"、".join(missing)}')
            entry_function_id = str(project['entry_function_id'])
            entry = os.path.join(path, 'program', 'functions', f'{entry_function_id}.json')
            if not os.path.isfile(entry):
                raise VNextWorkspaceError(f'主程序不存在：{entry_function_id}')
            repository = ProgramDocumentRepository(path)
            damaged_programs: list[dict[str, Any]] = []
            for program_path in sorted(repository.functions_path.glob('*.json')):
                function_id = program_path.stem
                try:
                    repository.load(function_id)
                except Exception as exc:
                    raw = program_path.read_bytes()
                    damaged_programs.append({
                        'function_id': function_id,
                        'is_entry': function_id == entry_function_id,
                        'message': str(exc),
                        'current_revision': content_revision(raw),
                        'history': [{
                            'history_id': item.history_id,
                            'revision': item.revision,
                            'created_at': item.created_at,
                            'reason': item.reason,
                            'display_name': item.document.function.display_name,
                            'statement_count': len(item.document.function.statements),
                        } for item in repository.list_history(function_id)],
                    })
            if damaged_programs:
                return {
                    **result,
                    'status': 'recovery',
                    'valid': False,
                    'project_id': project['project_id'],
                    'project_name': project['name'],
                    'format_version': self._format_version,
                    'entry_function_id': entry_function_id,
                    'damaged_programs': damaged_programs,
                    'errors': ['项目函数文件损坏；请选择历史版本恢复后再打开项目'],
                }
            try:
                load_easycode_lock(Path(path) / self._lock_file)
            except (ExtensionSchemaError, TypeError) as exc:
                raise VNextWorkspaceError(f'easycode.lock 损坏：{exc}') from exc
            return {
                **result,
                'status': 'valid',
                'valid': True,
                'project_id': project['project_id'],
                'project_name': project['name'],
                'format_version': self._format_version,
                'entry_function_id': entry_function_id,
                'program_model_version': int(project['program_model_version']),
                'read_only': not os.access(path, os.W_OK),
            }
        except VNextWorkspaceError as exc:
            return {**result, 'status': 'invalid', 'valid': False, 'errors': [str(exc)]}

    def initialize(self, raw_path: str, project_name: str = '') -> dict[str, Any]:
        path = self.canonicalize(raw_path)
        os.makedirs(path, exist_ok=True)
        inspection = self.inspect(path)
        if inspection['status'] == 'valid':
            return inspection
        if inspection['status'] == 'invalid':
            raise VNextWorkspaceError(inspection['errors'][0])
        if inspection['status'] == 'uninitialized':
            raise VNextWorkspaceError('目录不是空文件夹；vNext初始化不会混入已有内容')
        name = str(project_name or os.path.basename(path) or '新项目').strip()
        project_id = f'project_{uuid.uuid4().hex}'
        function_id = f'function_{uuid.uuid4().hex}'
        for relative in self._required_directories:
            os.makedirs(os.path.join(path, *relative.split('/')), exist_ok=True)
        self._write_json(os.path.join(path, self._project_file), {
            'format_version': self._format_version,
            'program_model_version': 1,
            'ecir_version': 1,
            'minimum_compiler_version': '6.0.0',
            'minimum_runtime_version': '6.0.0',
            'project_id': project_id,
            'name': name,
            'entry_function_id': function_id,
            'targets_schema_version': 1,
            'default_target_id': None,
            'targets': [],
            'network_policies_schema_version': 1,
            'network_policies': [],
            'enabled_extension_ids': [],
            'player_form': 'player/form.json',
            'created_at': datetime.now(timezone.utc).isoformat(timespec='seconds'),
        })
        self._write_json(os.path.join(path, self._lock_file), {
            'lock_version': 1,
            'project_format': self._format_version,
            'toolchain': {
                'compiler_version': '6.0.0',
                'program_schema': 1,
                'ecir': 1,
                'pure_value_registry_version': PURE_OPERATION_REGISTRY_VERSION,
                'pure_value_registry_sha256': pure_operation_registry_hash(),
            },
            'official_functions': [],
            'extensions': [],
        })
        self._write_json(os.path.join(path, 'program', 'variables.json'), {
            'schema_version': 1,
            'variables': [],
        })
        self._write_json(os.path.join(path, 'assets', 'registry.json'), {
            'schema_version': 2,
            'assets': {},
            'folders': {category: [] for category in ('image', 'ocr', 'page')},
        })
        self._write_json(
            os.path.join(path, 'player', 'form.json'),
            {'schema_version': 3, 'title': '脚本运行器', 'pages': []},
        )
        self._write_json(os.path.join(path, 'player', 'profiles.json'), {
            'schema_version': 1,
            'profiles': [],
        })
        self._write_json(os.path.join(path, '.easycode', 'view-state.json'), {
            'schema_version': 1,
            'active_function_id': function_id,
        })
        ProgramDocumentRepository(path).create(create_program_document(
            '主程序',
            function_id=function_id,
            document_id=f'document_{uuid.uuid4().hex}',
        ))
        return self.inspect(path)
