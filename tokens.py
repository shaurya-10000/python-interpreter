from enum import Enum, auto
from dataclasses import dataclass

class TokenType(Enum):
    # Literals
    NUMBER = auto(); STRING = auto(); FSTRING = auto(); IDENTIFIER = auto()
    # Keywords
    FALSE = auto(); TRUE = auto(); NONE = auto()
    AND = auto(); OR = auto(); NOT = auto()
    IF = auto(); ELIF = auto(); ELSE = auto()
    WHILE = auto(); FOR = auto(); IN = auto()
    DEF = auto(); RETURN = auto(); PASS = auto()
    BREAK = auto(); CONTINUE = auto()
    CLASS = auto(); ASSERT = auto()
    TRY = auto(); EXCEPT = auto(); RAISE = auto(); AS = auto(); YIELD = auto(); WITH = auto(); IMPORT = auto(); WALRUS = auto(); AT = auto(); AMP = auto(); PIPE = auto(); CARET = auto(); TILDE = auto(); LSHIFT = auto(); RSHIFT = auto(); DEL = auto(); NONLOCAL = auto(); FINALLY = auto(); GLOBAL = auto(); IS = auto(); LAMBDA = auto(); AUG_ASSIGN = auto()

    # Operators
    PLUS = auto(); MINUS = auto(); STAR = auto(); SLASH = auto()
    DOUBLE_SLASH = auto(); PERCENT = auto(); DOUBLE_STAR = auto()
    # Comparisons
    EQ = auto(); NEQ = auto(); LT = auto(); GT = auto(); LTE = auto(); GTE = auto()
    ASSIGN = auto()
    # Punctuation
    LPAREN = auto(); RPAREN = auto()
    LBRACKET = auto(); RBRACKET = auto()
    LBRACE = auto(); RBRACE = auto()
    COMMA = auto(); COLON = auto(); DOT = auto()
    # Indentation
    NEWLINE = auto(); INDENT = auto(); DEDENT = auto(); EOF = auto()

@dataclass
class Token:
    type: TokenType
    value: object
    line: int
    col: int
    def __repr__(self): return f"Token({self.type.name}, {self.value!r})"
