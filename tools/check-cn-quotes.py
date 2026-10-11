#!/usr/bin/env python3
"""检查简体中文 Markdown 文本的引号规范（GB/T 15834-2011）。

扫描非代码块、非行内代码中的直引号、全角无向引号与直角引号，
这些字符在简体中文横排中均不合规（规则见 ~/.agents_meow/AGENTS.main.md「中文引号」节）。

用法：
    python3 tools/check-cn-quotes.py 文件.md [更多文件.md ...]
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

# 违规字符：直引号 U+0022/U+0027、全角无向引号 U+FF02、直角引号 U+300C-300F
EXPECTED_ARG_COUNT = 2

_BAD_QUOTES = "[\u0022\u0027\uff02\u300c\u300d\u300e\u300f]"


def check_file(path: Path) -> int:
    """返回该文件的违规行数，并逐行打印。"""
    in_code = False
    violations = 0
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if re.match(r"^(```|~~~)", line):
            in_code = not in_code
            continue
        if in_code:
            continue
        # 行内代码（反引号包裹）视为代码字符串，跳过
        text = re.sub(r"`[^`]*`", "", line)
        if re.search(_BAD_QUOTES, text):
            print(f"{path}:{number}: {line.rstrip()}")
            violations += 1
    return violations


def main(argv: list[str]) -> int:
    if len(argv) < EXPECTED_ARG_COUNT:
        print(__doc__, file=sys.stderr)
        return 2
    total = sum(check_file(Path(name)) for name in argv[1:])
    return 1 if total else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
