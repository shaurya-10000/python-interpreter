from lexer import Lexer
from parser import Parser
from interpreter import Interpreter

test_code = """
class Dog:
    def __init__(self, name, breed):
        self.name = name
        self.breed = breed
        
    def bark(self):
        print(self.name + " says Woof!")
        
    def get_info(self):
        return self.name + " is a " + self.breed

my_dog = Dog("Buddy", "Golden Retriever")
print(my_dog.name)
my_dog.bark()
print(my_dog.get_info())

my_dog.name = "Max"
print(my_dog.name)
my_dog.bark()
"""

print("--- EXECUTING OOP TEST ---")
lexer = Lexer(test_code)
tokens = lexer.tokenize()

parser = Parser(tokens)
ast = parser.parse()

interpreter = Interpreter()
interpreter.run(ast)
