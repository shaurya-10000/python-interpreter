from dataclasses import dataclass
from typing import Any, List

@dataclass
class Number: value: Any; line: int = 0
@dataclass
class String: value: str; line: int = 0
@dataclass
class FString: value: str; line: int = 0
@dataclass
class Bool: value: bool; line: int = 0
@dataclass
class NoneType: pass
@dataclass
class Var: name: str; line: int = 0
@dataclass
class BinOp: left: Any; op: str; right: Any; line: int = 0
@dataclass
class UnaryOp: op: str; operand: Any; line: int = 0
@dataclass
class Assign: target: Any; value: Any; line: int = 0
@dataclass
class Call: callee: Any; args: List[Any]; line: int = 0
@dataclass
class TupleExpr: elements: List[Any]; line: int = 0
@dataclass
class ListExpr: elements: List[Any]; line: int = 0
@dataclass
class DictExpr: keys: List[Any]; values: List[Any]; line: int = 0
@dataclass
class SetExpr: elements: List[Any]; line: int = 0
@dataclass
class ListComp: expr: Any; target: str; iterable: Any; condition: Any; line: int = 0
@dataclass
class Subscript: obj: Any; index: Any; line: int = 0
@dataclass
class Attribute: obj: Any; name: str; line: int = 0

@dataclass
class ExprStmt: expr: Any; line: int = 0
@dataclass
class PrintStmt: expr: Any; line: int = 0
@dataclass
class Block: statements: List[Any]
@dataclass
class IfStmt: condition: Any; then_branch: Any; elif_branches: List[Any]; else_branch: Any
@dataclass
class WhileStmt: condition: Any; body: Any; else_body: Any = None
@dataclass
class ForStmt: target: Any; iterable: Any; body: Any; else_body: Any = None
@dataclass
class FuncDef: name: str; params: List[str]; defaults: List[Any]; vararg: str; body: Any; line: int = 0
@dataclass
class ReturnStmt: value: Any; line: int = 0
@dataclass
class ClassDef: name: str; parent_class: Any; methods: List[Any]
@dataclass
class PassStmt: pass
@dataclass
class BreakStmt: pass
@dataclass
class ContinueStmt: pass
@dataclass
class TryStmt: try_block: Any; except_var: str; except_block: Any
@dataclass
class RaiseStmt: value: Any; line: int = 0
@dataclass
class AssertStmt: test: Any; msg: Any; line: int = 0
