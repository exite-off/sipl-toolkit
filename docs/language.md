# SIPL language reference (version 1.0 of the grammar)

Source: О.В. Шишацька, А.В. Криволап, А.В. Шишацький. «Теорія програмування. Практикум», 2024,
practical work 1 (BNF of SIPL) and practical work 2 (semantic terms).

## Lexical structure

| Token | Form |
|---|---|
| keywords | `begin end if then else while do skip` and `or not div mod` |
| variable | `[A-Za-z_][A-Za-z0-9_]*`, not a keyword (`beginX`, `orange` are variables) |
| number | `[0-9]+`, a literal may have a leading minus: `-1` (the course allows `... -1 \| 0 \| 1 ...`) |
| operators | `:=  ;  +  -  *  =  >  (  )` |
| disjunction | `or`, `∨`, `\/` |
| negation | `not`, `¬`, `!` |
| whitespace | ignored |
| comments (SIPL+) | `// to end of line` and `/* block */` |

## Syntax

```
P ::= begin S end
S ::= x := a | S1 ; S2 | if b then S1 else S2 | while b do S | begin S end | skip
a ::= n | x | a1 + a2 | a1 - a2 | a1 * a2 | (a)
b ::= a1 = a2 | a1 > a2 | b1 ∨ b2 | ¬ b | (b)
```

The BNF is ambiguous, so the implementation fixes priorities (from weakest to strongest):

1. `;` is the weakest operator. `while b do S1; S2` is `(while b do S1); S2`, exactly as in the
   textbook ("оператор циклу має вищий пріоритет ніж оператор послідовного виконання").
   To put several statements into a loop or branch use `begin ... end`.
   `S1; S2; S3` is grouped to the left, `(S1; S2); S3`; the meaning does not depend on it because `·` is associative.
2. `else` is mandatory, so there is no dangling else problem.
3. In conditions `not` binds tighter than `or`: `not X = 1 or X > 2` is `(¬(X = 1)) ∨ (X > 2)`.
4. In expressions `*` (and `div`, `mod`) bind tighter than `+` and `-`; all binary operators are left associative:
   `1 - 2 - 3` is `(1 - 2) - 3`.

`;` separates statements, it does not terminate them: `begin X := 1; end` is a syntax error.

## SIPL+ extensions

Not part of the course BNF, documented here as an explicit extension:

- `a div b`, `a mod b`: several course variants use them (practical works 1-2, variants 2, 4, 9, 15).
  `div` is floor division, `mod` has the sign of the divisor (`-7 div 2 = -4`, `-7 mod 2 = 1`).
  Division by zero is a runtime error `E202`.
- comments `//` and `/* */`.
- ASCII spellings `or`/`not`, `\/`/`!` for `∨`/`¬`.

A program without these features is a plain SIPL program.

## Semantics used by the interpreter

A state is a finite map from variables to integers, `[X ↦ 5, Y ↦ 2]`. Integers are unbounded.

- `x := a` evaluates `a` in the current state and updates `x` (`st∇[x ↦ a(st)]`).
- reading a variable that has no value is an error `E201`: the naming function `x⇒` is undefined
  on such a state, so the program result is undefined.
- `while` that does not stop has an undefined result. The interpreter detects this only through
  a step limit (default 100000, error `E300`); this is a limit of the tool, not a proof of non-termination.

## Semantic terms

`sem_P`, `sem_S`, `sem_A`, `sem_B` are implemented with the rules of practical work 2
(`NS_Prog`, `NS_Stm_As`, `NS_Stm_Seq`, `NS_Stm_If`, `NS_Stm_Wh`, `NS_Stm_BE`, `NS_Stm_skip`,
`NS_A_Num`, `NS_A_Var`, `NS_A_Add`, `NS_A_Sub`, `NS_A_Mult`, `NS_B_eq`, `NS_B_gr`, `NS_B_or`, `NS_B_neg`),
plus `NS_A_Div`, `NS_A_Mod` for the extension. Parenthesis rules `NS_A_Par`, `NS_B_Par` are applied by the
parser: brackets do not appear in the AST.

Notation: `AS^x(f)` for assignment, `S^n(f, g1, ..., gn)` for superposition, `x⇒` for naming,
`f1 · f2` for sequential execution, `IF(b, f1, f2)`, `WH(b, f)`, `id`.
The brackets from `NS_Stm_BE` are printed only where they group a composition inside another composition.
