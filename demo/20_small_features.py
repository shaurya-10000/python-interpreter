x = 17
x //= 2
x **= 2
print(x)
y = 10
y /= 4
y %= 2
print(y)
bits = 1
bits <<= 3
bits >>= 1
bits |= 1
bits &= 7
bits ^= 2
print(bits)

a = b = [1]
a += [2]
print(a, b, a is b)
s = (1,)
t = s
t += (2,)
print(s, t)
d = {"a": 1}
d |= {"b": 2}
print(sorted(d.items()))
word = "ab"
word *= 2
print(word)


class Acc:
    def __init__(self):
        self.n = 0

    def __iadd__(self, k):
        self.n += k
        return self


acc = Acc()
same = acc
acc += 5
print(acc.n, acc is same)


class V:
    def __init__(self, n):
        self.n = n

    def __add__(self, other):
        return V(self.n + other.n)


v = V(1)
w = v
v += V(2)
print(v.n, w.n, v is w)

one = 1,
print(one, len(one))
first, = [5]
print(first)
pair = 1, 2,
print(pair)

print(r"a\nb")
print(r"C:\temp\new")
print(len(r"\n"))
print("a\tb")

n = 5
name = "Ada"
print(f"{n=}")
print(f"{name=}")
print(f"{n = }")
print(f"{n * 2=}")
print(f"{n=:>4}")
print(f"{n=!s}")
print(f"{n == 5}")

data = [3, 1, 2]
if (size := len(data)) > 2:
    print("big", size)
i = 0
while (i := i + 1) < 4:
    print(i)
print(i)


def f(a, *, b=2):
    return a + b


print(f(1), f(1, b=5))


def join(*xs, sep="-"):
    return sep.join(str(v) for v in xs)


print(join(1, 2, 3), join(1, 2, sep="+"))


def need(a, *, b):
    return a * b


print(need(3, b=4))
try:
    need(3)
except TypeError:
    print("missing keyword-only")


class K:
    def m(self, v, *, k=1):
        return v + k


print(K().m(1), K().m(1, k=5))


def packed(*a, **k):
    return a, sorted(k)


print(packed(1, 2, z=3, y=4))

count = lambda *a: len(a)
print(count(), count(1, 2, 3))
head = lambda first, *rest: (first, rest)
print(head(1, 2, 3))
names = lambda **kw: sorted(kw)
print(names(b=1, a=2))

try:
    try:
        raise ValueError("inner")
    except ValueError as e:
        raise KeyError("outer") from e
except KeyError as e2:
    print(e2.__cause__)

try:
    try:
        raise ValueError("a")
    except ValueError:
        raise KeyError("b") from None
except KeyError:
    print("suppressed")
