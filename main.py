import sys
from lexer import Lexer
from parser import Parser
from interpreter import Interpreter

def run_source(source: str, interpreter: Interpreter, silent_syntax=False):
    try:
        lexer = Lexer(source); tokens = lexer.tokenize()
        parser = Parser(tokens); ast = parser.parse()
        interpreter.run(ast)
        return True
    except SyntaxError as e:
        if not silent_syntax:
            print(f"Syntax Error: {e}")
        return False
    except NameError as e:
        print(f"Name Error: {e}")
        return True
    except Exception as e:
        print(f"Error: {e}")
        return True

def main():
    interpreter = Interpreter()
    if len(sys.argv) > 1:
        filename = sys.argv[1]
        try:
            with open(filename, "r") as f: source = f.read()
            run_source(source, interpreter)
        except FileNotFoundError: print(f"File not found: {filename}")
        return

    print("PySubset Interpreter v1.2")
    print("Type 'exit()' to quit.\n")
    buffer = []
    while True:
        try:
            prompt = ">>> " if not buffer else "... "
            line = input(prompt)
            if line.strip() in ("exit()", "quit()") and not buffer: break
            buffer.append(line)
            
            source = "\n".join(buffer)
            ok = run_source(source, interpreter, silent_syntax=True)
            if ok:
                buffer = []
            elif line.strip() == "" and len(buffer) > 1:
                run_source(source, interpreter, silent_syntax=False)
                buffer = []
        except (KeyboardInterrupt, EOFError):
            print("\nGoodbye!"); break

if __name__ == "__main__": main()
