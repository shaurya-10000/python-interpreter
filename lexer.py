from tokens import Token, TokenType

KEYWORDS = {
    "False": TokenType.FALSE, "True": TokenType.TRUE, "None": TokenType.NONE,
    "and": TokenType.AND, "or": TokenType.OR, "not": TokenType.NOT,
    "if": TokenType.IF, "elif": TokenType.ELIF, "else": TokenType.ELSE,
    "while": TokenType.WHILE, "for": TokenType.FOR, "in": TokenType.IN,
    "def": TokenType.DEF, "return": TokenType.RETURN, "pass": TokenType.PASS,
    "break": TokenType.BREAK, "continue": TokenType.CONTINUE,
    "class": TokenType.CLASS, "try": TokenType.TRY, "except": TokenType.EXCEPT,
    "raise": TokenType.RAISE, "as": TokenType.AS,
}

class Lexer:
    def __init__(self, source: str):
        self.source = source
        self.pos = 0; self.line = 1; self.col = 1
        self.tokens = []
        self.indent_stack = [0]
        self.paren_depth = 0

    def tokenize(self):
        while self.pos < len(self.source) and self.source[self.pos] in ' \t\r\n':
            if self.source[self.pos] == '\n': self.line += 1
            self.pos += 1
        self.col = 1

        while self.pos < len(self.source):
            ch = self._peek()
            if ch in ' \t\r': self._advance(); continue
            if ch == '\n': self._handle_newline(); continue
            if ch == '#':
                while not self._at_end() and self._peek() != '\n': self._advance()
                continue
            if ch.isdigit(): self._number()
            elif ch in '"\'':
                self._string()
            elif ch.isalpha() or ch == '_': self._identifier()
            else: self._operator()

        if self.tokens and self.tokens[-1].type != TokenType.NEWLINE:
            self.tokens.append(Token(TokenType.NEWLINE, '\n', self.line, self.col))
        while len(self.indent_stack) > 1:
            self.indent_stack.pop()
            self.tokens.append(Token(TokenType.DEDENT, None, self.line, self.col))
        self.tokens.append(Token(TokenType.EOF, None, self.line, self.col))
        return self.tokens

    def _peek(self, offset=0):
        i = self.pos + offset
        return self.source[i] if i < len(self.source) else '\0'

    def _at_end(self, offset=0):
        return self.pos + offset >= len(self.source)

    def _advance(self):
        ch = self.source[self.pos]
        self.pos += 1
        if ch == '\n': self.line += 1; self.col = 1
        else: self.col += 1
        return ch

    def _handle_newline(self):
        if self.paren_depth > 0: self._advance(); return
        temp_pos, temp_line, temp_col = self.pos, self.line, self.col
        lookahead = self.pos + 1
        indent_spaces = 0
        while lookahead < len(self.source) and self.source[lookahead] in ' \t':
            indent_spaces += 4 if self.source[lookahead] == '\t' else 1
            lookahead += 1
        if lookahead >= len(self.source) or self.source[lookahead] in '\n#':
            self._advance(); return
        self._advance()
        self.tokens.append(Token(TokenType.NEWLINE, '\n', temp_line, temp_col))
        self.pos = lookahead
        self.col = indent_spaces + 1
        if indent_spaces > self.indent_stack[-1]:
            self.indent_stack.append(indent_spaces)
            self.tokens.append(Token(TokenType.INDENT, indent_spaces, self.line, self.col))
        else:
            while indent_spaces < self.indent_stack[-1]:
                self.indent_stack.pop()
                self.tokens.append(Token(TokenType.DEDENT, indent_spaces, self.line, self.col))

    def _number(self):
        line, col = self.line, self.col
        start = self.pos; is_float = False
        while self._peek().isdigit(): self._advance()
        if self._peek() == '.' and self._peek(1).isdigit():
            is_float = True; self._advance()
            while self._peek().isdigit(): self._advance()
        val = float(self.source[start:self.pos]) if is_float else int(self.source[start:self.pos])
        self.tokens.append(Token(TokenType.NUMBER, val, line, col))

    def _string(self):
        line, col = self.line, self.col
        quote = self._advance(); start = self.pos
        while not self._at_end() and self._peek() != quote: self._advance()
        if self._at_end():
            raise SyntaxError(f'Unterminated string at line {line}, col {col}')
        val = self.source[start:self.pos]; self._advance()
        self.tokens.append(Token(TokenType.STRING, val, line, col))

    def _identifier(self):
        line, col = self.line, self.col; start = self.pos
        while self._peek().isalnum() or self._peek() == '_': self._advance()
        word = self.source[start:self.pos]
        self.tokens.append(Token(KEYWORDS.get(word, TokenType.IDENTIFIER), word, line, col))

    def _operator(self):
        line, col = self.line, self.col; ch = self._advance()
        pair = ch + self._peek()
        two_char = {'==': TokenType.EQ, '!=': TokenType.NEQ, '<=': TokenType.LTE, '>=': TokenType.GTE, '//': TokenType.DOUBLE_SLASH, '**': TokenType.DOUBLE_STAR}
        if pair in two_char: self._advance(); self.tokens.append(Token(two_char[pair], pair, line, col)); return
        one_char = {'+': TokenType.PLUS, '-': TokenType.MINUS, '*': TokenType.STAR, '/': TokenType.SLASH, '%': TokenType.PERCENT, '<': TokenType.LT, '>': TokenType.GT, '=': TokenType.ASSIGN, '(': TokenType.LPAREN, ')': TokenType.RPAREN, '[': TokenType.LBRACKET, ']': TokenType.RBRACKET, '{': TokenType.LBRACE, '}': TokenType.RBRACE, ',': TokenType.COMMA, ':': TokenType.COLON, '.': TokenType.DOT}
        if ch in one_char:
            if ch in '([{': self.paren_depth += 1
            elif ch in ')]}': self.paren_depth -= 1
            self.tokens.append(Token(one_char[ch], ch, line, col))
        else: raise SyntaxError(f"Unexpected character {ch!r} at line {line}, col {col}")
