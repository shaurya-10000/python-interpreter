a, *rest = [1, 2, 3, 4]
print(a, rest)
*init, last = [1, 2, 3]
print(init, last)
first, *mid, final = range(5)
print(first, mid, final)
x, y = 1, 2
x, y = y, x
print(x, y)
(p, q), r = (1, 2), 3
print(p, q, r)

def add3(a, b, c):
    return a + b + c
nums = [1, 2, 3]
print(add3(*nums))
opts = {"b": 2, "c": 3}
print(add3(1, **opts))
print(add3(*[1, 2], **{"c": 3}))
print(*nums)
print(*nums, sep="-")

def collect(*args, **kwargs):
    return len(args), sorted(kwargs.items())
print(collect(1, 2, x=3, y=4))
print(collect())

def tag(name, **attrs):
    parts = []
    for k in sorted(attrs):
        parts.append(k + "=" + str(attrs[k]))
    return name + "(" + ",".join(parts) + ")"
print(tag("div", id=1, cls="a"))

merged = {**{"a": 1}, **{"b": 2}, "c": 3}
print(sorted(merged.items()))
print([*nums, 4, *[5, 6]])
print((*nums, 0))

f = lambda a, b=10: a + b
print(f(1), f(1, 2), f(b=5, a=1))
scale = lambda x, k=2: x * k
print([scale(v) for v in [1, 2, 3]])
print(sorted([3, 1, 2], key=lambda v: -v))

pairs = [(1, "a"), (2, "b"), (3, "c")]
print([n for n, s in pairs])
print([s * n for n, s in pairs if n != 2])
print([(x, y) for x in range(3) for y in range(3) if x < y])
print([x * y for x in [1, 2, 3] for y in [10, 20]])
print({s: n for n, s in pairs})
print({n % 2 for n in range(6)} == {0, 1})
print(sorted({c for c in "hello"}))
grid = [[r * 3 + c for c in range(3)] for r in range(3)]
print(grid)
print([x for row in grid for x in row if x % 2 == 0])
print([x for x in range(10) if x % 2 == 0 if x > 3])
print(sum(x * x for x in range(5)))
print(max(len(w) for w in ["a", "bbb", "cc"]))
print(any(n > 2 for n, s in pairs), all(n > 0 for n, s in pairs))
print(sorted(set(x % 3 for x in range(10))))
print(list(x + 1 for x in [1, 2]))
print(",".join(str(n) for n in range(4)))
words = ["apple", "bob"]
print({w: len(w) for w in words if len(w) > 2})
total = 0
for i in range(3):
    total += sum(j for j in range(i))
print(total)
x = 5
print([x for x in range(2)], x)
