# Iteration patterns: tuple for-targets, tuple literals, tuple unpacking

pairs = [(1, 2), (3, 4), (5, 6)]
for a, b in pairs:
    print(a + b)

x, y = 10, 20
print(x + y)

m, n, p = 1, 2, 3
print(m + n + p)

a, b = 1, 2
a, b = b, a
print(a)
print(b)

d = {"x": 1, "y": 2, "z": 3}
for k in ["x", "y", "z"]:
    print(k + "=" + str(d[k]))

nums = [10, 20, 30]
for i in range(len(nums)):
    print(str(i) + ": " + str(nums[i]))
