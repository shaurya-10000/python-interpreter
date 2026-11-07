# PySubset Interpreter

**A Python interpreter for a subset of Python, built from scratch in Python. No `ast` module, no `eval()`, just lexing, parsing, and tree-walking evaluation.**

![CI](https://github.com/shaurya-10000/python-interpreter/actions/workflows/ci.yml/badge.svg)
![Python](https://img.shields.io/badge/python-3.12+-blue)
![License](https://img.shields.io/badge/license-MIT-green)

---

## Why this project exists

Most "language" projects stop at a calculator. This one implements a real subset of Python: indentation-sensitive syntax, object-oriented programming, inheritance, exception handling, list comprehensions, and more, all in pure Python.

Building it taught me how `if x == 5:` becomes an execution tree, why `__str__` is a method lookup and not a string substitution, and how scoping is implemented with environment chains.

---

## Feature Matrix

| Category | Supported |
|---|---|
| **Lexer** | Indentation (INDENT/DEDENT), comments, strings, operators, multi-char tokens |
| **Parser** | Recursive descent with correct operator precedence |
| **Control Flow** | `if` / `elif` / `else`, `while`, `for`, `break`, `continue`, `pass` |
| **Functions** | `def`, `return`, recursion, default args, `*args` |
| **Data Structures** | Lists, dicts, sets, list comprehensions |
| **Indexing** | `x[0]`, `d["key"]`, `x[0] = 5` |
| **OOP** | `class`, `__init__`, `self`, inheritance, `super()` |
| **Magic Methods** | `__str__` |
| **Exceptions** | `try`, `except as`, `raise` |
| **Builtins** | `print`, `len`, `range`, `str`, `int`, `float`, `type` |
| **REPL** | Interactive shell with multi-line block support |
| **CLI** | `python main.py script.py` |

---

## Quick Demo

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
    print(dog.name)

Output:

    Buddy barks!
    Animal: Buddy
    Buddy

---

## List Comprehensions

    nums = [1, 2, 3, 4, 5]
    print([x * 2 for x in nums])
    print([x for x in nums if x % 2 == 0])
    print([x ** 2 for x in nums])

Output:

    [2, 4, 6, 8, 10]
    [2, 4]
    [1, 4, 9, 16, 25]

---

## Exceptions

    try:
        raise("Something broke!")
    except as e:
        print("Caught: " + e)

---

## Performance

Tree-walking interpreters are slower than compiled runtimes. Benchmark on `fib(25)`:

| Runtime | Time |
|---|---|
| **PySubset Interpreter** | ~1.37 s |
| **CPython 3.12** | ~50 ms |

That is roughly 27x slower than CPython.

Ideas for future work:

- Compile the AST to bytecode and run it on a stack VM (the biggest single speedup)
- Cache variable lookups
- Collapse the operator precedence chain into fewer node types

---

## Usage

Run a file:

    python main.py demo.py

Start the REPL:

    python main.py

Then type code interactively:

    >>> def add(a, b):
    ...     return a + b
    >>> print(add(5, 5))
    10

---

## Architecture

    Source Code -> Lexer -> Tokens -> Parser -> AST -> Interpreter -> Output

| File | Responsibility |
|---|---|
| `tokens.py` | `TokenType` enum and `Token` dataclass |
| `lexer.py` | Converts source to tokens, handling INDENT/DEDENT |
| `ast_nodes.py` | AST node definitions (expressions and statements) |
| `parser.py` | Recursive descent parser |
| `environment.py` | Scoped variable store with a parent chain |
| `interpreter.py` | Tree-walking evaluator with class/instance runtime |
| `main.py` | CLI and REPL entry point |
| `tests/test_basic.py` | CI smoke test |
| `.github/workflows/ci.yml` | GitHub Actions workflow, runs on every push and PR |

---

## Testing

GitHub Actions runs `main.py tests/test_basic.py` on every push and PR.

Run locally:

    python main.py tests/test_basic.py

---

## What I Learned

- **Lexing is harder than it looks.** Python's whitespace-sensitive syntax means the lexer must track an indent stack, emit INDENT/DEDENT tokens, and skip blank lines and comments without breaking indentation state.
- **Parser precedence lives in function ordering.** The difference between `2 + 3 * 4` and `2 * 3 + 4` comes entirely from the order of the recursive descent functions.
- **Scoping is the hidden complexity.** `while` loops must not create a new scope, but function calls must. My early `while` loop froze because each iteration created a fresh environment that never saw the updated variable.
- **Magic methods are functions, not hooks.** When `print(obj)` showed the wrong output, it was because `print` called Python's raw `print()` instead of resolving `obj.__str__` first.

---

## License

MIT
