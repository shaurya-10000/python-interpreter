nums = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]

# List comprehension without condition
doubled = [x * 2 for x in nums]
print(doubled)

# List comprehension with condition
evens = [x for x in nums if x % 2 == 0]
print(evens)

# Squared numbers
squares = [x ** 2 for x in nums]
print(squares)

# Set literal
unique = {1, 2, 2, 3, 3, 3, 4}
print(len(unique))

# Dict comprehension style result via loop
squares_dict = {}
for n in nums:
    if n <= 5:
        squares_dict[n] = n ** 2
print(squares_dict)
