"""Lightweight optimistic-write conflict shared by format-6 repositories.

The exception intentionally lives outside ProgramDocument persistence so
runtime-safe type helpers can be imported by Player without pulling authoring
repositories, validators, or editable program facts into the frozen closure.
"""

from __future__ import annotations


class ProgramConflictError(RuntimeError):
    """A stable item changed after the caller read its expected revision."""

    def __init__(
        self,
        function_id: str,
        expected_revision: str | None,
        actual_revision: str | None,
    ) -> None:
        super().__init__(f'ProgramDocument changed on disk: {function_id}')
        self.function_id = function_id
        self.expected_revision = expected_revision
        self.actual_revision = actual_revision


__all__ = ['ProgramConflictError']
