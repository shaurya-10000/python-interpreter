def f(a, b=2, c=3):
    return a * 100 + b * 10 + c
print(f(1))
print(f(1, b=5))
print(f(1, c=9))
print(f(c=1, a=2, b=3))
def greet(name, greeting="Hello"):
    return greeting + ", " + name
print(greet("Al", greeting="Hi"))
print(greet(greeting="Yo", name="Bo"))
class P:
    def __init__(self, x, y=0):
        self.x = x
        self.y = y
    def add(self, k=1):
        return self.x + self.y + k
p = P(1, y=5)
print(p.add())
print(p.add(k=10))
count = 0
def bump():
    global count
    count = count + 1
bump()
bump()
print(count)
def local_only():
    count = 99
local_only()
print(count)
