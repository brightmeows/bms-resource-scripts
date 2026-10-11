import difflib
import re
import shutil
from collections import Counter
from collections.abc import Callable
from pathlib import Path

from fs import SIMILARITY_CONTENT_TRIGGER, bms_dir_similarity
from fs.move import (
    REPLACE_OPTION_UPDATE_PACK,
    is_dir_having_file,
    move_elements_across_dir,
)
from options import Input, InputType, Option, is_not_a_dir, is_root_dir
from options.bms_folder import remove_zero_sized_media_files

# 日文平假名
RE_JAPANESE_HIRAGANA = re.compile("[\u3040-\u309f]+")
# 日文片假名
RE_JAPANESE_KATAKANA = re.compile("[\u30a0-\u30ff]+")
# 汉字
RE_CHINESE_CHARACTER = re.compile("[\u4e00-\u9fa5]+")

FIRST_CHAR_RULES: list[tuple[str, Callable[[str], bool]]] = [
    ("0-9", lambda name: len(name) > 0 and "0" <= name[0].upper() <= "9"),
    ("ABCD", lambda name: len(name) > 0 and "A" <= name[0].upper() <= "D"),
    ("EFGHIJK", lambda name: len(name) > 0 and "E" <= name[0].upper() <= "K"),
    ("LMNOPQ", lambda name: len(name) > 0 and "L" <= name[0].upper() <= "Q"),
    ("RST", lambda name: len(name) > 0 and "R" <= name[0].upper() <= "T"),
    ("UVWXYZ", lambda name: len(name) > 0 and "U" <= name[0].upper() <= "Z"),
    ("平假名", lambda name: len(name) > 0 and RE_JAPANESE_HIRAGANA.search(name[0]) is not None),
    ("片假名", lambda name: len(name) > 0 and RE_JAPANESE_KATAKANA.search(name[0]) is not None),
    ("汉字", lambda name: len(name) > 0 and RE_CHINESE_CHARACTER.search(name[0]) is not None),
    ("+", lambda name: len(name) > 0),
]


def _first_char_rules_find(name: str) -> str:
    for group_name, func in FIRST_CHAR_RULES:
        if not func(name):
            continue
        return group_name
    return "未分类"


def split_folders_with_first_char(root_dir: Path) -> None:
    root_folder_name = root_dir.name
    if not root_dir.is_dir():
        print(f"{root_dir} is not a dir! Aborting...")
        return
    if root_folder_name.endswith("]"):
        print(f"{root_dir} endswith ']'. Aborting...")
        return
    parent_dir = root_dir.parent
    for element_name in [p.name for p in root_dir.iterdir()]:
        element_path = root_dir / element_name
        # Find target dir
        rule = _first_char_rules_find(element_name)
        target_dir = parent_dir / f"{root_folder_name} [{rule}]"
        if not target_dir.is_dir():
            target_dir.mkdir()
        # Move
        target_path = target_dir / element_name
        shutil.move(element_path, target_path)

    # Remove the original folder when possible
    if not is_dir_having_file(root_dir):
        root_dir.rmdir()


def undo_split_pack(root_dir: Path) -> None:
    root_folder_name = root_dir.name
    parent_dir = root_dir.parent
    pairs: list[tuple[Path, Path]] = []
    for folder_name in [p.name for p in parent_dir.iterdir()]:
        folder_path = parent_dir / folder_name
        if folder_name.startswith(f"{root_folder_name} [") and folder_name.endswith("]"):
            print(f" - {root_dir} <- {folder_path}")
            pairs.append((folder_path, root_dir))

    confirm = input("Confirm? [y/N]")
    if not confirm.lower().startswith("y"):
        return

    for from_dir, to_dir in pairs:
        move_elements_across_dir(from_dir, to_dir)


def merge_split_folders(root_dir: Path) -> None:
    dir_names: list[str] = [p.name for p in root_dir.iterdir() if p.is_dir()]

    pairs: list[tuple[str, str]] = []

    for dir_name in dir_names:
        dir_path = root_dir / dir_name
        if not dir_path.is_dir():
            continue
        # Situation 1: endswith "]"
        if dir_name.endswith("]"):
            # Find dir_name_without_artist
            dir_name_mps_i = dir_name.rfind("[")
            if dir_name_mps_i == -1:
                continue
            dir_name_without_artist = dir_name[: dir_name_mps_i - 1]
            if len(dir_name_without_artist) == 0:
                continue
            # Check folder
            dir_path_without_artist = root_dir / dir_name_without_artist
            if not dir_path_without_artist.is_dir():
                continue
            # Check has another folders
            dir_names_with_starter = [
                dir_name for dir_name in dir_names if dir_name.startswith(f"{dir_name_without_artist} [")
            ]
            if len(dir_names_with_starter) > MAX_PREFIX_DIR_COUNT:
                print(
                    f" !_! {dir_name_without_artist} have more than {MAX_PREFIX_DIR_COUNT} folders!"
                    f" {dir_names_with_starter}"
                )
                continue

            # Append
            pairs.append((dir_name, dir_name_without_artist))

    last_from_dir_name = ""
    duplicate_list: list[str] = []
    for _target_dir_name, from_dir_name in pairs:
        if last_from_dir_name == from_dir_name:
            duplicate_list.append(from_dir_name)
        last_from_dir_name = from_dir_name

    if len(duplicate_list) > 0:
        print("Duplicate!")
        for name in duplicate_list:
            print(f" -> {name}")
        msg = f"Found duplicate target directories: {duplicate_list}"
        raise ValueError(msg)

    # Confirm
    for target_dir_name, from_dir_name in pairs:
        # Print
        print(f"- Find Dir pair: {target_dir_name} <- {from_dir_name}")

    selection = input(f"There are {len(pairs)} actions. Do transferring? [y/N]:")
    if not selection.lower().startswith("y"):
        print("Aborted.")
        return

    for target_dir_name, from_dir_name in pairs:
        from_dir_path = root_dir / from_dir_name
        target_dir_path = root_dir / target_dir_name
        print(f" - Moving: {target_dir_name} <- {from_dir_name}")
        move_elements_across_dir(from_dir_path, target_dir_path)


def move_works_in_pack(root_dir_from: Path, root_dir_to: Path) -> None:
    if root_dir_from == root_dir_to:
        return
    move_count = 0
    for bms_dir_name in [p.name for p in root_dir_from.iterdir()]:
        bms_dir = root_dir_from / bms_dir_name
        if not bms_dir.is_dir():
            continue

        print(f"Moving: {bms_dir_name}")

        dst_bms_dir = root_dir_to / bms_dir_name
        move_elements_across_dir(
            bms_dir,
            dst_bms_dir,
            replace_options=REPLACE_OPTION_UPDATE_PACK,
        )
        move_count += 1
    if move_count > 0:
        print(f"Move {move_count} songs.")
        return

    # Deal with song dir
    move_elements_across_dir(
        root_dir_from,
        root_dir_to,
        replace_options=REPLACE_OPTION_UPDATE_PACK,
    )


def _workdir_remove_unneed_media_files(work_dir: Path, rule: list[tuple[list[str], list[str]]]) -> None:
    remove_pairs: list[tuple[Path, Path]] = []
    removed_files: set[Path] = set()
    for file_name in [p.name for p in work_dir.iterdir()]:
        check_file_path = work_dir / file_name
        if not check_file_path.is_file():
            continue

        file_ext = check_file_path.suffix.lstrip(".")
        for upper_exts, lower_exts in rule:
            if file_ext not in upper_exts:
                continue
            # File is empty?
            if check_file_path.stat().st_size == 0:
                print(f" - !x!: File {check_file_path} is Empty! Skipping...")
                continue
            # File is in upper_exts, search for file in lower_exts.
            for lower_ext in lower_exts:
                replacing_file_path = check_file_path.with_suffix(f".{lower_ext}")
                # File not exist?
                if not replacing_file_path.is_file():
                    continue
                if replacing_file_path in removed_files:
                    continue
                remove_pairs.append((check_file_path, replacing_file_path))
                removed_files.add(replacing_file_path)

    if len(remove_pairs) > 0:
        print(f"Entering: {work_dir}")

    # Remove file
    for check_file_path, replacing_file_path in remove_pairs:
        print(f"- Remove file {replacing_file_path.name}, because {check_file_path.name} exists.")
        replacing_file_path.unlink()

    # Finished: Count Ext
    ext_count: dict[str, list[str]] = {}
    for count_file_name in [p.name for p in work_dir.iterdir()]:
        count_file_path = work_dir / count_file_name
        if not count_file_path.is_file():
            continue

        # Count ext
        file_ext = count_file_path.suffix.lstrip(".")
        if ext_count.get(file_ext) is None:
            ext_count.update({file_ext: [count_file_name]})
        else:
            ext_count[file_ext].append(count_file_name)

    # Remove zero sized files
    remove_zero_sized_media_files(work_dir)

    # Do With Ext Count
    mp4_count = ext_count.get("mp4")
    if mp4_count is not None and len(mp4_count) > 1:
        print(f" - Tips: {work_dir} has more than 1 mp4 files! {mp4_count}")


REMOVE_MEDIA_RULE_ORAJA: list[tuple[list[str], list[str]]] = [
    (["mp4"], ["avi", "wmv", "mpg", "mpeg"]),
    (["avi"], ["wmv", "mpg", "mpeg"]),
    (["flac", "wav"], ["ogg"]),
    (["flac"], ["wav"]),
    (["mpg"], ["wmv"]),
]
REMOVE_MEDIA_RULE_WAV_FILL_FLAC: list[tuple[list[str], list[str]]] = [
    (["wav"], ["flac"]),
]
REMOVE_MEDIA_RULE_MPG_FILL_WMV: list[tuple[list[str], list[str]]] = [
    (["mpg"], ["wmv"]),
]

REMOVE_MEDIA_FILE_RULES: list[list[tuple[list[str], list[str]]]] = [
    REMOVE_MEDIA_RULE_ORAJA,
    REMOVE_MEDIA_RULE_WAV_FILL_FLAC,
    REMOVE_MEDIA_RULE_MPG_FILL_WMV,
]


def remove_unneed_media_files(root_dir: Path, rule: list[tuple[list[str], list[str]]] | None = None) -> None:
    # Select Preset
    if rule is None:
        rule = []
    if len(rule) == 0:
        for i, _rule in enumerate(REMOVE_MEDIA_FILE_RULES):
            print(f"- {i}: {_rule}")
        selection_str = input("Select Preset (Default: 0):")
        selection = 0
        if len(selection_str) > 0:
            selection = int(selection_str)
        rule = REMOVE_MEDIA_FILE_RULES[selection]
    print(f"Selected: {rule}")

    # Do
    for bms_dir_name in [p.name for p in root_dir.iterdir()]:
        bms_dir_path = root_dir / bms_dir_name
        if not bms_dir_path.is_dir():
            continue
        _workdir_remove_unneed_media_files(
            bms_dir_path,
            rule,
        )


def move_out_works(target_root_dir: Path) -> None:
    for root_dir_name in [p.name for p in target_root_dir.iterdir()]:
        root_dir_path = target_root_dir / root_dir_name
        if not root_dir_path.is_dir():
            continue
        for work_dir_name in [p.name for p in root_dir_path.iterdir()]:
            work_dir_path = root_dir_path / work_dir_name
            target_work_dir_path = target_root_dir / work_dir_name
            # Deal with song dir
            move_elements_across_dir(
                work_dir_path,
                target_work_dir_path,
                replace_options=REPLACE_OPTION_UPDATE_PACK,
            )
        if not is_dir_having_file(root_dir_path):
            root_dir_path.rmdir()


SIMILARITY_NAME_TRIGGER = 0.7
# 同名目录前缀检查时允许的最大同名前缀目录数
MAX_PREFIX_DIR_COUNT = 2


def _subdir_names(dir_path: Path) -> list[str]:
    return sorted(p.name for p in dir_path.iterdir() if p.is_dir())


def _match_dir_pairs(
    from_dir: Path,
    to_dirs: list[Path],
    name_trigger: float = SIMILARITY_NAME_TRIGGER,
    content_trigger: float = SIMILARITY_CONTENT_TRIGGER,
) -> tuple[list[tuple[Path, Path, float, float]], list[tuple[Path, Path, float, float]]]:
    """
    两道闸门配对：

    1. 闸门1（名称粗筛）：difflib 名称相似度达到 name_trigger，或目标名以来源名为前缀
    2. 闸门2（内容验证）：bms_dir_similarity（媒体文件 stem 交集率）达到 content_trigger

    每个来源目录至多配对一个目标目录：按内容相似度、名称相似度、名称字典序取最高。
    返回 (配对列表, 落选提示列表)，元素均为 (from_path, to_path, 名称相似度, 内容相似度)；
    落选提示为通过闸门1但未过闸门2的候选，不参与合并。
    """
    to_name_dirs: list[tuple[str, Path]] = []
    for to_dir in to_dirs:
        to_name_dirs.extend((name, to_dir) for name in _subdir_names(to_dir))

    pairs: list[tuple[Path, Path, float, float]] = []
    rejected: list[tuple[Path, Path, float, float]] = []

    for from_name in _subdir_names(from_dir):
        from_path = from_dir / from_name
        best: tuple[float, float, str, Path] | None = None
        for to_name, to_dir in to_name_dirs:
            to_path = to_dir / to_name
            if to_path == from_path:
                continue
            # 闸门1：名称粗筛（前缀直通保留旧行为，其余走 quick_ratio 预筛 + ratio）
            matcher = difflib.SequenceMatcher(None, from_name, to_name)
            if not to_name.startswith(from_name):
                if matcher.quick_ratio() < name_trigger:
                    continue
                if matcher.ratio() < name_trigger:
                    continue
            name_similarity = matcher.ratio()
            # 闸门2：内容验证
            content_similarity = bms_dir_similarity(from_path, to_path)
            if content_similarity < content_trigger:
                rejected.append((from_path, to_path, name_similarity, content_similarity))
                continue
            if best is not None:
                best_content, best_name, best_to_name, _best_path = best
                if (content_similarity, name_similarity) < (best_content, best_name):
                    continue
                if (content_similarity, name_similarity) == (best_content, best_name) and to_name >= best_to_name:
                    continue
            best = (content_similarity, name_similarity, to_name, to_path)
        if best is not None:
            best_content, best_name, _best_to_name, best_path = best
            pairs.append((from_path, best_path, best_name, best_content))

    return pairs, rejected


def _print_match_report(
    pairs: list[tuple[Path, Path, float, float]],
    rejected: list[tuple[Path, Path, float, float]],
) -> None:
    for from_path, to_path, name_similarity, content_similarity in rejected:
        print(
            f" -x- 名称相似但内容不符（跳过）: {from_path.name} <=> {to_path.name} "
            f"(名称: {name_similarity:.2f}, 内容: {content_similarity:.2f})"
        )
    target_counts: Counter[Path] = Counter(to_path for _, to_path, _, _ in pairs)
    for from_path, to_path, name_similarity, content_similarity in pairs:
        multi_source = " [多来源!]" if target_counts[to_path] > 1 else ""
        print(
            f" -> {from_path.name} => {to_path.name} "
            f"(名称: {name_similarity:.2f}, 内容: {content_similarity:.2f}){multi_source}"
        )


def move_works_with_same_name(root_dir_from: Path, root_dir_to: Path) -> None:
    """
    将源文件夹(dir_from)中的子文件夹，经两道闸门匹配后合并到目标文件夹(dir_to)中的对应子文件夹

    匹配规则：
    1. 闸门1（名称粗筛）：difflib 名称相似度 >= 0.7，或目标名以来源名为前缀
    2. 闸门2（内容验证）：bms_dir_similarity（媒体文件 stem 交集率）>= 0.8
    3. 每个来源目录按内容相似度、名称相似度、名称字典序取最高分目标

    参数:
        root_dir_from (Path): 源文件夹路径
        root_dir_to (Path): 目标文件夹路径
    """
    if not root_dir_from.is_dir():
        msg = f"源路径不存在或不是目录: {root_dir_from}"
        raise ValueError(msg)
    if not root_dir_to.is_dir():
        msg = f"目标路径不存在或不是目录: {root_dir_to}"
        raise ValueError(msg)

    pairs, rejected = _match_dir_pairs(root_dir_from, [root_dir_to])
    _print_match_report(pairs, rejected)

    if len(pairs) == 0:
        print("没有找到可合并的目录对。")
        return

    selection = input(f"共 {len(pairs)} 对。是否合并？[y/N]")
    if not selection.lower().startswith("y"):
        return

    for from_path, to_path, _, _ in pairs:
        print(f"合并: '{from_path}' -> '{to_path}'")
        move_elements_across_dir(
            from_path,
            to_path,
            replace_options=REPLACE_OPTION_UPDATE_PACK,
        )


def move_works_with_same_name_to_siblings(root_dir_from: Path) -> None:
    """
    将源文件夹(dir_from)中的子文件夹，经两道闸门匹配后合并到同级目录中的对应子文件夹

    匹配规则与 move_works_with_same_name 相同（名称粗筛 + 内容验证），
    目标范围为父目录下除自身外的所有同级目录的直接子目录。

    参数:
        root_dir_from (Path): 源文件夹路径
    """
    if not root_dir_from.is_dir():
        msg = f"源路径不存在或不是目录: {root_dir_from}"
        raise ValueError(msg)

    parent_dir = root_dir_from.parent
    root_base_name = root_dir_from.name

    to_dirs: list[Path] = [parent_dir / name for name in _subdir_names(parent_dir) if name != root_base_name]

    pairs, rejected = _match_dir_pairs(root_dir_from, to_dirs)
    _print_match_report(pairs, rejected)

    if len(pairs) == 0:
        print("没有找到可合并的目录对。")
        return

    selection = input(f"共 {len(pairs)} 对。是否合并到各平级目录？[y/N]")
    if not selection.lower().startswith("y"):
        return

    for from_path, to_path, _, _ in pairs:
        print(f"合并: '{from_path}' -> '{to_path}'")
        move_elements_across_dir(
            from_path,
            to_path,
            replace_options=REPLACE_OPTION_UPDATE_PACK,
        )


OPTIONS: list[Option] = [
    Option(
        split_folders_with_first_char,
        name="BMS大包目录：将该目录下的作品，按照首字符分成多个文件夹",
        inputs=[Input(InputType.Path, "")],
        check_func=is_root_dir,
    ),
    Option(
        undo_split_pack,
        name="BMS大包目录：（撤销操作）将该目录下的作品，按照首字符分成多个文件夹",
        inputs=[Input(InputType.Path, "The target folder path.", allow_missing=True)],
        check_func=is_not_a_dir,
    ),
    Option(
        move_works_in_pack,
        name="BMS大包目录：将目录A下的作品，移动到目录B（自动合并）",
        inputs=[Input(InputType.Path, "From"), Input(InputType.Path, "To")],
        check_func=is_root_dir,
    ),
    Option(
        move_out_works,
        name="BMS大包父目录：移出一层目录（自动合并）",
        inputs=[Input(InputType.Path, "Target Root Dir")],
    ),
    Option(
        move_works_with_same_name,
        name="BMS大包目录：将源文件夹(dir_from)中，文件名相似的子文件夹，合并到目标文件夹(dir_to)中的对应子文件夹",
        inputs=[Input(InputType.Path, "From"), Input(InputType.Path, "To")],
        check_func=is_root_dir,
    ),
    Option(
        move_works_with_same_name_to_siblings,
        name="BMS大包目录：将该目录中文件名相似的子文件夹，合并到各平级目录中",
        inputs=[Input(InputType.Path, "Dir")],
        check_func=is_root_dir,
    ),
]

OPTIONS_LEGACY: list[Option] = [
    Option(
        merge_split_folders,
        inputs=[Input(InputType.Path, "")],
        check_func=is_not_a_dir,
    ),
]
