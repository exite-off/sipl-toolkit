# SIPL grammar

The machine readable grammar is [`src/sipl/grammar/sipl.lark`](../src/sipl/grammar/sipl.lark)
(Lark EBNF, LALR(1)). It lives inside the package so that `pip install sipl-kit` ships it;
this folder only describes it. The full language reference is in [docs/language.md](../docs/language.md).

Positive and negative test programs: [`tests/grammar/valid`](../tests/grammar/valid) (14 files)
and [`tests/grammar/invalid`](../tests/grammar/invalid) (15 files), checked by `tests/test_grammar.py`.

Course BNF (practical work 1) and the rules of `sipl.lark` that implement it:

| BNF rule | Course name | Lark rule |
|---|---|---|
| `P ::= begin S end` | P1 | `program` |
| `S ::= x := a` | S1 | `assign` |
| `S ::= S1 ; S2` | S2 | `seq` |
| `S ::= if b then S1 else S2` | S3 | `if_stmt` |
| `S ::= while b do S` | S4 | `while_stmt` |
| `S ::= begin S end` | S5 | `block` |
| `S ::= skip` | S6 | `skip` |
| `a ::= n \| x` | A1, A2 | `num`, `var` |
| `a ::= a1 + a2 \| a1 - a2 \| a1 * a2` | A3-A5 | `aexp`, `term` (`binop`) |
| `a ::= (a)` | A6 | `factor` |
| `b ::= a1 = a2 \| a1 > a2` | B1, B2 | `batom` (`compare`) |
| `b ::= b1 ∨ b2` | B3 | `bexp` (`or_`) |
| `b ::= ¬ b` | B4 | `bterm` (`not_`) |
| `b ::= (b)` | B5 | `batom` |
