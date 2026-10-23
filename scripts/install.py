#!/usr/bin/env python3
"""Install the cw skill into a local skills root.

Designed to be run by an AI agent on behalf of a user who just said
"install this GitHub project for me". No third-party dependencies.

Usage
-----
    python scripts/install.py                    # 自动探测技能根并安装
    python scripts/install.py --target ~/.agents/skills
    python scripts/install.py --dry-run          # 只显示会做什么
    python scripts/install.py --list-roots       # 列出探测到的候选目录

Exit codes
----------
    0  安装成功并校验通过
    1  失败（目录不可写、校验不通过、目标已存在且未加 --force）
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

SKILL_NAME = "cw"
SKIP_DIRS = {".git", "dist", "profiles", "__pycache__", ".github"}


def candidate_roots() -> list[Path]:
    home = Path.home()
    return [
        home / ".agents" / "skills",   # DSH / Codex / Claude Code 通用
        home / ".dsh" / "skills",      # DSH 自有根
        home / ".claude" / "skills",
        home / ".codex" / "skills",
    ]


def pick_root(explicit: str | None, dry_run: bool) -> Path:
    if explicit:
        return Path(explicit).expanduser().resolve()
    for c in candidate_roots():
        if c.is_dir():
            return c.resolve()
    return candidate_roots()[0].resolve()


def copy_tree(src: Path, dst: Path) -> None:
    def ignore(directory: str, names: list[str]) -> set[str]:
        return {n for n in names if n in SKIP_DIRS}

    shutil.copytree(src, dst, ignore=ignore, dirs_exist_ok=True)


def validate(target: Path) -> tuple[bool, str]:
    validator = target / "scripts" / "validate_skill.py"
    if not validator.is_file():
        return False, "scripts/validate_skill.py 不存在"
    try:
        r = subprocess.run(
            [sys.executable, str(validator)],
            cwd=target,
            capture_output=True,
            text=True,
            timeout=120,
        )
    except Exception as exc:  # noqa: BLE001
        return False, f"校验器执行失败：{exc}"
    out = (r.stdout + r.stderr).strip()
    return r.returncode == 0, out


def main() -> int:
    ap = argparse.ArgumentParser(description="安装 cw skill")
    ap.add_argument("--target", help="技能根目录（默认自动探测）")
    ap.add_argument("--force", action="store_true", help="目标已存在时覆盖")
    ap.add_argument("--dry-run", action="store_true", help="只显示步骤，不执行")
    ap.add_argument("--list-roots", action="store_true", help="列出候选技能根")
    args = ap.parse_args()

    if args.list_roots:
        print("候选技能根：")
        for c in candidate_roots():
            mark = "存在" if c.is_dir() else "不存在"
            print(f"  [{mark}] {c}")
        return 0

    src = Path(__file__).resolve().parents[1]
    if not (src / "SKILL.md").is_file():
        print(f"失败：源目录不完整，{src} 下没有 SKILL.md")
        return 1

    root = pick_root(args.target, args.dry_run)
    target = root / SKILL_NAME

    print(f"源目录    {src}")
    print(f"技能根    {root}")
    print(f"安装到    {target}")

    if args.dry_run:
        print("\n[dry-run] 未做任何改动。")
        return 0

    try:
        root.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        print(f"失败：技能根不可创建 {root}（{exc}）")
        return 1

    if target.exists():
        if not args.force:
            print(f"失败：{target} 已存在。加 --force 覆盖，或先手动移走。")
            return 1
        shutil.rmtree(target)
        print("已移除旧版本")

    copy_tree(src, target)

    ok, out = validate(target)
    print("\n验证：")
    for line in out.splitlines():
        print(f"  {line}")

    if not ok:
        print("\n安装完成但校验未通过。请把上面的输出反馈给项目作者。")
        return 1

    print(f"\n安装成功。技能名 {SKILL_NAME}")
    print("下一步：刷新你的 agent 技能列表，确认 cw 出现在里面。")
    print("若列表里没有，重启 agent 或检查技能根的配置。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
