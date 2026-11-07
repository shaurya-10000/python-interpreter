from dataclasses import dataclass
from typing import Any, List

@dataclass
class Number: value: Any
@dataclass
class String: value: str
@dataclass
class Bool: value: bool
@dataclass
class NoneType: pass
@dataclass
class Var: name: str
@dataclass
class BinOp: left: Any; op: str; right: Any
@dataclass
class UnaryOp: op: str; operand: Any
@dataclass
class Assign: target: Any; value: Any
@dataclass
class Call: callee: Any; args: List[Any]
@dataclass
class ListExpr: elements: List[Any]
@dataclass
class DictExpr: keys: List[Any]; values: List[Any]
@dataclass
class Subscript: obj: Any; index: Any
@dataclass
class Attribute: obj: Any; name: str

@dataclass
class ExprStmt: expr: Any
@dataclass
class PrintStmt: expr: Any
@dataclass
class Block: statements: List[Any]
@dataclass
class IfStmt: condition: Any; then_branch: Any; elif_branches: List[Any]; else_branch: Any
@dataclass
class WhileStmt: condition: Any; body: Any
@dataclass
class ForStmt: target: Any; iterable: Any; body: Any
@dataclass
class FuncDef: name: str; params: List[str]; body: Any
@dataclass
class ReturnStmt: value: Any
@dataclass
class ClassDef: name: str; methods: List[Any]
@dataclass
class PassStmt: pass
@dataclass
class BreakStmt: pass
@dataclass
class ContinueStmt: pass

# Exception nodes
@dataclass
class TryStmt: try_block: Any; except_var: str; except_block: Any
@dataclass
class RaiseStmt: value: Any
