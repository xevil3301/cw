#!/usr/bin/env python3
"""Validate the chuwu skill package without third-party dependencies.

Usage:
    python scripts/validate_skill.py            # strict: missing files are errors
    python scripts/validate_skill.py --draft    # draft: missing files are warnings
"""

from __future__ import annotations

import argparse
import re
import sys
from math import ceil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ERRORS: list[str] = []
WARNINGS: list[str] = []

SKILL_MAX_LINES = 150
SKILL_MAX_CHARACTERS = 5_000
SKILL_MAX_APPROX_TOKENS = 4_500
DESC_MAX = 1_024

REQUIRED_KNOWLEDGE = (
    "01-权力结构与局面要素.md",
    "02-影响力杠杆与说服机制.md",
    "03-操控手法分类学.md",
    "04-博弈推演与策略树.md",
    "05-信息战与叙事控制.md",
    "06-组织政治与向上管理.md",
    "07-谈判杠杆与让步设计.md",
    "08-反操控与自保侦测.md",
    "09-古典谋略的现代转译.md",
    "10-代价、反噬与长期博弈.md",
    "11-案例库与书单.md",
    "12-操控的进攻性用法.md",
    "13-自我评估与不败结构.md",
    "14-对手评估与试探术.md",
    "15-结交判断、利用与策反.md",
    "16-防御体系与失败补救.md",
    "17-欺骗的结构与做局.md",
    "18-用间与反间.md",
    "19-证据工程与真伪对抗.md",
    "20-认知闭包.md",
    "21-官场心理与体制内博弈.md",
    "22-诉求识别与问诊.md",
    "23-基本博弈与场景映射.md",
    "24-九地与局面坐标.md",
    "25-利益冲突与亲属牵连.md",
    "26-长期关系中的低强度对抗.md",
    "27-框架控制与上围栏.md",
    "28-代价归属与长期修复.md",
    "29-以弱胜强与非对称战法.md",
)

REQUIRED_PRACTICAL = (
    "00-导读与使用分级.md",
    "局面建模卡：五力、筹码与关系图谱.md",
    "话术编排器：从施压到退路.md",
    "场域控制：会议、群聊与一对多.md",
    "锚定、拆解与让步节奏.md",
    "被操控时的识别与反制.md",
    "对手档案与长期跟踪.md",
    "人设经营与信号释放.md",
    "复盘模板与败局分析.md",
    "自我审计表与不败结构.md",
    "试探设计器.md",
    "策反操作手册.md",
    "做局设计器.md",
    "证据链设计卡.md",
    "认知闭包设计卡.md",
    "白话速查表.md",
    "体制内沟通卡.md",
    "复杂局面速判卡.md",
    "双系统路由与输出纪律.md",
    "问诊卡.md",
    "九地与力度闸门.md",
    "法律定性常识卡.md",
    "主动交代决策卡.md",
    "优先级排序卡.md",
    "弱势方诉求体检卡.md",
    "诉求合理性卡.md",
    "场景库-从简单到复杂.md",
    "行为卡.md",
    "现场应对卡.md",
    "自损局面处理.md",
    "场景话术库.md",
)

REQUIRED_SCRIPTS = ("validate_skill.py", "profile_store.py")

# 打包卫生：这些串不该出现在可分发包里
LEAK_PATTERNS = (
    (re.compile(r"[A-Za-z]:\\\\Users\\\\"), "absolute Windows user path"),
    (re.compile(r"/home/[A-Za-z0-9_.-]+/"), "absolute POSIX home path"),
    (re.compile(r"sk-[A-Za-z0-9]{16,}"), "possible API key"),
)
LEAK_SCAN_SUFFIXES = {".md", ".py", ".yaml", ".yml", ".json", ".txt"}


def missing(check: bool, path: str, bucket: tuple[str, ...] | None = None) -> None:
    target = ROOT / path
    if target.exists():
        return
    msg = f"missing required path: {path}"
    if check or bucket is None:
        ERRORS.append(msg)
    else:
        WARNINGS.append(msg)


def approximate_token_count(content: str) -> int:
    """Conservative dependency-free budget estimate for mixed Chinese text."""
    cjk = len(re.findall(r"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]", content))
    latin_words = len(re.findall(r"[A-Za-z0-9_]+", content))
    other = len(
        re.findall(r"[^\sA-Za-z0-9_\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]", content)
    )
    return cjk + ceil(latin_words * 1.3) + ceil(other / 4)


def validate_frontmatter() -> None:
    skill = ROOT / "SKILL.md"
    if not skill.is_file():
        ERRORS.append("SKILL.md is missing")
        return

    content = skill.read_text(encoding="utf-8")
    match = re.match(r"^---\n(.*?)\n---\n", content, re.DOTALL)
    if not match:
        ERRORS.append("SKILL.md has invalid YAML frontmatter boundaries")
        return

    frontmatter = match.group(1).replace("\r\n", "\n")
    keys = re.findall(r"^([A-Za-z0-9_-]+):", frontmatter, re.MULTILINE)
    if keys != ["name", "description"]:
        ERRORS.append(f"frontmatter keys must be exactly name, description; got {keys}")

    name_match = re.search(r"^name:\s*([^\n]+)$", frontmatter, re.MULTILINE)
    description_match = re.search(r"^description:\s*(.+)$", frontmatter, re.MULTILINE)
    name = name_match.group(1).strip() if name_match else ""
    description = description_match.group(1).strip() if description_match else ""

    if name != "chuwu" or not re.fullmatch(r"[a-z0-9-]{1,64}", name):
        ERRORS.append(f"invalid skill name: {name!r}")
    if not description:
        ERRORS.append("description is empty")
    else:
        if len(description) > DESC_MAX:
            ERRORS.append(f"description too long: {len(description)} > {DESC_MAX}")
        if "<" in description or ">" in description:
            ERRORS.append("description contains angle brackets")
    if name and not (ROOT / "agents" / "openai.yaml").is_file():
        ERRORS.append("agents/openai.yaml is missing (cross-tool packaging layer)")


def validate_skill_budget() -> None:
    skill = ROOT / "SKILL.md"
    if not skill.is_file():
        return

    content = skill.read_text(encoding="utf-8")
    lines = len(content.splitlines())
    characters = len(content)
    approx = approximate_token_count(content)

    if lines > SKILL_MAX_LINES:
        ERRORS.append(f"SKILL.md too long: {lines} lines > {SKILL_MAX_LINES}")
    if characters > SKILL_MAX_CHARACTERS:
        ERRORS.append(f"SKILL.md too big: {characters} chars > {SKILL_MAX_CHARACTERS}")
    if approx > SKILL_MAX_APPROX_TOKENS:
        ERRORS.append(f"SKILL.md exceeds token budget: ~{approx} > {SKILL_MAX_APPROX_TOKENS}")


def validate_relative_links() -> None:
    skill = ROOT / "SKILL.md"
    if not skill.is_file():
        return
    content = skill.read_text(encoding="utf-8")
    for ref in re.findall(r"`(references/[^`]+|scripts/[^`]+)`", content):
        target = ROOT / ref
        if not target.exists():
            WARNINGS.append(f"SKILL.md references a path that does not exist yet: {ref}")


def validate_leaks() -> None:
    for path in ROOT.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in LEAK_SCAN_SUFFIXES:
            continue
        if "dist" in path.parts:
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        for pattern, label in LEAK_PATTERNS:
            if pattern.search(text):
                ERRORS.append(f"{label} found in {path.relative_to(ROOT).as_posix()}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate the chuwu skill package.")
    parser.add_argument("--draft", action="store_true", help="downgrade missing files to warnings")
    args = parser.parse_args()
    strict = not args.draft

    validate_frontmatter()
    validate_skill_budget()

    missing(strict, "README.md")
    missing(strict, "LICENSE")
    missing(strict, "CHANGELOG.md")
    for rel in REQUIRED_KNOWLEDGE:
        missing(strict, f"references/knowledge/{rel}", ("knowledge",))
    for rel in REQUIRED_PRACTICAL:
        missing(strict, f"references/practical/{rel}", ("practical",))
    for rel in REQUIRED_SCRIPTS:
        missing(strict, f"scripts/{rel}", ("scripts",))

    validate_relative_links()
    validate_leaks()

    for warning in WARNINGS:
        print(f"WARN  {warning}")
    for error in ERRORS:
        print(f"FAIL  {error}")

    if ERRORS:
        print(f"\n{len(ERRORS)} error(s), {len(WARNINGS)} warning(s)")
        return 1
    print(f"\nOK — 0 error(s), {len(WARNINGS)} warning(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
