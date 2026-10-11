# media/ — 媒体转换层

## 定位

音频与视频的批量转换：以“预设”描述外部编码器命令，逐个作品目录转换，并在产物验证通过后才删除原件。

## 结构

| 文件 | 职责 |
| --- | --- |
| `audio.py` | `AudioPreset`、`AUDIO_PRESET_*`、`transfer_audio_by_format_in_dir`、`bms_folder_transfer_audio` |
| `video.py` | `VideoPreset`、`VIDEO_PRESETS`、`process_video_in_dir`、`bms_folder_transfer_video`、`get_video_info`/`get_video_size` |

## 约定

- `AudioPreset(command, output_format, arg)` 与 `VideoPreset(command, input_arg, fliter_arg, output_file_ext, output_codec, arg)` 只描述命令，不描述编排；新增编码器只加预设。
- 预设列表按顺序回退：当前预设失败才会尝试下一个；全部失败保留原文件并报告，绝不删除原件。
- 产物验证：输出存在且非空才视为成功并删除原件（音频按 `returncode == 0` 且文件非空；视频同样）。
- 视频预设按分辨率成对提供（512x512 与 480p），优先列表由 `get_prefered_preset_list` 依据源视频尺寸决定。
- 音频批量转换对每个目录并发起多个编码进程（上限 `min(cpu_count, 24)`），目录级别并行由调用方控制。

## 坑

- `flac` 命令行编码器不支持 32 位浮点 WAV（format type 3）：预设链会全部失败，原文件保留，需调用方决定去留。
- 子进程 stderr 写入临时文件而非管道：编码器输出量大时管道会写满阻塞（代码内有 `noqa: SIM115` 说明）。
- 视频转换命令用 `shell=True`，`flac`/`oggenc` 的路径参数会加引号；文件名含引号或与命令同形时会破坏命令，本工具假设 BMS 资源文件名不包含此类字符。
- `ffmpeg`、`oggenc` 缺失时命令返回非 0，效果等同转换失败；入口层用 `options` 的 `check_*_exec` 提前拦截。
