<div align="center">

# PySubset Interpreter

**A Python interpreter for a subset of Python, built from scratch in pure Python.**
No `ast` module. No `eval()`. Just hand-written lexing, parsing, and tree-walking evaluation.

[![CI](https://github.com/shaurya-10000/python-interpreter/actions/workflows/ci.yml/badge.svg)](https://github.com/shaurya-10000/python-interpreter/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow?style=for-the-badge)](./LICENSE)
[![Python](https://img.shields.io/badge/Python-3.12+-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)

[Quick start](#quick-start) · [Feature matrix](#feature-matrix) · [Architecture](#architecture) · [Benchmarks](#benchmarks) · [Report a bug](https://github.com/shaurya-10000/python-interpreter/issues)

</div>

---

## Contents

- [Overview](#overview)
- [Feature matrix](#feature-matrix)
- [Quick start](#quick-start)
- [The language](#the-language)
- [Architecture](#architecture)
- [Benchmarks](#benchmarks)
- [Comparison with CPython](#comparison-with-cpython)
- [Testing](#testing)
- [Project structure](#project-structure)
- [What I learned](#what-i-learned)
- [Roadmap](#roadmap)
- [License](#license)

---

## Overview

|  |  |
| :--- | :--- |
| **What** | An interpreter for a subset of Python. It runs scripts and drops into an interactive REPL. |
| **Why it's interesting** | It handles Python's whitespace-sensitive grammar (INDENT/DEDENT tokens), classes with inheritance, exception handling, and list comprehensions, all implemented from scratch. |
| **No shortcuts** | The lexer and parser are hand-written. There is no `ast.parse`, `compile()`, or `eval()`. |
| **Stack** | Python 3.12+ (standard library only), GitHub Actions |

## Feature matrix

| Category | Supported |
| :--- | :--- |
| **Lexer** | Indentation (INDENT/DEDENT), comments, strings, multi-character operators |
| **Parser** | Recursive descent with operator precedence (arithmetic, comparison, boolean logic) |
| **Control flow** | `if` / `elif` / `else`, `while`, `for`, `break`, `continue`, `pass` |
| **Functions** | `def`, `return`, recursion, default arguments, `*args` |
| **Data structures** | Lists, dicts, sets, list comprehensions |
| **Indexing** | `x[0]`, `d["key"]`, `x[0] = 5` |
| **OOP** | `class`, `__init__`, `self`, inheritance, `super()` |
| **Magic methods** | `__str__` |
| **Exceptions** | `try`, `except as`, `raise` |
| **Builtins** | `print`, `len`, `range`, `str`, `int`, `float`, `type` |
| **Methods** | String and list methods are delegated to the host Python objects |
| **REPL** | Interactive shell with multi-line block support |
| **CI** | GitHub Actions runs a smoke test on every push and PR |

## Quick start

Requires Python 3.12 or newer.

    git clone https://github.com/shaurya-10000/python-interpreter.git
    cd python-interpreter

Run a script:

    python main.py demo/01_basics.py

Start the REPL:

    python main.py

Multi-line blocks use `...` continuation prompts:

    >>> def add(a, b):
    ...     return a + b
    >>> print(add(5, 5))
    10
    >>> exit()

## The language

### Variables and math

    x = 10
    y = 3.14
    print(x + y)
    print(x // 3)
    print(x ** 2)

### Control flow

    x = 3
    while x > 0:
        print(x)
        x = x - 1

    for i in range(3):
        print("Loop " + str(i))

### Functions

    def greet(name="Guest"):
        print("Hello, " + name)

    greet()
    greet("Alice")

    def sum_all(*nums):
        total = 0
        for n in nums:
            total = total + n
        return total

    print(sum_all(1, 2, 3))

### Data structures

    nums = [1, 2, 3]
    nums.append(4)
    print(nums)

    person = {"name": "Alice", "age": 25}
    person["age"] = 26
    print(person)

### List comprehensions

    nums = [1, 2, 3, 4, 5]
    print([x * 2 for x in nums])
    print([x for x in nums if x % 2 == 0])

### Object-oriented programming

    class Animal:
        def __init__(self, name):
            self.name = name
        def speak(self):
            return self.name + " makes a sound."
        def __str__(self):
            return "Animal: " + self.name

    class Dog(Animal):
        def __init__(self, name, breed):
            super().__init__(name)
            self.breed = breed
        def speak(self):
            return self.name + " barks!"

    dog = Dog("Buddy", "Labrador")
    print(dog.speak())
    print(dog)

### Exceptions

This language uses its own syntax here: `raise` takes a value, and `except as e` binds the message.

    try:
        raise("Something broke!")
    except as e:
        print("Caught: " + e)

## Architecture

    Source Code -> Lexer -> Tokens -> Parser -> AST -> Interpreter -> Output

| File | Responsibility |
| :--- | :--- |
| `tokens.py` | `TokenType` enum and `Token` dataclass |
| `lexer.py` | Converts source text into tokens. Tracks an indent stack for INDENT/DEDENT and ignores newlines inside brackets. |
| `ast_nodes.py` | AST node definitions for expressions and statements |
| `parser.py` | Recursive descent parser that builds the AST from the token stream |
| `environment.py` | Scoped variable store. Environments form a parent chain. |
| `interpreter.py` | Tree-walking evaluator with the class and instance runtime |
| `main.py` | CLI entry point and REPL with multi-line buffering |
| `tests/test_basic.py` | Smoke test run by CI |
| `.github/workflows/ci.yml` | GitHub Actions workflow |

### Design principles

1. **The lexer owns whitespace.** INDENT and DEDENT are emitted by the lexer, so the parser sees explicit block boundaries.
2. **The parser owns precedence.** Precedence is encoded as nested functions (`_or`, `_and`, `_not`, `_comparison`, `_addition`, and so on).
3. **The interpreter owns scoping.** Each environment has a parent pointer and `get` walks up the chain. Function calls create a new environment; `while` and `if` blocks share the enclosing one.
4. **The interpreter is a visitor.** `_eval_statement` and `_eval_expr` dispatch on node type, so a new node means a new case.

## Benchmarks

Benchmark: `fib(25)`.

| Runtime | Time | Relative |
| :--- | :--- | :--- |
| CPython 3.12 | ~8 ms | 1x |
| PySubset Interpreter | ~1,300 ms | ~175x slower |

Reproduce on Windows PowerShell:

    Measure-Command { python benchmark.py }
    Measure-Command { python main.py benchmark.py }

Ideas for future work:

- Compile the AST to bytecode and run it on a stack VM
- Cache variable lookups instead of walking the scope chain
- Constant folding at parse time

## Comparison with CPython

`tests/compare_cpython.py` runs the same programs through CPython and through this interpreter, then compares the printed output. It covers arithmetic, strings, control flow, recursion, default args and `*args`, lists, dicts, sets, comprehensions, classes with inheritance, and exceptions. It also times `fib(25)` on both.

Run it:

    python tests/compare_cpython.py

Programs that use this language's own exception syntax (`raise("msg")` and `except as e`) are run on CPython using the standard equivalent (`raise Exception("msg")` and `except Exception as e`).

### Results

On the included programs, output matches CPython in 15/15 cases.

### Known differences from CPython

- Exception syntax is simplified (see above): there is no `except SomeError as e`, and `e` is the message string.
- nd / or return the correct operand but evaluate both sides (no short-circuiting).
- Only a subset of Python is implemented. See the feature matrix.
## Testing

GitHub Actions runs the smoke test on every push and pull request:

    python main.py tests/test_basic.py

The workflow is defined in `.github/workflows/ci.yml`.

## Project structure

    python-interpreter/
    |-- .github/workflows/ci.yml   GitHub Actions CI
    |-- tests/test_basic.py        CI smoke test
    |-- tokens.py                  TokenType enum and Token dataclass
    |-- lexer.py                   Source to tokens (INDENT/DEDENT)
    |-- ast_nodes.py               AST node dataclasses
    |-- parser.py                  Tokens to AST (recursive descent)
    |-- environment.py             Scoped variable store
    |-- interpreter.py             AST evaluation
    |-- main.py                    CLI entry point and REPL
    |-- benchmark.py               Fibonacci benchmark
    |-- README.md
    |-- LICENSE

## What I learned

- **Lexing is harder than it looks.** The lexer must track an indent stack, emit INDENT/DEDENT tokens, and skip blank lines and comments without breaking indentation state.
- **Parser precedence lives in function ordering.** The difference between `2 + 3 * 4` and `2 * 3 + 4` comes from the order of the recursive descent functions.
- **Scoping is the hidden complexity.** `while` loops must not create a new scope, but function calls must. My early `while` loop froze because each iteration created a fresh environment that never saw the updated counter.
- **Magic methods are lookups, not hooks.** `print(obj)` showed the wrong output because the `print` builtin called Python's raw `print()`. It had to resolve `obj.__str__` first.
- **Exceptions are control flow.** `return`, `break`, and `continue` are implemented as internal exceptions that unwind the call stack.

## Roadmap

- [ ] Tuple literals and unpacking ((1, 2), , b = 1, 2)
- [ ] `import` and modules
- [ ] More magic methods: `__repr__`, `__eq__`, `__add__`, `__len__`
- [ ] Generators (`yield`)
- [ ] Decorators
- [ ] Bytecode VM
- [ ] Error messages with line numbers and source snippets

## License

Released under the MIT license. See [LICENSE](./LICENSE).


