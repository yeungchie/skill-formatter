# 支持的语法 form 与格式化差异

本文枚举 `skfmt` **当前实际支持识别与格式化**的语法形式，并给出格式化前后的差异。示例均来自 `tests/` 中的回归用例；工具不会对未列出的语法做猜测，遇到未确认结构时保留整个顶层 form 的原字节。

## 读取器基础

| 形式 | 识别 | 格式化行为 |
| --- | --- | --- |
| 原子 `foo`、`?key`、`\@rest`、`1:2`、`x=1`、`x<3>` | 是 | 原子边界不变，只在原子之间调整空白 |
| 字符串 `"..."` | 是 | 原样保留；可跨行，不折断、不改转义 |
| 行注释 `; ...` | 是 | 正文逐字保留；独立注释重排缩进，尾注释前两个空格 |
| 前缀 `'`、`` ` ``、`,`、`,@`、`#.` | 是 | 与后续 form 紧贴，不插空格 |
| 括号 `()`、方括号 `[]`、花括号 `{}` | 是 | 分别按调用/索引/列表与 progn 体处理 |
| CRLF / LF | 是 | 默认输出 LF；`--skip eol` 保留源行尾 |
| 空行 | 是 | 默认连续空行压成一个；`--skip blank-lines` 保留原数量 |

## 调用与表达式

### C 风格调用

输入：

```lisp
foo(a b)
```

输出：

```lisp
foo(a b)
```

能单行放下时保持单行；超宽时参数换行并缩进 4 格。

### S 风格调用

在代码位置，符号开头的括号列表会转成 C 风格：

```lisp
(foo a b)
```

```lisp
foo(a b)
```

已知特殊形式同样转换：

```lisp
(if c then a else b)
```

```lisp
if(c then a else b)
```

以下位置不转换：引号内、反引号模板结构、`let` 绑定表、`cond`/`case` 子句本身、formals、`defclass` slots、普通 C 调用参数内。

### 未知 head

```lisp
(myMacro (a b))
```

```lisp
myMacro((a b))
```

外层按调用转 C；参数内的括号列表保持原样，避免误读未知宏语法。

### 分组中缀表达式

```lisp
!(a && b)
```

```lisp
!(a && b)
```

括号内出现顶层中缀运算符时按“分组表达式”处理，不误判为 S 调用。

### 中缀运算符

支持：`~>`、`->`、`.`、`**`、`*`、`/`、`+`、`-`、`<<`、`>>`、`<`、`>`、`<=`、`>=`、`==`、`!=`、`&`、`~&`、`^`、`~^`、`|`、`~|`、`&&`、`||`、`:`，以及赋值 `=`、`+=`、`-=`、`*=`、`/=`、`**=`、`|=`、`&=`；一元 `++ -- - ! ~`，后缀 `++ --`。

除 `~>`/`->` 外，运算符只在作为空白分隔的独立原子时识别；`1:2`、`x=1` 等紧贴写法整体作为原子保留，不拆分、不合并。

`~>` 与 `->` 是例外：它们识别紧贴写法，并统一输出为紧贴形式：

```lisp
a~>b
a -> b
car(g_edge)->x()
```

```lisp
a~>b
a->b
car(g_edge)->x()
```

右操作数以 `(`、`[`、`{`、字符串或前缀开头，且与 `->`/`~>` 之间没有空白时，仍视为同一个访问表达式，不会拆成两个参数：

```lisp
let(() a->())
let(() a~>())
```

```lisp
let(()
    a->()
)
let(()
    a~>()
)
```

`/`、`*`、`+`、`-` 等紧贴在后一个操作数前的写法也会识别，例如 `remainder(n 3600)/60` → `remainder(n 3600) / 60`。

```lisp
x = a + b * c
```

```lisp
x = a + b * c
```

超宽时在最低优先级运算符前断行，运算符置于续行行首并缩进 4 格。

### 索引

```lisp
_TypeCache[name]
```

```lisp
_TypeCache[name]
```

索引整体保持紧贴，不在 `[`/`]` 内侧插入空格。

### 花括号体

```lisp
errset({ nil ,@l_body } nil)
```

```lisp
errset({
    nil
    ,@l_body
} nil)
```

单行时写 `{ x y }`；多行时 `{` 与 `}` 各占边界，体缩进 4 格。

### `list` 调用

`list` 能单行则单行；超宽换行时**每个元素独占一行**，不做同行填充：

```lisp
list("first long element ..." "second long element ..." "third long element ...")
```

```lisp
list(
    "first long element ..."
    "second long element ..."
    "third long element ..."
)
```

## 特殊形式

### `procedure` / `defmacro` / `defmethod`

```lisp
procedure(foo(a "t")
; doc
a = 1)
```

```lisp
procedure(foo(a "t")
    ; doc
    a = 1
)
```

签名尽量单行；`; -> type` 尾注释留在签名行；体逐 form 一行并缩进 4 格。

### `defclass`

```lisp
defclass(Point () (x(\@initarg x \@initform 0.0) y()))
```

```lisp
defclass(Point () (
    x(
        \@initarg x
        \@initform 0.0
    )
    y()
))
```

槽列表与槽选项均块状缩进；结尾 `))` 对齐 `defclass`。

### `lambda`

```lisp
self->f = lambda((a b "gg")  ; -> t
a = 1)
```

```lisp
self->f = lambda((a b "gg")  ; -> t
    a = 1
)
```

### `inScheme`

```lisp
inScheme(
defmethod(x (self(A))  ; -> t
1
))
```

```lisp
inScheme(
defmethod(x (self(A))  ; -> t
    1
)
)
```

`inScheme` 体默认与 `inScheme` 同列（0 缩进）；配置 `rules.inScheme = "indent"` 可改为缩进 4 格。

### `let` / `letseq` / `letrec` / `prog`

```lisp
let((len i)
len = 1)
```

```lisp
let((len i)
    len = 1
)
```

绑定表能单行则单行，超宽时按首元素悬挂对齐；体逐 form 一行并缩进 4 格。

### `if`（含 `then` / `else`）

```lisp
if(ca == cb
then
i++
j++
else
a = 1)
```

```lisp
if(ca == cb
then
    i++
    j++
else
    a = 1
)
```

`then` / `else` 与 `if` 同列，分支体缩进 4 格。无 `then`/`else` 且能放下时允许单行。

### `when` / `unless` / `while`

```lisp
while(i <= n
i++)
```

```lisp
while(i <= n
    i++
)
```

条件留在首行，体缩进 4 格。

### `foreach` / `for`

```lisp
foreach(item l_items
a = 1)
```

```lisp
foreach(item l_items
    a = 1
)
```

变量与列表留在首行，体缩进 4 格。

### `cond`

```lisp
cond((a (foo b)) (t nil))
```

```lisp
cond(
    (a foo(b))
    (t nil)
)
```

子句逐行；子句本身保持括号列表，测试与体中的调用可转 C。`cond` 不做列对齐。

### `case`

```lisp
case(x
("a" 1)
("bb" 2)
(t 3))
```

```lisp
case(x
    ("a"  1)
    ("bb" 2)
    (t    3)
)
```

所有子句都是“键 + 单个值”且能单行时，按最长键对齐值列；否则块状。配置 `rules.case = "block"` 可关闭对齐。

### `errset`

普通体：

```lisp
errset(
(foo a)
nil)
```

```lisp
errset(
    foo(a)
    nil
)
```

花括号体：

```lisp
errset({ (foo a) (bar b) } nil)
```

```lisp
errset({
    foo(a)
    bar(b)
} nil)
```

### `progn` / `unwindProtect` / `setq`

按普通控制形式处理：首项留在首行，其余体逐行缩进 4 格；能单行且只有一个体时允许单行。

## 注释与空白

### 独立注释与尾注释

```lisp
procedure(foo(a "t")
; doc
a = 1  ; trailing
)
```

```lisp
procedure(foo(a "t")
    ; doc
    a = 1  ; trailing
)
```

注释正文不变；独立注释重排到当前块缩进，尾注释前固定两个空格。

### 函数定义之间

顶层函数/类定义（`procedure`、`defmacro`、`defmethod`、`defclass`）之间保留两个空行：

```lisp
procedure(a()
1)
procedure(b()
2)
```

```lisp
procedure(a()
    1
)


procedure(b()
    2
)
```

紧贴下一个定义的注释视为该定义的一部分，两个空行放在注释之前，注释与定义之间不空行。

### 空行

```lisp
a = 1



b = 2
```

```lisp
a = 1

b = 2
```

默认连续空行压成一个；不主动插入空行。

## 明确不格式化（原样保留）

以下结构当前标记为不支持：默认 `opaque` 下包含它的**整个顶层 form** 按原字节保留，并向 stderr 输出警告；`--strict` 下直接报错；`--best-effort` / `safety.unknown = "conservative"` 下整份输入改用保守空白布局。

| 形式 | 示例 | 原因 |
| --- | --- | --- |
| 运算符头列表/调用 | `(+ a b)`、`+(a b)` | SKILL 中运算符不是可调用函数头 |
| 非符号头列表 | `((lambda ...) a)`、`(1 2)` | 无法确定是数据还是调用 |
| 块注释 | `/* ... */` | 读取器语法未确认 |
| 竖线符号 | `\|quoted symbol\|` | 读取器语法未确认 |
| 位域 | `x<3>` | 与比较运算符存在歧义 |
| 注释阻碍转换 | `(foo ; c` 换行 `a)` | 转换会移动注释 |
| 空格式调用 | `foo (a)` | 与 C 风格调用语义不同 |
| 未知 `#` 前缀、行尾续行 | `#<...`、行尾 `\` | 读取器语法未确认 |
| 未闭合字符串/括号 | — | 直接报错，不产生输出 |

## 保守模式

`--skip wrapping` 关闭结构重排，保留原始换行位置，只做：

- 缩进（按括号深度，4 空格）
- 行内空白归一（`--skip spacing` 保留原间距）
- 注释缩进（`--skip comments` 保留原列）
- 空行归一（`--skip blank-lines` 保留原数量）
- 行尾与结尾换行（`--skip eol` 保留）

该模式适合不想产生大面积 diff 的场景；结构重排仍以默认模式为准。

## 选区格式化

`--lines A:B` 只把选中行当作独立片段格式化，不会扩展到外层 form：

- 选区按完整行处理，`A:` / `:B` 为开放区间；多个选区重叠时合并。
- 片段以自身最小缩进作为起始缩进，避免局部格式化顶到列首；`--base-indent N` 可覆盖。
- 选区外文本逐字保留。
- 片段不完整（括号未闭合、处于多行调用或 `cond` 子句中间）或替换后整体结构不成立时，选中行保持原样并输出警告；不会退化为整文件重排。

## 行宽

默认行宽上限为 150，可通过 `--line-width N` 覆盖，或在 `skfmt.toml` 中设置 `format.width`。行宽是对整行的全局限制（含缩进），只影响结构重排与 `list` 等换行决策，不折断字符串、原子与索引。
