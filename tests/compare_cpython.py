import sys, os, io, time, contextlib, pathlib
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from lexer import Lexer
from parser import Parser
from interpreter import Interpreter

ROOT = pathlib.Path(__file__).resolve().parent.parent

def run_cpython(src):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        exec(compile(src, "<demo>", "exec"), {})
    return buf.getvalue()

def normalize_subset(out):
    """Strip interpreter-only annotations (e.g. ' at line 3') so output
    is comparable to CPython's."""
    import re
    return re.sub(r" at line \d+", "", out)

def run_subset(src):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        Interpreter().run(Parser(Lexer(src).tokenize()).parse())
    return normalize_subset(buf.getvalue())

# Demos whose PySubset syntax differs from CPython get a translation here.
TRANSLATED = {
    "06_exceptions.py": (
        'try:\n    raise Exception("Something broke!")\nexcept Exception as e:\n    print("Caught: " + str(e))\n\n'
        'try:\n    try:\n        raise Exception("inner")\n    except Exception as e:\n        print("inner caught: " + str(e))\n        raise Exception("outer")\n'
        'except Exception as e:\n    print("outer caught: " + str(e))\n\n'
        'try:\n    print("all good")\nexcept Exception as e:\n    print("should not print")\n'
    ),
}

def discover():
    cases = []
    for f in sorted((ROOT / "demo").glob("*.py")):
        sub_src = f.read_text()
        py_src = TRANSLATED.get(f.name, sub_src)
        cases.append((f.name, sub_src, py_src))
    return cases

def main():
    cases = discover()
    print(f"=== Output comparison: PySubset vs CPython ({len(cases)} files) ===")
    passed = 0
    for name, sub_src, py_src in cases:
        try:
            expected = run_cpython(py_src)
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

    print(f"\n{passed}/{len(cases)} files match CPython")

    fib = 'def fib(n):\n    if n <= 1:\n        return n\n    return fib(n - 1) + fib(n - 2)\nx = fib(25)\n'
    print("\n=== Speed: fib(25) ===")
    t = time.perf_counter(); run_cpython(fib); cp = time.perf_counter() - t
    t = time.perf_counter(); run_subset(fib); ps = time.perf_counter() - t
    print(f"CPython : {cp * 1000:.1f} ms")
    print(f"PySubset: {ps * 1000:.1f} ms  ({ps / cp:.1f}x slower)")

    if passed != len(cases):
        sys.exit(1)

if __name__ == "__main__":
    main()
