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

The extension name stays `skill-formatter`; VS Code builds the extension id as
`publisher.name`, so the setting value is `YEUNGCHIE.skill-formatter`.

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
the whole document plus `--lines a:b` to `skillfmt format`. Only the selected
lines are replaced; the selection is formatted as a fragment using its own
base indentation. Incomplete fragments are left unchanged with a diagnostic,
and text outside the selected lines is preserved byte for byte.

Before formatting, the extension runs `skillfmt --version` and requires at
least `0.1.0`. If the version is older or cannot be parsed, the edit is
refused with an upgrade message.

Upgrade the installed CLI whenever the formatter or this extension changes:

```sh
cd skill-formatter
uv tool install --force .
```

If the CLI changes text outside the selection, the extension refuses the edit
and reports the command in the output channel.

`skillFormatter.enableRangeFormatting` controls whether range formatting is
registered, and changes take effect immediately.

```sh
npm install
npm run compile
npm test
npm run package
```
