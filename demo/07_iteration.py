# Iteration patterns: tuple for-targets over a list of pairs

# Each element is a two-item list, unpacked by the for target.
# (Tuple literals like (1, 2) aren't supported yet -- see README roadmap.)
pairs = [[1, 2], [3, 4], [5, 6]]
for a, b in pairs:
    print(a + b)

# Dict iteration via explicit key list
d = {"x": 1, "y": 2, "z": 3}
for k in ["x", "y", "z"]:
    print(k + "=" + str(d[k]))

# Index-based loop
nums = [10, 20, 30]
for i in range(len(nums)):
    print(str(i) + ": " + str(nums[i]))
