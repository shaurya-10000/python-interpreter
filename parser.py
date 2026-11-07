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
        if self._match(TokenType.IF): return self._if_statement()
        if self._match(TokenType.WHILE): return self._while_statement()
        if self._match(TokenType.FOR): return self._for_statement()
        if self._match(TokenType.DEF): return self._func_def()
        if self._match(TokenType.CLASS): return self._class_def()
        if self._match(TokenType.RETURN): return self._return_statement()
        if self._match(TokenType.TRY): return self._try_statement()
        if self._match(TokenType.RAISE):
            val = self._expression(); self._match(TokenType.NEWLINE); return RaiseStmt(val)
        if self._match(TokenType.PASS): self._expect(TokenType.NEWLINE); return PassStmt()
        if self._match(TokenType.BREAK): self._expect(TokenType.NEWLINE); return BreakStmt()
        if self._match(TokenType.CONTINUE): self._expect(TokenType.NEWLINE); return ContinueStmt()
        
        expr = self._expression()
        if self._match(TokenType.ASSIGN):
            if isinstance(expr, (Var, Subscript, Attribute)):
                value = self._expression(); self._expect(TokenType.NEWLINE); return Assign(expr, value)
            raise SyntaxError("Invalid assignment target")
        self._match(TokenType.NEWLINE)
        return ExprStmt(expr)

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
        self._expect(TokenType.EXCEPT)
        except_var = None
        if self._match(TokenType.AS):
            except_var = self._expect(TokenType.IDENTIFIER).value
        except_block = self._block()
        return TryStmt(try_block, except_var, except_block)

    def _if_statement(self):
        condition = self._expression(); then_branch = self._block()
        elif_branches = []
        while self._match(TokenType.ELIF):
            elif_branches.append((self._expression(), self._block()))
        else_branch = self._block() if self._match(TokenType.ELSE) else None
        return IfStmt(condition, then_branch, elif_branches, else_branch)

    def _while_statement(self): return WhileStmt(self._expression(), self._block())
    def _for_statement(self):
        target = self._primary(); self._expect(TokenType.IN)
        return ForStmt(target, self._expression(), self._block())
        
    # UPDATED: Parse default args and *args
    def _func_def(self):
        name = self._expect(TokenType.IDENTIFIER).value
        self._expect(TokenType.LPAREN)
        params, defaults, vararg = [], [], None
        if not self._check(TokenType.RPAREN):
            while True:
                if self._match(TokenType.STAR):
                    vararg = self._expect(TokenType.IDENTIFIER).value
                else:
                    param_name = self._expect(TokenType.IDENTIFIER).value
                    params.append(param_name)
                    if self._match(TokenType.ASSIGN):
                        defaults.append(self._expression())
                    else:
                        defaults.append(None)
                if not self._match(TokenType.COMMA): break
        self._expect(TokenType.RPAREN)
        body = self._block()
        return FuncDef(name, params, defaults, vararg, body)

    def _class_def(self):
        name = self._expect(TokenType.IDENTIFIER).value
        self._expect(TokenType.COLON); self._expect(TokenType.NEWLINE); self._expect(TokenType.INDENT)
        methods = []
        while not self._check(TokenType.DEDENT) and not self._check(TokenType.EOF):
            if self._match(TokenType.NEWLINE): continue
            if self._match(TokenType.DEF): methods.append(self._func_def())
            else: raise SyntaxError("Expected def inside class")
        self._expect(TokenType.DEDENT); return ClassDef(name, methods)
    def _return_statement(self):
        if self._check(TokenType.NEWLINE): self._advance(); return ReturnStmt(None)
        val = self._expression(); self._match(TokenType.NEWLINE); return ReturnStmt(val)

    def _expression(self): return self._or()
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
        expr = self._addition()
        while self._match(TokenType.EQ, TokenType.NEQ, TokenType.LT, TokenType.GT, TokenType.LTE, TokenType.GTE):
            expr = BinOp(expr, self.tokens[self.pos - 1].value, self._addition())
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
        if self._match(TokenType.MINUS, TokenType.PLUS):
            return UnaryOp(self.tokens[self.pos - 1].value, self._unary())
        return self._power()
    def _power(self):
        expr = self._call()
        if self._match(TokenType.DOUBLE_STAR): expr = BinOp(expr, "**", self._unary())
        return expr
    def _call(self):
        expr = self._primary()
        while True:
            if self._match(TokenType.LPAREN):
                args = []
                if not self._check(TokenType.RPAREN):
                    while True:
                        args.append(self._expression())
                        if not self._match(TokenType.COMMA): break
                self._expect(TokenType.RPAREN); expr = Call(expr, args)
            elif self._match(TokenType.LBRACKET):
                idx = self._expression(); self._expect(TokenType.RBRACKET); expr = Subscript(expr, idx)
            elif self._match(TokenType.DOT):
                expr = Attribute(expr, self._expect(TokenType.IDENTIFIER).value)
            else: break
        return expr
    def _primary(self):
        if self._match(TokenType.NUMBER): return Number(self.tokens[self.pos - 1].value)
        if self._match(TokenType.STRING): return String(self.tokens[self.pos - 1].value)
        if self._match(TokenType.TRUE): return Bool(True)
        if self._match(TokenType.FALSE): return Bool(False)
        if self._match(TokenType.NONE): return NoneType()
        if self._match(TokenType.IDENTIFIER): return Var(self.tokens[self.pos - 1].value)
        if self._match(TokenType.LBRACKET):
            elements = []
            if not self._check(TokenType.RBRACKET):
                while True:
                    elements.append(self._expression())
                    if not self._match(TokenType.COMMA): break
            self._expect(TokenType.RBRACKET); return ListExpr(elements)
        if self._match(TokenType.LBRACE):
            keys, values = [], []
            if not self._check(TokenType.RBRACE):
                while True:
                    keys.append(self._expression()); self._expect(TokenType.COLON); values.append(self._expression())
                    if not self._match(TokenType.COMMA): break
            self._expect(TokenType.RBRACE); return DictExpr(keys, values)
        if self._match(TokenType.LPAREN):
            expr = self._expression(); self._expect(TokenType.RPAREN); return expr
        raise SyntaxError(f"Unexpected token {self._cur().type.name} at line {self._cur().line}")
