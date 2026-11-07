from enum import Enum, auto
from dataclasses import dataclass

class TokenType(Enum):
    # Literals
    NUMBER = auto()
    STRING = auto()
    IDENTIFIER = auto()
    
    # Keywords
    FALSE = auto(); TRUE = auto(); NONE = auto()
    AND = auto(); OR = auto(); NOT = auto()
    IF = auto(); ELIF = auto(); ELSE = auto()
    WHILE = auto(); FOR = auto(); IN = auto()
    DEF = auto(); RETURN = auto(); PASS = auto()
    BREAK = auto(); CONTINUE = auto()
    CLASS = auto()  # Added for OOP Phase
    
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
    
    # Indentation & Structure
    NEWLINE = auto(); INDENT = auto(); DEDENT = auto(); EOF = auto()

@dataclass
class Token:
    type: TokenType
    value: object
    line: int
    col: int

    def __repr__(self):
        return f"Token({self.type.name}, {self.value!r})"
