# PySubset Interpreter

A custom interpreter for a subset of Python, built entirely from scratch in Python 3.
No external dependencies, no `ast` module, no `eval()`. Just pure lexing, parsing, and tree-walking evaluation.

## Features

- **Lexer**: Handles indentation (INDENT/DEDENT tokens), comments, strings, and operators.
- **Parser**: Recursive descent parser with proper operator precedence.
- **Interpreter**: Tree-walking evaluator with scoping via `Environment` chains.
- **Control Flow**: `if`/`elif`/`else`, `while`, `for`, `break`, `continue`.
- **Functions**: `def`, `return`, recursion, local scoping.
- **Data Structures**: Lists, dictionaries, subscript indexing, attribute access.
- **OOP**: `class`, `__init__`, `self`, instances, attributes, method binding.
- **Exceptions**: `try`, `except as`, `raise`.
- **REPL**: Interactive shell with multi-line block support.

## Usage

Run a file:

    python main.py demo.py

Start the REPL:

    python main.py

## Demo

    class Dog:
        def __init__(self, name):
            self.name = name
        def bark(self):
            print(self.name + " says Woof!")

    my_dog = Dog("Buddy")
    my_dog.bark()

    def fib(n):
        if n <= 1:
            return n
        return fib(n-1) + fib(n-2)

    for i in range(5):
        print(fib(i))
