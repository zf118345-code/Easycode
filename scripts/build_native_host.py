"""Build and verify the native desktop/capture host before packaging."""

from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.services.native_capture_overlay import NativeCaptureOverlay  # noqa: E402


def main() -> int:
    binary = NativeCaptureOverlay.ensure_binary()
    required = [
        binary,
        binary.parent / 'Microsoft.Web.WebView2.Core.dll',
        binary.parent / 'Microsoft.Web.WebView2.WinForms.dll',
        binary.parent / 'WebView2Loader.dll',
    ]
    missing = [str(path) for path in required if not path.is_file()]
    if missing:
        raise RuntimeError(f'原生宿主发布工件不完整: {", ".join(missing)}')
    print(binary)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
