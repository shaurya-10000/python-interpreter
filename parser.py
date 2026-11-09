from tokens import TokenType
from ast_nodes import *

class Parser:
    def __init__(self, tokens):
        self.tokens = tokens; self.pos = 0

    def parse(self) -> Block:
        statements = []
        while not self._check(TokenType.EOF):
            if self._match(TokenType.NEWLINE): continue
            statements.append(self._statement())
        return Block(statements)

    def _cur(self): return self.tokens[self.pos]
    def _check(self, ttype): return self._cur().type == ttype
    def _match(self, *ttypes):
        for t in ttypes:
            if self._check(t): self.pos += 1; return True
        return False
    def _advance(self): tok = self._cur(); self.pos += 1; return tok
    def _expect(self, ttype, msg=""):
        if self._check(ttype): return self._advance()
        raise SyntaxError(f"Line {self._cur().line}: Expected {ttype.name} {msg}, got {self._cur().type.name}")

    def _statement(self):
        ln = self._cur().line
        if self._match(TokenType.IF): return self._if_statement()
        if self._match(TokenType.WHILE): return self._while_statement()
        if self._match(TokenType.FOR): return self._for_statement()
        if self._match(TokenType.DEF): return self._func_def()
        if self._match(TokenType.CLASS): return self._class_def()
        if self._match(TokenType.RETURN): return self._return_statement()
        if self._match(TokenType.TRY): return self._try_statement()
        if self._match(TokenType.WITH):
            items = []
            while True:
                ctx = self._expression()
                var = None
                if self._match(TokenType.AS):
                    var = self._expect(TokenType.IDENTIFIER).value
                items.append((ctx, var))
                if not self._match(TokenType.COMMA): break
            return WithStmt(items, self._block(), line=ln)
        if self._match(TokenType.IMPORT):
            names = []
            while True:
                dotted = self._dotted_name()
                alias = self._expect(TokenType.IDENTIFIER).value if self._match(TokenType.AS) else None
                names.append((dotted, alias))
                if not self._match(TokenType.COMMA): break
            self._match(TokenType.NEWLINE)
            return ImportStmt(names, line=ln)
        if self._check(TokenType.IDENTIFIER) and self._cur().value == "from" and self.tokens[self.pos + 1].type == TokenType.IDENTIFIER:
            self.pos += 1
            module = self._dotted_name()
            self._expect(TokenType.IMPORT)
            names = []
            if self._match(TokenType.STAR):
                names = None
            else:
                paren = self._match(TokenType.LPAREN)
                while True:
                    nm = self._expect(TokenType.IDENTIFIER).value
                    alias = self._expect(TokenType.IDENTIFIER).value if self._match(TokenType.AS) else None
                    names.append((nm, alias))
                    if not self._match(TokenType.COMMA): break
                    if paren and self._check(TokenType.RPAREN): break
                if paren: self._expect(TokenType.RPAREN)
            self._match(TokenType.NEWLINE)
            return FromImportStmt(module, names, line=ln)
        if self._check(TokenType.AT):
            decorators = self._decorators()
            self._expect(TokenType.DEF)
            fd = self._func_def()
            fd.decorators = decorators
            return fd
        if self._match(TokenType.GLOBAL):
            names = [self._expect(TokenType.IDENTIFIER).value]
            while self._match(TokenType.COMMA):
                names.append(self._expect(TokenType.IDENTIFIER).value)
            self._match(TokenType.NEWLINE)
            return GlobalStmt(names, line=ln)
        if self._match(TokenType.NONLOCAL):
            names = [self._expect(TokenType.IDENTIFIER).value]
            while self._match(TokenType.COMMA):
                names.append(self._expect(TokenType.IDENTIFIER).value)
            self._match(TokenType.NEWLINE)
            return NonlocalStmt(names, line=ln)
        if self._match(TokenType.DEL):
            targets = [self._expression()]
            while self._match(TokenType.COMMA):
                targets.append(self._expression())
            self._match(TokenType.NEWLINE)
            return DelStmt(targets, line=ln)
        if self._match(TokenType.ASSERT):
            test = self._expression()
            msg = None
            if self._match(TokenType.COMMA):
                msg = self._expression()
            self._match(TokenType.NEWLINE)
            return AssertStmt(test, msg, line=ln)
        if self._match(TokenType.RAISE):
            val = None if self._check(TokenType.NEWLINE) else self._expression()
            cause = None
            if val is not None and self._check(TokenType.IDENTIFIER) and self._cur().value == "from":
                self.pos += 1
                cause = self._expression()
            self._match(TokenType.NEWLINE)
            rs = RaiseStmt(val, line=ln)
            rs.cause = cause
            return rs
        if self._match(TokenType.PASS): self._expect(TokenType.NEWLINE); return PassStmt()
        if self._match(TokenType.BREAK): self._expect(TokenType.NEWLINE); return BreakStmt()
        if self._match(TokenType.CONTINUE): self._expect(TokenType.NEWLINE); return ContinueStmt()

        expr = self._expression()
        # Augmented assignment: x += 1  ->  x = x + 1
        if self._match(TokenType.AUG_ASSIGN):
            op = self.tokens[self.pos - 1].value[:-1]
            if not isinstance(expr, (Var, Subscript, Attribute)):
                raise SyntaxError(f"Line {ln}: Invalid augmented assignment target")
            value = self._expression()
            self._expect(TokenType.NEWLINE)
            return Assign(expr, BinOp(expr, op + "=", value, line=ln), line=ln)
        # Tuple assignment target: 'a, b = ...' parses as TupleExpr(left)
        if self._match(TokenType.COMMA):
            elements = [expr]
            while True:
                if self._check(TokenType.ASSIGN) or self._check(TokenType.NEWLINE): break
                elements.append(self._expression())
                if not self._match(TokenType.COMMA): break
            expr = TupleExpr(elements, line=ln)
        if self._match(TokenType.ASSIGN):
            if isinstance(expr, (Var, Subscript, Attribute, TupleExpr)):
                value = self._expression()
                # RHS tuple: 'x = 1, 2' or 'a, b = b, a'
                if self._match(TokenType.COMMA):
                    elems = [value]
                    while True:
                        if self._check(TokenType.NEWLINE): break
                        elems.append(self._expression())
                        if not self._match(TokenType.COMMA): break
                    value = TupleExpr(elems, line=ln)
                if self._check(TokenType.ASSIGN):
                    targets = [expr, value]
                    while self._match(TokenType.ASSIGN):
                        targets.append(self._expression())
                    self._expect(TokenType.NEWLINE)
                    value = targets.pop()
                    for t in targets:
                        if not isinstance(t, (Var, Subscript, Attribute)):
                            raise SyntaxError(f"Line {ln}: Invalid assignment target")
                    return ChainAssign(targets, value, line=ln)
                self._expect(TokenType.NEWLINE); return Assign(expr, value, line=ln)
            raise SyntaxError("Invalid assignment target")
        self._match(TokenType.NEWLINE)
        return ExprStmt(expr, line=ln)

    def _block(self):
        self._expect(TokenType.COLON); self._expect(TokenType.NEWLINE); self._expect(TokenType.INDENT)
        statements = []
        while not self._check(TokenType.DEDENT) and not self._check(TokenType.EOF):
            if self._match(TokenType.NEWLINE): continue
            statements.append(self._statement())
        self._expect(TokenType.DEDENT)
        return Block(statements)

    def _try_statement(self):
        try_block = self._block()
        handlers = []; else_block = None; finally_block = None
        while self._check(TokenType.EXCEPT):
            self.pos += 1
            type_expr = None; var = None
            if not self._check(TokenType.AS) and not self._check(TokenType.COLON):
                type_expr = self._expression()
            if self._match(TokenType.AS):
                var = self._expect(TokenType.IDENTIFIER).value
            handlers.append((type_expr, var, self._block()))
        if handlers and self._match(TokenType.ELSE):
            else_block = self._block()
        if self._match(TokenType.FINALLY):
            finally_block = self._block()
        if not handlers and finally_block is None:
            raise SyntaxError(f"Line {self._cur().line}: 'try' needs an 'except' or 'finally' clause")
        first_var = handlers[0][1] if handlers else None
        first_block = handlers[0][2] if handlers else None
        return TryStmt(try_block, first_var, first_block, else_block, finally_block, handlers)

    def _if_statement(self):
        condition = self._expression(); then_branch = self._block()
        elif_branches = []
        while self._match(TokenType.ELIF):
            elif_branches.append((self._expression(), self._block()))
        else_branch = self._block() if self._match(TokenType.ELSE) else None
        return IfStmt(condition, then_branch, elif_branches, else_branch)

    def _while_statement(self):
        cond = self._expression(); body = self._block()
        else_body = self._block() if self._match(TokenType.ELSE) else None
        return WhileStmt(cond, body, else_body)
    def _for_statement(self):
        target = self._for_target(); self._expect(TokenType.IN)
        it = self._expression(); body = self._block()
        else_body = self._block() if self._match(TokenType.ELSE) else None
        return ForStmt(target, it, body, else_body)

    def _for_target(self):
        ln = self._cur().line
        first = self._primary()
        if self._match(TokenType.COMMA):
            elements = [first, self._primary()]
            while self._match(TokenType.COMMA):
                elements.append(self._primary())
            return ListExpr(elements, line=ln)
        return first
        
    def _func_def(self):
        ln = self._cur().line
        name = self._expect(TokenType.IDENTIFIER).value
        self._expect(TokenType.LPAREN)
        params, defaults, vararg, kwarg, kwonly = [], [], None, None, []
        star_seen = False
        if not self._check(TokenType.RPAREN):
            while True:
                if self._match(TokenType.DOUBLE_STAR):
                    kwarg = self._expect(TokenType.IDENTIFIER).value
                elif self._match(TokenType.STAR):
                    star_seen = True
                    if self._check(TokenType.IDENTIFIER):
                        vararg = self._advance().value
                else:
                    pname = self._expect(TokenType.IDENTIFIER).value
                    default = self._expression() if self._match(TokenType.ASSIGN) else None
                    if star_seen:
                        kwonly.append((pname, default))
                    else:
                        params.append(pname)
                        defaults.append(default)
                if not self._match(TokenType.COMMA): break
                if self._check(TokenType.RPAREN): break
        self._expect(TokenType.RPAREN)
        body = self._block()
        fd = FuncDef(name, params, defaults, vararg, body, line=ln, kwarg=kwarg)
        fd.kwonly = kwonly
        return fd

    def _class_def(self):
        name = self._expect(TokenType.IDENTIFIER).value
        bases = []
        if self._match(TokenType.LPAREN):
            while not self._check(TokenType.RPAREN):
                bases.append(self._expect(TokenType.IDENTIFIER).value)
                if not self._match(TokenType.COMMA): break
            self._expect(TokenType.RPAREN)
        parent_class = bases[0] if bases else None
        self._expect(TokenType.COLON); self._expect(TokenType.NEWLINE); self._expect(TokenType.INDENT)
        methods = []; attrs = []
        while not self._check(TokenType.DEDENT) and not self._check(TokenType.EOF):
            if self._match(TokenType.NEWLINE): continue
            if self._check(TokenType.AT):
                decorators = self._decorators()
                self._expect(TokenType.DEF)
                fd = self._func_def()
                fd.decorators = decorators
                methods.append(fd)
            elif self._match(TokenType.DEF):
                methods.append(self._func_def())
            elif self._match(TokenType.PASS):
                self._match(TokenType.NEWLINE)
            elif self._check(TokenType.STRING):
                self._statement()
            elif self._check(TokenType.IDENTIFIER) and self.tokens[self.pos + 1].type == TokenType.ASSIGN:
                stmt = self._statement()
                if not isinstance(stmt, Assign):
                    raise SyntaxError(f"Line {self._cur().line}: Only simple assignments are allowed in a class body")
                attrs.append(stmt)
            else:
                raise SyntaxError(f"Line {self._cur().line}: Unsupported statement in class body")
        self._expect(TokenType.DEDENT); return ClassDef(name, parent_class, methods, attrs, bases)

    def _dotted_name(self):
        parts = [self._expect(TokenType.IDENTIFIER).value]
        while self._match(TokenType.DOT):
            parts.append(self._expect(TokenType.IDENTIFIER).value)
        return ".".join(parts)

    def _decorators(self):
        decorators = []
        while self._match(TokenType.AT):
            decorators.append(self._expression())
            self._expect(TokenType.NEWLINE)
        return decorators

    def _return_statement(self):
        ln = self._cur().line
        if self._check(TokenType.NEWLINE): self._advance(); return ReturnStmt(None, line=ln)
        val = self._expression()
        if self._check(TokenType.COMMA):
            elems = [val]
            while self._match(TokenType.COMMA):
                if self._check(TokenType.NEWLINE): break
                elems.append(self._expression())
            val = TupleExpr(elems, line=ln)
        self._match(TokenType.NEWLINE); return ReturnStmt(val, line=ln)

    def _expression(self):
        if self._match(TokenType.YIELD):
            ln = self.tokens[self.pos - 1].line
            if self._check(TokenType.IDENTIFIER) and self._cur().value == "from":
                self.pos += 1
                return YieldFromExpr(self._expression(), line=ln)
            if (self._check(TokenType.NEWLINE) or self._check(TokenType.RPAREN) or self._check(TokenType.RBRACKET)
                    or self._check(TokenType.RBRACE) or self._check(TokenType.EOF) or self._check(TokenType.DEDENT)):
                return YieldExpr(None, line=ln)
            value = self._expression()
            if self._check(TokenType.COMMA):
                elems = [value]
                while self._match(TokenType.COMMA):
                    if self._check(TokenType.NEWLINE) or self._check(TokenType.RPAREN):
                        break
                    elems.append(self._expression())
                value = TupleExpr(elems, line=ln)
            return YieldExpr(value, line=ln)
        if self._match(TokenType.LAMBDA):
            ln = self.tokens[self.pos - 1].line
            params = []; defaults = []; vararg = None; kwarg = None
            if not self._check(TokenType.COLON):
                while True:
                    if self._match(TokenType.DOUBLE_STAR):
                        kwarg = self._expect(TokenType.IDENTIFIER).value
                    elif self._match(TokenType.STAR):
                        vararg = self._expect(TokenType.IDENTIFIER).value
                    else:
                        params.append(self._expect(TokenType.IDENTIFIER).value)
                        defaults.append(self._or() if self._match(TokenType.ASSIGN) else None)
                    if not self._match(TokenType.COMMA): break
            self._expect(TokenType.COLON)
            lam = Lambda(params, self._expression(), line=ln, defaults=defaults)
            lam.vararg = vararg
            lam.kwarg = kwarg
            return lam
        expr = self._or()
        if self._check(TokenType.WALRUS):
            if not isinstance(expr, Var):
                raise SyntaxError(f"Line {self._cur().line}: cannot use assignment expressions with this target")
            ln = self._cur().line
            self.pos += 1
            return NamedExpr(expr.name, self._expression(), line=ln)
        if self._check(TokenType.IF):
            ln = self._cur().line
            self.pos += 1
            cond = self._or()
            self._expect(TokenType.ELSE)
            other = self._expression()
            return IfExpr(cond, expr, other, line=ln)
        return expr

    def _or(self):
        expr = self._and()
        while self._match(TokenType.OR): expr = BinOp(expr, "or", self._and())
        return expr
    def _and(self):
        expr = self._not()
        while self._match(TokenType.AND): expr = BinOp(expr, "and", self._not())
        return expr
    def _not(self):
        if self._match(TokenType.NOT): return UnaryOp("not", self._not())
        return self._comparison()
    def _comparison(self):
        ln = self._cur().line
        left = self._bitor()
        result = None
        while True:
            if self._match(TokenType.EQ, TokenType.NEQ, TokenType.LT, TokenType.GT, TokenType.LTE, TokenType.GTE):
                op = self.tokens[self.pos - 1].value
            elif self._match(TokenType.IN):
                op = "in"
            elif self._check(TokenType.NOT) and self.tokens[self.pos + 1].type == TokenType.IN:
                self.pos += 2
                op = "not in"
            elif self._match(TokenType.IS):
                op = "is not" if self._match(TokenType.NOT) else "is"
            else:
                break
            right = self._bitor()
            cmp = BinOp(left, op, right, line=ln)
            result = cmp if result is None else BinOp(result, "and", cmp, line=ln)
            left = right
        return result if result is not None else left

    def _bitor(self):
        expr = self._bitxor()
        while self._match(TokenType.PIPE):
            expr = BinOp(expr, "|", self._bitxor(), line=self.tokens[self.pos - 1].line)
        return expr

    def _bitxor(self):
        expr = self._bitand()
        while self._match(TokenType.CARET):
            expr = BinOp(expr, "^", self._bitand(), line=self.tokens[self.pos - 1].line)
        return expr

    def _bitand(self):
        expr = self._shift()
        while self._match(TokenType.AMP):
            expr = BinOp(expr, "&", self._shift(), line=self.tokens[self.pos - 1].line)
        return expr

    def _shift(self):
        expr = self._addition()
        while self._match(TokenType.LSHIFT, TokenType.RSHIFT):
            op = self.tokens[self.pos - 1].value
            expr = BinOp(expr, op, self._addition(), line=self.tokens[self.pos - 1].line)
        return expr

    def _addition(self):
        expr = self._multiplication()
        while self._match(TokenType.PLUS, TokenType.MINUS):
            expr = BinOp(expr, self.tokens[self.pos - 1].value, self._multiplication())
        return expr
    def _multiplication(self):
        expr = self._unary()
        while self._match(TokenType.STAR, TokenType.SLASH, TokenType.DOUBLE_SLASH, TokenType.PERCENT):
            expr = BinOp(expr, self.tokens[self.pos - 1].value, self._unary())
        return expr
    def _unary(self):
        if self._match(TokenType.MINUS, TokenType.PLUS, TokenType.TILDE):
            return UnaryOp(self.tokens[self.pos - 1].value, self._unary())
        if self._match(TokenType.STAR):
            ln = self.tokens[self.pos - 1].line
            return Starred(self._unary(), line=ln)
        return self._power()

    def _power(self):
        expr = self._call()
        if self._match(TokenType.DOUBLE_STAR): expr = BinOp(expr, "**", self._unary())
        return expr
    def _call(self):
        ln = self._cur().line
        expr = self._primary()
        while True:
            if self._match(TokenType.LPAREN):
                args = []; kwargs = {}; splats = []
                if not self._check(TokenType.RPAREN):
                    while True:
                        if self._match(TokenType.DOUBLE_STAR):
                            splats.append(self._or())
                        elif self._check(TokenType.IDENTIFIER) and self.tokens[self.pos + 1].type == TokenType.ASSIGN:
                            kname = self._advance().value
                            self._advance()
                            kwargs[kname] = self._expression()
                        else:
                            val = self._expression()
                            if self._check(TokenType.FOR):
                                val = Comp("gen", val, None, self._comp_clauses(), line=ln)
                            if (kwargs or splats) and not isinstance(val, Starred):
                                raise SyntaxError(f"Line {ln}: positional argument follows keyword argument")
                            args.append(val)
                        if not self._match(TokenType.COMMA): break
                        if self._check(TokenType.RPAREN): break
                self._expect(TokenType.RPAREN)
                expr = Call(expr, args, line=ln, kwargs=kwargs, kw_splats=splats)
            elif self._match(TokenType.LBRACKET):
                expr = Subscript(expr, self._subscript_index(), line=ln)
            elif self._match(TokenType.DOT):
                expr = Attribute(expr, self._expect(TokenType.IDENTIFIER).value, line=ln)
            else: break
        return expr

    def _subscript_index(self):
        ln = self._cur().line
        lower = None if self._check(TokenType.COLON) else self._expression()
        if not self._check(TokenType.COLON):
            self._expect(TokenType.RBRACKET)
            return lower
        self._advance()
        upper = step = None
        if not self._check(TokenType.RBRACKET) and not self._check(TokenType.COLON):
            upper = self._expression()
        if self._match(TokenType.COLON):
            if not self._check(TokenType.RBRACKET):
                step = self._expression()
        self._expect(TokenType.RBRACKET)
        return SliceExpr(lower, upper, step, line=ln)

    def _comp_clauses(self):
        clauses = []
        while True:
            if self._match(TokenType.FOR):
                target = self._comp_target()
                self._expect(TokenType.IN)
                clauses.append(("for", target, self._or()))
            elif self._match(TokenType.IF):
                clauses.append(("if", self._or()))
            else:
                break
        return clauses

    def _comp_target(self):
        ln = self._cur().line
        first = self._comp_target_atom()
        if self._check(TokenType.COMMA):
            items = [first]
            while self._match(TokenType.COMMA):
                if self._check(TokenType.IN): break
                items.append(self._comp_target_atom())
            return TupleExpr(items, line=ln)
        return first

    def _comp_target_atom(self):
        if self._match(TokenType.LPAREN):
            inner = self._comp_target()
            self._expect(TokenType.RPAREN)
            return inner
        tok = self._expect(TokenType.IDENTIFIER)
        return Var(tok.value, line=tok.line)

    def _primary(self):
        ln = self._cur().line
        if self._match(TokenType.NUMBER): return Number(self.tokens[self.pos - 1].value, line=ln)
        if self._match(TokenType.STRING):
            val = self.tokens[self.pos - 1].value
            while self._check(TokenType.STRING):
                val += self._advance().value
            return String(val, line=ln)
        if self._match(TokenType.FSTRING): return FString(self.tokens[self.pos - 1].value, line=ln)
        if self._match(TokenType.TRUE): return Bool(True, line=ln)
        if self._match(TokenType.FALSE): return Bool(False, line=ln)
        if self._match(TokenType.NONE): return NoneType()
        if self._match(TokenType.IDENTIFIER): return Var(self.tokens[self.pos - 1].value, line=ln)

        # List / list comprehension
        if self._match(TokenType.LBRACKET):
            if self._check(TokenType.RBRACKET): self._advance(); return ListExpr([], line=ln)
            first = self._expression()
            if self._check(TokenType.FOR):
                clauses = self._comp_clauses()
                self._expect(TokenType.RBRACKET)
                return Comp("list", first, None, clauses, line=ln)
            elements = [first]
            while self._match(TokenType.COMMA):
                if self._check(TokenType.RBRACKET): break
                elements.append(self._expression())
            self._expect(TokenType.RBRACKET); return ListExpr(elements, line=ln)

        # Dict / dict comprehension / set / set comprehension
        if self._match(TokenType.LBRACE):
            if self._check(TokenType.RBRACE): self._advance(); return DictExpr([], [], line=ln)
            if self._check(TokenType.DOUBLE_STAR):
                keys, values = [], []
                while True:
                    if self._match(TokenType.DOUBLE_STAR):
                        keys.append(None); values.append(self._or())
                    else:
                        keys.append(self._expression()); self._expect(TokenType.COLON); values.append(self._expression())
                    if not self._match(TokenType.COMMA): break
                    if self._check(TokenType.RBRACE): break
                self._expect(TokenType.RBRACE); return DictExpr(keys, values, line=ln)
            first = self._expression()
            if self._match(TokenType.COLON):
                val = self._expression()
                if self._check(TokenType.FOR):
                    clauses = self._comp_clauses()
                    self._expect(TokenType.RBRACE)
                    return Comp("dict", first, val, clauses, line=ln)
                keys, values = [first], [val]
                while self._match(TokenType.COMMA):
                    if self._check(TokenType.RBRACE): break
                    if self._match(TokenType.DOUBLE_STAR):
                        keys.append(None); values.append(self._or())
                    else:
                        keys.append(self._expression()); self._expect(TokenType.COLON); values.append(self._expression())
                self._expect(TokenType.RBRACE); return DictExpr(keys, values, line=ln)
            if self._check(TokenType.FOR):
                clauses = self._comp_clauses()
                self._expect(TokenType.RBRACE)
                return Comp("set", first, None, clauses, line=ln)
            elements = [first]
            while self._match(TokenType.COMMA):
                if self._check(TokenType.RBRACE): break
                elements.append(self._expression())
            self._expect(TokenType.RBRACE); return SetExpr(elements, line=ln)

        # Parenthesised expression / tuple / generator expression
        if self._match(TokenType.LPAREN):
            if self._check(TokenType.RPAREN): self._advance(); return TupleExpr([], line=ln)
            first = self._expression()
            if self._check(TokenType.FOR):
                clauses = self._comp_clauses()
                self._expect(TokenType.RPAREN)
                return Comp("gen", first, None, clauses, line=ln)
            if self._match(TokenType.COMMA):
                elements = [first]
                while not self._check(TokenType.RPAREN):
                    elements.append(self._expression())
                    if not self._match(TokenType.COMMA): break
                self._expect(TokenType.RPAREN)
                return TupleExpr(elements, line=ln)
            self._expect(TokenType.RPAREN); return first
        raise SyntaxError(f"Unexpected token {self._cur().type.name} at line {self._cur().line}")

