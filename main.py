from lexer import Lexer
from parser import Parser

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

def add(a, b):
    return a + b
"""

print("--- PARSING TEST CODE ---")
lexer = Lexer(test_code)
tokens = lexer.tokenize()

parser = Parser(tokens)
ast = parser.parse()

print("Parsing Successful! AST:")
print(ast)
