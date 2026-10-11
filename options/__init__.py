from __future__ import annotations

import subprocess
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum, auto
from pathlib import Path
from typing import Any

from bms import CHART_FILE_EXTS

# 获取当前文件的绝对路径
_CURRENT_PATH = Path(__file__).resolve()

# 获取当前文件所在目录
_CURRENT_DIR = _CURRENT_PATH.parent

_LOG_FILE_PATH = _CURRENT_DIR / "history.log"

# 历史路径展示条数
DISPLAY_PATH_COUNT = 5


def callable_name(func: Callable[..., object]) -> str:
    """取可调用对象的展示名：函数用 __name__，其它退化到类型名。"""
    return getattr(func, "__name__", type(func).__name__)


def _path_mark(path: Path) -> str:
    """历史条目的实时状态标记：只在展示时计算，不写回历史文件。"""
    if path.is_dir():
        return ""
    if path.exists():
        return "（不是目录）"
    return "（不存在）"


def _path_reject_reason(path: Path, allow_missing: bool) -> str | None:
    if path.is_dir():
        return None
    if path.exists():
        return f"路径已存在但不是目录：{path}"
    if allow_missing:
        return None
    return f"路径不存在或不是目录：{path}"


def input_path(allow_missing: bool = False) -> Path:
    if not _LOG_FILE_PATH.is_file():
        with _LOG_FILE_PATH.open("w") as f:
            f.write("\n")

    # 读取历史路径，存储为Path对象
    paths: list[Path] = []
    with _LOG_FILE_PATH.open() as f:
        for line in f.readlines():
            path_str = line.strip()
            if len(path_str) == 0:
                continue
            # 移除引号
            if path_str.startswith('"') and path_str.endswith('"'):
                path_str = path_str[1:-1]
            paths.append(Path(path_str))

    # 去重并保持顺序，越往前代表时间越近
    seen: set[str] = set()
    unique_paths: list[Path] = []
    for path in paths:
        path_str = str(path)
        if path_str not in seen:
            seen.add(path_str)
            unique_paths.append(path)
    paths = unique_paths  # 保存所有选择过的路径

    # 显示历史路径（只显示最近的5个），失效条目附加实时标记
    if len(paths) > 0:
        print("输入路径开始。以下是之前使用过的路径：")
        display_paths = paths[:DISPLAY_PATH_COUNT]  # 只显示最近的几个
        for i, path in enumerate(display_paths):
            print(f" -> {i}: {path}{_path_mark(path)}")
        if len(paths) > DISPLAY_PATH_COUNT:
            print(f"（还有 {len(paths) - DISPLAY_PATH_COUNT} 个历史路径，输入？查看全部）")

    # 获取用户输入，直到得到符合要求的路径
    while True:
        selection_str = input("直接输入路径，或输入上面的数字（索引）进行选择，输入？查看所有选项：").strip()

        # 处理帮助命令
        if selection_str in ["？", "?"]:
            if len(paths) > 0:
                print("所有可选选项：")
                for i, path in enumerate(paths):
                    print(f"  {i}: {path}{_path_mark(path)}")
            else:
                print("暂无历史路径记录")
            continue

        # 处理空输入
        if len(selection_str) == 0:
            print(" - 输入为空，请重新输入。")
            continue

        # 处理选择
        if selection_str.isdigit() and 0 <= int(selection_str) < len(paths):
            selected_path = paths[int(selection_str)]
        else:
            selected_path = Path(selection_str)

        # 校验选择
        reject_reason = _path_reject_reason(selected_path, allow_missing)
        if reject_reason is not None:
            print(f" - {reject_reason}，请重新输入。")
            continue
        break

    # 将选中的路径移到最前面（最新的位置）
    if selected_path in paths:
        paths.remove(selected_path)
    paths.insert(0, selected_path)

    # 保存更新后的路径（保存所有选择过的路径）
    with _LOG_FILE_PATH.open("w") as f:
        for path in paths:
            # 序列化到文件时需要转换为字符串
            f.write(str(path) + "\n")

    return selected_path


class InputType(Enum):
    Any = auto()
    Word = auto()
    Int = auto()
    Path = auto()


@dataclass
class Input:
    type: InputType = InputType.Any
    description: str = ""
    # True 时允许路径不存在（由后续流程创建），但仍要求不是已存在的文件
    allow_missing: bool = False

    def exec_input(self) -> Any:
        match self.type:
            case InputType.Any:
                return input("Input:")
            case InputType.Word:
                tips = "Input a word:"
                w_str = input(tips)
                while w_str.find(" ") != -1:
                    print("Requires a word. Re-input.")
                    w_str = input(tips)
                return w_str
            case InputType.Int:
                tips = "Input a number:"
                w_str = input(tips)
                while not w_str.isdigit():
                    print("Requires a number. Re-input.")
                    w_str = input(tips)
                return int(w_str)
            case InputType.Path:
                return input_path(self.allow_missing)


class ConfirmType(Enum):
    NoConfirm = auto()
    DefaultYes = auto()
    DefaultNo = auto()


@dataclass
class Option:
    func: Callable[..., None]
    name: str = ""
    inputs: list[Input] = field(default_factory=list)
    check_func: Callable[..., bool] | list[Callable[..., bool]] | None = None
    confirm: ConfirmType = ConfirmType.DefaultYes

    def exec(self) -> None:
        print(self.name or callable_name(self.func))
        # Input
        args = []
        for i, input_arg in enumerate(self.inputs):
            print(f"参数编号： {i + 1}/{len(self.inputs)}, 类型：{input_arg.type}, 描述：{input_arg.description}")
            res = input_arg.exec_input()
            print(f' - 输入："{res}"')
            args.append(res)
        # Check
        if self.check_func is not None:
            checks: list[Callable[..., bool]] = (
                self.check_func
                if isinstance(self.check_func, list)
                else [self.check_func]
                if self.check_func is not None
                else []
            )
            for idx, check in enumerate(checks, start=1):
                try:
                    passed = check(*args)
                except (ValueError, TypeError, OSError, RuntimeError) as e:
                    print(f" - 检查 {idx} 异常：{e}")
                    return
                if not passed:
                    print(f" - 检查未通过（第 {idx} 项：{callable_name(check)}）。")
                    return
        # Confirm
        match self.confirm:
            case ConfirmType.NoConfirm:
                pass
            case ConfirmType.DefaultYes:
                # 在确认前打印当前输入及其描述
                if len(self.inputs) > 0:
                    print("确认以下输入：")
                    for i, input_arg in enumerate(self.inputs):
                        val = args[i] if i < len(args) else None
                        print(f" - 参数{i + 1}: {input_arg.description} = {val}")
                confirm = input("确认？ [Y/n]:")
                go_pass = len(confirm) == 0 or confirm.lower().startswith("y")
                if not go_pass:
                    return
            case ConfirmType.DefaultNo:
                # 在确认前打印当前输入及其描述
                if len(self.inputs) > 0:
                    print("确认以下输入：")
                    for i, input_arg in enumerate(self.inputs):
                        val = args[i] if i < len(args) else None
                        print(f" - 参数{i + 1}: {input_arg.description} = {val}")
                confirm = input("确认？ [y/N]:")
                go_pass = confirm.lower().startswith("y")
                if not go_pass:
                    return
        # Exec
        self.func(*args)


def is_root_dir(*args: Any) -> bool:
    for index, arg in enumerate(args, start=1):
        # 非 Path 参数（如 BMS活动目录的编号）不参与目录校验
        if not isinstance(arg, Path):
            continue
        if not arg.is_dir():
            print(f" - 参数{index} 路径不存在或不是目录：{arg}")
            return False
        has_chart_file = any(p.name.endswith(CHART_FILE_EXTS) and p.is_file() for p in arg.iterdir())
        if has_chart_file:
            print(f" - 参数{index} 下存在谱面文件，不是作品根目录：{arg}")
            return False
    return True


def is_work_dir(*root_dir: Path) -> bool:
    for dir_path in root_dir:
        result = len([p.name for p in dir_path.iterdir() if p.name.endswith(CHART_FILE_EXTS) and p.is_file()]) > 0
        if not result:
            return False
    return True


def is_not_a_dir(dir_path: Path) -> bool:
    return not dir_path.is_dir()


# === Exec checks (split by executable) ===
def _check_exec(cmd: str, name: str) -> bool:
    run = subprocess.run(cmd, shell=True, stdin=subprocess.PIPE, capture_output=True, check=False)
    if run.returncode != 0:
        print(f' - 未找到或无法执行 {name}（命令 "{cmd}" 失败）。')
        return False
    return True


def check_ffmpeg_exec(*_args: Any) -> bool:
    return _check_exec("ffmpeg -version", "ffmpeg")


def check_flac_exec(*_args: Any) -> bool:
    return _check_exec("flac --version", "flac")


def check_oggenc_exec(*_args: Any) -> bool:
    return _check_exec("oggenc -v", "oggenc")
