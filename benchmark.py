# Fibonacci benchmark - test recursion speed
def fib(n):
    if n <= 1:
        return n
    return fib(n - 1) + fib(n - 2)

print("Computing fib(20)...")
print(fib(20))

print("Computing fib(25)...")
print(fib(25))
