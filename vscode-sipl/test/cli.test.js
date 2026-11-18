"use strict";

const test = require("node:test");
const assert = require("node:assert");
const path = require("path");
const { execFileSync } = require("child_process");
const { EventEmitter } = require("events");
const { resolveCommand, candidates, resetCache, stateArgs, spanToRange, formatState, formatEvent, runCli, defaultPython } = require("../src/cli");

test("resolveCommand prefers cliPath", () => {
  assert.deepStrictEqual(resolveCommand({ cliPath: "C:/tools/sipl.exe" }, "win32"), ["C:/tools/sipl.exe", []]);
  assert.deepStrictEqual(resolveCommand({ pythonPath: "" }, "win32"), ["py", ["-3", "-m", "sipl"]]);
  assert.deepStrictEqual(resolveCommand({ pythonPath: "" }, "linux"), ["python3", ["-m", "sipl"]]);
  assert.deepStrictEqual(resolveCommand({ pythonPath: "/venv/bin/python" }, "linux"), ["/venv/bin/python", ["-m", "sipl"]]);
});

test("stateArgs parses and validates", () => {
  assert.deepStrictEqual(stateArgs("X=5, Y=-2"), ["-s", "X=5", "-s", "Y=-2"]);
  assert.deepStrictEqual(stateArgs(""), []);
  assert.throws(() => stateArgs("X=a"), /Bad state item/);
  assert.throws(() => stateArgs("1X=1"), /Bad state item/);
});

test("spanToRange converts to zero-based and never returns empty range", () => {
  assert.deepStrictEqual(spanToRange({ line: 3, column: 1, end_line: 3, end_column: 4 }), {
    line: 2, col: 0, endLine: 2, endCol: 3,
  });
  assert.deepStrictEqual(spanToRange({ line: 2, column: 5, end_line: 2, end_column: 5 }), {
    line: 1, col: 4, endLine: 1, endCol: 5,
  });
});

test("formatting helpers", () => {
  assert.strictEqual(formatState({ X: 5, Y: 2 }), "[X ↦ 5, Y ↦ 2]");
  const line = formatEvent({ kind: "assign", step: 1, span: { line: 2, column: 3 }, variable: "R", old: null, new: 1 });
  assert.match(line, /R: ⊥ -> 1/);
  assert.match(formatEvent({ kind: "condition", step: 2, construct: "while", value: true, iteration: 0 }), /while -> true \(iteration 0\)/);
});

function findPython() {
  for (const candidate of [process.env.SIPL_PYTHON, defaultPython(), "python"]) {
    if (!candidate) {
      continue;
    }
    try {
      execFileSync(candidate, ["-c", "import sipl"], { stdio: "ignore" });
      return candidate;
    } catch (_) {
      // try next
    }
  }
  return null;
}

const python = findPython();

test("integration: check and run through the real CLI", { skip: python ? false : "sipl is not installed" }, async () => {
  const cfg = { pythonPath: python };
  const cwd = path.join(__dirname, "..");
  const ok = await runCli(cfg, ["check"], "begin X := 1 end", { cwd });
  assert.strictEqual(ok.code, 0);
  assert.strictEqual(ok.json.ok, true);

  const bad = await runCli(cfg, ["check"], "begin\n  X := 1;\nend", { cwd });
  assert.strictEqual(bad.code, 1);
  assert.strictEqual(bad.json.diagnostics[0].span.line, 3);

  const run = await runCli(cfg, ["run", "-s", "X=5", "-s", "Y=2"],
    "begin R := 1; while Y > 0 do begin R := R * X; Y := Y - 1 end end", { cwd });
  assert.strictEqual(run.json.state.R, 25);
});

test("missing interpreter gives a helpful error", async () => {
  await assert.rejects(
    runCli({ cliPath: "definitely-not-a-real-sipl-binary" }, ["check"], "begin skip end"),
    /Cannot run sipl/
  );
});

test("candidates: fallback list only when nothing is configured", () => {
  assert.deepStrictEqual(candidates({}, "win32").map((c) => c[0]), ["py", "python", "python3", "sipl"]);
  assert.deepStrictEqual(candidates({}, "linux").map((c) => c[0]), ["python3", "python", "sipl"]);
  assert.strictEqual(candidates({ pythonPath: "C:/py/python.exe" }, "win32").length, 1);
});

// fake child process: behaviour[command] = {code, stdout, stderr} or "ENOENT"
function fakeSpawn(behaviour, calls) {
  return (command) => {
    calls.push(command);
    const child = new EventEmitter();
    child.stdout = new EventEmitter();
    child.stderr = new EventEmitter();
    child.stdout.setEncoding = () => {};
    child.stderr.setEncoding = () => {};
    child.stdin = new EventEmitter();
    child.stdin.end = () => {
      setImmediate(() => {
        const b = behaviour[command];
        if (b === undefined || b === "ENOENT") {
          const err = new Error("spawn " + command + " ENOENT");
          err.code = "ENOENT";
          child.emit("error", err);
          return;
        }
        if (b.stdout) child.stdout.emit("data", b.stdout);
        if (b.stderr) child.stderr.emit("data", b.stderr);
        child.emit("close", b.code);
      });
    };
    return child;
  };
}

const okJson = JSON.stringify({ ok: true, diagnostics: [] });
const storeStub = { code: 9009, stderr: "Python was not found; run without arguments to install from the Microsoft Store" };

test("runCli skips the Microsoft Store stub and remembers the working command", async () => {
  resetCache();
  const calls = [];
  const spawnFn = fakeSpawn({ py: "ENOENT", python: storeStub, python3: { code: 0, stdout: okJson } }, calls);
  const res = await runCli({}, ["check"], "begin skip end", { platform: "win32", spawn: spawnFn });
  assert.strictEqual(res.json.ok, true);
  assert.deepStrictEqual(calls, ["py", "python", "python3"]);

  calls.length = 0;
  await runCli({}, ["check"], "begin skip end", { platform: "win32", spawn: spawnFn });
  assert.deepStrictEqual(calls, ["python3"]);
  resetCache();
});

test("runCli skips an interpreter without sipl-kit", async () => {
  resetCache();
  const calls = [];
  const spawnFn = fakeSpawn({
    python3: { code: 1, stderr: "/usr/bin/python3: No module named sipl" },
    python: { code: 0, stdout: okJson },
  }, calls);
  const res = await runCli({}, ["check"], "begin skip end", { platform: "linux", spawn: spawnFn });
  assert.strictEqual(res.json.ok, true);
  assert.deepStrictEqual(calls, ["python3", "python"]);
  resetCache();
});

test("runCli explains how to fix a missing Python on Windows", async () => {
  resetCache();
  const spawnFn = fakeSpawn({ python: storeStub }, []);
  await assert.rejects(
    runCli({}, ["check"], "begin skip end", { platform: "win32", spawn: spawnFn }),
    (err) => /tried "py", "python", "python3", "sipl"/.test(err.message) &&
      /sipl\.pythonPath/.test(err.message) && /App execution aliases/.test(err.message)
  );
});

test("configured pythonPath is not replaced by fallbacks", async () => {
  resetCache();
  const calls = [];
  const spawnFn = fakeSpawn({ "C:/bad/python.exe": storeStub, py: { code: 0, stdout: okJson } }, calls);
  await assert.rejects(
    runCli({ pythonPath: "C:/bad/python.exe" }, ["check"], "begin skip end", { platform: "win32", spawn: spawnFn }),
    /Check sipl\.pythonPath/
  );
  assert.deepStrictEqual(calls, ["C:/bad/python.exe"]);
});
