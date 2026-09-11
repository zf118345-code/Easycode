"""Function-contract inputs used by the source-free ProgramDocument slice.

The registry is injected into editing and compilation.  Keeping it independent
from ``language.py`` prevents the format-6 core from accidentally depending on
the retired source parser or its display-name based parameter lookup.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any, Protocol

LOG_OUTPUT_FUNCTION_ID = 'official.log.output'
LOG_OUTPUT_CONTENT_PARAMETER_ID = 'official.log.output.parameter.content'
LOG_OUTPUT_LEVEL_PARAMETER_ID = 'official.log.output.parameter.level'
LOG_OUTPUT_CATEGORY_PARAMETER_ID = 'official.log.output.parameter.category'
WAIT_DURATION_FUNCTION_ID = 'official.wait.duration'
WAIT_DURATION_PARAMETER_ID = 'official.wait.duration.parameter.duration'


_NO_DEFAULT = object()


@dataclass(frozen=True, slots=True)
class ParameterContract:
    parameter_id: str
    name: str
    display_name: str
    value_type: str
    required: bool = True
    default: Any = _NO_DEFAULT

    @property
    def has_default(self) -> bool:
        return self.default is not _NO_DEFAULT


@dataclass(frozen=True, slots=True)
class FunctionContract:
    function_id: str
    qualified_name: str
    opcode: str
    parameters: tuple[ParameterContract, ...]
    return_type: str = 'null'
    platforms: tuple[str, ...] = ('android_adb', 'android_local', 'windows')
    capabilities: tuple[str, ...] = ()
    contract_version: str = '1.0.0'
    contract_fingerprint: str = ''
    minimum_android_api: int = 21
    timeout_ms: int = 30_000

    def parameter(self, parameter_id: str) -> ParameterContract | None:
        return next((item for item in self.parameters if item.parameter_id == parameter_id), None)


class FunctionContractRegistry:
    """Immutable lookup table supplied by the Function Service."""

    def __init__(self, contracts: Iterable[FunctionContract]) -> None:
        by_id: dict[str, FunctionContract] = {}
        for contract in contracts:
            if contract.function_id in by_id:
                raise ValueError(f'duplicate function contract: {contract.function_id}')
            parameter_ids = [item.parameter_id for item in contract.parameters]
            if len(parameter_ids) != len(set(parameter_ids)):
                raise ValueError(f'duplicate parameter contract in {contract.function_id}')
            by_id[contract.function_id] = contract
        self._by_id = by_id

    def get(self, function_id: str) -> FunctionContract | None:
        return self._by_id.get(function_id)

    def require(self, function_id: str) -> FunctionContract:
        contract = self.get(function_id)
        if contract is None:
            raise KeyError(function_id)
        return contract

    def values(self) -> tuple[FunctionContract, ...]:
        return tuple(self._by_id.values())


class FunctionContractProvider(Protocol):
    def require(self, function_id: str) -> Any: ...


def get_contract(registry: FunctionContractProvider, function_id: str) -> Any | None:
    getter = getattr(registry, 'get', None)
    if callable(getter):
        return getter(function_id)
    try:
        return registry.require(function_id)
    except KeyError:
        return None


def require_contract(registry: FunctionContractProvider, function_id: str) -> Any:
    contract = get_contract(registry, function_id)
    if contract is None:
        raise KeyError(function_id)
    return contract


def contract_parameter(contract: Any, parameter_id: str) -> Any | None:
    lookup = getattr(contract, 'parameter', None)
    if callable(lookup):
        return lookup(parameter_id)
    return next((item for item in contract.parameters if item.parameter_id == parameter_id), None)


def parameter_display_name(parameter: Any) -> str:
    """Return presentation text without using it as a runtime identity."""

    return str(
        getattr(parameter, 'display_name', '')
        or getattr(parameter, 'name', '')
        or parameter.parameter_id
    )


def parameter_has_default(parameter: Any) -> bool:
    marker = getattr(parameter, 'has_default', None)
    if marker is not None:
        return bool(marker)
    return not (bool(parameter.required) and getattr(parameter, 'default', None) is None)


def contract_platforms(contract: Any) -> tuple[str, ...]:
    matrix = getattr(contract, 'platform_support', None)
    if matrix:
        return tuple(
            item.platform
            for item in matrix
            if item.support != 'unsupported' and item.implementation == 'verified'
        )
    direct = getattr(contract, 'platforms', None)
    if direct is not None:
        return tuple(direct)
    hosts = set(getattr(contract, 'host_requirements', ()) or ())
    targets = tuple(getattr(contract, 'target_kinds', ()) or ())
    if targets:
        return tuple(
            target for target in targets
            if (target in {'windows', 'android_adb'} and 'windows' in hosts)
            or (target == 'android_local' and 'android' in hosts)
        )
    result: list[str] = []
    if 'windows' in hosts:
        result.extend(('windows', 'android_adb'))
    if 'android' in hosts:
        result.append('android_local')
    return tuple(result)


def contract_platform_detail(contract: Any, platform: str) -> Any | None:
    """Return the canonical per-platform support entry when one is declared."""

    return next(
        (
            item
            for item in (getattr(contract, 'platform_support', None) or ())
            if item.platform == platform
        ),
        None,
    )


def contract_capabilities(contract: Any) -> tuple[str, ...]:
    direct = getattr(contract, 'capabilities', None)
    if direct is not None:
        return tuple(direct)
    return tuple(dict.fromkeys((
        *(getattr(contract, 'target_capabilities', ()) or ()),
        *(getattr(contract, 'permissions', ()) or ()),
    )))


def contract_minimum_android_api(contract: Any) -> int:
    """Return the Android-local API floor declared by a function contract.

    Project-function calls themselves use the base floor; their reachable
    official calls are aggregated separately by the linker.
    """

    detail = contract_platform_detail(contract, 'android_local')
    if detail is not None and getattr(detail, 'support', 'unsupported') != 'unsupported':
        value = getattr(detail, 'minimum_android_api', None)
        if isinstance(value, int) and not isinstance(value, bool) and 21 <= value <= 37:
            return value
    direct = set(getattr(contract, 'platforms', ()) or ())
    value = getattr(contract, 'minimum_android_api', 21)
    if 'android_local' in direct and isinstance(value, int) and not isinstance(value, bool) and 21 <= value <= 37:
        return value
    return 21


def minimal_function_registry() -> FunctionContractRegistry:
    """Return the first executable catalog slice.

    Later catalog work supplies the same contract objects for frame, vision,
    input, project, and extension functions without changing ProgramDocument.
    """

    return FunctionContractRegistry((
        FunctionContract(
            function_id=LOG_OUTPUT_FUNCTION_ID,
            qualified_name='日志.输出',
            opcode='log.write',
            parameters=(ParameterContract(
                parameter_id=LOG_OUTPUT_CONTENT_PARAMETER_ID,
                name='content',
                display_name='内容',
                value_type='any',
            ), ParameterContract(
                parameter_id=LOG_OUTPUT_LEVEL_PARAMETER_ID,
                name='level',
                display_name='级别',
                value_type='string',
                required=False,
                default='info',
            ), ParameterContract(
                parameter_id=LOG_OUTPUT_CATEGORY_PARAMETER_ID,
                name='category',
                display_name='分类',
                value_type='string',
                required=False,
                default='script',
            )),
            return_type='unit',
        ),
        FunctionContract(
            function_id=WAIT_DURATION_FUNCTION_ID,
            qualified_name='等待.持续',
            opcode='wait.duration',
            parameters=(ParameterContract(
                parameter_id=WAIT_DURATION_PARAMETER_ID,
                name='duration',
                display_name='时长',
                value_type='duration',
                default={'kind': 'duration', 'milliseconds': 1000},
            ),),
            return_type='unit',
        ),
    ))


__all__ = [
    'FunctionContract',
    'FunctionContractProvider',
    'FunctionContractRegistry',
    'LOG_OUTPUT_CATEGORY_PARAMETER_ID',
    'LOG_OUTPUT_CONTENT_PARAMETER_ID',
    'LOG_OUTPUT_FUNCTION_ID',
    'LOG_OUTPUT_LEVEL_PARAMETER_ID',
    'ParameterContract',
    'WAIT_DURATION_FUNCTION_ID',
    'WAIT_DURATION_PARAMETER_ID',
    'contract_capabilities',
    'contract_platform_detail',
    'contract_parameter',
    'contract_platforms',
    'get_contract',
    'minimal_function_registry',
    'parameter_has_default',
    'parameter_display_name',
    'require_contract',
]
