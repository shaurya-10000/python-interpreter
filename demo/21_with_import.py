import math
import math as m
from math import sqrt, floor as fl
import json
import io
import itertools
import functools
import random
import string
import re
import statistics
from collections import Counter

print(math.sqrt(16), m.floor(2.5), sqrt(9), fl(-2.5))
print(math.pi)
print(json.dumps({"a": [1, 2], "b": None}))
print(json.loads('{"x": 3}')["x"])
print(list(itertools.chain([1], [2, 3])))
print(functools.reduce(lambda a, b: a + b, [1, 2, 3, 4]))
random.seed(3)
first = random.random()
random.seed(3)
print(first == random.random())
print(string.ascii_lowercase[:3])
print(re.findall("[0-9]+", "a12b345"))
print(re.sub("a+", "-", "caaandaa"))
print(statistics.mean([1, 2, 3, 4]))
counts = Counter("abca")
print(counts["a"], counts.most_common(1))


class Tracker:
    def __init__(self, name, swallow=False):
        self.name = name
        self.swallow = swallow

    def __enter__(self):
        print("enter", self.name)
        return self

    def __exit__(self, exc_type, exc, tb):
        if exc_type is None:
            print("exit", self.name, "clean")
        else:
            print("exit", self.name, exc_type.__name__, exc)
        return self.swallow


with Tracker("a") as t:
    print("inside", t.name)

with Tracker("b") as b1, Tracker("c") as c1:
    print("both", b1.name, c1.name)

with Tracker("d", True):
    raise ValueError("swallowed")
print("after swallow")

try:
    with Tracker("e"):
        raise ValueError("boom")
except ValueError as err:
    print("caught", err)


def early():
    with Tracker("f"):
        return "returned"


print(early())

for i in range(3):
    with Tracker("loop" + str(i)):
        if i == 0:
            continue
        if i == 1:
            break
print("loop done")

try:
    with Tracker("g1") as g1, Tracker("g2", True) as g2:
        raise ValueError("inner")
except ValueError:
    print("not reached")
print("g2 swallowed")

with io.StringIO() as buf:
    buf.write("hello ")
    buf.write("world")
    print(buf.getvalue())

try:
    with 5 as number:
        pass
except TypeError:
    print("not a context manager")
