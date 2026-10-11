# bms/ — BMS/BMSON 解析层

## 定位

把 `.bms`/`.bme`/`.bml`/`.pms`/`.bmson` 解析为统一的 `BMSInfo`（标题、艺术家、流派、难度、等级、BMP 格式），并集中定义扩展名常量。上层（`fs`、`media`、`options`、`scripts`）通过本包判定谱面与媒体类型。

## 结构

| 文件 | 职责 |
| --- | --- |
| `parse.py` | BMS/BMSON 解析与 `BMSInfo`、`BMSDifficulty` 定义 |
| `encoding.py` | 编码优先级解码器 `PriorityDecoder`、BOFTT 特例编码表 |
| `work.py` | 从多个标题/艺术家字符串中提取共同作品名 |
| `__init__.py` | 扩展名常量、`get_dir_bms_list` / `get_dir_bms_info` |

## 约定

- 扩展名常量的权威源是 `bms/__init__.py`：`BMS_FILE_EXTS`、`BMSON_FILE_EXTS`、`CHART_FILE_EXTS`、`AUDIO_FILE_EXTS`、`VIDEO_FILE_EXTS`、`IMAGE_FILE_EXTS`、`MEDIA_FILE_EXTS`。其它模块一律导入，不自行拼列表。
- 解析失败不抛异常：返回空 `BMSInfo` 或 `None`，由调用方决定报错策略（`get_dir_bms_info` 返回 `None` 表示未找到可解析文件）。
- 作品名从目录内全部谱面文件提取公共前缀（`extract_work_name`，相似度阈值三分之二），单文件时即该文件标题。
- 编码探测顺序：meta 声明优先，其次 `shift_jis`、`shift_jis_2004`、`euc-jp` 等固定列表；逐字符解码，非法字节按 `errors` 参数处理。
- `#PLAYLEVEL`、`#DIFFICULTY` 的合法范围由 `PLAYLEVEL_MAX`、`DIFFICULTY_MAX` 常量承载，超出视为无效。

## 坑

- 目录名带编号时取 `no` 作为 BOFTT 特例编码表的键；无编号目录用目录名整体作键。
- BMSON 解析依赖 `json`，坏 JSON 只打印并返回 `Error` 占位信息，不中断批量流程。
- `get_dir_bms_info` 只读目录第一层文件；媒体在子目录中的作品（如 `keysounds/`）仍可解析，但命名只依据顶层谱面。
