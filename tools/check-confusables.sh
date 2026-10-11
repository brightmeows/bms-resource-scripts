#!/usr/bin/env bash
# 检测与 ASCII 等价的混淆字符（各种连字符、窄空格、零宽字符、BOM）。
#
# 用法：bash tools/check-confusables.sh [路径...]（不带参数时检查当前目录）
# 由 pre-commit 钩子与 CI 共同调用，保持单一事实来源。

set -euo pipefail

targets=("$@")
if [ ${#targets[@]} -eq 0 ]; then
  targets=(.)
fi

# 各码点：U+2010/2011/2012 连字符、U+2212 减号、U+00A0 不换行空格、
# U+202F 窄不换行空格、U+200B 零宽空格、U+FEFF BOM
if rg -l \
  -e "$(printf '\xe2\x80\x90')" -e "$(printf '\xe2\x80\x91')" \
  -e "$(printf '\xe2\x80\x92')" -e "$(printf '\xe2\x88\x92')" \
  -e "$(printf '\xc2\xa0')" -e "$(printf '\xe2\x80\xaf')" \
  -e "$(printf '\xe2\x80\x8b')" -e "$(printf '\xef\xbb\xbf')" \
  "${targets[@]}"; then
  echo "发现混淆字符（见上），请替换为 ASCII 等价字符" >&2
  exit 1
fi
