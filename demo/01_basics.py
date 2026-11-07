# --- 1. String Methods ---
name = "Hello World"
print(name.upper())
print(name.lower())
print(name.split(" "))

# --- 2. List Methods ---
nums = [1, 2]
nums.append(3)
nums.append(4)
print(nums)
print(nums.pop())
print(nums)

# --- 3. Default Arguments ---
def greet(name="Guest"):
    print("Hello, " + name)

greet()
greet("Alice")

# --- 4. *args (Variable Arguments) ---
def sum_all(*nums):
    total = 0
    for n in nums:
        total = total + n
    return total

print(sum_all(1, 2, 3))
print(sum_all(10, 20, 30, 40))
