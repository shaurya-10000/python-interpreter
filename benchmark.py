import time
from lexer import Lexer
from parser import Parser
from interpreter import Interpreter
from vm import VM

BENCHMARKS = {
    "fib(25)": """
def fib(n):
    if n <= 1:
        return n
    return fib(n - 1) + fib(n - 2)
fib(25)
""",
    "sum_loop(10000)": """
total = 0
for i in range(10000):
    total += i
""",
    "generators(1000)": """
def gen(n):
    for i in range(n):
        yield i * 2
sum(gen(1000))
""",
}


def bench(label, src):
    ast = Parser(Lexer(src).tokenize()).parse()

    t0 = time.perf_counter()
    exec(compile(src, "<cpython>", "exec"), {})
    cp_ms = (time.perf_counter() - t0) * 1000

    t0 = time.perf_counter()
    Interpreter().run(ast)
    tree_ms = (time.perf_counter() - t0) * 1000

    t0 = time.perf_counter()
    VM().run(ast)
    vm_ms = (time.perf_counter() - t0) * 1000

    print(f"{label:<20s} | CPython: {cp_ms:7.2f} ms | Tree: {tree_ms:8.2f} ms | VM: {vm_ms:8.2f} ms")


if __name__ == "__main__":
    print("=== PySubset Benchmark Suite ===")
    for name, code in BENCHMARKS.items():
        bench(name, code)