# options/ — 交互菜单与检查层

## 定位

交互式菜单的选项注册与执行：收集输入、运行检查函数、确认后调用 `func`。菜单本身是人工工作流的界面，不承载业务逻辑（业务在 `bms`/`fs`/`media`/`scripts`）。

## 结构

| 文件 | 职责 |
| --- | --- |
| `__init__.py` | `InputType`/`Input`/`Option`/`ConfirmType`、路径输入与历史、检查函数（含 `check_*_exec`） |
| `bms_events.py` | 跳转 manbow 作品页 |
| `bms_folder.py` | 目录命名、相似目录扫描、编号目录名同步 |
| `bms_folder_bigpack.py` | 大包目录整理（首字符分组、合并、移动、冗余媒体清理） |
| `bms_folder_event.py` | 活动目录编号检查与信息表导出 |
| `bms_folder_media.py` | 媒体转换菜单入口 |
| `rawpack.py` | 原始包编号与解压到作品目录 |

## 约定

- 每个模块导出 `OPTIONS: list[Option]`，由 `main.py` 汇总编号；新增功能就是新增 `Option`。
- `Option.inputs` 声明参数（类型 + 描述），`check_func` 接收与输入同序的位置参数并返回 `bool`；检查失败由框架打印原因并中止。
- 路径输入统一走 `InputType.Path`：支持历史记录、`?` 查看全部、缺失校验，`allow_missing=True` 表示路径可不存在（后续创建）。
- 外部命令检查按工具拆分（`check_flac_exec`、`check_oggenc_exec`、`check_ffmpeg_exec`），在 `check_func` 列表中先于路径检查执行。
- 交互提示与错误文案用简体中文；引号遵循 GB/T 15834-2011（pre-commit 钩子检查）。

## 坑

- `check_func` 可以传单个函数或列表，框架按 `check(*args)` 调用；检查函数签名必须能接受该选项全部输入。
- 菜单编号按十位分组显示，`main.py` 的编号映射与 `OPTIONS` 顺序耦合，修改顺序会改变用户记忆中的编号。
- 历史路径文件写在包目录（`history.log`），已在 `.gitignore` 中忽略。
- 复杂度豁免（`PLR0912`、`ANN401` 等）登记在 `pyproject.toml`，新增菜单分支不要顺手放宽全局阈值。
