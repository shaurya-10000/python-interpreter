import sys
from lexer import Lexer
from parser import Parser
from interpreter import Interpreter

def run_source(source: str, interpreter: Interpreter):
    try:
        lexer = Lexer(source); tokens = lexer.tokenize()
        parser = Parser(tokens); ast = parser.parse()
        interpreter.run(ast)
    except SyntaxError as e: print(f"Syntax Error: {e}")
    except NameError as e: print(f"Name Error: {e}")
    except Exception as e: print(f"Error: {e}")

def main():
    interpreter = Interpreter()
    if len(sys.argv) > 1:
        with open(sys.argv[1], "r") as f: source = f.read()
        run_source(source, interpreter)
        return
    while True:
        try:
            line = input(">>> ")
            if line.strip() in ("exit()", "quit()"): break
            run_source(line, interpreter)
        except (KeyboardInterrupt, EOFError): break

if __name__ == "__main__": main()
