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
        filename = sys.argv[1]
        try:
            with open(filename, "r") as f: source = f.read()
            run_source(source, interpreter)
        except FileNotFoundError: print(f"File not found: {filename}")
        return

    print("PySubset Interpreter v1.1 (Multi-line REPL)")
    print("Type 'exit()' to quit.\n")
    buffer = []
    while True:
        try:
            prompt = ">>> " if not buffer else "... "
            line = input(prompt)
            if line.strip() in ("exit()", "quit()") and not buffer: break
            buffer.append(line)

            # Try to parse the accumulated buffer
            try:
                source = "\n".join(buffer)
                lexer = Lexer(source)
                tokens = lexer.tokenize()
                parser = Parser(tokens)
                ast = parser.parse()
                interpreter.run(ast)
                buffer = []  # Clear buffer on success
            except SyntaxError:
                # Might be incomplete (e.g. missing indented block).
                # Only show an error if the user pressed Enter on an empty line.
                if line.strip() == "" and len(buffer) > 1:
                    print("Syntax Error: Incomplete block or invalid syntax.")
                    buffer = []
                else:
                    continue
        except (KeyboardInterrupt, EOFError):
            print("\nGoodbye!"); break

if __name__ == "__main__": main()
