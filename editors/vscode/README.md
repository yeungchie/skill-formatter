# SKILL Formatter for VS Code

Thin VS Code client for `skillfmt`. It registers the empty `skill` language id
for `.il`/`.ils` files (no syntax highlighting), a document formatter and a
range formatter. Use the standard Format Document and Format Selection
commands; the extension does not override `Ctrl+Shift+F`.

The `skillfmt` executable must be on `PATH`, or set
`skillFormatter.executablePath`. Range formatting is implemented by sending
the whole document plus `--lines a:b` to `skillfmt format`. A selection may
cover one form or several top-level forms; formatting expands to the complete
forms it touches, and text outside those forms is preserved byte for byte.

`skillFormatter.enableRangeFormatting` controls whether range formatting is
registered, and `skillFormatter.languages` controls the language ids served by
the extension. Changes to either setting take effect immediately.

```sh
npm install
npm run compile
npm test
npm run package
```
