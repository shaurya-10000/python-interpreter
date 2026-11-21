# Missing required positional argument & duplicate argument checks
def need_two(a, b, c=10):
    return a + b + c

print(need_two(1, 2))
try:
    need_two(1)
except TypeError:
    print("missing arg caught")

try:
    need_two(1, 2, a=9)
except TypeError:
    print("duplicate arg caught")

f_none = lambda x, y=None: (x, y)
print(f_none(5))
try:
    f_none()
except TypeError:
    print("lambda missing arg caught")

# Full for-loop unpacking (starred + nested)
rows = [[1, 2, 3, 4], [10, 20]]
for head, *tail in rows:
    print(head, tail)

nested = [((1, 2), 3), ((4, 5), 6)]
for (a, b), c in nested:
    print(a + b + c)

# del with global and nonlocal
g = 100
def drop_global():
    global g
    del g

drop_global()
try:
    print(g)
except NameError:
    print("global deleted")

def outer():
    v = 42
    def drop_local():
        nonlocal v
        del v
    drop_local()
    try:
        return v
    except NameError:
        return "nonlocal deleted"

print(outer())

# Control flow & nested classes inside class bodies
FLAG = True
class Outer:
    if FLAG:
        def greet(self):
            return "hello from conditional method"
    items = []
    for i in range(3):
        items.append(i * 10)

    class Inner:
        def val(self):
            return 99

print(Outer().greet())
print(Outer.items)
print(Outer.Inner().val())
print(Outer().Inner().val())