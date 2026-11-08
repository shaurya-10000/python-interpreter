print("a\tb")
print("line1\nline2")
print('it\'s')
print("say \"hi\"")
print("back\\slash")
print("a" "b" 'c')
text = """first
second"""
print(text)
print(len(text))
print("""one "quoted" word""")

name = "Ada"
n = 3.14159
width = 8
print(f"{name:>6}|{name:<6}|{name:^6}|")
print(f"{n:.2f} {n:8.3f} {42:05d} {255:x} {255:#x} {0.256:.1%}")
print(f"{1234567:,}")
print(f"{name!r} {name!s}")
print(f"[{n:{width}.2f}]")
print(f"{{literal}} {name}")
print(f"{[1, 2][0] + 1} {'x' * 3}")
print(f"{{{name}}}")
print(f'{name}\t{n:.1f}')

print(5 & 3, 5 | 3, 5 ^ 3, 1 << 4, 256 >> 2, ~5)
flags = 0
flags |= 4
flags |= 1
flags &= 5
flags ^= 1
print(flags)
print(1 | 2 == 3)
print(2 + 3 << 1)
print(6 & 3 + 1)
a = {1, 2, 3}
b = {3, 4}
print(sorted(a | b), sorted(a & b), sorted(a ^ b), sorted(a - b))

single = (1,)
print(single, len(single))
empty = ()
print(empty, len(empty))
print((1, 2,) == (1, 2))
nums = [1, 2, 3,]
print(nums)
print(max(1, 5, 2,))

def pair():
    return 1, 2
x, y = pair()
print(x, y, pair())
