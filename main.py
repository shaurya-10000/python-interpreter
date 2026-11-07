from lexer import Lexer
from parser import Parser
from interpreter import Interpreter

test_code = """
nums = [1, 2, 3, 4]
print(nums[0])
nums[1] = 99
print(nums)

person = {"name": "Alice", "age": 25}
print(person["name"])
person["age"] = 26
print(person)

for n in nums:
    print(n * 2)
"""

print("--- EXECUTING DATA STRUCTURES TEST ---")
lexer = Lexer(test_code)
tokens = lexer.tokenize()

parser = Parser(tokens)
ast = parser.parse()

interpreter = Interpreter()
interpreter.run(ast)
