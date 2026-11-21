from ast_nodes import *
from opcodes import CodeObject, Op
from runtime import MISSING


def _collect_locals_and_refs(block, is_function=False):
    assigned = set()
    globals_decl = set()
    nonlocals_decl = set()
    referenced = set()
    child_frees = set()

    def scan_target(t):
        if isinstance(t, Var):
            assigned.add(t.name)
        elif isinstance(t, (TupleExpr, ListExpr)):
            for e in t.elements:
                scan_target(e)
        elif isinstance(t, Starred):
            scan_target(t.value)
        elif isinstance(t, (Subscript, Attribute)):
            scan_expr(t)

    def scan_expr(e):
        if e is None:
            return
        if isinstance(e, Var):
            referenced.add(e.name)
        elif isinstance(e, NamedExpr):
            assigned.add(e.name)
            scan_expr(e.value)
        elif isinstance(e, BinOp):
            scan_expr(e.left); scan_expr(e.right)
        elif isinstance(e, UnaryOp):
            scan_expr(e.operand)
        elif isinstance(e, Call):
            scan_expr(e.callee)
            for a in e.args: scan_expr(a)
            for v in (e.kwargs or {}).values(): scan_expr(v)
            for sp in (e.kw_splats or []): scan_expr(sp)
        elif isinstance(e, (TupleExpr, ListExpr, SetExpr)):
            for el in e.elements: scan_expr(el)
        elif isinstance(e, DictExpr):
            for k, v in zip(e.keys, e.values):
                if k is not None: scan_expr(k)
                scan_expr(v)
        elif isinstance(e, Subscript):
            scan_expr(e.obj); scan_expr(e.index)
        elif isinstance(e, Attribute):
            scan_expr(e.obj)
        elif isinstance(e, IfExpr):
            scan_expr(e.cond); scan_expr(e.then); scan_expr(e.other)
        elif isinstance(e, SliceExpr):
            scan_expr(e.lower); scan_expr(e.upper); scan_expr(e.step)
        elif isinstance(e, Starred):
            scan_expr(e.value)
        elif isinstance(e, (YieldExpr, YieldFromExpr)):
            scan_expr(e.value)
        elif isinstance(e, Lambda):
            for d in (e.defaults or []):
                scan_expr(d)
            _, _, _, _, c_refs = _analyze_lambda(e)
            child_frees.update(c_refs)
        elif isinstance(e, Comp):
            for cl in e.clauses:
                if cl[0] == "for":
                    scan_expr(cl[2])
                else:
                    scan_expr(cl[1])
            scan_expr(e.elt)
            scan_expr(e.elt2)

    def scan_stmt(s):
        if isinstance(s, ExprStmt):
            scan_expr(s.expr)
        elif isinstance(s, PrintStmt):
            scan_expr(s.expr)
        elif isinstance(s, Assign):
            scan_expr(s.value)
            scan_target(s.target)
        elif isinstance(s, ChainAssign):
            scan_expr(s.value)
            for t in s.targets:
                scan_target(t)
        elif isinstance(s, ReturnStmt):
            scan_expr(s.value)
        elif isinstance(s, IfStmt):
            scan_expr(s.condition)
            for st in s.then_branch.statements: scan_stmt(st)
            for c, b in s.elif_branches:
                scan_expr(c)
                for st in b.statements: scan_stmt(st)
            if s.else_branch:
                for st in s.else_branch.statements: scan_stmt(st)
        elif isinstance(s, WhileStmt):
            scan_expr(s.condition)
            for st in s.body.statements: scan_stmt(st)
            if s.else_body:
                for st in s.else_body.statements: scan_stmt(st)
        elif isinstance(s, ForStmt):
            scan_expr(s.iterable)
            scan_target(s.target)
            for st in s.body.statements: scan_stmt(st)
            if s.else_body:
                for st in s.else_body.statements: scan_stmt(st)
        elif isinstance(s, TryStmt):
            for st in s.try_block.statements: scan_stmt(st)
            for te, var, blk in (s.handlers or []):
                scan_expr(te)
                if var: assigned.add(var)
                for st in blk.statements: scan_stmt(st)
            if s.except_block and not s.handlers:
                if s.except_var: assigned.add(s.except_var)
                for st in s.except_block.statements: scan_stmt(st)
            if s.else_block:
                for st in s.else_block.statements: scan_stmt(st)
            if s.finally_block:
                for st in s.finally_block.statements: scan_stmt(st)
        elif isinstance(s, WithStmt):
            for ctx, var in s.items:
                scan_expr(ctx)
                if var: assigned.add(var)
            for st in s.body.statements: scan_stmt(st)
        elif isinstance(s, RaiseStmt):
            scan_expr(s.value)
            scan_expr(getattr(s, "cause", None))
        elif isinstance(s, AssertStmt):
            scan_expr(s.test); scan_expr(s.msg)
        elif isinstance(s, DelStmt):
            for t in s.targets:
                if isinstance(t, Var):
                    referenced.add(t.name)
                else:
                    scan_expr(t)
        elif isinstance(s, GlobalStmt):
            globals_decl.update(s.names)
        elif isinstance(s, NonlocalStmt):
            nonlocals_decl.update(s.names)
        elif isinstance(s, ImportStmt):
            for dotted, alias in s.names:
                assigned.add(alias if alias else dotted.split(".")[0])
        elif isinstance(s, FromImportStmt):
            if s.names is not None:
                for nm, alias in s.names:
                    assigned.add(alias or nm)
        elif isinstance(s, FuncDef):
            assigned.add(s.name)
            for d in (s.defaults or []): scan_expr(d)
            for _, d in (getattr(s, "kwonly", None) or []): scan_expr(d)
            for dec in (getattr(s, "decorators", None) or []): scan_expr(dec)
            _, _, _, _, c_refs = _analyze_func(s)
            child_frees.update(c_refs)
        elif isinstance(s, ClassDef):
            assigned.add(s.name)
            for b in (s.bases or ([s.parent_class] if s.parent_class else [])):
                referenced.add(b)
            if s.body is not None:
                _, _, _, _, c_refs = _analyze_class(s)
                child_frees.update(c_refs)

    for st in block.statements:
        scan_stmt(st)
    return assigned, globals_decl, nonlocals_decl, referenced, child_frees


def _analyze_func(fnode, enclosing_locals=None, is_method=False):
    params = list(fnode.params)
    for k, _ in (getattr(fnode, "kwonly", None) or []):
        params.append(k)
    if fnode.vararg:
        params.append(fnode.vararg)
    if getattr(fnode, "kwarg", None):
        params.append(fnode.kwarg)
    assigned, globals_decl, nonlocals_decl, referenced, child_frees = _collect_locals_and_refs(fnode.body, True)
    locals_set = (set(params) | assigned) - globals_decl - nonlocals_decl
    needed_by_children = child_frees - globals_decl
    cellvars = sorted(locals_set & needed_by_children)
    unresolved = (nonlocals_decl | needed_by_children | (referenced - locals_set - globals_decl))
    if enclosing_locals is None:
        freevars = unresolved
    else:
        enc = set(enclosing_locals)
        if is_method:
            enc.add("super")
        freevars = unresolved & enc
    return locals_set, globals_decl, nonlocals_decl, cellvars, freevars


def _analyze_lambda(lnode, enclosing_locals=None):
    params = list(lnode.params)
    if getattr(lnode, "vararg", None):
        params.append(lnode.vararg)
    if getattr(lnode, "kwarg", None):
        params.append(lnode.kwarg)
    block = Block([ReturnStmt(lnode.body, line=lnode.line, col=lnode.col)])
    assigned, globals_decl, nonlocals_decl, referenced, child_frees = _collect_locals_and_refs(block, True)
    locals_set = (set(params) | assigned) - globals_decl - nonlocals_decl
    unresolved = (referenced | child_frees) - locals_set - globals_decl
    freevars = unresolved if enclosing_locals is None else (unresolved & set(enclosing_locals))
    return locals_set, globals_decl, nonlocals_decl, [], freevars


def _analyze_class(cnode, enclosing_locals=()):
    if cnode.body is None:
        return set(), set(), set(), [], set()
    assigned, globals_decl, nonlocals_decl, referenced, child_frees = _collect_locals_and_refs(cnode.body, False)
    enc = set(enclosing_locals)
    outer_refs = ((referenced | child_frees) - globals_decl - assigned) & enc
    return assigned, globals_decl, nonlocals_decl, [], outer_refs


def _fold_constant(node):
    if isinstance(node, Number):
        return True, node.value
    if isinstance(node, String):
        return True, node.value
    if isinstance(node, Bool):
        return True, node.value
    if isinstance(node, NoneType):
        return True, None
    if isinstance(node, UnaryOp):
        ok, v = _fold_constant(node.operand)
        if not ok:
            return False, None
        try:
            if node.op == "-": return True, -v
            if node.op == "+": return True, +v
            if node.op == "~": return True, ~v
            if node.op == "not": return True, not v
        except Exception:
            return False, None
    if isinstance(node, BinOp) and node.op in ("+", "-", "*", "//", "%", "**", "<<", ">>", "&", "|", "^"):
        ok1, l = _fold_constant(node.left)
        ok2, r = _fold_constant(node.right)
        if not (ok1 and ok2):
            return False, None
        try:
            if node.op == "+": return True, l + r
            if node.op == "-": return True, l - r
            if node.op == "*": return True, l * r
            if node.op == "//" and r != 0: return True, l // r
            if node.op == "%" and r != 0: return True, l % r
            if node.op == "**" and (not isinstance(r, int) or r <= 100): return True, l ** r
            if node.op == "<<": return True, l << r
            if node.op == ">>": return True, l >> r
            if node.op == "&": return True, l & r
            if node.op == "|": return True, l | r
            if node.op == "^": return True, l ^ r
        except Exception:
            return False, None
    return False, None


class _FuncCompiler:
    def __init__(self, name, filename, params=(), defaults_count=0, kwonly=(), vararg=None, kwarg=None,
                 locals_set=None, globals_decl=None, nonlocals_decl=None, cellvars=(), freevars=(),
                 is_module=False, is_class_body=False, is_generator=False, allow_loop_exc=False):
        self.code = CodeObject(
            name=name,
            filename=filename,
            argcount=len(params),
            kwonly=list(kwonly),
            vararg=vararg,
            kwarg=kwarg,
            cellvars=list(cellvars),
            freevars=list(freevars),
            is_generator=is_generator,
            is_class_body=is_class_body,
        )
        self.is_module = is_module
        self.is_class_body = is_class_body
        self.allow_loop_exc = allow_loop_exc
        self.globals_decl = set(globals_decl or ())
        self.nonlocals_decl = set(nonlocals_decl or ())
        self.locals_set = set(locals_set or ())
        self.cell_set = set(cellvars)
        self.free_set = set(freevars)
        self.loop_stack = []  # list of (continue_target, break_patches, stack_delta)
        self.finally_stack = []  # list of list[patch_idx]
        self.loc = (0, 0)

        # Reserve varnames for parameters first, then cellvars/other locals
        for p in params:
            self._var_idx(p)
        for k, _ in kwonly:
            self._var_idx(k)
        if vararg:
            self._var_idx(vararg)
        if kwarg:
            self._var_idx(kwarg)
        for c in cellvars:
            self._var_idx(c)

    def _const_idx(self, val):
        for i, c in enumerate(self.code.consts):
            if type(c) is type(val) and c == val:
                return i
        self.code.consts.append(val)
        return len(self.code.consts) - 1

    def _name_idx(self, name):
        if name not in self.code.names:
            self.code.names.append(name)
        return self.code.names.index(name)

    def _var_idx(self, name):
        if name not in self.code.varnames:
            self.code.varnames.append(name)
        return self.code.varnames.index(name)

    def _deref_idx(self, name):
        if name in self.code.cellvars:
            return self.code.cellvars.index(name)
        if name not in self.code.freevars:
            self.code.freevars.append(name)
        return len(self.code.cellvars) + self.code.freevars.index(name)

    def emit(self, op, arg=None, loc=None):
        idx = len(self.code.instructions)
        self.code.instructions.append((op, arg))
        self.code.locations.append(loc or self.loc)
        return idx

    def patch(self, idx, target=None):
        if target is None:
            target = len(self.code.instructions)
        op, _ = self.code.instructions[idx]
        self.code.instructions[idx] = (op, target)

    def _set_loc(self, node):
        ln = getattr(node, "line", 0)
        col = getattr(node, "col", 0)
        if ln:
            self.loc = (ln, col)

    def emit_load(self, name, loc=None):
        if self.is_module or name in self.globals_decl:
            self.emit(Op.LOAD_GLOBAL, self._name_idx(name), loc)
        elif name in self.cell_set or name in self.nonlocals_decl or name in self.free_set:
            if name in self.locals_set and name not in self.cell_set:
                self.emit(Op.LOAD_FAST, self._var_idx(name), loc)
            else:
                self.emit(Op.LOAD_DEREF, self._deref_idx(name), loc)
        elif name in self.locals_set:
            self.emit(Op.LOAD_FAST, self._var_idx(name), loc)
        else:
            self.emit(Op.LOAD_GLOBAL, self._name_idx(name), loc)

    def emit_store(self, name, loc=None):
        if self.is_module or name in self.globals_decl:
            self.emit(Op.STORE_GLOBAL, self._name_idx(name), loc)
        elif name in self.cell_set or name in self.nonlocals_decl:
            self.emit(Op.STORE_DEREF, self._deref_idx(name), loc)
        elif self.is_class_body or name in self.locals_set:
            self.emit(Op.STORE_FAST, self._var_idx(name), loc)
        else:
            self.emit(Op.STORE_GLOBAL, self._name_idx(name), loc)

    def emit_delete(self, name, loc=None):
        if self.is_module or name in self.globals_decl:
            self.emit(Op.DELETE_GLOBAL, self._name_idx(name), loc)
        elif name in self.cell_set or name in self.nonlocals_decl:
            self.emit(Op.DELETE_DEREF, self._deref_idx(name), loc)
        elif self.is_class_body or name in self.locals_set:
            self.emit(Op.DELETE_FAST, self._var_idx(name), loc)
        else:
            self.emit(Op.DELETE_GLOBAL, self._name_idx(name), loc)

    def compile_block(self, block):
        for stmt in block.statements:
            self.compile_stmt(stmt)

    def compile_target(self, target):
        self._set_loc(target)
        if isinstance(target, Var):
            self.emit_store(target.name)
        elif isinstance(target, Subscript):
            self.compile_expr(target.obj)
            self.compile_expr(target.index)
            self.emit(Op.STORE_SUBSCR)
        elif isinstance(target, Attribute):
            self.compile_expr(target.obj)
            self.emit(Op.STORE_ATTR, self._name_idx(target.name))
        elif isinstance(target, (TupleExpr, ListExpr)):
            elems = target.elements
            star = [i for i, t in enumerate(elems) if isinstance(t, Starred)]
            if len(star) > 1:
                raise SyntaxError("multiple starred expressions in assignment")
            if not star:
                self.emit(Op.UNPACK_SEQUENCE, len(elems))
                for t in elems:
                    self.compile_target(t)
            else:
                k = star[0]
                after = len(elems) - k - 1
                self.emit(Op.UNPACK_EX, (k, after))
                for i, t in enumerate(elems):
                    self.compile_target(t.value if i == k else t)
        else:
            raise SyntaxError("cannot assign to this expression")

    def compile_stmt(self, node):
        self._set_loc(node)
        t = type(node)
        if t is PassStmt:
            return
        if t is GlobalStmt or t is NonlocalStmt:
            return
        if t is ExprStmt:
            self.compile_expr(node.expr)
            self.emit(Op.POP_TOP)
            return
        if t is PrintStmt:
            self.emit_load("print")
            self.compile_expr(node.expr)
            self.emit(Op.CALL_SIMPLE, 1)
            self.emit(Op.POP_TOP)
            return
        if t is Assign:
            self.compile_expr(node.value)
            self.compile_target(node.target)
            return
        if t is ChainAssign:
            self.compile_expr(node.value)
            for i, tgt in enumerate(node.targets):
                if i < len(node.targets) - 1:
                    self.emit(Op.DUP_TOP)
                self.compile_target(tgt)
            return
        if t is ReturnStmt:
            if node.value is not None:
                self.compile_expr(node.value)
            else:
                self.emit(Op.LOAD_CONST, self._const_idx(None))
            if self.finally_stack:
                self.emit(Op.WRAP_EXC, "return")
                j = self.emit(Op.JUMP, None)
                self.finally_stack[-1].append(j)
            else:
                self.emit(Op.RETURN_VALUE)
            return
        if t is BreakStmt:
            if not self.loop_stack:
                if self.allow_loop_exc:
                    self.emit(Op.BREAK_LOOP)
                    return
                raise SyntaxError("'break' outside loop")
            j = self.emit(Op.JUMP, None)
            self.loop_stack[-1][1].append(j)
            return
        if t is ContinueStmt:
            if not self.loop_stack:
                if self.allow_loop_exc:
                    self.emit(Op.CONTINUE_LOOP)
                    return
                raise SyntaxError("'continue' outside loop")
            self.emit(Op.JUMP, self.loop_stack[-1][0])
            return
        if t is IfStmt:
            end_jumps = []
            self.compile_expr(node.condition)
            jf = self.emit(Op.JUMP_IF_FALSE, None)
            self.compile_block(node.then_branch)
            end_jumps.append(self.emit(Op.JUMP, None))
            self.patch(jf)
            for cond, body in node.elif_branches:
                self.compile_expr(cond)
                jf = self.emit(Op.JUMP_IF_FALSE, None)
                self.compile_block(body)
                end_jumps.append(self.emit(Op.JUMP, None))
                self.patch(jf)
            if node.else_branch:
                self.compile_block(node.else_branch)
            for j in end_jumps:
                self.patch(j)
            return
        if t is WhileStmt:
            loop_start = len(self.code.instructions)
            break_patches = []
            self.loop_stack.append((loop_start, break_patches, 0))
            self.compile_expr(node.condition)
            jf = self.emit(Op.JUMP_IF_FALSE, None)
            self.compile_block(node.body)
            self.emit(Op.JUMP, loop_start)
            self.patch(jf)
            loop_end_body = len(self.code.instructions)
            self.loop_stack.pop()
            if node.else_body is not None:
                self.compile_block(node.else_body)
            after_else = len(self.code.instructions)
            for bp in break_patches:
                self.patch(bp)
            self.code.loop_ranges.append((loop_start, loop_end_body, loop_start, after_else))
            return
        if t is ForStmt:
            self.compile_expr(node.iterable)
            self.emit(Op.GET_ITER)
            loop_start = len(self.code.instructions)
            break_patches = []
            self.loop_stack.append((loop_start, break_patches, 1))
            for_iter = self.emit(Op.FOR_ITER, None)
            self.compile_target(node.target)
            self.compile_block(node.body)
            self.emit(Op.JUMP, loop_start)
            self.patch(for_iter)
            loop_end_body = len(self.code.instructions)
            self.loop_stack.pop()
            if node.else_body is not None:
                self.compile_block(node.else_body)
            after_else = len(self.code.instructions)
            for bp in break_patches:
                self.patch(bp)
            self.code.loop_ranges.append((loop_start, loop_end_body, loop_start, after_else))
            return
        if t is DelStmt:
            for tgt in node.targets:
                if isinstance(tgt, Var):
                    self.emit_delete(tgt.name)
                elif isinstance(tgt, Subscript):
                    self.compile_expr(tgt.obj)
                    self.compile_expr(tgt.index)
                    self.emit(Op.DELETE_SUBSCR)
                elif isinstance(tgt, Attribute):
                    self.compile_expr(tgt.obj)
                    self.emit(Op.DELETE_ATTR, self._name_idx(tgt.name))
                else:
                    raise SyntaxError("cannot delete this expression")
            return
        if t is FuncDef:
            enc = set() if self.is_module else (self.free_set if self.is_class_body else (self.locals_set | self.free_set | self.cell_set))
            fn_code = compile_funcdef(node, self.code.filename, is_method=self.is_class_body, enclosing_locals=enc)
            # Push defaults, kwonly defaults, closure cells, then code object
            for d in node.defaults:
                if d is not None:
                    self.compile_expr(d)
                else:
                    self.emit(Op.LOAD_CONST, self._const_idx(MISSING))
            for _, d in (getattr(node, "kwonly", None) or []):
                if d is not None:
                    self.compile_expr(d)
                else:
                    self.emit(Op.LOAD_CONST, self._const_idx(MISSING))
            for fv in fn_code.freevars:
                if fv in self.cell_set or fv in self.free_set or fv in self.nonlocals_decl:
                    self.emit(Op.LOAD_CLOSURE, self._deref_idx(fv))
                else:
                    self.emit(Op.LOAD_CONST, self._const_idx(MISSING))
            self.emit(Op.LOAD_CONST, self._const_idx(fn_code))
            self.emit(Op.MAKE_FUNCTION, (len(node.defaults), len(getattr(node, "kwonly", None) or []), len(fn_code.freevars), self.is_class_body))
            for dec in reversed(node.decorators or []):
                self.compile_expr(dec)
                self.emit(Op.ROT_TWO)
                self.emit(Op.CALL_SIMPLE, 1)
            self.emit_store(node.name)
            return
        if t is ClassDef:
            names = node.bases if node.bases is not None else ([node.parent_class] if node.parent_class else [])
            for b in names:
                self.emit_load(b)
            enc = set() if self.is_module else (self.free_set if self.is_class_body else (self.locals_set | self.free_set | self.cell_set))
            cls_code = compile_classdef(node, self.code.filename, enclosing_locals=enc)
            for fv in cls_code.freevars:
                if fv in self.cell_set or fv in self.free_set or fv in self.nonlocals_decl:
                    self.emit(Op.LOAD_CLOSURE, self._deref_idx(fv))
                else:
                    self.emit(Op.LOAD_CONST, self._const_idx(MISSING))
            self.emit(Op.LOAD_CONST, self._const_idx(cls_code))
            self.emit(Op.BUILD_CLASS, (node.name, len(names), len(cls_code.freevars)))
            self.emit_store(node.name)
            return
        if t is RaiseStmt:
            if node.value is None:
                self.emit(Op.RAISE_OP, 0)
            elif getattr(node, "cause", None) is not None:
                self.compile_expr(node.value)
                self.compile_expr(node.cause)
                self.emit(Op.RAISE_OP, 2)
            else:
                self.compile_expr(node.value)
                self.emit(Op.RAISE_OP, 1)
            return
        if t is AssertStmt:
            self.compile_expr(node.test)
            if node.msg is not None:
                self.compile_expr(node.msg)
                self.emit(Op.ASSERT_OP, 1)
            else:
                self.emit(Op.ASSERT_OP, 0)
            return
        if t is TryStmt:
            self._compile_try(node)
            return
        if t is WithStmt:
            self.emit(Op.EXEC_WITH, node)
            return
        if t is ImportStmt:
            self.emit(Op.IMPORT_NAME, node)
            return
        if t is FromImportStmt:
            if node.names is None:
                self.emit(Op.IMPORT_STAR, node)
            else:
                self.emit(Op.IMPORT_FROM, node)
            return
        raise NotImplementedError(f"Compiler: statement not implemented: {t.__name__}")

    def _compile_try(self, node):
        depth = sum(x[2] for x in self.loop_stack)
        handlers = node.handlers
        if handlers is None and node.except_block is not None:
            handlers = [(None, node.except_var, node.except_block)]
        handlers = handlers or []

        def compile_body():
            if not handlers:
                self.compile_block(node.try_block)
                return
            try_start = len(self.code.instructions)
            self.compile_block(node.try_block)
            try_end = len(self.code.instructions)
            else_j = self.emit(Op.JUMP, None)
            handler_pc = len(self.code.instructions)
            end_jumps = []
            for type_expr, var, blk in handlers:
                next_j = None
                if type_expr is not None:
                    self.emit(Op.DUP_TOP)
                    self.compile_expr(type_expr)
                    self.emit(Op.EXC_MATCH)
                    next_j = self.emit(Op.JUMP_IF_FALSE, None)
                if var:
                    self.emit(Op.EXC_BIND, type_expr is None)
                    self.emit_store(var)
                self.emit(Op.POP_TOP)
                self.compile_block(blk)
                end_jumps.append(self.emit(Op.JUMP, None))
                if next_j is not None:
                    self.patch(next_j)
            self.emit(Op.RAISE_OBJ)
            self.patch(else_j)
            if node.else_block is not None:
                self.compile_block(node.else_block)
            for ej in end_jumps:
                self.patch(ej)
            self.code.exc_table.append((try_start, try_end, handler_pc, depth))

        if node.finally_block is None:
            compile_body()
            return

        fin_patches = []
        self.finally_stack.append(fin_patches)
        fin_start = len(self.code.instructions)
        compile_body()
        fin_end = len(self.code.instructions)
        self.emit(Op.LOAD_CONST, self._const_idx((None, None)))
        fin_normal_j = self.emit(Op.JUMP, None)
        fin_exc_pc = len(self.code.instructions)
        self.emit(Op.WRAP_EXC, "exc")
        fin_body_pc = len(self.code.instructions)
        self.patch(fin_normal_j, fin_body_pc)
        for fp in fin_patches:
            self.patch(fp, fin_body_pc)
        self.finally_stack.pop()
        self.compile_block(node.finally_block)
        self.emit(Op.END_FINALLY)
        self.code.exc_table.append((fin_start, fin_end, fin_exc_pc, depth))

    def compile_expr(self, node):
        self._set_loc(node)
        ok, cval = _fold_constant(node)
        if ok:
            self.emit(Op.LOAD_CONST, self._const_idx(cval))
            return
        t = type(node)
        if t is Const:
            self.emit(Op.LOAD_CONST, self._const_idx(node.value))
            return
        if t is Var:
            self.emit_load(node.name)
            return
        if t is NamedExpr:
            self.compile_expr(node.value)
            self.emit(Op.DUP_TOP)
            self.emit_store(node.name)
            return
        if t is UnaryOp:
            self.compile_expr(node.operand)
            self.emit(Op.UNARY_OP, node.op)
            return
        if t is BinOp:
            if node.op == "and":
                self.compile_expr(node.left)
                j = self.emit(Op.JUMP_IF_FALSE_OR_POP, None)
                self.compile_expr(node.right)
                self.patch(j)
                return
            if node.op == "or":
                self.compile_expr(node.left)
                j = self.emit(Op.JUMP_IF_TRUE_OR_POP, None)
                self.compile_expr(node.right)
                self.patch(j)
                return
            self.compile_expr(node.left)
            self.compile_expr(node.right)
            if node.op.endswith("=") and node.op not in ("==", "!=", "<=", ">="):
                self.emit(Op.INPLACE_OP, node.op)
            elif node.op in ("==", "!=", "<", ">", "<=", ">=", "in", "not in", "is", "is not"):
                self.emit(Op.COMPARE_OP, node.op)
            else:
                self.emit(Op.BINARY_OP, node.op)
            return
        if t is IfExpr:
            self.compile_expr(node.cond)
            jf = self.emit(Op.JUMP_IF_FALSE, None)
            self.compile_expr(node.then)
            je = self.emit(Op.JUMP, None)
            self.patch(jf)
            self.compile_expr(node.other)
            self.patch(je)
            return
        if t is Subscript:
            self.compile_expr(node.obj)
            self.compile_expr(node.index)
            self.emit(Op.LOAD_SUBSCR)
            return
        if t is Attribute:
            self.compile_expr(node.obj)
            self.emit(Op.LOAD_ATTR, self._name_idx(node.name))
            return
        if t is SliceExpr:
            for part in (node.lower, node.upper, node.step):
                if part is not None:
                    self.compile_expr(part)
                else:
                    self.emit(Op.LOAD_CONST, self._const_idx(None))
            self.emit(Op.BUILD_SLICE)
            return
        if t is ListExpr or t is TupleExpr or t is SetExpr:
            has_star = any(isinstance(e, Starred) for e in node.elements)
            if not has_star:
                for e in node.elements:
                    self.compile_expr(e)
                op = Op.BUILD_LIST if t is ListExpr else (Op.BUILD_TUPLE if t is TupleExpr else Op.BUILD_SET)
                self.emit(op, len(node.elements))
            else:
                self.emit(Op.BUILD_LIST, 0)
                for e in node.elements:
                    if isinstance(e, Starred):
                        self.compile_expr(e.value)
                        self.emit(Op.LIST_EXTEND, True)
                    else:
                        self.compile_expr(e)
                        self.emit(Op.LIST_EXTEND, False)
                if t is TupleExpr:
                    self.emit(Op.CALL_SIMPLE, -1)  # unused; convert below
                    self.code.instructions.pop()
                    self.code.locations.pop()
                    self.emit(Op.BUILD_TUPLE, -1)
                elif t is SetExpr:
                    self.emit(Op.BUILD_SET, -1)
            return
        if t is DictExpr:
            has_splat = any(k is None for k in node.keys)
            if not has_splat:
                for k, v in zip(node.keys, node.values):
                    self.compile_expr(k)
                    self.compile_expr(v)
                self.emit(Op.BUILD_DICT, len(node.keys))
            else:
                self.emit(Op.BUILD_DICT, 0)
                for k, v in zip(node.keys, node.values):
                    if k is None:
                        self.compile_expr(v)
                        self.emit(Op.DICT_UPDATE, True)
                    else:
                        self.compile_expr(k)
                        self.compile_expr(v)
                        self.emit(Op.DICT_UPDATE, False)
            return
        if t is Call:
            plain = (not node.kwargs and not node.kw_splats and not any(isinstance(a, Starred) for a in node.args))
            self.compile_expr(node.callee)
            if plain:
                for a in node.args:
                    self.compile_expr(a)
                self.emit(Op.CALL_SIMPLE, len(node.args))
            else:
                # Build args list, kwargs dict
                self.emit(Op.BUILD_LIST, 0)
                for a in node.args:
                    if isinstance(a, Starred):
                        self.compile_expr(a.value)
                        self.emit(Op.LIST_EXTEND, True)
                    else:
                        self.compile_expr(a)
                        self.emit(Op.LIST_EXTEND, False)
                self.emit(Op.BUILD_DICT, 0)
                for k, v in (node.kwargs or {}).items():
                    self.emit(Op.LOAD_CONST, self._const_idx(k))
                    self.compile_expr(v)
                    self.emit(Op.DICT_UPDATE, False)
                for sp in (node.kw_splats or []):
                    self.compile_expr(sp)
                    self.emit(Op.DICT_UPDATE, True)
                self.emit(Op.CALL_EX)
            return
        if t is Lambda:
            enc = set() if self.is_module else (self.free_set if self.is_class_body else (self.locals_set | self.free_set | self.cell_set))
            lam_code = compile_lambda(node, self.code.filename, enclosing_locals=enc)
            for d in (node.defaults or []):
                if d is not None:
                    self.compile_expr(d)
                else:
                    self.emit(Op.LOAD_CONST, self._const_idx(MISSING))
            for fv in lam_code.freevars:
                if fv in self.cell_set or fv in self.free_set or fv in self.nonlocals_decl:
                    self.emit(Op.LOAD_CLOSURE, self._deref_idx(fv))
                else:
                    self.emit(Op.LOAD_CONST, self._const_idx(MISSING))
            self.emit(Op.LOAD_CONST, self._const_idx(lam_code))
            self.emit(Op.MAKE_FUNCTION, (len(node.defaults or []), 0, len(lam_code.freevars), False))
            return
        if t is FString:
            self.emit(Op.EVAL_FSTRING, node.value)
            return
        if t is Comp:
            self.emit(Op.EVAL_COMP, node)
            return
        if t is YieldExpr:
            if node.value is not None:
                self.compile_expr(node.value)
            else:
                self.emit(Op.LOAD_CONST, self._const_idx(None))
            self.emit(Op.YIELD_VALUE)
            return
        if t is YieldFromExpr:
            self.compile_expr(node.value)
            self.emit(Op.YIELD_FROM)
            return
        if t is Starred:
            raise SyntaxError("can't use starred expression here")
        raise NotImplementedError(f"Compiler: expression not implemented: {t.__name__}")


def compile_funcdef(fnode, filename, is_method=False, enclosing_locals=()):
    from generators import is_generator_def
    locals_set, globals_decl, nonlocals_decl, cellvars, freevars = _analyze_func(fnode, enclosing_locals, is_method=is_method)
    kwonly = getattr(fnode, "kwonly", None) or []
    fc = _FuncCompiler(
        name=fnode.name,
        filename=filename,
        params=fnode.params,
        kwonly=kwonly,
        vararg=fnode.vararg,
        kwarg=getattr(fnode, "kwarg", None),
        locals_set=locals_set,
        globals_decl=globals_decl,
        nonlocals_decl=nonlocals_decl,
        cellvars=cellvars,
        freevars=sorted(freevars),
        is_generator=is_generator_def(fnode),
    )
    fc.compile_block(fnode.body)
    fc.emit(Op.LOAD_CONST, fc._const_idx(None), (fnode.line, fnode.col))
    fc.emit(Op.RETURN_VALUE, None, (fnode.line, fnode.col))
    return fc.code


def compile_lambda(lnode, filename, enclosing_locals=()):
    locals_set, globals_decl, nonlocals_decl, cellvars, freevars = _analyze_lambda(lnode, enclosing_locals)
    fc = _FuncCompiler(
        name="<lambda>",
        filename=filename,
        params=lnode.params,
        vararg=getattr(lnode, "vararg", None),
        kwarg=getattr(lnode, "kwarg", None),
        locals_set=locals_set,
        globals_decl=globals_decl,
        nonlocals_decl=nonlocals_decl,
        cellvars=cellvars,
        freevars=sorted(freevars),
    )
    fc.compile_expr(lnode.body)
    fc.emit(Op.RETURN_VALUE, None, (lnode.line, lnode.col))
    return fc.code


def compile_classdef(cnode, filename, enclosing_locals=()):
    locals_set, globals_decl, nonlocals_decl, cellvars, freevars = _analyze_class(cnode, enclosing_locals)
    fc = _FuncCompiler(
        name=cnode.name,
        filename=filename,
        locals_set=locals_set,
        globals_decl=globals_decl,
        nonlocals_decl=nonlocals_decl,
        cellvars=cellvars,
        freevars=sorted(freevars),
        is_class_body=True,
    )
    if cnode.body is not None:
        fc.compile_block(cnode.body)
    fc.emit(Op.LOAD_CONST, fc._const_idx(None), (cnode.line, cnode.col))
    fc.emit(Op.RETURN_VALUE, None, (cnode.line, cnode.col))
    return fc.code


def compile_module(block, filename="<main>", name="<module>"):
    fc = _FuncCompiler(name=name, filename=filename, is_module=True)
    fc.compile_block(block)
    fc.emit(Op.LOAD_CONST, fc._const_idx(None))
    fc.emit(Op.RETURN_VALUE)
    return fc.code