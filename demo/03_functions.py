# Functions: defaults, *args, recursion, closures

def fib(n):
    if n <= 1:
        return n
    return fib(n - 1) + fib(n - 2)

print(fib(10))

def greet(name="Guest", greeting="Hello"):
    print(greeting + ", " + name)

greet()
greet("Alice")
greet("Bob", "Hi")

def sum_all(*nums):
    total = 0
    for n in nums:
        total = total + n
    return total

print(sum_all(1, 2, 3))
print(sum_all(10, 20, 30, 40))

def make_adder(k):
    def add(x):
        return x + k
    return add

add5 = make_adder(5)
print(add5(10))
