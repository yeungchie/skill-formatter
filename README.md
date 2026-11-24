# skill-formatter

一个面向 Cadence SKILL 源码的保守格式化器。默认做结构重排，但只改变空白与调用括号位置；不改变 token、注释正文或语义。遇到未确认的读取器语法时，整个顶层 form 原样保留。

支持的语法 form 与格式化前后差异见 [docs/supported-forms.md](docs/supported-forms.md)。

## 安装

需要 Python 3.12+ 与 [uv](https://docs.astral.sh/uv/)。

```sh
git clone <repo>
cd skill-formatter
uv tool install .
```

开发环境：

```sh
uv sync --dev
```

## 命令行

```sh
skillfmt file.il                 # 输出到 stdout
skillfmt -w file.il              # 原地写入
skillfmt --check file.il         # 只检查，有差异 exit 1
skillfmt --diff file.il          # 输出 unified diff
cat file.il | skillfmt           # stdin 过滤模式
skillfmt --lines 10:20 file.il   # 只格式化第 10-20 行
```

常用选项：

| 选项 | 说明 |
| --- | --- |
| `-w, --write` | 原子写入；失败不写任何字节 |
| `--check` | 不改文件；有差异 exit 1 |
| `--diff` | 输出 unified diff |
| `--lines A:B` | 1 基、含两端；可重复；支持 `A:` / `:B` |
| `--base-indent N` | 指定第一层起始缩进 |
| `--stdin-path PATH` | stdin 输入对应的真实文件路径 |
| `--only CATS` / `--skip CATS` | 只启用/跳过分类 |
| `--strict` | 任一警告视为错误 |
| `--best-effort` | 未确认语法保留原样（兼容预留） |

退出码：`0` 成功；`1` check/diff 有差异；`2` 用法、IO、解析或校验失败。

`stdin` 格式化模式出错时会把输入原字节写回 stdout 并返回 2，保证 `:%!skillfmt` 与编辑器不会丢文本。

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

`--skip wrapping` 进入保守模式：保留原换行位置，只做缩进、空白、注释、空行与行尾归一。

顶层函数/类定义（`procedure`、`defmacro`、`defmethod`、`defclass`）之间固定保留两个空行；紧贴下一个定义的注释随该定义移动。

## 配置

从当前目录（或 `--stdin-path` 所在目录）向上查找 `skillfmt.toml`，也可用 `--config` 指定：

```toml
[format]
width = 150
indent = 4
base_indent = 0
output_style = "c"        # 目前只支持 "c"

[categories]
eol = true
blank-lines = true
indent = true
spacing = true
wrapping = true
comments = true

[safety]
unknown = "opaque"        # opaque | error | conservative

[rules]
inScheme = "flat"         # flat | indent
case = "align"            # align | block
hanging = ["let", "letseq", "letrec", "quote"]
```

`wrapping=true` 自动要求 `indent` 与 `spacing`；`comments=true` 自动要求 `indent`。

## 编辑器

### VS Code

扩展位于 `editors/vscode/`，注册空语言 id `skill`（`.il`/`.ils`）与格式化器；不提供语法高亮。使用 VS Code 标准 Format Document（Windows/Linux `Shift+Alt+F`）与 Format Selection（`Ctrl+K Ctrl+F`），不占用 `Ctrl+Shift+F`。

```sh
cd editors/vscode
npm install
npm run compile
npm run package
code --install-extension skillfmt-skill-formatter-0.1.0.vsix
```

扩展通过 PATH 上的 `skillfmt` 工作；可在设置中改 `skillFormatter.executablePath`。

### Vim（7.4+）

插件位于 `editors/vim/`，只依赖 PATH 上的 `skillfmt` 与 `encoding=utf-8`。

```vim
:Skillfmt              " 格式化整个缓冲区
:'<,'>SkillfmtRange    " 只格式化选区所在的结构 form
:%!skillfmt            " 原生过滤：整文件
:'<,'>!skillfmt        " 原生过滤：选区（片段模式）
```

`ftplugin` 在 `skillfmt` 可执行时设置 `formatprg=skillfmt`，可用 `gq`。插件不使用 Vim 8+ 的 `systemlist`、job、timer、JSON 等特性。

## 安全模型

- 原子边界不可变：`a->b`、`1:2`、`x=1`、`x<3>` 等不会被拆开或合并。
- 只调整空白与 C/S 调用括号位置；不把 `if` 改 `when`、不把 `strcat` 改 `lsprintf`。
- 写入前重新解析输出，比较规范化 AST 与注释；不一致立即退出且不写文件。
- 未确认语法、运算符头列表、非符号头、块注释、竖线符号、位域、未知 `#` 前缀等：含它的顶层 form 原样保留。

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
