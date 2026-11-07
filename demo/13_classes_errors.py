class Empty:
    pass

class Config:
    debug = False
    name = "app"
    def show(self):
        return self.name + " " + str(self.debug)

class Child(Config):
    level = 3

c = Config()
print(c.show())
print(Config.name)
c.name = "override"
print(c.show())
print(Config.name)
print(Child().name)
print(Child().level)
print(Empty() is not None)

a = b = 7
print(a + b)
xs = ys = []
xs.append(1)
print(ys)
p = q = r = 0
print(p, q, r)

items = [1, 2, 3, 4]
del items[0]
print(items)
del items[1:3]
print(items)
table = {"a": 1, "b": 2}
del table["a"]
print(table)

def make_counter():
    count = 0
    def inc():
        nonlocal count
        count = count + 1
        return count
    return inc
c1 = make_counter()
c1()
c1()
print(c1())
c2 = make_counter()
print(c2())

def safe_div(n):
    try:
        result = 10 / n
    except Exception as e:
        print("error")
        return -1
    else:
        print("ok")
        return result
    finally:
        print("done")
print(safe_div(2))
print(safe_div(0))

try:
    try:
        x = 1 / 0
    except Exception as e:
        print("inner")
        raise
except Exception as e2:
    print("outer", e2)
