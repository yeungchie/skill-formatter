# SKILL Formatter for Vim

Vim 7.4+ 的 `skfmt` 格式化插件。插件只调用外部 `skfmt`，自身不解析 SKILL。

## 1. 先安装 skfmt

在 `skill-formatter` 仓库根目录执行：

```sh
uv tool install .
skfmt --version
```

确认 `skfmt` 在 `PATH` 上。若使用其他安装方式，只要 `skfmt` 可执行即可。

## 2. 安装插件

### Vim 7.4：手动复制

Vim 7.4 没有 `:packadd` / package 目录机制，直接把插件目录内容复制到用户运行目录。

Unix（Linux/macOS）：

```sh
mkdir -p ~/.vim
cp -R /path/to/skill-formatter/editors/vim/* ~/.vim/
vim -Nu NONE -c 'helptags ~/.vim/doc' -c 'q'
```

Windows（Git Bash）：

```sh
mkdir -p ~/vimfiles
cp -R /path/to/skill-formatter/editors/vim/* ~/vimfiles/
vim -Nu NONE -c 'helptags ~/vimfiles/doc' -c 'q'
```

把 `/path/to/skill-formatter` 换成实际仓库路径。Windows 上也可以在 Vim 里执行
`:set runtimepath?`，确认哪个用户目录在 `runtimepath` 中，再把文件复制到该目录。

复制后至少应存在：

```text
plugin/skfmt.vim
autoload/skfmt.vim
ftplugin/skill.vim
ftdetect/skill.vim
doc/skfmt.txt
```

### Vim 8+：package

```sh
mkdir -p ~/.vim/pack/plugins/start
ln -s /path/to/skill-formatter/editors/vim ~/.vim/pack/plugins/start/skfmt
vim -Nu NONE -c 'helptags ~/.vim/pack/plugins/start/skfmt/doc' -c 'q'
```

Windows 若不能创建符号链接，改用上面的手动复制。

### Pathogen

```sh
mkdir -p ~/.vim/bundle
ln -s /path/to/skill-formatter/editors/vim ~/.vim/bundle/skfmt
```

### vim-plug

```vim
Plug '/path/to/skill-formatter', {'rtp': 'editors/vim'}
```

然后执行 `:PlugInstall`。

## 3. 验证安装

打开一个 `.il` 文件后执行：

```vim
:set filetype?              " 应显示 filetype=skill
:echo executable('skfmt')   " 应为 1
:command Skfmt              " 应存在
:SkfmtVersion               " 应显示版本与最低要求
:help skfmt                 " 应能打开帮助
```

如果 `filetype` 不是 `skill`，检查 `ftdetect/skill.vim` 是否在运行目录中，或手动执行
`:set filetype=skill`。

## 4. 配置

在 `.vimrc` 中设置：

```vim
let g:skfmt_executable = '/absolute/path/to/skfmt'
let g:skfmt_args = '--line-width 100'
```

- `g:skfmt_executable`：`skfmt` 路径；默认 `"skfmt"`，即从 `PATH` 查找。
- `g:skfmt_args`：追加给 `skfmt format` 的原始 shell 参数，也会进入 `formatprg`。

插件在格式化前运行 `skfmt --version`，当前要求 `>= 0.1.0`；版本过低或无法解析时拒绝格式化。

运行中修改这两个变量后执行：

```vim
:SkfmtRefresh
```

重新生成 `formatprg`。

## 5. 使用

```vim
:Skfmt                     " 格式化整个缓冲区
:'<,'>SkfmtRange           " 只格式化选区行（片段模式）
:gq                        " 使用 formatprg 格式化当前段落/动作范围
:%!skfmt format            " 原生过滤：整文件
:'<,'>!skfmt format        " 原生过滤：选区
```

`SkfmtRange` 只替换选中的完整行，选区外逐字保留；片段不完整或替换后结构不成立时保持原样并输出诊断。

## 6. Vim 7.4 注意事项

- 不支持 `:packadd`、job、timer、`systemlist()` 等 Vim 8+ 特性；插件只用
  `system()`、`tempname()`、`writefile()`、`readfile()` 等 Vim 7.4 可用接口。
- 格式化是同步的，大文件会阻塞编辑器直到 `skfmt` 返回。
- `'encoding'` 建议为 `utf-8`，否则非 ASCII 源码可能显示异常。
- `formatprg` 只在打开文件时检测到 `skfmt` 可执行才设置；之后改路径请执行
  `:SkfmtRefresh`。
- 升级 CLI 后执行 `:SkfmtRefresh` 重新检测版本并生成 `formatprg`。

## 7. 排错

| 现象 | 检查 |
| --- | --- |
| `E492: Not an editor command: Skfmt` | `plugin/skfmt.vim` 不在 `runtimepath`；用 `:set runtimepath?` 检查 |
| `E117: Unknown function: skfmt#FormatAll` | `autoload/skfmt.vim` 未复制或运行目录不对 |
| `skfmt: executable not found` | `:echo executable('skfmt')`；安装 CLI 或设置 `g:skfmt_executable` |
| `skfmt ... is too old` | 用 `uv tool install --force .` 升级，然后 `:SkfmtRefresh` |
| `formatprg` 为空 / `gq` 无效 | 打开文件时 `skfmt` 不在 PATH；设置 `g:skfmt_executable` 后 `:SkfmtRefresh` |
| `:help skfmt` 找不到 | 在 `doc/` 所在目录执行 `:helptags` |
| 中文乱码 | 执行 `:set encoding?`，必要时 `:set encoding=utf-8` |

## 8. 卸载

删除复制到 `~/.vim`（或 `~/vimfiles`）中的：

```text
plugin/skfmt.vim
autoload/skfmt.vim
ftplugin/skill.vim
ftdetect/skill.vim
doc/skfmt.txt
```

如果使用 package/Pathogen/vim-plug，删除对应的 `skfmt` 目录或插件条目即可。
