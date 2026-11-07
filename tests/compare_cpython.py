import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import io, time, contextlib
from lexer import Lexer
from parser import Parser
from interpreter import Interpreter

# (name, source for PySubset, source for CPython or None if identical)
TESTS = [
    ("arithmetic", 'print(2 + 3 * 4)\nprint(10 // 3)\nprint(2 ** 10)\nprint(7 % 3)\nprint(10 / 4)\n', None),
    ("floats", 'print(3.14 + 1)\nprint(0.1 + 0.2)\n', None),
    ("strings", 'print("a" + "b")\nprint("hi".upper())\nprint(len("hello"))\n', None),
    ("comparisons + booleans", 'print(1 < 2)\nprint(3 == 4)\nprint(not False)\nprint(True and False)\n', None),
    ("if/elif/else", 'x = 7\nif x < 5:\n    print("low")\nelif x < 10:\n    print("mid")\nelse:\n    print("high")\n', None),
    ("while loop", 'x = 3\nwhile x > 0:\n    print(x)\n    x = x - 1\n', None),
    ("for + break/continue", 'for i in range(10):\n    if i == 2:\n        continue\n    if i == 5:\n        break\n    print(i)\n', None),
    ("recursion", 'def fib(n):\n    if n <= 1:\n        return n\n    return fib(n - 1) + fib(n - 2)\nprint(fib(15))\n', None),
    ("default args + *args", 'def g(n="Guest"):\n    print(n)\ng()\ng("Al")\ndef s(*n):\n    t = 0\n    for x in n:\n        t = t + x\n    return t\nprint(s(1, 2, 3))\n', None),
    ("lists + dicts", 'a = [1, 2]\na.append(3)\nprint(a)\nd = {"k": 1}\nd["k"] = 2\nprint(d)\nprint(a[0])\n', None),
    ("sets", 'u = {1, 2, 2, 3}\nprint(len(u))\n', None),
    ("list comprehensions", 'n = [1, 2, 3, 4, 5]\nprint([x * 2 for x in n])\nprint([x for x in n if x % 2 == 0])\nprint([x ** 2 for x in n])\n', None),
    ("classes + inheritance", 'class A:\n    def __init__(self, n):\n        self.n = n\n    def speak(self):\n        return self.n + " makes a sound."\n    def __str__(self):\n        return "Animal: " + self.n\nclass D(A):\n    def __init__(self, n, b):\n        super().__init__(n)\n        self.b = b\n    def speak(self):\n        return self.n + " barks!"\nd = D("Buddy", "Lab")\nprint(d.speak())\nprint(d)\nprint(d.b)\n', None),
    ("try/except/raise",
     'try:\n    raise("boom")\nexcept as e:\n    print("Caught: " + e)\n',
     'try:\n    raise Exception("boom")\nexcept Exception as e:\n    print("Caught: " + str(e))\n'),
    ("and/or return values", 'print(0 or 5)\nprint(3 and 4)\n', None),
]

def run_cpython(src):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        exec(src, {})
    return buf.getvalue()

def run_subset(src):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        Interpreter().run(Parser(Lexer(src).tokenize()).parse())
    return buf.getvalue()

print("=== Output comparison: PySubset vs CPython ===")
passed = 0
for name, sub_src, py_src in TESTS:
    try:
        expected = run_cpython(py_src or sub_src)
        actual = run_subset(sub_src)
    except Exception as e:
        print(f"FAIL  {name}  ({type(e).__name__}: {e})")
        continue
    if expected == actual:
        passed += 1
        print(f"PASS  {name}")
    else:
        print(f"FAIL  {name}")
        print(f"      CPython : {expected!r}")
        print(f"      PySubset: {actual!r}")
print(f"\n{passed}/{len(TESTS)} programs match CPython")

print("\n=== Speed: fib(25) ===")
fib = 'def fib(n):\n    if n <= 1:\n        return n\n    return fib(n - 1) + fib(n - 2)\nx = fib(25)\n'
t = time.perf_counter(); run_cpython(fib); cp = time.perf_counter() - t
t = time.perf_counter(); run_subset(fib); ps = time.perf_counter() - t
print(f"CPython : {cp * 1000:.1f} ms")
print(f"PySubset: {ps * 1000:.1f} ms  ({ps / cp:.1f}x slower)")


if passed != len(TESTS):
    sys.exit(1)
