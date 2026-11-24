# skfmt

一个面向 Cadence SKILL 源码的保守格式化器。默认做结构重排，但只改变空白与调用括号位置；不改变 token、注释正文或语义。遇到未确认的读取器语法时，整个顶层 form 原样保留。

支持的语法 form 与格式化前后差异见 [docs/supported-forms.md](docs/supported-forms.md)。

## 安装

需要 Python 3.12+ 与 [uv](https://docs.astral.sh/uv/)。

```sh
git clone <repo>
cd skill-formatter
uv tool install .
uv tool list          # 应显示 skfmt
```

发布到 PyPI 后也可以直接临时运行：

```sh
uvx skfmt --version
```

开发环境：

```sh
uv sync --dev
```

## 命令行

```sh
skfmt format file.il                 # 输出到 stdout
skfmt format -w file.il              # 原地写入
skfmt check file.il                  # 只检查，有差异 exit 1
skfmt diff file.il                   # 输出 unified diff
cat file.il | skfmt format           # stdin 过滤模式
skfmt format --lines 10:20 file.il   # 只格式化第 10-20 行
skfmt check src/                     # 递归检查目录下的 *.il / *.ils
skfmt config template > skfmt.toml   # 打印配置模板
```

子命令：

| 子命令 | 说明 |
| --- | --- |
| `format` | 格式化文件或 stdin；默认写到 stdout，`-w` 原地写入 |
| `check` | 报告需要格式化的输入；有差异 exit 1 |
| `diff` | 输出 unified diff；有差异 exit 1 |
| `config` | 打印模板、读取/写入配置值、查看当前生效的配置文件 |

选项（`-w` 仅用于 `format`，其余由三个格式化子命令共用）：

| 选项 | 说明 |
| --- | --- |
| `PATH` | 文件、目录或 `-`（stdin）；目录递归展开为 `*.il` / `*.ils` |
| `-w, --write` | 仅 `format`：原子写入；失败不写任何字节 |
| `--lines A:B` | 只格式化 A:B 行；1 基、含两端、可重复、支持 `A:` / `:B`；片段不完整时保持原样 |
| `--line-width N` | 全局行宽上限；覆盖配置 `format.width`，默认 150 |
| `--base-indent N` | 指定选区片段或最外层 form 的起始缩进 |
| `--stdin-path PATH` | stdin 输入对应的真实文件路径 |
| `--only CATS` / `--skip CATS` | 只启用/跳过分类 |
| `--strict` | 任一警告视为错误 |
| `--best-effort` | 未确认语法使用保守空白布局 |
| `-v, --verbose` | 向 stderr 输出配置来源与每个输入的状态 |

退出码：`0` 成功；`1` check/diff 有差异；`2` 用法、IO、解析/校验失败或 strict 警告。

`stdin` 格式化模式出错时会把输入原字节写回 stdout 并返回 2，保证 `:%!skfmt format` 与编辑器不会丢文本。

`stdin` 读取到 EOF 为止；POSIX 终端用 `Ctrl+D` 结束输入，Windows 控制台通常用 `Ctrl+Z`，或改用管道/重定向输入。

`Ctrl+C` 视为中止：返回 130，不写文件，也不输出部分格式化结果。

帮助信息支持中文/英文：按 `SKFMT_LANG`、`LC_ALL`、`LC_MESSAGES`、`LANGUAGE`、`LANG` 与系统默认语言自动选择；也可用互斥的 `--zh` / `--en` 强制指定。它们可写在子命令前后，例如 `skfmt --zh check` 与 `skfmt check --zh` 等价。这两个开关只影响帮助、警告与诊断，不改变格式化结果。

帮助只介绍工具用途、子命令与选项；退出码、语言检测和实现取舍等细节留在本文档。

## 版本与兼容性

- CLI 用 `skfmt --version` 输出 `skfmt 0.1.0`。
- VS Code 扩展与 Vim 插件在格式化前运行 `skfmt --version`，当前要求 `>= 0.1.0`；版本过低或无法解析时拒绝格式化并提示升级。
- 升级 CLI：`uv tool install --force .`。VS Code 需重载窗口；Vim 执行 `:SkfmtRefresh`。
- 发布前版本保持 `0.1.0`。开始发布后，工具行为或特性有变化时同步提升版本号，并同步更新编辑器插件的最低要求。

`config` 子命令：

| 子命令 | 说明 |
| --- | --- |
| `template` | 打印带注释的 `skfmt.toml` 模板 |
| `get KEY` | 打印 `KEY` 的生效值；没有配置文件时取默认值 |
| `set KEY VALUE` | 写入发现到的配置文件；没有时在当前目录创建 `skfmt.toml` |
| `trace` | 打印当前生效的配置文件；没有时输出为空 |

## 格式分类

默认全部开启：

| 分类 | 作用 |
| --- | --- |
| `eol` | LF、去行尾空白、结尾换行 |
| `blank-lines` | 连续空行压成一个 |
| `indent` | 4 空格结构缩进 |
| `spacing` | 行内单空格、尾注释前两空格 |
| `wrapping` | 结构重排与折行 |
| `comments` | 独立注释重排缩进 |

`--skip wrapping` 进入保守模式：保留原换行位置，只做缩进、空白、注释、空行与行尾归一。关闭 `indent`、`spacing` 或 `comments` 也会关闭 `wrapping`，并输出警告。

`--lines` 需要结构重排，因此与关闭 `wrapping` 的组合会直接报错，不会静默忽略。

`safety.unknown = "conservative"` 只适用于整文件格式化；与 `--lines` 组合且遇到未确认语法时会报错。

顶层函数/类定义（`procedure`、`defmacro`、`defmethod`、`defclass`）之间固定保留两个空行；紧贴下一个定义的注释随该定义移动。

## 配置

从当前目录（或 `--stdin-path` 所在目录）向上查找 `skfmt.toml`，也可用 `--config` 指定：

```toml
[format]
width = 150
indent = 4
base_indent = 0

[categories]
eol = true
blank-lines = true
indent = true
spacing = true
wrapping = true
comments = true

[safety]
unknown = "opaque"        # opaque | error | conservative（保守空白布局）

[rules]
inScheme = "flat"         # flat | indent
case = "align"            # align | block
hanging = ["let", "letseq", "letrec", "prog", "case", "if", "when", "unless", "while", "foreach", "for", "quote"]
```

`wrapping` 需要 `indent`、`spacing` 与 `comments`；显式关闭其中任一分类会关闭 `wrapping`。`comments` 需要 `indent`。

`rules.hanging` 控制调用/特殊 form 的首参数是否留在头行；`procedure`、`lambda`、`defclass` 等定义的签名固定留在头行。

配置命令：

```sh
skfmt config template > skfmt.toml          # 英文注释
skfmt --zh config template > skfmt.toml     # 中文注释
skfmt config get format.width               # 读取生效值
skfmt config set format.width 100           # 写入当前配置
skfmt config set categories.wrapping false
skfmt config set format.base_indent unset   # 删除该键，恢复默认行为
skfmt config trace                          # 查看生效文件
```

键名使用点号形式：`format.width`、`format.indent`、`format.base_indent`、`categories.<名称>`、`safety.unknown`、`rules.inScheme`、`rules.case`、`rules.hanging`。

`template` 只打印到 stdout，不写文件；`set` 才会写入文件。`get` / `set` / `trace` 可用 `--config PATH` 指定目标（写在子命令之后），写入前会重新解析校验，非法值不会落盘。模板注释语言随 `--zh` / `--en` 选择。

## 编辑器

### VS Code

扩展位于 `editors/vscode/`，声明 `skill` 语言并注册文档/选区格式化器；不自动关联 `.il`/`.ils`，也不设置默认 formatter。

VS Code 自带的 `Shift+Alt+F` 是 Format Document，会格式化整个文件；Format Selection 的标准快捷键是 `Ctrl+K Ctrl+F`（macOS `Cmd+K Cmd+F`）。为方便操作，扩展对 `skill` 语言增加了限定：有选区时 `Shift+Alt+F` 自动执行 Format Selection，只格式化选中行；其他语言仍使用标准规则，或自行在 `keybindings.json` 中绑定 `skfmt.formatSelection`。扩展不占用 `Ctrl+Shift+F`。

格式化器对所有语言开放，用户自己指定哪些语言使用本插件，例如在 `settings.json` 中：

```json
"[skill]": {
  "editor.defaultFormatter": "YEUNGCHIE.skfmt"
}
```

扩展 ID 由 `publisher.name` 组成，因此配置值写作 `YEUNGCHIE.skfmt`。

其他语言同理，把 `[skill]` 换成目标语言的 id 即可；也可以在 Format Document With... 中选择 `SKILL Formatter`。若希望 `.il`/`.ils` 自动识别为 `skill`，由用户自行配置：

```json
"files.associations": {
  "*.il": "skill",
  "*.ils": "skill"
}
```

Format Selection 只格式化选中的完整行，不会扩展到外层 form；选区按自身最小缩进作为起始缩进，选区外文本逐字保留。片段不完整或离开上下文后结构不成立时保持原样，并在输出面板输出提示。`skfmt.enableRangeFormatting` 为 `false` 时不注册选区格式化，命令面板中的 Format Selection 也会提示已禁用。

扩展设置：

| 设置 | 作用 |
| --- | --- |
| `skfmt.executablePath` | `skfmt` 可执行文件路径 |
| `skfmt.configPath` | 指定 `skfmt.toml`；留空则自动查找 |
| `skfmt.extraArgs` | 追加给 `skfmt format` 的参数 |
| `skfmt.timeoutMs` | 单次格式化超时（毫秒） |
| `skfmt.enableRangeFormatting` | 是否启用 Format Selection |

```sh
cd editors/vscode
npm install
npm run compile
npm run package
code --install-extension skfmt-0.1.0.vsix
```

扩展通过 PATH 上的 `skfmt` 工作；可在设置中改 `skfmt.executablePath`。

扩展只负责调用 CLI；升级插件或本仓库后，务必同步更新已安装的 CLI，否则 VS Code 仍会调用旧版 `skfmt`：

```sh
cd skill-formatter
uv tool install --force .
```

选区格式化还会校验实际改动范围；若 CLI 试图修改选区外文本，扩展会拒绝本次编辑并在输出面板说明。

### Vim（7.4+）

插件位于 `editors/vim/`。完整安装、配置与排错见 [editors/vim/README.md](editors/vim/README.md)。

先安装 CLI：

```sh
cd skill-formatter
uv tool install .
skfmt --version
```

Vim 7.4 手动安装（Unix 示例；Windows 把 `~/.vim` 换成 `~/vimfiles`）：

```sh
mkdir -p ~/.vim
cp -R /path/to/skill-formatter/editors/vim/* ~/.vim/
vim -Nu NONE -c 'helptags ~/.vim/doc' -c 'q'
```

复制后打开 `.il` 文件，验证：

```vim
:set filetype?              " skill
:echo executable('skfmt')   " 1
:command Skfmt              " 存在
:help skfmt
```

`skfmt` 不在 PATH 时，在 `.vimrc` 中设置 `g:skfmt_executable`；追加参数用 `g:skfmt_args`。修改后执行 `:SkfmtRefresh`。

```vim
:Skfmt                    " 格式化整个缓冲区
:'<,'>SkfmtRange          " 只格式化选区行（片段模式）
:%!skfmt format           " 原生过滤：整文件
:'<,'>!skfmt format       " 原生过滤：选区（片段模式）
```

`ftplugin` 在 `skfmt` 可执行时设置 `formatprg`，可用 `gq`。插件不使用 Vim 8+ 的 `systemlist`、job、timer、JSON 等特性。

## 安全模型

- 原子边界不可变：`a->b`、`1:2`、`x=1`、`x<3>` 等不会被拆开或合并。
- 只调整空白与 C/S 调用括号位置；不把 `if` 改 `when`、不把 `strcat` 改 `lsprintf`。
- 写入前重新解析输出，比较规范化 AST 与注释；不一致立即退出且不写文件。
- 未确认语法、运算符头列表、非符号头、块注释、竖线符号、位域、未知 `#` 前缀等：默认 `opaque` 下含它的顶层 form 原样保留；`conservative` 下整份输入改用保守空白布局。

## 开发

```sh
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv run ty check src tests
```

VS Code：

```sh
cd editors/vscode
npm run compile
npm test
```

Vim：

```sh
vim -Nu NONE -es -S tests/editors/vim_test.vim
python tests/editors/check_vim74.py
```

## 许可证

MIT
