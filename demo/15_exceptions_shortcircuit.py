calls = []
def side(tag, value):
    calls.append(tag)
    return value
print(side("a", False) and side("b", True))
print(side("c", True) or side("d", False))
print(calls)
x = 0
print(x != 0 and 10 / x > 1)
print(x == 0 or 10 / x > 1)
print(0 or "default")
print("" or [] or None)
print(1 and 2 and 3)

class AppError(Exception):
    pass

class ValidationError(AppError):
    def __init__(self, field, msg):
        super().__init__(field + ": " + msg)
        self.field = field

def check(age):
    if age < 0:
        raise ValidationError("age", "must be >= 0")
    if age > 150:
        raise ValueError("unrealistic age")
    return age

for v in [5, -1, 200]:
    try:
        print(check(v))
    except ValidationError as e:
        print("validation:", e, e.field)
    except ValueError as e:
        print("value:", e)

try:
    check(-5)
except AppError as e:
    print("caught by parent:", e)

try:
    1 / 0
except ZeroDivisionError as e:
    print("zero:", e)

try:
    [1, 2][5]
except IndexError as e:
    print("index:", e)

d = {"a": 1}
try:
    d["zz"]
except KeyError as e:
    print("key:", e)

try:
    int("abc")
except ValueError as e:
    print("int failed")

try:
    try:
        raise ValueError("first")
    except KeyError as e:
        print("wrong handler")
except ValueError as e:
    print("outer got", e)

def risky(n):
    if n == 0:
        raise KeyError("k")
    if n == 1:
        raise IndexError("i")
    return n
for n in [0, 1, 2]:
    try:
        print(risky(n))
    except (KeyError, IndexError) as e:
        print("lookup error")

def cleanup_demo():
    try:
        raise RuntimeError("boom")
    except RuntimeError as e:
        print("handled", e)
        raise ValueError("converted")
    finally:
        print("cleanup")
try:
    cleanup_demo()
except ValueError as e:
    print("outer:", e)

try:
    raise ValidationError("name", "required")
except Exception as e:
    print(isinstance(e, ValidationError), isinstance(e, AppError), isinstance(e, ValueError))

try:
    raise AppError("x")
except:
    print("bare except")

def parse(s):
    try:
        n = int(s)
    except ValueError:
        print("bad", s)
        return None
    else:
        print("good", n)
        return n
    finally:
        print("done", s)
print(parse("12"))
print(parse("zz"))

try:
    raise ValueError
except ValueError as e:
    print(repr(str(e)))

try:
    raise ValueError("a")
except ValueError as e:
    print(e.args)

try:
    assert 1 == 2, "math"
except AssertionError as e:
    print("assert:", e)
