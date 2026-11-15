"use strict";

// tokenizes example programs with the real TextMate engine used by VS Code
const test = require("node:test");
const assert = require("node:assert");
const fs = require("fs");
const path = require("path");
const vsctm = require("vscode-textmate");
const oniguruma = require("vscode-oniguruma");

const wasm = fs.readFileSync(require.resolve("vscode-oniguruma/release/onig.wasm")).buffer;
const onigLib = oniguruma.loadWASM(wasm).then(() => ({
  createOnigScanner: (patterns) => new oniguruma.OnigScanner(patterns),
  createOnigString: (s) => new oniguruma.OnigString(s),
}));

const registry = new vsctm.Registry({
  onigLib,
  loadGrammar: async (scopeName) => {
    if (scopeName !== "source.sipl") {
      return null;
    }
    const file = path.join(__dirname, "..", "syntaxes", "sipl.tmLanguage.json");
    return vsctm.parseRawGrammar(fs.readFileSync(file, "utf8"), file);
  },
});

async function tokenize(text) {
  const grammar = await registry.loadGrammar("source.sipl");
  const result = [];
  let stack = vsctm.INITIAL;
  for (const line of text.split(/\r?\n/)) {
    const r = grammar.tokenizeLine(line, stack);
    for (const t of r.tokens) {
      const value = line.slice(t.startIndex, t.endIndex);
      if (value.trim()) {
        result.push([value.trim(), t.scopes[t.scopes.length - 1]]);
      }
    }
    stack = r.ruleStack;
  }
  return result;
}

function scopeOf(tokens, value) {
  const found = tokens.find(([v]) => v === value);
  assert.ok(found, `token ${value} not found`);
  return found[1];
}

test("power example is highlighted", async () => {
  const src = fs.readFileSync(path.join(__dirname, "..", "..", "examples", "power.sipl"), "utf8");
  const tokens = await tokenize(src);
  assert.match(scopeOf(tokens, "begin"), /^keyword\.control/);
  assert.match(scopeOf(tokens, "while"), /^keyword\.control/);
  assert.match(scopeOf(tokens, "do"), /^keyword\.control/);
  assert.match(scopeOf(tokens, "R"), /^variable\.other/);
  assert.match(scopeOf(tokens, "1"), /^constant\.numeric/);
  assert.match(scopeOf(tokens, ":="), /^keyword\.operator\.assignment/);
  assert.match(scopeOf(tokens, "*"), /^keyword\.operator\.arithmetic/);
  assert.match(scopeOf(tokens, ">"), /^keyword\.operator\.comparison/);
  assert.match(tokens[0][1], /^comment\.line/);
});

test("conditions, comments and keyword-like names", async () => {
  const tokens = await tokenize("if not X = 1 ∨ beginX > 0 then skip else Q := X mod 2 /* c */");
  assert.match(scopeOf(tokens, "if"), /^keyword\.control/);
  assert.match(scopeOf(tokens, "not"), /^keyword\.operator\.logical/);
  assert.match(scopeOf(tokens, "∨"), /^keyword\.operator\.logical/);
  assert.match(scopeOf(tokens, "beginX"), /^variable\.other/);
  assert.match(scopeOf(tokens, "skip"), /^keyword/);
  assert.match(scopeOf(tokens, "mod"), /^keyword\.operator/);
  assert.match(scopeOf(tokens, "/*"), /^comment\.block/);
});

test("every example file has no unscoped tokens", async () => {
  const dir = path.join(__dirname, "..", "..", "examples");
  for (const name of fs.readdirSync(dir).filter((f) => f.endsWith(".sipl"))) {
    const tokens = await tokenize(fs.readFileSync(path.join(dir, name), "utf8"));
    for (const [value, scope] of tokens) {
      assert.notStrictEqual(scope, "source.sipl", `${name}: "${value}" has no scope`);
    }
  }
});
