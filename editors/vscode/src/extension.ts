import * as vscode from "vscode";
import { type FormatOptions, minimalEdit, runFormatter } from "./format";

const output = vscode.window.createOutputChannel("SKILL Formatter");

function configFor(document: vscode.TextDocument): FormatOptions {
  const config = vscode.workspace.getConfiguration("skillFormatter", document.uri);
  return {
    executable: config.get<string>("executablePath", "skillfmt"),
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

async function formatDocument(
  document: vscode.TextDocument,
  range?: vscode.Range,
): Promise<vscode.TextEdit[]> {
  const options = configFor(document);
  if (range) {
    options.lines = lineRange(range);
  }
  const text = document.getText();
  try {
    const result = await runFormatter(options, text);
    if (result.stderr) {
      output.appendLine(result.stderr.trimEnd());
    }
    if (result.code !== 0) {
      vscode.window.showErrorMessage("skillfmt: formatting failed; document left unchanged");
      return [];
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
      "skillfmt: cannot run executable; install it with `uv tool install skill-formatter`",
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
    const config = vscode.workspace.getConfiguration("skillFormatter");
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
      if (event.affectsConfiguration("skillFormatter.enableRangeFormatting")) {
        registerProviders();
      }
    }),
    vscode.commands.registerCommand("skillFormatter.formatDocument", async () => {
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
    vscode.commands.registerCommand("skillFormatter.formatSelection", async () => {
      const editor = vscode.window.activeTextEditor;
      if (!editor) {
        return;
      }
      const enabled = vscode.workspace
        .getConfiguration("skillFormatter", editor.document.uri)
        .get<boolean>("enableRangeFormatting", true);
      if (!enabled) {
        vscode.window.showInformationMessage(
          "skillfmt: Format Selection is disabled by skillFormatter.enableRangeFormatting",
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
