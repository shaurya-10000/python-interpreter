for i in range(3):
    print(i)
else:
    print("no break")

for i in range(3):
    if i == 1:
        break
    print(i)
else:
    print("this should not print")

n = 0
while n < 3:
    n = n + 1
    print(n)
else:
    print("while finished cleanly")

n = 0
while True:
    n = n + 1
    if n >= 2:
        break
else:
    print("this should not print")
