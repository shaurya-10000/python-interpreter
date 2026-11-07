import pathlib

# AST
p = pathlib.Path("ast_nodes.py"); src = p.read_text()
old_w = "class WhileStmt: condition: Any; body: Any"
new_w = "class WhileStmt: condition: Any; body: Any; else_body: Any = None"
if new_w in src:
    print("  SKIP  WhileStmt else")
elif old_w in src:
    src = src.replace(old_w, new_w, 1); print("  OK    WhileStmt else")
else:
    print("  MISS  WhileStmt"); raise SystemExit(1)

old_f = "class ForStmt: target: Any; iterable: Any; body: Any"
new_f = "class ForStmt: target: Any; iterable: Any; body: Any; else_body: Any = None"
if new_f in src:
    print("  SKIP  ForStmt else")
elif old_f in src:
    src = src.replace(old_f, new_f, 1); print("  OK    ForStmt else")
else:
    print("  MISS  ForStmt"); raise SystemExit(1)
p.write_text(src)

# Parser
p = pathlib.Path("parser.py"); src = p.read_text()

old_w = "    def _while_statement(self): return WhileStmt(self._expression(), self._block())"
new_w = '''    def _while_statement(self):
        cond = self._expression(); body = self._block()
        else_body = self._block() if self._match(TokenType.ELSE) else None
        return WhileStmt(cond, body, else_body)'''
if "cond = self._expression(); body = self._block()" in src:
    print("  SKIP  while else parse")
elif old_w in src:
    src = src.replace(old_w, new_w, 1); print("  OK    while else parse")
else:
    print("  MISS  _while_statement"); raise SystemExit(1)

old_f = '''    def _for_statement(self):
        target = self._for_target(); self._expect(TokenType.IN)
        return ForStmt(target, self._expression(), self._block())'''
new_f = '''    def _for_statement(self):
        target = self._for_target(); self._expect(TokenType.IN)
        it = self._expression(); body = self._block()
        else_body = self._block() if self._match(TokenType.ELSE) else None
        return ForStmt(target, it, body, else_body)'''
if "it = self._expression(); body = self._block()" in src:
    print("  SKIP  for else parse")
elif old_f in src:
    src = src.replace(old_f, new_f, 1); print("  OK    for else parse")
else:
    print("  MISS  _for_statement"); raise SystemExit(1)
p.write_text(src)

# Interpreter
p = pathlib.Path("interpreter.py"); src = p.read_text()

old_w = '''        elif isinstance(node, WhileStmt):
            while self._is_truthy(self._eval_expr(node.condition, env)):
                try: self._eval_block(node.body, env)
                except BreakException: break
                except ContinueException: continue'''
new_w = '''        elif isinstance(node, WhileStmt):
            broke = False
            while self._is_truthy(self._eval_expr(node.condition, env)):
                try: self._eval_block(node.body, env)
                except BreakException: broke = True; break
                except ContinueException: continue
            if not broke and node.else_body is not None:
                self._eval_block(node.else_body, env)'''
if "if not broke and node.else_body is not None" in src and "WhileStmt" in src:
    # might already be there; just check the while context
    if old_w in src:
        src = src.replace(old_w, new_w, 1); print("  OK    while else eval")
    else:
        print("  SKIP  while else eval")
else:
    print("  MISS  WhileStmt eval"); raise SystemExit(1)

old_f = '''        elif isinstance(node, ForStmt):
            iterable = self._eval_expr(node.iterable, env)
            for item in iterable:
                if isinstance(node.target, Var): env.set(node.target.name, item)
                elif isinstance(node.target, (ListExpr, TupleExpr)):
                    for i, target_expr in enumerate(node.target.elements):
                        if isinstance(target_expr, Var): env.set(target_expr.name, item[i])
                try: self._eval_block(node.body, env)
                except BreakException: break
                except ContinueException: continue'''
new_f = '''        elif isinstance(node, ForStmt):
            iterable = self._eval_expr(node.iterable, env)
            broke = False
            for item in iterable:
                if isinstance(node.target, Var): env.set(node.target.name, item)
                elif isinstance(node.target, (ListExpr, TupleExpr)):
                    for i, target_expr in enumerate(node.target.elements):
                        if isinstance(target_expr, Var): env.set(target_expr.name, item[i])
                try: self._eval_block(node.body, env)
                except BreakException: broke = True; break
                except ContinueException: continue
            if not broke and node.else_body is not None:
                self._eval_block(node.else_body, env)'''
if old_f in src:
    src = src.replace(old_f, new_f, 1); print("  OK    for else eval")
else:
    print("  MISS  ForStmt eval"); raise SystemExit(1)

p.write_text(src)
