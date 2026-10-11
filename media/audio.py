import dataclasses
import multiprocessing
import subprocess
import tempfile
import time
from pathlib import Path
from typing import IO

"""
Audio
"""


class AudioPreset:
    def __init__(self, command: str, output_format: str, arg: str | None = None) -> None:
        self.command = command
        self.output_format = output_format
        self.arg = arg

    def __str__(self) -> str:
        return f"AudioPreset {{ command: {self.command}, output_format: {self.output_format} arg: {self.arg} }}"

    def __repr__(self) -> str:
        return self.__str__()


AUDIO_PRESET_OGG_Q10 = AudioPreset("oggenc", "ogg", "-q10")

AUDIO_PRESET_WAV_FROM_FLAC = AudioPreset("flac", "wav", "-d --keep-foreign-metadata-if-present -f")

AUDIO_PRESET_FLAC = AudioPreset("flac", "flac", "--keep-foreign-metadata-if-present --best -f")

AUDIO_PRESETS = [
    AUDIO_PRESET_FLAC,
    AUDIO_PRESET_WAV_FROM_FLAC,
    AUDIO_PRESET_OGG_Q10,
]


@dataclasses.dataclass
class _AudioProcess:
    """One in-flight conversion task inside transfer_audio_by_format_in_dir."""

    file_path: Path
    preset_index: int
    process: subprocess.Popen | None
    stderr_file: IO[bytes] | None
    # True when the task was skipped because a valid target file already existed.
    target_existed: bool
    error_message: str | None = None


def _get_audio_precess_cmd(
    file_path: Path,
    output_file_path: Path,
    preset: AudioPreset,
) -> str:
    # Execute
    arg = preset.arg if preset.arg is not None else ""
    if preset.command == "oggenc":
        return f'oggenc {arg} "{file_path}" -o "{output_file_path}"'
    if preset.command == "flac":
        return f'flac {arg} "{file_path}" -o "{output_file_path}"'
    return ""


def transfer_audio_by_format_in_dir(
    dir_path: Path,
    input_exts: list[str],
    presets: list[AudioPreset],
    remove_origin_file_when_success: bool = True,
    remove_existing_target_file: bool = True,
) -> bool:
    """
    Example:
    wav flac flac
    wav ogg ogg -ab 320k

    Origin files are only removed after the converted output is verified
    to exist and be non-empty. Files that fail every preset are kept on
    disk for manual handling; they are never deleted.
    """

    def check_input_file(dir_path: Path, file_name: str, input_exts: list[str]) -> Path | None:
        file_path = dir_path / file_name
        if not file_path.is_file():
            return None
        # Check ext
        ext_found: str | None = None
        for ext in input_exts:
            if file_path.suffix.lower() == "." + ext:
                ext_found = ext
        if ext_found is None:
            return None
        return dir_path / file_name

    def get_output_file_path(file_path: Path, preset: AudioPreset) -> Path:
        return file_path.parent / (file_path.stem + "." + preset.output_format)

    def remove_origin_file(file_path: Path) -> None:
        if remove_origin_file_when_success and file_path.is_file():
            try:
                file_path.unlink()
            except PermissionError:
                print(f" -> PermissionError When Deleting: {file_path}")

    def spawn_parse_audio_process(file_path: Path, preset_index: int, preset: AudioPreset) -> _AudioProcess:
        # New cmd
        output_file_path = get_output_file_path(file_path, preset)
        # Target File exists?
        if output_file_path.is_file():
            if output_file_path.stat().st_size > 0 and not remove_existing_target_file:
                print(f" - File {output_file_path} exists! Skipping...")
                return _AudioProcess(file_path, preset_index, None, None, True)
            print(f" - Remove existing file: {output_file_path}")
            output_file_path.unlink()
        # Run cmd
        cmd = _get_audio_precess_cmd(
            file_path,
            output_file_path,
            preset,
        )
        if len(cmd) == 0:
            return _AudioProcess(file_path, preset_index, None, None, False)
        # stderr must go to a real file: with a pipe, a chatty encoder blocks
        # forever once the 64KB pipe buffer fills up, because nothing drains
        # it while we only poll the process.
        # 需要在轮询子进程期间保持打开，不能交给 with 管理生命周期
        stderr_file = tempfile.TemporaryFile(mode="w+b")  # noqa: SIM115
        process = subprocess.Popen(cmd, shell=True, stdout=subprocess.DEVNULL, stderr=stderr_file)
        return _AudioProcess(file_path, preset_index, process, stderr_file, False)

    has_error = False
    error_reports: list[str] = []

    # 创建线程池
    hdd = dir_path.drive.upper() != "C:"
    max_workers = min(multiprocessing.cpu_count(), 24) if hdd else multiprocessing.cpu_count()

    # Submit
    processes: list[_AudioProcess] = []
    task_args: list[tuple[Path, int, AudioPreset]] = [
        (dir_path / file_name, 0, presets[0])
        for file_name in [p.name for p in dir_path.iterdir()]
        if check_input_file(dir_path, file_name, input_exts) is not None
    ]

    if len(task_args) > 0:
        print("Entering dir:", dir_path, "Input ext:", input_exts)
        print("Preset:", presets)

    # Count
    file_count = len(task_args)
    fallback_file_names: list[tuple[str, int]] = []

    for task_arg in task_args:
        if len(processes) >= max_workers:
            break
        processes.append(spawn_parse_audio_process(*task_arg))
    task_args = task_args[len(processes) :]

    # 等待所有任务完成
    while len(processes) > 0:
        new_processes: list[_AudioProcess] = []

        # 检查进程状态
        switch_next_list: list[_AudioProcess] = []
        for task in processes:
            # Switch Next?
            switch_next = False
            if task.process is None:
                # No process: either skipped because a valid target file
                # already existed (same as a success), or no command for
                # this preset (same as a failure).
                if task.target_existed:
                    remove_origin_file(task.file_path)
                else:
                    switch_next = True
                    task.error_message = f"Preset {task.preset_index} produced no command for file: {task.file_path}"
            else:
                process_returncode = task.process.poll()
                if process_returncode is None:
                    # Running
                    new_processes.append(task)
                else:
                    output_file_path = get_output_file_path(task.file_path, presets[task.preset_index])
                    output_verified = (
                        process_returncode == 0 and output_file_path.is_file() and output_file_path.stat().st_size > 0
                    )
                    if output_verified:
                        # Verified Success
                        remove_origin_file(task.file_path)
                    else:
                        # Failed (or output missing/empty): keep the origin file.
                        switch_next = True
                        stderr_text = ""
                        if task.stderr_file is not None:
                            task.stderr_file.seek(0)
                            stderr_text = task.stderr_file.read().decode(errors="replace")
                            task.stderr_file.close()
                        task.error_message = (
                            f"Preset {task.preset_index} failed"
                            f" (return code {process_returncode}) for file: {task.file_path}\n"
                            f"stderr:\n{stderr_text}"
                        )

            if switch_next:
                switch_next_list.append(task)

        # 切换下个预设
        for task in switch_next_list:
            new_preset_index = task.preset_index + 1
            if new_preset_index not in range(len(presets)):
                # All presets failed. Never delete the origin file here.
                has_error = True
                if task.error_message is not None:
                    error_reports.append(task.error_message)
                continue
            # Count
            fallback_file_names.append((task.file_path.name, new_preset_index))
            # Try Next
            task_args.append((task.file_path, new_preset_index, presets[new_preset_index]))

        # 启动新进程
        running_count_delta = 0
        for task_arg in task_args:
            if len(new_processes) >= max_workers:
                break
            new_processes.append(spawn_parse_audio_process(*task_arg))
            running_count_delta += 1
        task_args = task_args[running_count_delta:]

        processes = new_processes

        # 休眠一阵子
        time.sleep(0.001)

    if len(error_reports) > 0:
        print("Has Error!")
        for report in error_reports:
            print("-", report)
        print(" ! Failed files are kept on disk.")

    if file_count > 0:
        print(f" -v- Parsed {file_count} file(s).")
    if len(fallback_file_names) > 0:
        print(f" x_x Fallback: {fallback_file_names}. Totally {len(fallback_file_names)} files.")

    return not has_error


MODES: list[tuple[str, list[str], list[AudioPreset]]] = [
    ("Convert: WAV to FLAC", ["wav"], [AUDIO_PRESET_FLAC]),
    ("Compress: FLAC to OGG Q10", ["flac"], [AUDIO_PRESET_OGG_Q10]),
    ("Compress: WAV to OGG Q10", ["wav"], [AUDIO_PRESET_OGG_Q10]),
    ("Reverse: FLAC to WAV", ["flac"], [AUDIO_PRESET_WAV_FROM_FLAC]),
]


def bms_folder_transfer_audio(
    root_dir: Path,
    input_ext: list[str] | None = None,
    transfer_mode: list[AudioPreset] | None = None,
    remove_origin_file_when_success: bool = True,
    stop_on_error: bool = False,
) -> None:
    # Select Modes
    if transfer_mode is None:
        transfer_mode = []
    if input_ext is None:
        input_ext = []
    if len(transfer_mode) == 0 or len(input_ext) == 0:
        for i, (mode_str, mode_input_exts, mode_presets) in enumerate(MODES):
            print(f"- {i}: {mode_str} ({mode_input_exts}) ({mode_presets})")
        selection = int(input("Select Mode (Type numbers above):"))
        input_ext = MODES[selection][1]
        transfer_mode = MODES[selection][2]

    for bms_dir_name in [p.name for p in root_dir.iterdir()]:
        bms_dir_path = root_dir / bms_dir_name
        if not bms_dir_path.is_dir():
            continue
        is_success = transfer_audio_by_format_in_dir(
            bms_dir_path,
            input_ext,
            transfer_mode,
            remove_origin_file_when_success=remove_origin_file_when_success,
        )
        if not is_success:
            print(" - Dir:", bms_dir_path, "Error occured!")
            if stop_on_error:
                break
