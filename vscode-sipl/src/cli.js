// Thin wrapper around the sipl CLI. No vscode imports here, so it can be tested with plain node.
"use strict";

const { spawn } = require("child_process");

function defaultPython(platform = process.platform) {
  return platform === "win32" ? "python" : "python3";
}

// commands to try in order, each is [command, baseArgs]
function candidates(config, platform = process.platform) {
  const cliPath = (config.cliPath || "").trim();
  if (cliPath) {
    return [[cliPath, []]];
  }
  const python = (config.pythonPath || "").trim();
  if (python) {
    return [[python, ["-m", "sipl"]]];
  }
  if (platform === "win32") {
    // "python" may be the Microsoft Store stub, so the py launcher goes first
    return [["py", ["-3", "-m", "sipl"]], ["python", ["-m", "sipl"]], ["python3", ["-m", "sipl"]], ["sipl", []]];
  }
  return [["python3", ["-m", "sipl"]], ["python", ["-m", "sipl"]], ["sipl", []]];
}

// returns [command, baseArgs] that will be tried first
function resolveCommand(config, platform = process.platform) {
  return candidates(config, platform)[0];
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

// true when the command did not start or is not a working sipl
function isMissing(res) {
  if (res.error) {
    return res.error.code === "ENOENT";
  }
  return (
    res.code === 9009 ||
    /Python was not found/i.test(res.stderr) ||
    /No module named '?sipl'?/.test(res.stderr) ||
    /is not recognized as an internal or external command/i.test(res.stderr)
  );
}

function spawnOnce(command, argv, source, options) {
  const spawnFn = options.spawn || spawn;
  return new Promise((resolve) => {
    let child;
    try {
      child = spawnFn(command, argv, {
        cwd: options.cwd,
        env: { ...process.env, PYTHONIOENCODING: "utf-8", PYTHONUTF8: "1" },
      });
    } catch (error) {
      resolve({ error, stdout: "", stderr: "" });
      return;
    }
    let stdout = "";
    let stderr = "";
    let done = false;
    const finish = (res) => {
      if (!done) {
        done = true;
        resolve(res);
      }
    };
    child.stdout.setEncoding("utf8");
    child.stderr.setEncoding("utf8");
    child.stdout.on("data", (d) => (stdout += d));
    child.stderr.on("data", (d) => (stderr += d));
    child.on("error", (error) => finish({ error, stdout, stderr }));
    child.on("close", (code) => finish({ code, stdout, stderr }));
    child.stdin.on("error", () => {});
    child.stdin.end(source, "utf8");
  });
}

function missingMessage(tried, configured, platform) {
  const list = tried.map((c) => `"${c}"`).join(", ");
  if (configured) {
    return `Cannot run sipl with ${list}. Check sipl.pythonPath / sipl.cliPath and that sipl-kit is installed there (pip install sipl-kit).`;
  }
  let msg = `Python with sipl-kit was not found (tried ${list}). Install it with "pip install sipl-kit" ` +
    "and, if Python is not on PATH, set sipl.pythonPath to the full path of python.exe.";
  if (platform === "win32") {
    msg += " A \"Python was not found\" message comes from the Microsoft Store alias: " +
      "turn it off in Settings > Apps > Advanced app settings > App execution aliases.";
  }
  return msg;
}

// the command that worked last time, so the fallback search runs once
let cached = null;

// runs the CLI with source on stdin, resolves with {code, json, stderr}
async function runCli(config, args, source, options = {}) {
  const platform = options.platform || process.platform;
  let list = candidates(config, platform);
  const configured = list.length === 1;
  if (!configured && cached && cached.platform === platform) {
    list = [cached.command, ...list.filter((c) => c[0] !== cached.command[0])];
  }
  const tried = [];
  for (const [command, base] of list) {
    tried.push(command);
    const res = await spawnOnce(command, [...base, ...args, "-", "--json"], source, options);
    if (res.error && !isMissing(res)) {
      throw res.error;
    }
    if (isMissing(res)) {
      if (cached && cached.command[0] === command) {
        cached = null;
      }
      continue;
    }
    let json = null;
    try {
      json = res.stdout.trim() ? JSON.parse(res.stdout) : null;
    } catch (_) {
      json = null;
    }
    if (json === null) {
      throw new Error(`sipl exited with code ${res.code}: ${res.stderr.trim() || "no output"}`);
    }
    if (!configured) {
      cached = { platform, command: [command, base] };
    }
    return { code: res.code, json, stderr: res.stderr };
  }
  throw new Error(missingMessage(tried, configured, platform));
}

function resetCache() {
  cached = null;
}

module.exports = { defaultPython, candidates, resolveCommand, resetCache, stateArgs, spanToRange, formatState, formatEvent, runCli };
