# scripts/ — 大包流水线入口

## 定位

把“原始包目录”变成“HQ 版/LQ 版作品目录”的端到端入口；编排 `fs`、`media`、`options.bms_folder` 的能力，不重复实现底层操作。

## 结构

| 入口 | 输入 | 说明 |
| --- | --- | --- |
| `pack_setup_rawpack_to_hq` | 原始包目录、新作品目录 | 首次打包：解压、按 BMS 命名、WAV 转 FLAC、清理冗余媒体 |
| `pack_update_rawpack_to_hq` | 原始包目录、新差量目录、既有作品目录 | 更新包：用既有目录同步命名，再软同步出差量 |
| `pack_raw_to_hq` | 作品目录 | 对已有目录补做 HQ 化（WAV 转 FLAC + 冗余媒体清理） |
| `pack_hq_to_lq` | 作品目录 | HQ 转 LQ：FLAC 转 OGG、MP4 转 MPG/WMV/AVI |

## 约定

- `pack_raw_to_hq` 与 `pack_setup_rawpack_to_hq` 的第 3/4 步必须成对：先 `bms_folder_transfer_audio` 转音频，再 `remove_unneed_media_files(..., REMOVE_MEDIA_RULE_ORAJA)` 清冗余，顺序颠倒会误删可选格式。
- 更新包流程依赖 `SYNC_PRESET_FOR_APPEND` 的软同步语义：`remove_src_same_files=True` 把与主目录相同的文件从差量目录移除，最后 `remove_empty_folder` 清空壳目录。
- 处理成功的原始包移入 `<pack_dir>/BOFTTPacks/`，失败保留原地；不要在这里删除原始包。
- 交互入口（`Option`）从 `main.py` 汇总，新增入口沿用 `check_func` 先检查外部工具（`check_flac_exec`、`check_oggenc_exec`、`check_ffmpeg_exec`）。

## 坑

- 目标作品目录要求“不存在”（首次打包）或“是既有作品目录”（更新包），检查函数会拦截反例，直接调用函数则不做校验。
- HQ 转换只处理传入目录的顶层文件；调用方（如大包生成器）需要对子目录逐层调用。
- LQ 转换会改写源目录（删除 FLAC 与 MP4），确认 HQ 包已产出后再执行。
