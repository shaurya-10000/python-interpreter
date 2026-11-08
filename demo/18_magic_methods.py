class Vec:
    def __init__(self, x, y):
        self.x = x
        self.y = y

    def __repr__(self):
        return "Vec(" + str(self.x) + ", " + str(self.y) + ")"

    def __str__(self):
        return "<" + str(self.x) + "," + str(self.y) + ">"

    def __eq__(self, other):
        return isinstance(other, Vec) and self.x == other.x and self.y == other.y

    def __hash__(self):
        return hash((self.x, self.y))

    def __add__(self, other):
        return Vec(self.x + other.x, self.y + other.y)

    def __sub__(self, other):
        return Vec(self.x - other.x, self.y - other.y)

    def __mul__(self, k):
        return Vec(self.x * k, self.y * k)

    def __rmul__(self, k):
        return Vec(self.x * k, self.y * k)

    def __neg__(self):
        return Vec(-self.x, -self.y)

    def __abs__(self):
        return (self.x ** 2 + self.y ** 2) ** 0.5

    def __lt__(self, other):
        return abs(self) < abs(other)

    def __len__(self):
        return 2

    def __getitem__(self, i):
        if i == 0:
            return self.x
        if i == 1:
            return self.y
        raise IndexError("index out of range")

    def __iter__(self):
        return iter([self.x, self.y])

    def __contains__(self, v):
        return v == self.x or v == self.y

    def __bool__(self):
        return self.x != 0 or self.y != 0


a = Vec(1, 2)
b = Vec(3, 4)
print(a)
print(repr(a))
print([a, b])
print(a + b)
print(b - a)
print(a * 3, 3 * a)
print(-a)
print(abs(b))
print(a == Vec(1, 2), a == b, a != b)
print(a < b, b < a)
print(len(a))
print(a[0], a[1])
print(list(a))
print(2 in a, 9 in a)
x, y = a
print(x, y)
print(sorted([b, a]))
print(max(a, b))
print({a: "first"}[Vec(1, 2)])
print(len({a, Vec(1, 2), b}))
print(bool(Vec(0, 0)), bool(a))
print("yes" if a else "no")


class Money:
    def __init__(self, v):
        self.v = v

    def __add__(self, other):
        if isinstance(other, Money):
            return Money(self.v + other.v)
        return Money(self.v + other)

    def __radd__(self, other):
        return self + other

    def __repr__(self):
        return "Money(" + str(self.v) + ")"


print(sum([Money(1), Money(2), Money(3)]))
print(Money(5) + 1, 1 + Money(5))


class Tag:
    def __init__(self, n):
        self.n = n

    def __eq__(self, other):
        return self.n == other.n


print(Tag(1) == Tag(1), Tag(1) != Tag(2), Tag(2) in [Tag(1), Tag(2)])


class Counter:
    def __init__(self, start):
        self.n = start

    def __call__(self, step):
        self.n += step
        return self.n


c = Counter(10)
print(c(1), c(5), callable(c))


class Countdown:
    def __init__(self, n):
        self.n = n

    def __iter__(self):
        return self

    def __next__(self):
        if self.n <= 0:
            raise StopIteration
        self.n -= 1
        return self.n + 1


for v in Countdown(3):
    print(v)
print(list(Countdown(4)))
print(sum(Countdown(4)))


class Grid:
    def __init__(self):
        self.cells = {}

    def __setitem__(self, key, value):
        self.cells[key] = value

    def __getitem__(self, key):
        return self.cells.get(key, 0)

    def __delitem__(self, key):
        del self.cells[key]

    def __len__(self):
        return len(self.cells)


g = Grid()
g[1] = 10
g[2] = 20
print(g[1], g[3], len(g))
del g[1]
print(len(g))


class OnlyRepr:
    def __repr__(self):
        return "OnlyRepr!"


print(OnlyRepr())
print(str(OnlyRepr()))
print([OnlyRepr()])


class Empty:
    def __len__(self):
        return 0


print(bool(Empty()), "full" if Empty() else "empty")
