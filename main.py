from lexer import Lexer

# Let's test a complex Python script with classes, functions, and indentation
test_code = """
class Dog:
    def __init__(self, name):
        self.name = name

x = 5
y = 10.5

if x > 0:
    print("Positive")
    if y > 10:
        print("Big")
"""

print("--- TOKENIZING TEST CODE ---")
lexer = Lexer(test_code)
tokens = lexer.tokenize()

for t in tokens:
    print(t)
