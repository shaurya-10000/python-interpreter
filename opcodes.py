from dataclasses import dataclass, field
from enum import IntEnum, auto
from typing import Any, List, Optional, Tuple


class Op(IntEnum):
    NOP = auto()
    POP_TOP = auto()
    DUP_TOP = auto()
    ROT_TWO = auto()

    LOAD_CONST = auto()
    LOAD_FAST = auto()
    STORE_FAST = auto()
    DELETE_FAST = auto()
    LOAD_GLOBAL = auto()
    STORE_GLOBAL = auto()
    DELETE_GLOBAL = auto()
    LOAD_DEREF = auto()
    STORE_DEREF = auto()
    DELETE_DEREF = auto()
    LOAD_CLOSURE = auto()

    UNARY_OP = auto()
    BINARY_OP = auto()
    INPLACE_OP = auto()
    COMPARE_OP = auto()

    JUMP = auto()
    JUMP_IF_FALSE = auto()
    JUMP_IF_TRUE = auto()
    JUMP_IF_FALSE_OR_POP = auto()
    JUMP_IF_TRUE_OR_POP = auto()

    BUILD_TUPLE = auto()
    BUILD_LIST = auto()
    BUILD_SET = auto()
    BUILD_DICT = auto()
    BUILD_SLICE = auto()
    LIST_EXTEND = auto()
    DICT_UPDATE = auto()
    UNPACK_SEQUENCE = auto()
    UNPACK_EX = auto()

    LOAD_ATTR = auto()
    STORE_ATTR = auto()
    DELETE_ATTR = auto()
    LOAD_SUBSCR = auto()
    STORE_SUBSCR = auto()
    DELETE_SUBSCR = auto()

    GET_ITER = auto()
    FOR_ITER = auto()

    CALL_SIMPLE = auto()
    CALL_EX = auto()
    MAKE_FUNCTION = auto()
    RETURN_VALUE = auto()
    BREAK_LOOP = auto()
    CONTINUE_LOOP = auto()

    BUILD_CLASS = auto()

    RAISE_OP = auto()
    ASSERT_OP = auto()
    EXEC_TRY = auto()
    EXEC_WITH = auto()
    EVAL_COMP = auto()
    EVAL_FSTRING = auto()

    IMPORT_NAME = auto()
    IMPORT_FROM = auto()
    IMPORT_STAR = auto()

    YIELD_VALUE = auto()
    YIELD_FROM = auto()


@dataclass
class CodeObject:
    name: str
    filename: str
    instructions: List[Tuple[Op, Any]] = field(default_factory=list)
    locations: List[Tuple[int, int]] = field(default_factory=list)
    consts: List[Any] = field(default_factory=list)
    names: List[str] = field(default_factory=list)
    varnames: List[str] = field(default_factory=list)
    freevars: List[str] = field(default_factory=list)
    cellvars: List[str] = field(default_factory=list)
    argcount: int = 0
    kwonly: List[Tuple[str, Any]] = field(default_factory=list)
    vararg: Optional[str] = None
    kwarg: Optional[str] = None
    is_generator: bool = False
    is_class_body: bool = False
    loop_ranges: List[Tuple[int, int, int, int]] = field(default_factory=list)


def disassemble(code: CodeObject, indent: int = 0) -> str:
    prefix = "  " * indent
    lines = [f"{prefix}CodeObject <{code.name}> ({code.filename})"]
    for idx, (op, arg) in enumerate(code.instructions):
        ln, col = code.locations[idx] if idx < len(code.locations) else (0, 0)
        arg_str = ""
        if arg is not None:
            if op == Op.LOAD_CONST and isinstance(arg, int) and arg < len(code.consts):
                val = code.consts[arg]
                arg_str = f"{arg} ({val!r})" if not isinstance(val, CodeObject) else f"{arg} (<code {val.name}>)"
            elif op in (Op.LOAD_FAST, Op.STORE_FAST, Op.DELETE_FAST) and isinstance(arg, int) and arg < len(code.varnames):
                arg_str = f"{arg} ({code.varnames[arg]})"
            elif op in (Op.LOAD_GLOBAL, Op.STORE_GLOBAL, Op.DELETE_GLOBAL, Op.LOAD_ATTR, Op.STORE_ATTR, Op.DELETE_ATTR) and isinstance(arg, int) and arg < len(code.names):
                arg_str = f"{arg} ({code.names[arg]})"
            else:
                arg_str = repr(arg)
        lines.append(f"{prefix}  {idx:4d}  {ln:3d}:{col:<2d}  {op.name:<22s} {arg_str}")
    for c in code.consts:
        if isinstance(c, CodeObject):
            lines.append("")
            lines.append(disassemble(c, indent + 1))
    return "\n".join(lines)