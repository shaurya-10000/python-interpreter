import argparse
import sys
from compiler import compile_module
from diagnostics import format_traceback
from interpreter import Interpreter
from lexer import Lexer
from opcodes import disassemble
from parser import Parser
from vm import VM


def run_source(source: str, interpreter, filename: str = "<repl>", silent_syntax: bool = False):
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


def main(argv=None):
    ap = argparse.ArgumentParser(prog="pysubset", description="PySubset Python Interpreter")
    ap.add_argument("script", nargs="?", help="Python script to execute (omit for REPL)")
    ap.add_argument("--engine", choices=("tree", "vm"), default="tree", help="Execution engine")
    ap.add_argument("--dis", action="store_true", help="Disassemble bytecode and exit")
    args = ap.parse_args(argv)

    engine = VM() if args.engine == "vm" else Interpreter()

    if args.script:
        filename = args.script
        try:
            with open(filename, "r", encoding="utf-8") as f:
                source = f.read()
            if args.dis:
                ast = Parser(Lexer(source, filename=filename).tokenize(), filename=filename).parse()
                print(disassemble(compile_module(ast, filename=filename)))
                return
            engine.set_script(filename)
            run_source(source, engine, filename=filename)
        except FileNotFoundError:
            print(f"File not found: {filename}")
        return

    print(f"PySubset Interpreter v1.4 ({args.engine})")
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
            ok = run_source(source, engine, filename="<repl>", silent_syntax=True)
            if ok:
                buffer = []
            elif line.strip() == "" and len(buffer) > 1:
                run_source(source, engine, filename="<repl>", silent_syntax=False)
                buffer = []
        except (KeyboardInterrupt, EOFError):
            print("\nGoodbye!")
            break


if __name__ == "__main__":
    main()