# Smoke test: features exercised in one file
n = "A"
print(f"Hi {n}, {1 + 1} {{x}}")

assert 1 + 1 == 2
print("ok")

def mk(a):
    def f(b):
        return a + b
    return f
print(mk(2)(3))

print(sorted([3, 1, 2]))
print(sum([1, 2]))
print(max([1, 5]))
print(min([1, 5]))
print(abs(-3))
print(len([1, 2, 3]))

for i, v in enumerate(["a", "b"]):
    print(str(i) + ":" + v)

for a, b in zip([1, 2], [10, 20]):
    print(a + b)
