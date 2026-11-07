import sys
from lexer import Lexer
from parser import Parser
from interpreter import Interpreter

def run_source(source: str, interpreter: Interpreter):
    try:
        lexer = Lexer(source)
        tokens = lexer.tokenize()
        parser = Parser(tokens)
        ast = parser.parse()
        interpreter.run(ast)
    except SyntaxError as e:
        print(f"Syntax Error: {e}")
    except NameError as e:
        print(f"Name Error: {e}")
    except Exception as e:
        print(f"Error: {e}")

def main():
    interpreter = Interpreter()

    # Mode 1: Run a file
    if len(sys.argv) > 1:
        filename = sys.argv[1]
        try:
            with open(filename, "r") as f:
                source = f.read()
            print(f"--- Running {filename} ---")
            run_source(source, interpreter)
        except FileNotFoundError:
            print(f"File not found: {filename}")
        return

    # Mode 2: REPL
    print("PySubset Interpreter v1.0")
    print("Type 'exit()' to quit.\n")
    while True:
        try:
            line = input(">>> ")
            if line.strip() in ("exit()", "quit()", "exit", "quit"):
                break
            if not line.strip():
                continue
            run_source(line, interpreter)
        except (KeyboardInterrupt, EOFError):
            print("\nGoodbye!")
            break

if __name__ == "__main__":
    main()
