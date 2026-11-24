import * as vscode from "vscode";
import {
  CONFIG_SECTION,
  type FormatOptions,
  MIN_CLI_VERSION,
  TOOL_NAME,
  changedSpan,
  containsSpan,
  describeCommand,
  invocationArgs,
  minimalEdit,
  parseVersion,
  resolveCommand,
  runFormatter,
  runCommand,
  versionAtLeast,
} from "./format";

const output = vscode.window.createOutputChannel("SKILL Formatter");
const versionChecks = new Map<string, Promise<string | null>>();

function commandKey(command: string, prefixArgs: string[]): string {
  return [command, ...prefixArgs].join("\0");
}

function cliVersion(
  command: string,
  prefixArgs: string[],
  timeoutMs: number,
): Promise<string | null> {
  const key = commandKey(command, prefixArgs);
  let pending = versionChecks.get(key);
  if (!pending) {
    pending = runCommand(command, [...prefixArgs, "--version"], "", timeoutMs)
      .then((result) => {
        const version = result.code === 0 ? parseVersion(result.stdout) : null;
        if (version === null) {
          versionChecks.delete(key);
        }
        return version;
      })
      .catch(() => {
        versionChecks.delete(key);
        return null;
      });
    versionChecks.set(key, pending);
  }
  return pending;
}

function probeCommand(
  command: string,
  _args: string[],
  timeoutMs: number,
): Promise<boolean> {
  return cliVersion(command, [], timeoutMs).then((version) => version !== null);
}

function configFor(document: vscode.TextDocument): FormatOptions {
  const config = vscode.workspace.getConfiguration(CONFIG_SECTION, document.uri);
  const executable = config.get<string>("executablePath", "").trim();
  return {
    executable: executable || undefined,
    configPath: config.get<string>("configPath", "") || undefined,
    extraArgs: config.get<string[]>("extraArgs", []),
    stdinPath: document.uri.scheme === "file" ? document.uri.fsPath : undefined,
    timeoutMs: config.get<number>("timeoutMs", 10000),
  };
}

function lineRange(range: vscode.Range): string {
  let start = range.start.line + 1;
  let end = range.end.line + 1;
  if (range.end.character === 0 && range.end.line > range.start.line) {
    end -= 1;
  }
  if (end < start) {
    end = start;
  }
  return `${start}:${end}`;
}

function selectionBounds(
  document: vscode.TextDocument,
  range: vscode.Range,
): { start: number; end: number } {
  const endLine =
    range.end.character === 0 && range.end.line > range.start.line
      ? range.end.line - 1
      : range.end.line;
  const start = document.offsetAt(new vscode.Position(range.start.line, 0));
  const end =
    endLine + 1 < document.lineCount
      ? document.offsetAt(new vscode.Position(endLine + 1, 0))
      : document.getText().length;
  return { start, end };
}

async function formatDocument(
  document: vscode.TextDocument,
  range?: vscode.Range,
): Promise<vscode.TextEdit[]> {
  const options = configFor(document);
  const resolved = await resolveCommand(options, (command, args) =>
    probeCommand(command, args, options.timeoutMs),
  );
  if (resolved === null) {
    output.appendLine("skfmt is not installed and neither uvx nor uv is available");
    vscode.window.showErrorMessage(
      `${TOOL_NAME}: not found. Install skfmt, or install uv so the extension can run \`uvx skfmt\`.`,
    );
    return [];
  }
  const command = describeCommand(resolved);
  const version = await cliVersion(resolved.command, resolved.prefixArgs, options.timeoutMs);
  if (version === null) {
    output.appendLine(`cannot determine version: ${command} --version`);
    const hint =
      resolved.source === "uvx" || resolved.source === "uv"
        ? "uvx/uv could not run skfmt; install skfmt locally or ensure PyPI is reachable"
        : "install or update the executable";
    vscode.window.showErrorMessage(
      `${TOOL_NAME}: cannot determine CLI version (${command}); ${hint}`,
    );
    return [];
  }
  if (!versionAtLeast(version, MIN_CLI_VERSION)) {
    output.appendLine(`${command} ${version} is older than required ${MIN_CLI_VERSION}`);
    vscode.window.showErrorMessage(
      `${TOOL_NAME} ${command} ${version} is too old; requires >= ${MIN_CLI_VERSION}. Run: uv tool install --force <repository>`,
    );
    return [];
  }
  if (range) {
    options.lines = lineRange(range);
  }
  const text = document.getText();
  try {
    const result = await runFormatter(resolved, options, text);
    if (result.stderr) {
      output.appendLine(result.stderr.trimEnd());
    }
    if (result.code !== 0) {
      vscode.window.showErrorMessage(`${TOOL_NAME}: formatting failed; document left unchanged`);
      return [];
    }
    if (range) {
      const changed = changedSpan(text, result.stdout);
      const bounds = selectionBounds(document, range);
      if (changed && !containsSpan(bounds, changed)) {
        output.appendLine(
          `command: ${resolved.command} ${invocationArgs(resolved, options).join(" ")}`,
        );
        output.appendLine(
          `${TOOL_NAME} changed text outside lines ${options.lines}; edit refused`,
        );
        vscode.window.showErrorMessage(
          `${TOOL_NAME}: formatter changed text outside the selection; update the executable and retry`,
        );
        return [];
      }
    }
    const edit = minimalEdit(text, result.stdout);
    if (!edit) {
      return [];
    }
    return [
      vscode.TextEdit.replace(
        new vscode.Range(document.positionAt(edit.start), document.positionAt(edit.end)),
        edit.text,
      ),
    ];
  } catch (error) {
    output.appendLine(String(error));
    vscode.window.showErrorMessage(
      `${TOOL_NAME}: cannot run ${command}; install skfmt or ensure \`uvx skfmt\` works`,
    );
    return [];
  }
}

export function activate(context: vscode.ExtensionContext): void {
  let providers: vscode.Disposable[] = [];
  const documentSelector: vscode.DocumentSelector = [
    { scheme: "file" },
    { scheme: "untitled" },
  ];

  const registerProviders = (): void => {
    for (const provider of providers) {
      provider.dispose();
    }
    providers = [];
    const config = vscode.workspace.getConfiguration(CONFIG_SECTION);
    const enableRange = config.get<boolean>("enableRangeFormatting", true);
    providers.push(
      vscode.languages.registerDocumentFormattingEditProvider(documentSelector, {
        provideDocumentFormattingEdits: (document) => formatDocument(document),
      }),
    );
    if (enableRange) {
      providers.push(
        vscode.languages.registerDocumentRangeFormattingEditProvider(documentSelector, {
          provideDocumentRangeFormattingEdits: (document, range) =>
            formatDocument(document, range),
        }),
      );
    }
  };

  registerProviders();

  context.subscriptions.push(
    { dispose: () => providers.forEach((provider) => provider.dispose()) },
    vscode.workspace.onDidChangeConfiguration((event) => {
      if (event.affectsConfiguration("skfmt.enableRangeFormatting")) {
        registerProviders();
      }
    }),
    vscode.commands.registerCommand(`${TOOL_NAME}.formatDocument`, async () => {
      const editor = vscode.window.activeTextEditor;
      if (!editor) {
        return;
      }
      const edits = await formatDocument(editor.document);
      if (edits.length) {
        await editor.edit((builder) => {
          for (const edit of edits) {
            builder.replace(edit.range, edit.newText);
          }
        });
      }
    }),
    vscode.commands.registerCommand(`${TOOL_NAME}.formatSelection`, async () => {
      const editor = vscode.window.activeTextEditor;
      if (!editor) {
        return;
      }
      const enabled = vscode.workspace
        .getConfiguration(CONFIG_SECTION, editor.document.uri)
        .get<boolean>("enableRangeFormatting", true);
      if (!enabled) {
        vscode.window.showInformationMessage(
          `${TOOL_NAME}: Format Selection is disabled by ${CONFIG_SECTION}.enableRangeFormatting`,
        );
        return;
      }
      const edits = await formatDocument(editor.document, editor.selection);
      if (edits.length) {
        await editor.edit((builder) => {
          for (const edit of edits) {
            builder.replace(edit.range, edit.newText);
          }
        });
      }
    }),
    output,
  );
}

export function deactivate(): void {}
