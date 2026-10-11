# bms-resource-scripts

## 项目定位

BMS 资源整理工具集：交互式菜单脚本与可复用模块，负责 BMS 解析、目录命名、媒体转换与大包生成。`bms-event-bigpack-generator` 以本仓库为 Python 依赖，复用其解压、命名与 HQ 转换流水线，改动公共函数签名会直接影响该生成器。

文档分工：用法见 [README.md](README.md) 与 [README-BOFTT.md](README-BOFTT.md)；各目录的职责、契约与坑见包内 `AGENTS.md`（[bms](bms/AGENTS.md)、[fs](fs/AGENTS.md)、[media](media/AGENTS.md)、[options](options/AGENTS.md)、[scripts](scripts/AGENTS.md)）。

## 模块职责

| 目录 | 职责 |
| --- | --- |
| `bms/` | BMS/BMSON 解析、编码判定、作品名提取、扩展名常量 |
| `fs/` | 目录命名、文件移动、软同步、压缩包解压与缓存目录整理 |
| `media/` | 音频与视频转换预设、批量转换与失败保留语义 |
| `options/` | 交互菜单的选项注册、输入类型与路径检查函数 |
| `scripts/` | 大包流水线入口（原包到 HQ/LQ、更新差分包） |
| `tools/` | 仓库自带检查脚本，pre-commit 与 CI 共用 |
| `wasted/` | 遗留脚本，不参与打包，仅供考古 |

## 命令

### 提交前自动执行（pre-commit hooks）

```bash
pre-commit install   # 同时安装 pre-commit 与 commit-msg 钩子
pre-commit run --all-files
```

| Hook | 作用 | 失败意味着 |
| --- | --- | --- |
| `ruff check` / `ruff format --check` | Lint 与格式 | 运行 `uv run ruff check --fix .` 与 `uv run ruff format .` |
| `ty check` | 类型检查 | 修类型或补注解 |
| `markdownlint` | Markdown 格式 | 按提示修改；豁免需在 `.markdownlint.toml` 写明理由 |
| `cn-quotes` | 中文引号（GB/T 15834-2011） | 改用弯引号 |
| `no-confusable-unicode` | 混淆字符（连字符、窄空格、零宽字符等） | 换成 ASCII 等价字符 |
| `conventional-commit` | 提交信息格式 | 按 Conventional Commits 改写 |

钩子只检查、不改写文件。CI 分 lint、typecheck、docs 三个 job，与钩子同源。

### 手动执行

```bash
uv run main.py              # 交互式菜单
uv run ruff check --fix .   # 自动修复 lint
uv run ty check             # 类型检查
```

## 约定

- 可复用模块（`bms`、`fs`、`media`）不内嵌交互；交互只在 `options` 与 `scripts` 的入口层，结果用返回值或异常表达。
- 破坏性文件操作先验证产物再删除原件；失败时的中间文件一律保留，交由调用方处置。
- 共享常量与阈值在所属模块定义并导出（`CHART_FILE_EXTS`、`MEDIA_FILE_EXTS`、`SIMILARITY_CONTENT_TRIGGER` 等），调用处不重复字面量。
- ruff 复杂度豁免集中登记在 `pyproject.toml` 的 `[tool.ruff.lint.per-file-ignores]`，新增豁免必须写明所属目录与理由。
- 中文全角标点触发的 `RUF001`-`RUF003` 已全局关闭；新增文档与注释使用简体中文弯引号。
- 提交信息遵循 Conventional Commits，scope 用模块名（如 `audio`、`rawpack`、`toolchain`）。

## 诊断注意

- 外部可执行文件（`flac`、`oggenc`、`ffmpeg`）由 `options` 的 `check_*_exec` 在菜单启动时检查，缺失时对应选项不可选；直接调用底层函数不会做该检查。
- `flac` 命令行编码器不支持 32 位浮点 WAV（format type 3）：转换失败、原文件保留，是否接受由调用方决定（大包生成器按警告处理）。
- 解压按后缀分发（`.zip`/`.7z`/`.rar`，其余按裸文件搬运）；带嵌套压缩包的整包（如 Dropbox 文件夹下载）需要调用方自行再解一层。
- 大包相关流水线会改写目标目录：处理成功的原始包被移入 `BOFTTPacks/`，失败保留原地。对实验性操作先用副本验证。
