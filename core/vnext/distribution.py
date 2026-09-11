"""Assemble a verified vNext bundle with the reusable frozen Player runtime."""

from __future__ import annotations

import json
import os
import shutil
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .bundle_signing_v6 import trust_root_document
from .player_bundle import VNextPlayerBundleManager


DEFAULT_PLAYER_RUNTIME_TEMPLATE_NAME = 'EasycodePlayerRuntimeV6'
PLAYER_RUNTIME_CONTRACT_FILE = 'runtime-contract.json'
PLAYER_RUNTIME_CONTRACT_VERSION = 7
PLAYER_RUNTIME_CAPABILITIES = frozenset({
    'console-diagnostics-v1',
    'console-isolated-workers-v1',
    'native-window-resize-v1',
})


class DistributionError(RuntimeError):
    pass


def write_player_runtime_contract(runtime_root: str | Path) -> Path:
    root = Path(runtime_root).resolve()
    root.mkdir(parents=True, exist_ok=True)
    path = root / PLAYER_RUNTIME_CONTRACT_FILE
    payload = {
        'schema_version': 1,
        'contract_version': PLAYER_RUNTIME_CONTRACT_VERSION,
        'capabilities': sorted(PLAYER_RUNTIME_CAPABILITIES),
    }
    temporary = path.with_name(f'.{path.name}.{os.getpid()}.tmp')
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    os.replace(temporary, path)
    return path


class VNextDistributionAssembler:
    def __init__(self, runtime_template: str, web_directory: str, *, require_current_runtime: bool = False) -> None:
        self.runtime_template = Path(runtime_template).resolve()
        self.web_directory = Path(web_directory).resolve()
        self.require_current_runtime = bool(require_current_runtime)

    def readiness(self) -> dict[str, Any]:
        required = [
            self.runtime_template / 'EasycodePlayer.exe',
            self.runtime_template / 'EasycodeUpdateHelper.exe',
            self.web_directory / 'player.html',
            self.web_directory / 'capture.html',
            self.web_directory / 'console.html',
        ]
        if self.require_current_runtime:
            required.append(self.runtime_template / PLAYER_RUNTIME_CONTRACT_FILE)
        missing = [str(item) for item in required if not item.is_file()]
        if self.require_current_runtime and not missing:
            try:
                contract = json.loads((self.runtime_template / PLAYER_RUNTIME_CONTRACT_FILE).read_text(encoding='utf-8'))
                capabilities = {str(item) for item in contract.get('capabilities') or []}
                if int(contract.get('contract_version') or 0) != PLAYER_RUNTIME_CONTRACT_VERSION:
                    missing.append(
                        f'Player Runtime 契约版本不匹配：需要 {PLAYER_RUNTIME_CONTRACT_VERSION}，'
                        f'实际 {contract.get("contract_version") or 0}；请重建通用 Runtime',
                    )
                absent = sorted(PLAYER_RUNTIME_CAPABILITIES - capabilities)
                if absent:
                    missing.append(f'Player Runtime 缺少能力 {", ".join(absent)}；请重建通用 Runtime')
            except (OSError, ValueError, TypeError, json.JSONDecodeError):
                missing.append('Player Runtime 能力清单无效；请重建通用 Runtime')
        forbidden = sorted(
            self._forbidden_web_files() + self._forbidden_runtime_files()
        )
        return {
            'ready': not missing and not forbidden,
            'missing': missing,
            'forbidden': forbidden,
            'runtime_template': str(self.runtime_template), 'web_directory': str(self.web_directory),
        }

    def _forbidden_web_files(self) -> list[str]:
        if not self.web_directory.is_dir():
            return []
        forbidden: list[str] = []
        source_suffixes = {'.vue', '.ts', '.tsx', '.jsx', '.map', '.easy'}
        for path in self.web_directory.rglob('*'):
            if not path.is_file():
                continue
            relative = path.relative_to(self.web_directory)
            parts = {part.casefold() for part in relative.parts}
            if (
                relative.as_posix().casefold() == 'index.html'
                or 'src' in parts
                or path.suffix.casefold() in source_suffixes
            ):
                forbidden.append(str(path))
        return sorted(forbidden)

    @staticmethod
    def _is_forbidden_delivery_file(path: Path, root: Path) -> bool:
        relative = path.relative_to(root)
        parts = {part.casefold() for part in relative.parts}
        suffix = path.suffix.casefold()
        relative_parts = tuple(part.casefold() for part in relative.parts)
        # A frozen onedir runtime may legitimately contain third-party Python
        # support files (OpenCV config loaders are one concrete example) and
        # dependency licence trees whose path contains ``src``.  Rejecting
        # every .py file or every ``src`` segment makes a real PyInstaller
        # runtime impossible to release while the fake test runtime passes.
        # Source isolation protects EasyCode/author sources, not redistributable
        # dependency runtime assets already inside ``_internal``.
        author_python_source = suffix in {'.py', '.pyi'} and (
            not relative_parts
            or relative_parts[0] != '_internal'
            or len(relative_parts) < 2
            or relative_parts[1] in {'api', 'core', 'scripts'}
            or relative_parts[-1] in {'player.py', 'player.pyi'}
        )
        return (
            suffix in {'.easy', '.vue', '.ts', '.tsx', '.jsx', '.map'}
            or author_python_source
            or path.name.casefold() == 'index.html'
            or ('src' in parts and relative_parts[0] != '_internal')
            or 'programs' in parts
            or path.name.casefold() == 'program.json'
            or 'programdocument' in path.name.casefold()
            or 'program_document' in path.name.casefold()
        )

    def _forbidden_runtime_files(self) -> list[str]:
        if not self.runtime_template.is_dir():
            return []
        return sorted(
            str(path)
            for path in self.runtime_template.rglob('*')
            if path.is_file()
            and self._is_forbidden_delivery_file(path, self.runtime_template)
        )

    @staticmethod
    def _assert_bundle_source_boundary(bundle: Path) -> None:
        try:
            with zipfile.ZipFile(bundle, 'r') as archive:
                names = [item.filename.replace('\\', '/') for item in archive.infolist()]
        except (OSError, zipfile.BadZipFile) as exc:
            raise DistributionError(f'Player 发布包无法读取：{exc}') from exc
        forbidden = [
            name for name in names
            if name.casefold().endswith('.easy')
            or '/programs/' in f'/{name.casefold()}'
            or name.casefold().rsplit('/', 1)[-1] == 'program.json'
            or 'programdocument' in name.casefold()
            or 'program_document' in name.casefold()
        ]
        if forbidden:
            raise DistributionError(f'Player 发布包包含可编辑程序源码：{forbidden[0]}')

    @staticmethod
    def _safe_remove(path: Path, allowed_parent: Path) -> None:
        resolved, parent = path.resolve(), allowed_parent.resolve()
        if resolved == parent or parent not in resolved.parents:
            raise DistributionError(f'拒绝清理不安全路径：{resolved}')
        if resolved.exists():
            shutil.rmtree(resolved)

    def assemble(self, bundle_path: str, output_directory: str, *, product_name: str = 'EasyCode Player') -> dict[str, Any]:
        readiness = self.readiness()
        if not readiness['ready']:
            reason = (readiness['missing'] or readiness['forbidden'])[0]
            raise DistributionError(f'Player 最小发布边界尚未就绪：{reason}')
        bundle = Path(bundle_path).resolve()
        self._assert_bundle_source_boundary(bundle)
        verifier = VNextPlayerBundleManager()
        try:
            metadata = verifier.load(str(bundle))
        finally:
            verifier.shutdown()
        output_root = Path(output_directory).resolve()
        output_root.mkdir(parents=True, exist_ok=True)
        destination = output_root / 'Player_Bundle'
        staging = output_root / f'.Player_Bundle-building-{os.getpid()}'
        backup = output_root / '.Player_Bundle-previous'
        self._safe_remove(staging, output_root)
        staging.mkdir(parents=True)
        try:
            shutil.copytree(self.runtime_template, staging, dirs_exist_ok=True)
            release = staging / 'release'
            release.mkdir(exist_ok=True)
            shutil.copytree(self.web_directory, release / 'web', dirs_exist_ok=True)
            packaged_bundle = release / 'project.ecplayer'
            shutil.copy2(bundle, packaged_bundle)
            bundle_metadata = metadata.get('bundle') or {}
            trust_root = trust_root_document(
                bundle_metadata.get('signature') or {},
                str(bundle_metadata.get('project_id') or ''),
            )
            trust_root_path = release / 'trust-root.json'
            trust_root_path.write_text(
                json.dumps(trust_root, ensure_ascii=False, indent=2) + '\n',
                encoding='utf-8',
            )
            form = metadata.get('form') if isinstance(metadata.get('form'), dict) else {}
            application_name = str(form.get('title') or product_name).strip() or product_name
            icon_asset_id = str(form.get('icon_asset_id') or '').strip()
            product_metadata = {
                'schema_version': 1,
                'application_name': application_name,
                'icon': '',
            }
            if icon_asset_id:
                asset_inventory = metadata.get('assets') if isinstance(metadata.get('assets'), dict) else {}
                icon_asset = next((
                    item for item in asset_inventory.get('assets') or []
                    if isinstance(item, dict) and str(item.get('asset_id') or '') == icon_asset_id
                ), None)
                if icon_asset is None or icon_asset.get('category') != 'image':
                    raise DistributionError('Player 应用图标没有进入已验证的发布资源闭包')
                source_name = str(icon_asset.get('path') or '').replace('\\', '/')
                source_parts = [part for part in source_name.split('/') if part]
                if not source_parts or source_name.startswith('/') or any(part in {'.', '..'} for part in source_parts):
                    raise DistributionError('Player 应用图标资源路径无效')
                extension = str(icon_asset.get('extension') or '.png').casefold()
                if extension not in {'.png', '.jpg', '.jpeg', '.bmp'}:
                    raise DistributionError('Player 应用图标格式不受原生窗口支持')
                branding = release / 'branding'
                branding.mkdir(exist_ok=True)
                icon_name = f'app-icon{extension}'
                try:
                    with zipfile.ZipFile(bundle, 'r') as archive:
                        icon_content = archive.read('/'.join(source_parts))
                except (OSError, KeyError, zipfile.BadZipFile) as exc:
                    raise DistributionError('Player 应用图标无法从已验证发布包读取') from exc
                (branding / icon_name).write_bytes(icon_content)
                product_metadata['icon'] = f'branding/{icon_name}'
            (release / 'product.json').write_text(
                json.dumps(product_metadata, ensure_ascii=False, indent=2) + '\n',
                encoding='utf-8',
            )
            launcher = staging / '启动脚本助手.bat'
            launcher.write_text(
                '@echo off\nchcp 65001 >nul\ncd /d "%~dp0"\n'
                'start "" EasycodePlayer.exe\n',
                encoding='gbk',
            )
            manifest = {
                'product': application_name,
                'project': bundle_metadata.get('name'),
                'project_id': bundle_metadata.get('project_id'),
                'release_id': bundle_metadata.get('release_id'),
                'signing_key_id': trust_root['key_id'],
                'built_at': datetime.now(timezone.utc).isoformat(timespec='seconds'),
                'package_mode': 'onedir', 'desktop_shell': 'native-webview2',
                'bundle': 'release/project.ecplayer',
                'trust_root': 'release/trust-root.json',
                'product_metadata': 'release/product.json',
                'source_included': False,
            }
            (staging / 'build_manifest.json').write_text(
                json.dumps(manifest, ensure_ascii=False, indent=2) + '\n', encoding='utf-8',
            )
            forbidden_delivery = [
                path for path in staging.rglob('*')
                if path.is_file() and self._is_forbidden_delivery_file(path, staging)
            ]
            if forbidden_delivery:
                raise DistributionError(f'交付目录意外包含源码或 IDE 入口：{forbidden_delivery[0]}')
            if (
                not (staging / 'EasycodePlayer.exe').is_file()
                or not (staging / 'EasycodeUpdateHelper.exe').is_file()
                or not (release / 'web' / 'player.html').is_file()
                or not (release / 'web' / 'capture.html').is_file()
                or not (release / 'web' / 'console.html').is_file()
            ):
                raise DistributionError('交付目录缺少 Player 运行边界')
            self._safe_remove(backup, output_root)
            if destination.exists():
                os.replace(destination, backup)
            try:
                os.replace(staging, destination)
            except Exception:
                if backup.exists() and not destination.exists():
                    os.replace(backup, destination)
                raise
            self._safe_remove(backup, output_root)
        except Exception:
            self._safe_remove(staging, output_root)
            raise
        return {
            'created': True, 'path': str(destination),
            'executable': str(destination / 'EasycodePlayer.exe'),
            'bundle': str(destination / 'release' / 'project.ecplayer'),
            'manifest': manifest,
        }
