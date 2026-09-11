"""EasyCode format-6 public contracts with lazy package exports.

The package initializer deliberately stays side-effect free.  In particular,
importing a Player runtime module must not construct the IDE workspace manager
or pull authoring/compiler services into the standalone Player import graph.
"""

from __future__ import annotations

from importlib import import_module
from typing import Any


_EXPORTS: dict[str, tuple[str, str]] = {
    'compile_program_document': ('.program_compiler', 'compile_program_document'),
    'ProgramCommandRequestError': ('.program_service_v6', 'ProgramCommandRequestError'),
    'ProgramEntryPointDeletionError': ('.program_service_v6', 'ProgramEntryPointDeletionError'),
    'ProgramReferencedError': ('.program_service_v6', 'ProgramReferencedError'),
    'ProgramServiceV6': ('.program_service_v6', 'ProgramServiceV6'),
    'ProjectVariableNotFoundError': ('.project_variable_service_v6', 'ProjectVariableNotFoundError'),
    'ProjectVariableReferencedError': ('.project_variable_service_v6', 'ProjectVariableReferencedError'),
    'ProjectVariableRequestError': ('.project_variable_service_v6', 'ProjectVariableRequestError'),
    'ProjectVariableServiceV6': ('.project_variable_service_v6', 'ProjectVariableServiceV6'),
    'ProjectVariableDefinition': ('.project_variables_v6', 'ProjectVariableDefinition'),
    'ProjectVariableRegistry': ('.project_variables_v6', 'ProjectVariableRegistry'),
    'RuntimeFailure': ('.runtime', 'RuntimeFailure'),
    'vnext_runtime': ('.runtime', 'vnext_runtime'),
    'AndroidAdbTargetDefinition': ('.target_service', 'AndroidAdbTargetDefinition'),
    'AndroidLocalTargetDefinition': ('.target_service', 'AndroidLocalTargetDefinition'),
    'TargetConfiguration': ('.target_service', 'TargetConfiguration'),
    'TargetConfigurationCorruptError': ('.target_service', 'TargetConfigurationCorruptError'),
    'TargetConflictError': ('.target_service', 'TargetConflictError'),
    'TargetDefinition': ('.target_service', 'TargetDefinition'),
    'TargetNotFoundError': ('.target_service', 'TargetNotFoundError'),
    'TargetReferencedError': ('.target_service', 'TargetReferencedError'),
    'TargetRequestError': ('.target_service', 'TargetRequestError'),
    'TargetServiceError': ('.target_service', 'TargetServiceError'),
    'WindowsTargetDefinition': ('.target_service', 'WindowsTargetDefinition'),
    'VNextWorkspaceError': ('.workspace', 'VNextWorkspaceError'),
    'vnext_workspace_manager': ('.workspace', 'vnext_workspace_manager'),
}

__all__ = list(_EXPORTS)


def __getattr__(name: str) -> Any:
    try:
        module_name, attribute_name = _EXPORTS[name]
    except KeyError as exc:  # pragma: no cover - normal Python attribute protocol
        raise AttributeError(name) from exc
    value = getattr(import_module(module_name, __name__), attribute_name)
    globals()[name] = value
    return value
