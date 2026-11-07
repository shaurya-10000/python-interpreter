import pathlib

# ===== 1. Lexer =====
p = pathlib.Path("lexer.py")
src = p.read_text()

old = "            elif ch in '\"' + chr(39) + "':\n                self._string()"
new = "            elif ch in 'fF' and self._peek(1) in '\"' + chr(39) + "':\n                self._advance()\n                self._fstring()\n            elif ch in '\"' + chr(39) + "':\n                self._string()"

if "_fstring()" in src:
    print("  SKIP  fstring dispatch")
elif old in src:
    src = src.replace(old, new, 1)
    print("  OK    fstring dispatch")
else:
    print("  MISS  string dispatch -- lexer lines with 'elif ch in':")
    for i, line in enumerate(src.splitlines(), 1):
        if "elif ch in" in line or "_string()" in line:
            print("  line", i, ":", line)
    raise SystemExit(1)

method = '''    def _fstring(self):
        line, col = self.line, self.col
        quote = self._advance(); start = self.pos
        while not self._at_end() and self._peek() != quote:
            self._advance()
        if self._at_end():
            raise SyntaxError(f"Unterminated f-string at line {line}, col {col}")
        val = self.source[start:self.pos]; self._advance()
        self.tokens.append(Token(TokenType.FSTRING, val, line, col))

'''
if "def _fstring" in src:
    print("  SKIP  _fstring method")
else:
    anchor = "    def _string(self):"
    if anchor in src:
        src = src.replace(anchor, method + anchor, 1)
        print("  OK    _fstring method")
    else:
        print("  MISS  _string method")
        raise SystemExit(1)

p.write_text(src)

# ===== 2. AST node =====
p = pathlib.Path("ast_nodes.py")
src = p.read_text()
if "class FString" in src:
    print("  SKIP  FString node")
else:
    old = "class String: value: str; line: int = 0"
    if old not in src:
        old = "class String: value: str"
        if old not in src:
            print("  MISS  String node")
            raise SystemExit(1)
    new = old + "\n@dataclass\nclass FString: value: str; line: int = 0"
    src = src.replace(old, new, 1)
    p.write_text(src)
    print("  OK    FString node")

# ===== 3. Parser =====
p = pathlib.Path("parser.py")
src = p.read_text()
old = "        if self._match(TokenType.STRING): return String(self.tokens[self.pos - 1].value, line=ln)"
new = old + "\n        if self._match(TokenType.FSTRING): return FString(self.tokens[self.pos - 1].value, line=ln)"
if "FString(self.tokens" in src:
    print("  SKIP  FSTRING parse")
elif old in src:
    src = src.replace(old, new, 1)
    p.write_text(src)
    print("  OK    FSTRING parse")
else:
    print("  MISS  STRING parse line -- showing:")
    for i, line in enumerate(src.splitlines(), 1):
        if "TokenType.STRING" in line:
            print("  line", i, ":", line)
    raise SystemExit(1)

# ===== 4. Interpreter eval =====
p = pathlib.Path("interpreter.py")
src = p.read_text()

old = "        if isinstance(node, String): return node.value"
new = old + "\n        if isinstance(node, FString): return self._eval_fstring(node.value, env)"
if "isinstance(node, FString)" in src:
    print("  SKIP  FString eval")
elif old in src:
    src = src.replace(old, new, 1)
    print("  OK    FString eval dispatch")
else:
    print("  MISS  String eval line")
    raise SystemExit(1)

method = '''    def _eval_fstring(self, raw, env):
        from lexer import Lexer as _L
        from parser import Parser as _P
        result = []
        i = 0
        while i < len(raw):
            if raw[i] == "{" and i + 1 < len(raw) and raw[i + 1] == "{":
                result.append("{"); i += 2; continue
            if raw[i] == "}" and i + 1 < len(raw) and raw[i + 1] == "}":
                result.append("}"); i += 2; continue
            if raw[i] == "{":
                j = i + 1
                while j < len(raw) and raw[j] != "}": j += 1
                expr_text = raw[i + 1:j]
                toks = _L(expr_text).tokenize()
                ast = _P(toks).parse()
                if ast.statements and hasattr(ast.statements[0], "expr"):
                    val = self._eval_expr(ast.statements[0].expr, env)
                    result.append(self._to_string(val))
                i = j + 1
                continue
            result.append(raw[i]); i += 1
        return "".join(result)

'''
if "def _eval_fstring" in src:
    print("  SKIP  _eval_fstring")
else:
    anchor = "    def _to_string(self, val):"
    if anchor in src:
        src = src.replace(anchor, method + anchor, 1)
        print("  OK    _eval_fstring")
    else:
        print("  MISS  _to_string")
        raise SystemExit(1)

p.write_text(src)
print("  DONE f-string implementation")
