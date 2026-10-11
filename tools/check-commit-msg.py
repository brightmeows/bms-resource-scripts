#!/usr/bin/env python3
"""校验提交信息符合 Conventional Commits（约定见 AGENTS.md「提交」节）。

pre-commit 以 commit-msg stage 调用，参数为提交信息文件路径；
CI 对 PR 中的每个提交调用同一脚本。

用法：
    python3 tools/check-commit-msg.py .git/COMMIT_EDITMSG
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

_TYPES = "build|chore|ci|docs|feat|fix|perf|refactor|revert|style|test"
_PATTERN = re.compile(rf"^({_TYPES})(\([a-z0-9][a-z0-9-]*\))?!?: .+")
EXPECTED_ARG_COUNT = 2

_SKIP = re.compile(r"^(Merge |Revert |fixup! |squash! )")


def main(argv: list[str]) -> int:
    if len(argv) != EXPECTED_ARG_COUNT:
        print(__doc__, file=sys.stderr)
        return 2

    message = Path(argv[1]).read_text(encoding="utf-8")

    subject = ""
    for line in message.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        subject = stripped
        break

    if not subject:
        print("提交信息为空", file=sys.stderr)
        return 1
    if _SKIP.match(subject):
        return 0
    if not _PATTERN.match(subject):
        print("提交信息不符合 Conventional Commits 格式：", file=sys.stderr)
        print(f"  {subject}", file=sys.stderr)
        print(file=sys.stderr)
        print("期望：type(scope)!: subject", file=sys.stderr)
        print(f"type 取值：{_TYPES.replace('|', ' ')}", file=sys.stderr)
        print("scope 为小写 kebab-case（可省略），! 表示破坏性变更", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
