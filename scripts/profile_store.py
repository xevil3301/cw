#!/usr/bin/env python3
"""Store and audit opponent profiles for the chuwu skill.

Design notes
------------
Profiles live as one JSON file per person under ``profiles/``.
The only opinionated rule in this script: a hypothesis must carry a
``falsified_by`` field. A hypothesis without a falsification condition is a
bias wearing a hypothesis costume, so the tool refuses to store it.

Usage
-----
    python scripts/profile_store.py list
    python scripts/profile_store.py init zhangsan --role "采购经理"
    python scripts/profile_store.py show zhangsan
    python scripts/profile_store.py add-behavior zhangsan \
        --event "预算会" --action "砍价20%" --result "接受10%"
    python scripts/profile_store.py add-hypothesis zhangsan \
        --text "他更在意进度而非价格" --falsified-by "若他为省钱接受延期两周"
    python scripts/profile_store.py audit          # 体检：无证伪条件的假设、过期档案
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROFILES = ROOT / "profiles"
CODE_RE = re.compile(r"^[a-z0-9_-]{1,32}$")
STALE_DAYS = 90


def profile_path(code: str) -> Path:
    if not CODE_RE.fullmatch(code):
        raise SystemExit(f"invalid code: {code!r} (use a-z, 0-9, _ or -, max 32)")
    return PROFILES / f"{code}.json"


def load(code: str) -> dict:
    path = profile_path(code)
    if not path.is_file():
        raise SystemExit(f"profile not found: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def save(code: str, data: dict) -> Path:
    PROFILES.mkdir(parents=True, exist_ok=True)
    path = profile_path(code)
    data["updated"] = date.today().isoformat()
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return path


def blank_profile(code: str) -> dict:
    return {
        "code": code,
        "updated": date.today().isoformat(),
        "base": {"role": "", "kpi": "", "reports_to": "", "resources": [], "limits": []},
        "utility": {"wants": [], "fears": [], "secondary": [], "evidence": ""},
        "behavior": [],
        "channels": {"sources": [], "trusts": [], "format": ""},
        "triggers": {"angry": [], "non_negotiable": [], "public_commitments": []},
        "hypotheses": [],
    }


# ---------------------------------------------------------------- commands


def cmd_list(_: argparse.Namespace) -> int:
    if not PROFILES.is_dir():
        print("(no profiles yet)")
        return 0
    files = sorted(PROFILES.glob("*.json"))
    if not files:
        print("(no profiles yet)")
        return 0
    today = date.today()
    for path in files:
        data = json.loads(path.read_text(encoding="utf-8"))
        updated = data.get("updated", "?")
        stale = ""
        try:
            age = (today - datetime.fromisoformat(updated).date()).days
            if age > STALE_DAYS:
                stale = f"  [过期 {age} 天]"
        except ValueError:
            stale = "  [日期无法解析]"
        role = data.get("base", {}).get("role", "")
        n_beh = len(data.get("behavior", []))
        n_hyp = len(data.get("hypotheses", []))
        print(f"{data.get('code','?'):<16} {role:<14} 行为{n_beh} 假设{n_hyp} 更新{updated}{stale}")
    return 0


def cmd_init(args: argparse.Namespace) -> int:
    path = profile_path(args.code)
    if path.exists() and not args.force:
        raise SystemExit(f"already exists: {path} (use --force to overwrite)")
    data = blank_profile(args.code)
    if args.role:
        data["base"]["role"] = args.role
    path = save(args.code, data)
    print(f"created {path}")
    return 0


def cmd_show(args: argparse.Namespace) -> int:
    data = load(args.code)
    print(json.dumps(data, ensure_ascii=False, indent=2))
    return 0


def cmd_add_behavior(args: argparse.Namespace) -> int:
    data = load(args.code)
    data.setdefault("behavior", []).append(
        {
            "date": args.date or date.today().isoformat(),
            "event": args.event,
            "action": args.action,
            "result": args.result,
        }
    )
    save(args.code, data)
    print(f"behavior appended ({len(data['behavior'])} total)")
    return 0


def cmd_add_hypothesis(args: argparse.Namespace) -> int:
    if not args.falsified_by.strip():
        raise SystemExit(
            "refused: --falsified-by is required. "
            "A hypothesis without a falsification condition is a bias."
        )
    data = load(args.code)
    data.setdefault("hypotheses", []).append(
        {"text": args.text.strip(), "falsified_by": args.falsified_by.strip()}
    )
    save(args.code, data)
    print(f"hypothesis appended ({len(data['hypotheses'])} total)")
    return 0


def cmd_audit(_: argparse.Namespace) -> int:
    if not PROFILES.is_dir():
        print("(no profiles yet)")
        return 0
    problems = 0
    today = date.today()
    for path in sorted(PROFILES.glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        code = data.get("code", path.stem)
        for i, hyp in enumerate(data.get("hypotheses", []), 1):
            if not hyp.get("falsified_by"):
                print(f"FAIL {code}: hypothesis #{i} has no falsified_by")
                problems += 1
        try:
            age = (today - datetime.fromisoformat(data.get("updated", "")).date()).days
            if age > STALE_DAYS:
                print(f"WARN {code}: not updated for {age} days (>{STALE_DAYS})")
        except ValueError:
            print(f"WARN {code}: unreadable updated date")
        base = data.get("base", {})
        if not base.get("kpi"):
            print(f"WARN {code}: base.kpi is empty — you cannot predict him without it")
    if problems:
        print(f"\n{problems} blocking problem(s)")
        return 1
    print("\nOK — no blocking problems")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="chuwu opponent profile store")
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("list", help="list all profiles").set_defaults(func=cmd_list)

    p_init = sub.add_parser("init", help="create a profile")
    p_init.add_argument("code")
    p_init.add_argument("--role", default="")
    p_init.add_argument("--force", action="store_true")
    p_init.set_defaults(func=cmd_init)

    p_show = sub.add_parser("show", help="print a profile as JSON")
    p_show.add_argument("code")
    p_show.set_defaults(func=cmd_show)

    p_beh = sub.add_parser("add-behavior", help="append one observed event")
    p_beh.add_argument("code")
    p_beh.add_argument("--event", required=True)
    p_beh.add_argument("--action", required=True)
    p_beh.add_argument("--result", required=True)
    p_beh.add_argument("--date", default="")
    p_beh.set_defaults(func=cmd_add_behavior)

    p_hyp = sub.add_parser("add-hypothesis", help="append a falsifiable hypothesis")
    p_hyp.add_argument("code")
    p_hyp.add_argument("--text", required=True)
    p_hyp.add_argument("--falsified-by", required=True, dest="falsified_by")
    p_hyp.set_defaults(func=cmd_add_hypothesis)

    sub.add_parser("audit", help="check for unfalsifiable hypotheses and stale files").set_defaults(
        func=cmd_audit
    )

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
