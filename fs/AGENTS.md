# fs/ — 文件系统操作层

## 定位

提供目录命名、文件移动、软同步与压缩包解压的基础能力；所有函数都可在无交互环境下调用，供 `options` 与 `scripts` 编排。

## 结构

| 文件 | 职责 |
| --- | --- |
| `name.py` | 文件名合法化（全角化特殊字符）与作品目录名生成 |
| `move.py` | `move_elements_across_dir` 与替换策略（`ReplaceOptions`） |
| `sync.py` | 软同步 `sync_folder` 与预设 `SoftSyncPreset` |
| `rawpack.py` | 压缩包解压到缓存目录、编号文件识别、缓存目录整理 |
| `__init__.py` | 空目录清理 `remove_empty_folder`、目录内容相似度 `bms_dir_similarity` |

## 约定

- 目录命名统一走 `get_valid_fs_name`：`：＼／＊？＂＜＞｜` 等特殊字符换全角；编号前缀由调用方给出（`get_work_folder_name`）。
- 移动一律走 `move_elements_across_dir`；覆盖同名文件的语义由 `ReplaceOptions` 决定，更新包场景使用 `REPLACE_OPTION_UPDATE_PACK`。同名不同内容且不覆盖时写入 `xxx.0.ext`、`xxx.1.ext` 形式的新名。
- 解压按后缀分发：`.zip`（`zipfile`，含 CP932/CP437 文件名修复）、`.7z`（`py7zr`）、`.rar`（`rarfile`），其余扩展名按裸文件搬运；调用方保证文件名形如 `<编号> <原名>`，`get_num_set_file_names` 只认数字前缀。
- 软同步预设语义见 `SoftSyncPreset` 字段：`command` 决定 `NONE`（只校验与删除源中相同的文件）、`COPY`、`MOVE`；`remove_dst_extra_files` 控制是否清理目标多余文件，更新包预设为 `False`。
- 共享阈值 `SIMILARITY_CONTENT_TRIGGER` 定义在 `fs/__init__.py`，同名目录合并（`options/bms_folder.py`）与两道闸门匹配（`options/bms_folder_bigpack.py`）都引用它。

## 坑

- `move_out_files_in_folder_in_cache_dir` 处理解压缓存：单层目录或“一个目录 + 若干文件”会自动摊平；多个目录且不含谱面时报错返回 `False`，需要人工处理。
- 嵌套压缩包（整包内还有一层作品压缩包）不会自动再解，由调用方决定是否展开。
- `__MACOSX` 目录与 0 字节媒体文件在缓存整理阶段被清理；其余 0 字节文件保留。
- 并发移动用预占位（`new_dst_path.touch()`）避免撞名，目标目录必须可写。
