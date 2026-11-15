"use strict";

const test = require("node:test");
const assert = require("node:assert");
const path = require("path");
const { execFileSync } = require("child_process");
const { resolveCommand, stateArgs, spanToRange, formatState, formatEvent, runCli, defaultPython } = require("../src/cli");

test("resolveCommand prefers cliPath", () => {
  assert.deepStrictEqual(resolveCommand({ cliPath: "C:/tools/sipl.exe" }, "win32"), ["C:/tools/sipl.exe", []]);
  assert.deepStrictEqual(resolveCommand({ pythonPath: "" }, "win32"), ["python", ["-m", "sipl"]]);
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
    /Cannot start/
  );
});
