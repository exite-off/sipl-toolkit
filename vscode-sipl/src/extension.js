// VS Code client for the SIPL toolkit. All language logic lives in the Python package,
// the extension only calls "sipl ... --json" and shows the results.
"use strict";

const vscode = require("vscode");
const path = require("path");
const { stateArgs, spanToRange, formatState, formatEvent, runCli } = require("./cli");

let diagnostics;
let output;
const lastState = new Map();
const pending = new Map();

function config() {
  const c = vscode.workspace.getConfiguration("sipl");
  return {
    pythonPath: c.get("pythonPath", ""),
    cliPath: c.get("cliPath", ""),
    maxSteps: c.get("maxSteps", 100000),
    checkOnType: c.get("checkOnType", true),
  };
}

function toDiagnostic(d) {
  const r = spanToRange(d.span || {});
  const range = new vscode.Range(r.line, r.col, r.endLine, r.endCol);
  const severity = d.severity === "warning" ? vscode.DiagnosticSeverity.Warning : vscode.DiagnosticSeverity.Error;
  const diag = new vscode.Diagnostic(range, d.message, severity);
  diag.source = "sipl";
  diag.code = d.code;
  return diag;
}

function cwdOf(doc) {
  return doc.uri.scheme === "file" ? path.dirname(doc.uri.fsPath) : undefined;
}

function fileLabel(doc) {
  return doc.isUntitled ? doc.fileName : path.basename(doc.fileName);
}

async function check(doc, { quiet = false } = {}) {
  if (doc.languageId !== "sipl") {
    return null;
  }
  try {
    const { json } = await runCli(config(), ["check"], doc.getText(), { cwd: cwdOf(doc) });
    diagnostics.set(doc.uri, json.diagnostics.map(toDiagnostic));
    if (!quiet) {
      if (json.ok) {
        vscode.window.setStatusBarMessage(`$(check) SIPL: ${fileLabel(doc)} is correct`, 4000);
      } else {
        const d = json.diagnostics[0];
        vscode.window.showErrorMessage(`SIPL ${d.span.line}:${d.span.column}: ${d.message}`);
      }
    }
    return json;
  } catch (err) {
    if (!quiet) {
      vscode.window.showErrorMessage(err.message);
    }
    return null;
  }
}

function scheduleCheck(doc) {
  if (doc.languageId !== "sipl" || !config().checkOnType) {
    return;
  }
  clearTimeout(pending.get(doc.uri.toString()));
  pending.set(
    doc.uri.toString(),
    setTimeout(() => check(doc, { quiet: true }), 400)
  );
}

async function askState(doc) {
  const key = doc.uri.toString();
  let suggestion = lastState.get(key);
  if (suggestion === undefined) {
    // first run: suggest all program variables
    const checked = await check(doc, { quiet: true });
    if (checked && checked.ok) {
      suggestion = checked.variables.map((v) => `${v}=0`).join(", ");
    } else {
      suggestion = "";
    }
  }
  const value = await vscode.window.showInputBox({
    title: "SIPL initial state",
    prompt: "Initial values, e.g. X=5, Y=2 (leave empty for the empty state)",
    value: suggestion,
    validateInput: (text) => {
      try {
        stateArgs(text);
        return null;
      } catch (err) {
        return err.message;
      }
    },
  });
  if (value !== undefined) {
    lastState.set(key, value);
  }
  return value;
}

async function execute(withTrace) {
  const editor = vscode.window.activeTextEditor;
  if (!editor || editor.document.languageId !== "sipl") {
    vscode.window.showWarningMessage("Open a .sipl file first");
    return;
  }
  const doc = editor.document;
  const stateText = await askState(doc);
  if (stateText === undefined) {
    return;
  }
  const cfg = config();
  const args = [withTrace ? "trace" : "run", ...stateArgs(stateText), "--max-steps", String(cfg.maxSteps)];
  let res;
  try {
    res = await runCli(cfg, args, doc.getText(), { cwd: cwdOf(doc) });
  } catch (err) {
    vscode.window.showErrorMessage(err.message);
    return;
  }
  const { json } = res;
  diagnostics.set(doc.uri, json.diagnostics.map(toDiagnostic));
  output.clear();
  output.show(true);
  output.appendLine(`${withTrace ? "Trace" : "Run"}: ${fileLabel(doc)}`);
  if (json.initial_state === undefined) {
    // syntax error, nothing was executed
    const d = json.diagnostics[0];
    output.appendLine(`Syntax error at ${d.span.line}:${d.span.column}: ${d.message}`);
    vscode.window.showErrorMessage(`SIPL syntax error at ${d.span.line}:${d.span.column}: ${d.message}`);
    return;
  }
  output.appendLine(`Initial state: ${formatState(json.initial_state)}`);
  output.appendLine("");
  if (withTrace) {
    for (const e of json.trace) {
      output.appendLine(formatEvent(e));
    }
    output.appendLine("");
  }
  if (json.status === "ok") {
    output.appendLine(`Final state:   ${formatState(json.state)}`);
    output.appendLine(`Steps: ${json.steps}`);
  } else {
    const d = json.diagnostics[0];
    output.appendLine(`Error at ${d.span.line}:${d.span.column}: ${d.message} [${d.code}]`);
    output.appendLine(`State at failure: ${formatState(json.state)}`);
    vscode.window.showErrorMessage(`SIPL runtime error at ${d.span.line}:${d.span.column}: ${d.message}`);
  }
}

async function showTerm() {
  const editor = vscode.window.activeTextEditor;
  if (!editor || editor.document.languageId !== "sipl") {
    vscode.window.showWarningMessage("Open a .sipl file first");
    return;
  }
  const doc = editor.document;
  let res;
  try {
    res = await runCli(config(), ["term"], doc.getText(), { cwd: cwdOf(doc) });
  } catch (err) {
    vscode.window.showErrorMessage(err.message);
    return;
  }
  const { json } = res;
  diagnostics.set(doc.uri, json.diagnostics.map(toDiagnostic));
  if (!json.ok) {
    vscode.window.showErrorMessage(`SIPL: ${json.diagnostics[0].message}`);
    return;
  }
  output.clear();
  output.show(true);
  output.appendLine(`Semantic term: ${fileLabel(doc)}`);
  output.appendLine("");
  json.rules.forEach((s, i) => output.appendLine(`${String(i + 1).padStart(3)}. ${s.rule}: ${s.lhs} = ${s.rhs}`));
  output.appendLine("");
  output.appendLine(json.term);
}

function activate(context) {
  diagnostics = vscode.languages.createDiagnosticCollection("sipl");
  output = vscode.window.createOutputChannel("SIPL");
  context.subscriptions.push(
    diagnostics,
    output,
    vscode.commands.registerCommand("sipl.run", () => execute(false)),
    vscode.commands.registerCommand("sipl.trace", () => execute(true)),
    vscode.commands.registerCommand("sipl.term", showTerm),
    vscode.commands.registerCommand("sipl.check", () => {
      const editor = vscode.window.activeTextEditor;
      if (editor) {
        return check(editor.document);
      }
      return undefined;
    }),
    vscode.workspace.onDidOpenTextDocument((doc) => check(doc, { quiet: true })),
    vscode.workspace.onDidSaveTextDocument((doc) => check(doc, { quiet: true })),
    vscode.workspace.onDidChangeTextDocument((e) => scheduleCheck(e.document)),
    vscode.workspace.onDidCloseTextDocument((doc) => diagnostics.delete(doc.uri))
  );
  for (const doc of vscode.workspace.textDocuments) {
    check(doc, { quiet: true });
  }
}

function deactivate() {}

module.exports = { activate, deactivate };
