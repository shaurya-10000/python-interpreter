<div align="center">

# PySubset Interpreter

**A Python interpreter for a subset of Python, built from scratch in pure Python.**
No `ast` module. No `eval()`. Just hand-written lexing, parsing, and tree-walking evaluation.

[![CI](https://github.com/shaurya-10000/python-interpreter/actions/workflows/ci.yml/badge.svg)](https://github.com/shaurya-10000/python-interpreter/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow?style=for-the-badge)](./LICENSE)
[![Python](https://img.shields.io/badge/Python-3.12+-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)

[Quick start](#quick-start) | [Feature matrix](#feature-matrix) | [The language](#the-language) | [Architecture](#architecture) | [Benchmarks](#benchmarks) | [Testing](#testing) | [Roadmap](#roadmap)

</div>

---

## Overview

|  |  |
| :--- | :--- |
| **What** | An interpreter for a subset of Python. Runs scripts and drops into an interactive REPL. |
| **Why it's interesting** | It handles Python's whitespace-sensitive grammar (INDENT/DEDENT tokens), classes with inheritance and `super()`, exception handling, f-strings, list comprehensions, and tuple unpacking, all implemented from scratch. |
| **No shortcuts** | The lexer and parser are hand-written. There is no `ast.parse`, `compile()`, or `eval()`. |
| **Debugging** | Runtime errors include line numbers. Exceptions print a call-stack traceback. |
| **Tested against CPython** | Every demo is executed through both CPython and the interpreter, and stdout must match. |
| **Stack** | Python 3.12+ (standard library only), GitHub Actions |

## Feature matrix

| Category | Supported |
| :--- | :--- |
| **Lexer** | Indentation (INDENT/DEDENT), comments, single- and double-quoted strings, f-string literals, multi-character operators |
| **Parser** | Recursive descent with operator precedence (arithmetic, comparison, boolean logic, unary) |
| **Control flow** | `if` / `elif` / `else`, `while`, `for`, `break`, `continue`, `pass` |
| **Loop else** | `while...else`, `for...else` (else runs when the loop exits without `break`) |
| **Functions** | `def`, `return`, recursion, closures, default arguments, keyword arguments, `*args`, `global` |
| **Data structures** | Lists, dicts, sets, tuple literals, list comprehensions |
| **Unpacking** | `a, b = 1, 2`, `for a, b in pairs`, nested list targets |
| **Indexing** | `x[0]`, `d["key"]`, `x[0] = 5`, slicing `x[1:3]` |
| **Expressions** | augmented assignment (`+=`), `in` / `not in`, `is` / `is not`, ternary, `lambda`, dict comprehensions, chained comparisons |
| **OOP** | `class`, `__init__`, `self`, inheritance, `super()` |
| **Magic methods** | `__str__` |
| **Exceptions** | `try`, `except as`, `raise` |
| **Modern syntax** | f-strings with `{expr}` interpolation, `assert` with optional message |
| **Builtins** | `print`, `len`, `range`, `str`, `int`, `float`, `bool`, `type`, `repr`, `input`, `enumerate`, `zip`, `sum`, `min`, `max`, `abs`, `sorted`, `reversed`, `any`, `all`, `map`, `filter` |
| **Methods** | String and list methods delegate to the host Python objects |
| **Debugging** | Line-numbered runtime errors, call-stack tracebacks on exceptions |
| **REPL** | Interactive shell with multi-line block support |
| **CI** | GitHub Actions runs the smoke test and the CPython comparison on every push and PR |

## Quick start

Requires Python 3.12 or newer.

    git clone https://github.com/shaurya-10000/python-interpreter.git
    cd python-interpreter

Run a demo:

    python main.py demo/01_basics.py

Run the comparison suite against CPython:

    python tests/compare_cpython.py

Start the REPL:

    python main.py

Multi-line blocks use `...` continuation prompts:

    >>> def add(a, b):
    ...     return a + b
    >>> print(add(5, 5))
    10
    >>> exit()

## The language

### Variables and arithmetic

    x = 10
    y = 3.14
    print(x + y)
    print(x // 3)
    print(x ** 2)

### Control flow and loop else

    for i in range(5):
        if i == 3:
            break
        print(i)
    else:
        print("no break")      # not printed, the loop broke

    n = 0
    while n < 3:
        n = n + 1
    else:
        print("clean exit")    # printed

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

### Data structures and unpacking

    nums = [1, 2, 3]
    nums.append(4)
    print(nums)

    a, b = 10, 20
    print(a + b)

    pairs = [(1, 2), (3, 4)]
    for x, y in pairs:
        print(x + y)

    person = {"name": "Alice", "age": 25}
    person["age"] = 26
    print(person)

### List comprehensions

    nums = [1, 2, 3, 4, 5]
    print([x * 2 for x in nums])
    print([x for x in nums if x % 2 == 0])

### f-strings

    name = "Alice"
    age = 30
    print(f"Hello, {name}!")
    print(f"Next year: {age + 1}")
    print(f"Literal braces: {{not interpolated}}")

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

### Exceptions and assert

This language uses its own exception syntax: `raise` takes a value, and `except as e` binds the message.

    try:
        raise("Something broke!")
    except as e:
        print("Caught: " + e)

    assert 1 + 1 == 2
    assert 2 > 1, "math is broken"

### Debugging

Runtime errors report the line number, for example:

    Runtime Error: Name 'foo' is not defined at line 12

Errors raised inside called functions print a call-stack traceback.

## Architecture

    Source Code -> Lexer -> Tokens -> Parser -> AST -> Interpreter -> Output

| File | Responsibility |
| :--- | :--- |
| `tokens.py` | `TokenType` enum and `Token` dataclass |
| `lexer.py` | Converts source text into tokens. Tracks an indent stack for INDENT/DEDENT and ignores newlines inside brackets. Handles f-string literals. |
| `ast_nodes.py` | AST node definitions for expressions and statements, with line numbers on nodes that can appear in runtime errors |
| `parser.py` | Recursive descent parser that builds the AST from the token stream |
| `environment.py` | Scoped variable store. Environments form a parent chain. |
| `interpreter.py` | Tree-walking evaluator, class/instance runtime, call-stack tracking |
| `main.py` | CLI entry point and REPL with multi-line buffering |
| `demo/` | Numbered demo scripts covering each feature area |
| `tests/compare_cpython.py` | Runs each demo through CPython and the interpreter and compares stdout |
| `tests/test_basic.py` | Smoke test run by CI |
| `.github/workflows/ci.yml` | GitHub Actions workflow |

### Design principles

1. **The lexer owns whitespace.** INDENT and DEDENT are emitted by the lexer, so the parser sees explicit block boundaries.
2. **The parser owns precedence.** Precedence is encoded as nested functions (`_or`, `_and`, `_not`, `_comparison`, `_addition`, and so on).
3. **The interpreter owns scoping.** Each environment has a parent pointer and `get` walks up the chain. Function calls create a new environment; `while` and `if` blocks share the enclosing one.
4. **The interpreter is a visitor.** `_eval_statement` and `_eval_expr` dispatch on node type, so a new node means a new case.
5. **Errors carry context.** Expression nodes carry a `line`, and statement evaluation attaches it to errors. The call stack is snapshotted onto the exception before unwinding, so tracebacks can be rendered after the stack is empty.

## Benchmarks

Benchmark: `fib(25)`, timed in-process so Python startup time is excluded.

| Runtime | Time | Relative |
| :--- | :--- | :--- |
| CPython 3.12 | ~7 ms | 1x |
| PySubset Interpreter | ~1,300-1,450 ms | ~175-210x slower |

That gap is expected for a tree-walking interpreter written in Python: it is an interpreter running on top of another interpreter. Timing whole processes (for example with `Measure-Command`) hides the gap, because interpreter startup dominates CPython's run.

Ideas for future work:

- Compile the AST to bytecode and run it on a stack VM (the biggest expected speedup)
- Cache variable lookups instead of walking the scope chain
- Constant folding at parse time

## Testing

The comparison harness is the main test suite. It discovers every file in `demo/`, executes it through CPython and through the interpreter, and requires identical stdout. Demos that use this language's own exception syntax are translated to standard Python for the CPython side.

    python tests/compare_cpython.py

CI runs the smoke test and the comparison on every push and pull request:

    python main.py tests/test_basic.py
    python tests/compare_cpython.py

The workflow is defined in `.github/workflows/ci.yml`.

### Known differences from CPython

- **Exception syntax is simplified.** There is no `except SomeError as e`; the language uses `except as e`, and `e` is the message string. `raise` takes a value, not an exception class.
- **`and` / `or` return the correct operand but evaluate both sides.** There is no short-circuiting.
- **`except Exception as e` is accepted but catches everything.** Exception classes are not matched.
- **Only a subset of Python is implemented.** See the feature matrix.
- **No imports, generators, or decorators** (yet).

## Project structure

    python-interpreter/
    |-- .github/workflows/ci.yml    GitHub Actions CI
    |-- demo/                       Numbered demo scripts (feature coverage)
    |-- tests/
    |   |-- compare_cpython.py      Runs demos on CPython and PySubset, diffs stdout
    |   |-- test_basic.py           CI smoke test
    |-- tokens.py                   TokenType enum and Token dataclass
    |-- lexer.py                    Source to tokens (INDENT/DEDENT, f-strings)
    |-- ast_nodes.py                AST node dataclasses with line numbers
    |-- parser.py                   Tokens to AST (recursive descent)
    |-- environment.py              Scoped variable store
    |-- interpreter.py              AST evaluation and class runtime
    |-- main.py                     CLI entry point and REPL
    |-- benchmark.py                Fibonacci benchmark
    |-- README.md
    |-- LICENSE

## What I learned

- **Lexing is harder than it looks.** The lexer must track an indent stack, emit INDENT/DEDENT tokens, and skip blank lines and comments without breaking indentation state. F-strings add a second lexical mode (string literal vs. interpolated expression).
- **Parser precedence lives in function ordering.** The difference between `2 + 3 * 4` and `2 * 3 + 4` comes from the order of the recursive descent functions.
- **Scoping is the hidden complexity.** `while` loops must not create a new scope, but function calls must. My early `while` loop froze because each iteration created a fresh environment that never saw the updated counter.
- **Magic methods are lookups, not hooks.** `print(obj)` showed the wrong output because the `print` builtin called Python's raw `print()`. It had to resolve `obj.__str__` first.
- **Exceptions are control flow.** `return`, `break`, and `continue` are implemented as internal exceptions that unwind the call stack. A `try` handler must re-raise them, or it silently swallows the return.
- **Tracebacks need a snapshot before unwinding.** The `finally: stack.pop()` runs before the exception reaches the top, so the stack is empty by the time you want to print it. The fix is to attach a snapshot to the exception object.
- **Test against a reference implementation.** Running the same programs through CPython found a real bug (`and` / `or` returned booleans instead of operands) that hand-written expected outputs would not have caught.

## Roadmap

- [ ] Bytecode VM
- [ ] `import` and modules
- [ ] More magic methods: `__repr__`, `__eq__`, `__add__`, `__len__`, `__getitem__`
- [ ] Generators (`yield`)
- [ ] Decorators
- [ ] Short-circuit evaluation for `and` / `or`
- [ ] `try / except SomeError as e` (typed exceptions)
- [ ] Column-level error positions and source-snippet rendering
- [ ] Single-element tuple literal `(x,)`

## License

Released under the MIT license. See [LICENSE](./LICENSE).

