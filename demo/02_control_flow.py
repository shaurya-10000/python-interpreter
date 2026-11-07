# Control flow: if/elif/else, while + break/continue, for, range

x = 7
if x < 5:
    print("low")
elif x < 10:
    print("mid")
else:
    print("high")

# while with break
n = 0
while True:
    n = n + 1
    if n >= 3:
        break
    print("tick " + str(n))

# for with continue
for i in range(6):
    if i % 2 == 0:
        continue
    print("odd " + str(i))

# nested for
for i in range(2):
    for j in range(2):
        print(str(i) + "," + str(j))
