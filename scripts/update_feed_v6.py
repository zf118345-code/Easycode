"""Create and maintain a deployable EasyCode v6 static signed Feed.

Examples:
  python scripts/update_feed_v6.py init --root D:\feed --product-id p --domain project_content --feed-url https://cdn.example/feed/p/project_content
  python scripts/update_feed_v6.py publish-content --root D:\feed --product-id p --bundle app.ecplayer --platform windows --architecture x86_64 --version 1.2.0

The command never uploads signing keys or contacts a service.  Deploy the
resulting directory with an HTTPS object store/CDN or ``api.update_feed_app``.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.vnext.bundle_signing_v6 import AuthorSigningKeyStore  # noqa: E402
from core.vnext.update_repository_v6 import (  # noqa: E402
    StaticUpdateRepository,
    UpdateRepositorySigner,
    UpdateSigningKeyStore,
)


def _repository(args: argparse.Namespace) -> StaticUpdateRepository:
    mirrors = [args.feed_url] if getattr(args, "feed_url", "") else []
    signer = UpdateRepositorySigner.from_author_store(args.product_id, mirrors=mirrors)
    return StaticUpdateRepository(args.root, signer)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="EasyCode v6 signed static update Feed publisher")
    sub = parser.add_subparsers(dest="command", required=True)

    def common(command: str) -> argparse.ArgumentParser:
        item = sub.add_parser(command)
        item.add_argument("--root", required=True)
        item.add_argument("--product-id", required=True)
        item.add_argument("--feed-url", default="")
        return item

    init = common("init")
    init.add_argument("--domain", action="append", choices=["ide", "player_application", "project_content"], required=True)

    content = common("publish-content")
    content.add_argument("--bundle", required=True)
    content.add_argument("--platform", choices=["windows", "android"], required=True)
    content.add_argument("--architecture", required=True)
    content.add_argument("--version", required=True)
    content.add_argument("--notes", default="")
    content.add_argument("--expected-public-key", default=None)

    artifact = common("publish-artifact")
    artifact.add_argument("--domain", choices=["ide", "player_application"], required=True)
    artifact.add_argument("--artifact", required=True)
    artifact.add_argument("--platform", choices=["windows", "android"], required=True)
    artifact.add_argument("--architecture", required=True)
    artifact.add_argument("--version", required=True)
    artifact.add_argument("--runtime-min", default="0.0.0")
    artifact.add_argument("--runtime-max", default="9999.0.0")
    artifact.add_argument("--ecir-min", default="0.0.0")
    artifact.add_argument("--ecir-max", default="9999.0.0")
    artifact.add_argument("--application-fingerprint", required=True)
    artifact.add_argument("--permissions-fingerprint", required=True)
    artifact.add_argument("--abi", action="append", default=[])
    artifact.add_argument("--android-version-code", type=int)
    artifact.add_argument("--android-certificate-sha256", default="")
    artifact.add_argument("--notes", default="")

    rollout = common("rollout")
    rollout.add_argument("--domain", choices=["ide", "player_application", "project_content"], required=True)
    rollout.add_argument("--release-id", required=True)
    rollout.add_argument("--channel", choices=["test", "stable"], required=True)
    rollout.add_argument("--percent-bps", type=int, default=0)
    rollout.add_argument("--whitelist-code", action="append", default=[])
    rollout.add_argument("--whitelist-hash", action="append", default=[])
    rollout.add_argument("--paused", action="store_true")

    required = common("required")
    required.add_argument("--domain", choices=["ide", "player_application", "project_content"], required=True)
    required.add_argument("--release-id", required=True)
    required.add_argument("--effective-at", type=datetime.fromisoformat, required=True)
    required.add_argument("--grace-deadline", type=datetime.fromisoformat, required=True)
    required.add_argument("--reason", required=True)
    required.add_argument("--platform-target", action="append", required=True)

    revoke = common("revoke-required")
    revoke.add_argument("--domain", choices=["ide", "player_application", "project_content"], required=True)
    rotate = common("rotate-online-keys")
    rotate.add_argument("--domain", action="append", choices=["ide", "player_application", "project_content"], required=True)
    rotate.add_argument("--root-version", type=int, required=True)
    rotate.add_argument("--role", action="append", choices=["targets", "snapshot", "timestamp", "rollout", "policy"], default=[])
    return parser


def main() -> int:
    args = _parser().parse_args()
    repository = _repository(args)
    if args.command == "init":
        result = repository.initialize(args.domain)
    elif args.command == "publish-content":
        result = repository.publish_project_content(
            args.bundle,
            display_version=args.version,
            platform=args.platform,
            architecture=args.architecture,
            expected_public_key=args.expected_public_key,
            notes=args.notes,
        )
    elif args.command == "publish-artifact":
        record = {
            "source": args.artifact,
            "platform": args.platform,
            "architecture": args.architecture,
            "runtime_min": args.runtime_min,
            "runtime_max": args.runtime_max,
            "ecir_min": args.ecir_min,
            "ecir_max": args.ecir_max,
            "application_fingerprint": args.application_fingerprint,
            "permissions_fingerprint": args.permissions_fingerprint,
            "abi": args.abi,
        }
        if args.platform == "android":
            record["android_version_code"] = args.android_version_code
            record["android_certificate_sha256"] = args.android_certificate_sha256
        result = repository.publish_release(
            args.domain, [record], display_version=args.version, notes=args.notes,
        )
    elif args.command == "rollout":
        result = repository.set_rollout(
            args.domain,
            release_id=args.release_id,
            channel=args.channel,
            percent_bps=args.percent_bps,
            whitelist_codes=args.whitelist_code,
            whitelist_hashes=args.whitelist_hash,
            paused=args.paused,
        )
    elif args.command == "required":
        result = repository.publish_required_policy(
            args.domain,
            release_id=args.release_id,
            effective_at=args.effective_at,
            grace_deadline=args.grace_deadline,
            reason=args.reason,
            platform_targets=args.platform_target,
        )
    elif args.command == "revoke-required":
        result = repository.revoke_required_policy(args.domain)
    else:
        author_store = AuthorSigningKeyStore()
        update_store = UpdateSigningKeyStore()
        author = author_store.get_or_create(args.product_id)
        old_identities = update_store.get_or_create(args.product_id, root_identity=author)
        old_signer = UpdateRepositorySigner(
            args.product_id,
            old_identities,
            root_version=args.root_version - 1,
            mirrors=tuple([args.feed_url] if args.feed_url else []),
        )
        new_identities = update_store.rotate_online_roles(
            args.product_id,
            root_identity=author,
            roles=args.role or ("targets", "snapshot", "timestamp", "rollout", "policy"),
        )
        new_signer = UpdateRepositorySigner(
            args.product_id,
            new_identities,
            root_version=args.root_version,
            mirrors=tuple([args.feed_url] if args.feed_url else []),
        )
        result = StaticUpdateRepository(args.root, old_signer).rotate_root(
            new_signer,
            domains=args.domain,
        )
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
