// Thin wrapper around the sipl CLI. No vscode imports here, so it can be tested with plain node.
"use strict";

const { spawn } = require("child_process");

function defaultPython(platform = process.platform) {
  return platform === "win32" ? "python" : "python3";
}

// returns [command, baseArgs] for running the CLI
function resolveCommand(config, platform = process.platform) {
  const cliPath = (config.cliPath || "").trim();
  if (cliPath) {
    return [cliPath, []];
  }
  const python = (config.pythonPath || "").trim() || defaultPython(platform);
  return [python, ["-m", "sipl"]];
}

// "X=5, Y=2" -> ["-s", "X=5", "-s", "Y=2"], throws on bad input
function stateArgs(text) {
  const args = [];
  for (const raw of (text || "").split(/[,;\s]+/)) {
    const part = raw.trim();
    if (!part) {
      continue;
    }
    if (!/^[A-Za-z_][A-Za-z0-9_]*=-?\d+$/.test(part)) {
      throw new Error(`Bad state item "${part}", expected NAME=INT`);
    }
    args.push("-s", part);
  }
  return args;
}

// CLI span (1-based, end exclusive) -> zero-based range parts
function spanToRange(span) {
  const line = Math.max((span.line || 1) - 1, 0);
  const col = Math.max((span.column || 1) - 1, 0);
  let endLine = Math.max((span.end_line || span.line || 1) - 1, 0);
  let endCol = Math.max((span.end_column || span.column || 1) - 1, 0);
  if (endLine < line || (endLine === line && endCol <= col)) {
    endLine = line;
    endCol = col + 1;
  }
  return { line, col, endLine, endCol };
}

function formatState(state) {
  const items = Object.entries(state || {}).map(([k, v]) => `${k} ↦ ${v}`);
  return `[${items.join(", ")}]`;
}

function formatEvent(e) {
  const where = e.span ? `${e.span.line}:${e.span.column}` : "-";
  const head = `#${String(e.step).padEnd(4)} ${where.padEnd(7)} ${e.kind.padEnd(17)}`;
  switch (e.kind) {
    case "assign":
      return `${head} ${e.variable}: ${e.old === null ? "⊥" : e.old} -> ${e.new}`;
    case "condition":
      return `${head} ${e.construct} -> ${e.value}` + (e.iteration !== undefined ? ` (iteration ${e.iteration})` : "");
    case "start":
    case "finish":
      return `${head} ${formatState(e.state)}`;
    case "error":
      return `${head} ${e.error.message}`;
    default:
      return `${head} ${e.node || ""}`;
  }
}

// runs the CLI with source on stdin, resolves with {code, json, stderr}
function runCli(config, args, source, options = {}) {
  const [command, base] = resolveCommand(config, options.platform);
  const spawnFn = options.spawn || spawn;
  return new Promise((resolve, reject) => {
    let child;
    try {
      child = spawnFn(command, [...base, ...args, "-", "--json"], {
        cwd: options.cwd,
        env: { ...process.env, PYTHONIOENCODING: "utf-8", PYTHONUTF8: "1" },
      });
    } catch (err) {
      reject(err);
      return;
    }
    let stdout = "";
    let stderr = "";
    child.stdout.setEncoding("utf8");
    child.stderr.setEncoding("utf8");
    child.stdout.on("data", (d) => (stdout += d));
    child.stderr.on("data", (d) => (stderr += d));
    child.on("error", (err) => {
      if (err.code === "ENOENT") {
        reject(new Error(`Cannot start "${command}". Install sipl-kit (pip install sipl-kit) or set sipl.pythonPath / sipl.cliPath.`));
      } else {
        reject(err);
      }
    });
    child.on("close", (code) => {
      let json = null;
      try {
        json = stdout.trim() ? JSON.parse(stdout) : null;
      } catch (_) {
        json = null;
      }
      if (json === null) {
        const hint = /No module named sipl/.test(stderr) ? " Install it with: pip install sipl-kit" : "";
        reject(new Error(`sipl exited with code ${code}: ${stderr.trim() || "no output"}.${hint}`));
        return;
      }
      resolve({ code, json, stderr });
    });
    child.stdin.end(source, "utf8");
  });
}

module.exports = { defaultPython, resolveCommand, stateArgs, spanToRange, formatState, formatEvent, runCli };
