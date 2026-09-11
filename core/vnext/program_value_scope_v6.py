"""Lexical value sources available to a format-6 statement.

This is shared by the value creation catalog and command validation.  Keeping
scope discovery on the server prevents the editor from advertising symbols or
optional members that are not legal at the selected statement.
"""

from __future__ import annotations

from dataclasses import dataclass

from .program_types import (
    AssignmentStatement,
    CallStatement,
    IfStatement,
    LocalAssignmentTarget,
    LoopStatement,
    ProgramDocument,
    Statement,
    TargetScopeStatement,
    TryStatement,
)
from .program_validation import narrowed_optional_symbols
from .project_variables_v6 import ProjectVariableRegistry


@dataclass(frozen=True)
class AvailableValueSourceV6:
    source: str  # local | project
    source_id: str
    display_name: str
    value_type: str
    narrowed_type: str = ''

    def to_dict(self) -> dict[str, str]:
        return {
            'source': self.source,
            'source_id': self.source_id,
            'display_name': self.display_name,
            'value_type': self.value_type,
            'narrowed_type': self.narrowed_type,
        }


def _optional_inner(value_type: str) -> str:
    return value_type[9:-1] if value_type.startswith('optional<') and value_type.endswith('>') else ''


def available_value_sources(
    document: ProgramDocument,
    statement_id: str,
    project_variables: ProjectVariableRegistry | None = None,
) -> tuple[AvailableValueSourceV6, ...]:
    symbols: dict[str, AvailableValueSourceV6] = {
        item.symbol_id: AvailableValueSourceV6(
            source='local',
            source_id=item.symbol_id,
            display_name=item.display_name,
            value_type=item.value_type,
        )
        for item in document.function.parameters
    }

    def with_narrowed(
        current: dict[str, AvailableValueSourceV6],
        narrowed: set[str],
    ) -> dict[str, AvailableValueSourceV6]:
        result = dict(current)
        for symbol_id in narrowed:
            source = result.get(symbol_id)
            inner = _optional_inner(source.value_type) if source else ''
            if source and inner:
                result[symbol_id] = AvailableValueSourceV6(
                    source=source.source,
                    source_id=source.source_id,
                    display_name=source.display_name,
                    value_type=source.value_type,
                    narrowed_type=inner,
                )
        return result

    def add_binding(current: dict[str, AvailableValueSourceV6], binding) -> None:
        if binding is None:
            return
        current[binding.symbol_id] = AvailableValueSourceV6(
            source='local',
            source_id=binding.symbol_id,
            display_name=binding.display_name,
            value_type=binding.value_type,
        )

    def find(
        statements: tuple[Statement, ...],
        initial: dict[str, AvailableValueSourceV6],
    ) -> dict[str, AvailableValueSourceV6] | None:
        current = dict(initial)
        for statement in statements:
            if statement.statement_id == statement_id:
                return current
            if isinstance(statement, IfStatement):
                narrowed_then = with_narrowed(current, narrowed_optional_symbols(statement.condition))
                found = find(statement.then_statements, narrowed_then)
                if found is not None:
                    return found
                for branch in statement.additional_branches:
                    found = find(
                        branch.statements,
                        with_narrowed(current, narrowed_optional_symbols(branch.condition)),
                    )
                    if found is not None:
                        return found
                found = find(statement.otherwise_statements, current)
                if found is not None:
                    return found
            elif isinstance(statement, LoopStatement):
                loop = dict(current)
                for binding in (
                    statement.item_binding,
                    statement.index_binding,
                    statement.key_binding,
                    statement.value_binding,
                ):
                    add_binding(loop, binding)
                found = find(statement.body, loop)
                if found is not None:
                    return found
            elif isinstance(statement, TryStatement):
                found = find(statement.body, current)
                if found is not None:
                    return found
                for clause in statement.catches:
                    caught = dict(current)
                    add_binding(caught, clause.error_binding)
                    found = find(clause.statements, caught)
                    if found is not None:
                        return found
                found = find(statement.finally_statements, current)
                if found is not None:
                    return found
            elif isinstance(statement, TargetScopeStatement):
                found = find(statement.body, current)
                if found is not None:
                    return found

            if isinstance(statement, CallStatement):
                add_binding(current, statement.result_binding)
            elif (
                isinstance(statement, AssignmentStatement)
                and isinstance(statement.target, LocalAssignmentTarget)
            ):
                add_binding(current, statement.target)
        return None

    visible = find(document.function.statements, symbols)
    if visible is None:
        raise ValueError(f'语句不存在：{statement_id}')
    values = list(visible.values())
    if project_variables is not None:
        values.extend(
            AvailableValueSourceV6(
                source='project',
                source_id=item.variable_id,
                display_name=item.display_name,
                value_type=item.value_type,
            )
            for item in project_variables.variables
        )
    return tuple(values)


__all__ = ['AvailableValueSourceV6', 'available_value_sources']
