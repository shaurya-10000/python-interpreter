from itertools import islice
from contextlib import contextmanager


def countdown(n):
    while n > 0:
        yield n
        n -= 1


print(list(countdown(3)))
for v in countdown(2):
    print(v)


def counter():
    print("start")
    yield 1
    print("middle")
    yield 2
    print("end")


g = counter()
print("created")
print(next(g))
print(next(g))
try:
    next(g)
except StopIteration:
    print("stopped")


def fib():
    a, b = 0, 1
    while True:
        yield a
        a, b = b, a + b


print(list(islice(fib(), 10)))
gen = fib()
print([next(gen) for _ in range(6)])


def inner():
    yield 1
    yield 2
    return "inner done"


def outer():
    result = yield from inner()
    print("got", result)
    yield 3


print(list(outer()))


def flatten(items):
    for item in items:
        if isinstance(item, list):
            yield from flatten(item)
        else:
            yield item


print(list(flatten([1, [2, [3, 4]], 5])))


def accumulator():
    total = 0
    while True:
        value = yield total
        if value is None:
            break
        total += value


acc = accumulator()
print(next(acc))
print(acc.send(10))
print(acc.send(5))
try:
    acc.send(None)
except StopIteration:
    print("finished")


def resource():
    try:
        yield 1
        yield 2
    finally:
        print("cleanup")


r = resource()
print(next(r))
r.close()
print("closed")


def guarded():
    try:
        yield 1
    except ValueError:
        print("caught inside")
        yield 99


h = guarded()
print(next(h))
print(h.throw(ValueError("bad")))

lazy = (x * x for x in range(4))
print(next(lazy), next(lazy))
print(list(lazy))
print(sum(x for x in range(5)))


def noisy(n):
    for i in range(n):
        print("produce", i)
        yield i


pipeline = (v * 2 for v in noisy(3))
print("built")
print(next(pipeline))


class Bag:
    def __init__(self, items):
        self.items = items

    def __iter__(self):
        for item in self.items:
            yield item

    def pairs(self):
        for i, item in enumerate(self.items):
            yield i, item


bag = Bag(["a", "b"])
print(list(bag))
print(list(bag.pairs()))
for i, item in bag.pairs():
    print(i, item)


def stepper(n, step=1, *, scale=1):
    for i in range(0, n, step):
        yield i * scale


print(list(stepper(6, step=2, scale=10)))


def naturals():
    n = 0
    while True:
        yield n
        n += 1


for n in naturals():
    if n > 3:
        break
    print(n)
evens = (n for n in naturals() if n % 2 == 0)
print([next(evens) for _ in range(4)])
print(list(zip(range(3), naturals())))
print(list(zip("ab", map(str, [1, 2]))))
print(list(enumerate("ab", 1)))
print(list(filter(None, [0, 1, 2])))


@contextmanager
def tag(name):
    print("<" + name + ">")
    try:
        yield name.upper()
    finally:
        print("</" + name + ">")


with tag("b") as t:
    print("inside", t)

try:
    with tag("i"):
        raise ValueError("boom")
except ValueError as e:
    print("caught", e)


@contextmanager
def quiet():
    try:
        yield
    except ValueError:
        print("swallowed")


with quiet():
    raise ValueError("x")
print("after")
