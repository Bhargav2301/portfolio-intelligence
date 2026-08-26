"""Fail CI when foundational safety or repository rules are violated."""

from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REQUIRED = (
    "README.md",
    ".env.example",
    "docs/SECRETS_SETUP.md",
    "services/api/src/portfolio_api/main.py",
    "services/agents/src/portfolio_agents/graph.py",
    "apps/web/app/page.tsx",
)
REQUIREMENT_DOCS = tuple(
    f"docs/requirements/0{index}_{name}.md"
    for index, name in (
        (1, "Product_Requirements_Document"),
        (2, "Market_and_Business_Requirements_Document"),
        (3, "Technical_Design_and_System_Architecture"),
        (4, "UX_UI_Design_Specification"),
        (5, "Data_Model_and_API_Specification"),
        (6, "QA_and_Test_Plan"),
    )
)
CODE_SUFFIXES = {".py", ".ts", ".tsx", ".js", ".sql"}
TEXT_SUFFIXES = CODE_SUFFIXES | {".md", ".json", ".toml", ".yml", ".yaml"}
FORBIDDEN_EXECUTION = (
    re.compile(r"\bplace_order\b", re.IGNORECASE),
    re.compile(r"\bexecute_trade\b", re.IGNORECASE),
    re.compile(r"route\([^)]*/orders", re.IGNORECASE),
)
SECRET_PATTERNS = (
    re.compile(r"sk-[A-Za-z0-9_-]{20,}"),
    re.compile(r"github_pat_[A-Za-z0-9_]{20,}"),
    re.compile(r"gh[opsu]_[A-Za-z0-9]{20,}"),
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
)


def code_files() -> list[Path]:
    return [
        path
        for path in ROOT.rglob("*")
        if path.is_file()
        and path.suffix in CODE_SUFFIXES
        and ".next" not in path.parts
        and "node_modules" not in path.parts
    ]


def text_files() -> list[Path]:
    special_names = {"Dockerfile", "Makefile", ".env.example"}
    return [
        path
        for path in ROOT.rglob("*")
        if path.is_file()
        and (path.suffix in TEXT_SUFFIXES or path.name in special_names)
        and ".next" not in path.parts
        and "node_modules" not in path.parts
    ]


def main() -> int:
    failures: list[str] = []
    for relative in REQUIRED + REQUIREMENT_DOCS:
        if not (ROOT / relative).is_file():
            failures.append(f"missing required file: {relative}")

    for path in code_files():
        text = path.read_text(encoding="utf-8", errors="replace")
        relative = path.relative_to(ROOT)
        for pattern in FORBIDDEN_EXECUTION:
            if pattern.search(text):
                failures.append(f"forbidden execution capability in {relative}")

    for path in text_files():
        text = path.read_text(encoding="utf-8", errors="replace")
        relative = path.relative_to(ROOT)
        for pattern in SECRET_PATTERNS:
            if pattern.search(text):
                failures.append(f"possible committed secret in {relative}")

    env_path = ROOT / ".env"
    if env_path.exists():
        failures.append(".env exists in the repository validation workspace")

    if failures:
        for failure in failures:
            print(f"ERROR: {failure}")
        return 1
    print("Repository policy checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
