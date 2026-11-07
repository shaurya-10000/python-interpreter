total = 10
total += 5
total -= 3
total *= 2
total /= 4
print(total)
n = [1, 2, 3, 4, 5]
print(2 in n)
print(9 not in n)
v = None
print(v is None)
print(n is not None)
print(1 if len(n) > 3 else 0)
print(n[1:3])
print(n[:2])
print(n[3:])
print(n[::2])
print(n[-1])
inc = lambda a: a + 1
add = lambda a, b: a + b
print(inc(4))
print(add(2, 3))
print({k: k * 2 for k in n})
print({k: k for k in n if k % 2 == 0})
print([x for x in n if x > 2])
print(1 < 2 < 3)
print(3 > 2 > 1)
print(3 > 2 > 5)
print(1 < 3 < 2)
