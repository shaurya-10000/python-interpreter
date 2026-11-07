from lexer import Lexer
from parser import Parser
from interpreter import Interpreter

test_code = """
def greet(name):
    print("Hello, " + name + "!")

greet("World")

x = 10
while x > 0:
    if x == 5:
        print("Halfway there!")
    print(x)
    x = x - 1

for i in range(3):
    print("Loop iteration: " + str(i))

print("Done!")
"""

print("--- EXECUTING SCRIPT ---")
lexer = Lexer(test_code)
tokens = lexer.tokenize()

parser = Parser(tokens)
ast = parser.parse()

interpreter = Interpreter()
interpreter.run(ast)
