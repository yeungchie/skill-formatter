# SKILL Formatter for VS Code

Thin VS Code client for `skillfmt`. It declares the `skill` language and
registers a document formatter and a range formatter. It does not associate
`.il`/`.ils` automatically and does not set a default formatter.

The formatter is available to every language; configure which languages use it
yourself, for example:

```json
"[skill]": {
  "editor.defaultFormatter": "YEUNGCHIE.skill-formatter"
}
```

Use the standard Format Document and Format Selection commands, or pick
`SKILL Formatter` from Format Document With.... The extension does not
override `Ctrl+Shift+F`.

To make `.il`/`.ils` files open as `skill`, add your own association:

```json
"files.associations": {
  "*.il": "skill",
  "*.ils": "skill"
}
```

The `skillfmt` executable must be on `PATH`, or set
`skillFormatter.executablePath`. Range formatting is implemented by sending
the whole document plus `--lines a:b` to `skillfmt format`. A selection may
cover one form or several top-level forms; formatting expands to the complete
forms it touches, and text outside those forms is preserved byte for byte.

`skillFormatter.enableRangeFormatting` controls whether range formatting is
registered, and changes take effect immediately.

```sh
npm install
npm run compile
npm test
npm run package
```
