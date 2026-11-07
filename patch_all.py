import pathlib, re

def patch(path, old, new, label):
    p = pathlib.Path(path)
    src = p.read_text()
    if new in src:
        print(f"  SKIP  {label} (already applied)")
        return
    if old not in src:
        print(f"  MISS  {label} (pattern not found)")
        return
    p.write_text(src.replace(old, new, 1))
    print(f"  OK    {label}")

print("[1/6] TryStmt: re-raise control flow")
patch("interpreter.py",
"""        elif isinstance(node, TryStmt):
            try: self._eval_block(node.try_block, env)
            except Exception as e:
                if node.except_var: env.set(node.except_var, str(e))
                self._eval_block(node.except_block, env)""",
"""        elif isinstance(node, TryStmt):
            try:
                self._eval_block(node.try_block, env)
            except (ReturnException, BreakException, ContinueException):
                raise
            except Exception as e:
                if node.except_var: env.set(node.except_var, str(e))
                self._eval_block(node.except_block, env)""",
"TryStmt filter")

print("[2/6] run(): guard top-level break/continue")
patch("interpreter.py",
"""    def run(self, ast):
        try: self._eval_block(ast, self.global_env)
        except Exception as e: print(f"Runtime Error: {e}")""",
"""    def run(self, ast):
        try:
            self._eval_block(ast, self.global_env)
        except (BreakException, ContinueException):
            print("Runtime Error: 'break'/'continue' outside loop")
        except Exception as e:
            print(f"Runtime Error: {e}")""",
"top-level break guard")

print("[3/6] Class methods capture defining env")
patch("interpreter.py",
"""                def make_method(m, parent_cls):
                    def method_func(*args):
                        method_env = Environment(env)""",
"""                def make_method(m, parent_cls, class_env):
                    def method_func(*args):
                        method_env = Environment(class_env)""",
"make_method signature")
patch("interpreter.py",
"                methods[method.name] = make_method(method, parent)",
"                methods[method.name] = make_method(method, parent, env)",
"make_method call")

print("[4/6] Defaults evaluated at def-time")
patch("interpreter.py",
"""        elif isinstance(node, FuncDef):
            def func(*args):
                func_env = Environment(env)
                if node.vararg: func_env.set(node.vararg, list(args[len(node.params):]))
                for i, param in enumerate(node.params):
                    if i < len(args): func_env.set(param, args[i])
                    elif node.defaults[i] is not None: func_env.set(param, self._eval_expr(node.defaults[i], env))
                    else: func_env.set(param, None)""",
"""        elif isinstance(node, FuncDef):
            evaluated_defaults = [self._eval_expr(d, env) if d is not None else None for d in node.defaults]
            def func(*args):
                func_env = Environment(env)
                if node.vararg: func_env.set(node.vararg, list(args[len(node.params):]))
                for i, param in enumerate(node.params):
                    if i < len(args): func_env.set(param, args[i])
                    elif evaluated_defaults[i] is not None: func_env.set(param, evaluated_defaults[i])
                    else: func_env.set(param, None)""",
"def-time defaults")

print("[5/6] Parser: tuple for-targets")
patch("parser.py",
"""    def _for_statement(self):
        target = self._primary(); self._expect(TokenType.IN)
        return ForStmt(target, self._expression(), self._block())""",
"""    def _for_statement(self):
        target = self._for_target(); self._expect(TokenType.IN)
        return ForStmt(target, self._expression(), self._block())

    def _for_target(self):
        first = self._primary()
        if self._match(TokenType.COMMA):
            elements = [first, self._primary()]
            while self._match(TokenType.COMMA):
                elements.append(self._primary())
            return ListExpr(elements)
        return first""",
"parser tuple targets")

print("[6/6] REPL: no double syntax-error print")
patch("main.py",
"""def run_source(source: str, interpreter: Interpreter):
    try:
        lexer = Lexer(source); tokens = lexer.tokenize()
        parser = Parser(tokens); ast = parser.parse()
        interpreter.run(ast)
    except SyntaxError as e: print(f"Syntax Error: {e}")
    except NameError as e: print(f"Name Error: {e}")
    except Exception as e: print(f"Error: {e}")""",
"""def run_source(source: str, interpreter: Interpreter, silent_syntax=False):
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
        return True""",
"run_source returns flag")
patch("main.py",
"""            try:
                source = "\\n".join(buffer)
                run_source(source, interpreter)
                buffer = []
            except SyntaxError:
                if line.strip() == "" and len(buffer) > 1:
                    print("Syntax Error: Incomplete block or invalid syntax.")
                    buffer = []
                else:
                    continue""",
"""            source = "\\n".join(buffer)
            ok = run_source(source, interpreter, silent_syntax=True)
            if ok:
                buffer = []
            elif line.strip() == "" and len(buffer) > 1:
                run_source(source, interpreter, silent_syntax=False)
                buffer = []""",
"REPL buffering")

print("\\nDone.")
