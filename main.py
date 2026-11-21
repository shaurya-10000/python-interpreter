import sys
from diagnostics import format_traceback
from lexer import Lexer
from parser import Parser
from interpreter import Interpreter


def run_source(source: str, interpreter: Interpreter, filename: str = "<repl>", silent_syntax: bool = False):
    interpreter.register_source(filename, source)
    try:
        lexer = Lexer(source, filename=filename)
        tokens = lexer.tokenize()
        parser = Parser(tokens, filename=filename)
        ast = parser.parse()
        interpreter.run(ast, source=source, filename=filename)
        return True
    except SyntaxError as e:
        if not silent_syntax:
            line = getattr(e, "lineno", 0) or 0
            col = getattr(e, "offset", 0) or 0
            fn = getattr(e, "filename", None) or filename
            print(format_traceback("SyntaxError", str(e), fn, line, col, interpreter.sources))
        return False
    except NameError as e:
        print(f"NameError: {e}")
        return True
    except Exception as e:
        print(f"Error: {e}")
        return True


def main():
    interpreter = Interpreter()
    if len(sys.argv) > 1:
        filename = sys.argv[1]
        try:
            with open(filename, "r", encoding="utf-8") as f:
                source = f.read()
            interpreter.set_script(filename)
            run_source(source, interpreter, filename=filename)
        except FileNotFoundError:
            print(f"File not found: {filename}")
        return

    print("PySubset Interpreter v1.3")
    print("Type 'exit()' to quit.\n")
    buffer = []
    while True:
        try:
            prompt = ">>> " if not buffer else "... "
            line = input(prompt)
            if line.strip() in ("exit()", "quit()") and not buffer:
                break
            buffer.append(line)

            source = "\n".join(buffer)
            ok = run_source(source, interpreter, filename="<repl>", silent_syntax=True)
            if ok:
                buffer = []
            elif line.strip() == "" and len(buffer) > 1:
                run_source(source, interpreter, filename="<repl>", silent_syntax=False)
                buffer = []
        except (KeyboardInterrupt, EOFError):
            print("\nGoodbye!")
            break


if __name__ == "__main__":
    main()