import operator
import os
from types import FunctionType as _FunctionType

from ast_nodes import Starred, TupleExpr, ListExpr, Var
from builtins_env import setup_builtins, setup_exceptions
from compiler import compile_module
from diagnostics import format_traceback
from environment import Environment
from modules import exec_from_import, exec_import
from opcodes import Op
from runtime import (
    FAST_BINOPS, MISSING, BreakException, ContinueException, PyClassMethod,
    PyProperty, PyRaise, PyStaticMethod, ReturnException, SuperView,
    UserClass, UserInstance, UserInstanceProxy, call_any, del_item,
    get_attr, get_item, instance_truth, make_raise, set_attr, set_item,
    strip_line, to_exc_instance, exc_match, _cm_parts,
)


class Cell:
    __slots__ = ("value",)

    def __init__(self, value=MISSING):
        self.value = value


class Frame:
    __slots__ = ("code", "globals", "locals", "cells", "stack", "pc", "owner_class", "_sub_iter", "_sub_send", "_sub_err", "_pending_exc")

    def __init__(self, code, globals_dict, locals_list=None, cells=None, owner_class=None):
        self.code = code
        self.globals = globals_dict
        self.locals = locals_list if locals_list is not None else [MISSING] * len(code.varnames)
        self.cells = cells or []
        self.stack = []
        self.pc = 0
        self.owner_class = owner_class
        self._sub_iter = None
        self._sub_send = None
        self._sub_err = None
        self._pending_exc = None


class VMGenerator:
    def __init__(self, vm, frame, name):
        self.vm = vm
        self.frame = frame
        self.name = name
        self.state = "created"

    def __iter__(self):
        return self

    def __next__(self):
        return self._step(None)

    def send(self, value=None):
        if self.state == "created" and value is not None:
            raise TypeError("can't send non-None value to a just-started generator")
        return self._step(value)

    def throw(self, exc, val=None, tb=None):
        target = val if isinstance(val, UserInstance) else exc
        err = make_raise(self.vm, target)
        if self.state == "created":
            self.state = "done"
            raise err
        return self._step(None, err=err)

    def close(self):
        if self.state in ("created", "done"):
            self.state = "done"
            return None
        if self.state == "running":
            raise ValueError("generator already executing")
        from generators import _GenExit
        try:
            self._step(None, err=_GenExit())
        except (StopIteration, _GenExit):
            self.state = "done"
            return None
        raise RuntimeError("generator ignored GeneratorExit")

    def _step(self, value, err=None):
        if self.state == "running":
            raise ValueError("generator already executing")
        if self.state == "done":
            if err is not None:
                raise err
            raise StopIteration
        if self.state == "suspended":
            if getattr(self.frame, "_sub_iter", None) is not None:
                self.frame._sub_send = value
                self.frame._sub_err = err
            elif err is not None:
                self.frame._pending_exc = err
            else:
                self.frame.stack.append(value)
        self.state = "running"
        try:
            res = self.vm._run_frame(self.frame, yield_capable=True)
        except _YieldSignal as y:
            self.state = "suspended"
            return y.value
        except BaseException:
            self.state = "done"
            raise
        self.state = "done"
        raise StopIteration(res)

    def __repr__(self):
        return f"<generator object {self.name}>"


VMGenerator.__name__ = "generator"


class _YieldSignal(BaseException):
    __slots__ = ("value",)

    def __init__(self, value):
        self.value = value


class _FrameEnvBridge:
    """Adapts a VM Frame + globals dict to the Environment interface for helpers."""
    def __init__(self, vm, frame):
        self.vm = vm
        self.frame = frame
        self.vars = frame.globals
        self.parent = None
        self.global_names = frozenset()
        self.nonlocal_names = frozenset()

    def get(self, name):
        code = self.frame.code
        if name in code.varnames:
            idx = code.varnames.index(name)
            v = self.frame.locals[idx]
            if v is not MISSING:
                return v
        if name in code.cellvars:
            v = self.frame.cells[code.cellvars.index(name)].value
            if v is not MISSING:
                return v
        if name in code.freevars:
            v = self.frame.cells[len(code.cellvars) + code.freevars.index(name)].value
            if v is not MISSING:
                return v
        if name in self.frame.globals:
            return self.frame.globals[name]
        raise NameError(f"Name '{name}' is not defined")

    def set(self, name, value):
        code = self.frame.code
        if name in code.cellvars:
            self.frame.cells[code.cellvars.index(name)].value = value
        elif name in code.freevars:
            self.frame.cells[len(code.cellvars) + code.freevars.index(name)].value = value
        elif not code.is_class_body and name in code.varnames:
            self.frame.locals[code.varnames.index(name)] = value
        else:
            self.frame.globals[name] = value


class VM:
    def __init__(self):
        self.global_env = Environment()
        self.call_stack = []
        self.sources = {}
        self.current_file = "<main>"
        setup_exceptions(self)
        setup_builtins(self)
        self.builtins_snapshot = dict(self.global_env.vars)
        self.modules = {}
        self.virtual_modules = {}
        self.search_paths = [os.getcwd()]
        self.global_env.set("__name__", "__main__")

    def register_source(self, filename, source):
        if filename and source is not None:
            self.sources[filename] = source.splitlines()

    def set_script(self, path):
        path = os.path.abspath(path)
        self.current_file = path
        self.global_env.set("__file__", path)
        folder = os.path.dirname(path)
        self.search_paths = [folder] + [p for p in self.search_paths if p != folder]

    def register_module(self, name, source):
        self.virtual_modules[name] = source
        self.modules.pop(name, None)

    def _to_string(self, val):
        if isinstance(val, UserInstance):
            str_method = val.cls.get_method("__str__")
            if str_method:
                try:
                    result = str_method(val)
                    if result is not None:
                        return str(result)
                except Exception as e:
                    return f"<error: {e}>"
            return repr(val)
        return str(val)

    def _is_truthy(self, val):
        if val is None or val is False:
            return False
        if isinstance(val, (int, float)) and val == 0:
            return False
        if isinstance(val, (str, list, dict, set, tuple, frozenset)) and len(val) == 0:
            return False
        if isinstance(val, UserInstance):
            return instance_truth(val)
        return True

    def _eval_block(self, block, env):
        # Used by modules.py when loading PyModule via VM
        code = compile_module(block, filename=self.current_file, name=env.vars.get("__name__", "<module>"))
        frame = Frame(code, env.vars)
        return self._run_frame(frame)

    def _eval_expr(self, expr, env):
        # Used by exec_try / exec_with / _assign_to helpers
        from ast_nodes import ReturnStmt
        code = compile_module(type("_B", (), {"statements": [ReturnStmt(expr)]})(), filename=self.current_file)
        # Re-compile expression with env-aware wrapper
        from compiler import _FuncCompiler
        fc = _FuncCompiler("<expr>", self.current_file, is_module=True)
        fc.compile_expr(expr)
        fc.emit(Op.RETURN_VALUE)
        g = self.global_env.vars if isinstance(env, Environment) and env.parent is None else _EnvDictProxy(env)
        return self._run_frame(Frame(fc.code, g))

    def run(self, ast, source=None, filename=None):
        if filename is not None:
            self.current_file = filename
        if source is not None:
            self.register_source(self.current_file, source)
        try:
            code = compile_module(ast, filename=self.current_file)
            self._run_frame(Frame(code, self.global_env.vars))
        except SyntaxError as e:
            ln = getattr(e, "lineno", 0) or 0
            col = getattr(e, "offset", 0) or 0
            fn = getattr(e, "filename", None) or self.current_file
            print(format_traceback("SyntaxError", str(e), fn, ln, col, self.sources))
        except Exception as e:
            tb = getattr(e, "_pysubset_tb", None) or self.call_stack
            loc = getattr(e, "_pysubset_loc", None)
            if loc is not None:
                ef, el, ec = loc
            elif isinstance(e, PyRaise) and e.line:
                ef, el, ec = self.current_file, e.line, 0
            else:
                ef, el, ec = self.current_file, 0, 0
            if isinstance(e, PyRaise):
                kind = e.inst.cls.name if e.inst is not None else "RuntimeError"
                msg = e.message() if e.inst is not None else str(e.legacy)
            else:
                kind = type(e).__name__
                msg = str(e)
            print(format_traceback(kind, msg, ef, el, ec, self.sources, tb))

    def _run_frame(self, frame, yield_capable=False, in_subblock=False):
        code = frame.code
        insns = code.instructions
        locs = code.locations
        consts = code.consts
        names = code.names
        g = frame.globals
        loc = frame.locals
        cells = frame.cells
        stack = frame.stack
        n_cells = len(code.cellvars)
        pc = frame.pc

        while frame.pc < len(insns):
            try:
                while frame.pc < len(insns):
                    if yield_capable and getattr(frame, "_pending_exc", None) is not None:
                        exc = frame._pending_exc
                        frame._pending_exc = None
                        raise exc
                    pc = frame.pc
                    op, arg = insns[pc]
                    frame.pc = pc + 1
                    if op == Op.LOAD_CONST:
                        stack.append(consts[arg])
                    elif op == Op.LOAD_FAST:
                        v = loc[arg]
                        if v is MISSING:
                            raise NameError(f"cannot access local variable '{code.varnames[arg]}' where it is not associated with a value")
                        stack.append(v)
                    elif op == Op.STORE_FAST:
                        loc[arg] = stack.pop()
                    elif op == Op.DELETE_FAST:
                        if loc[arg] is MISSING:
                            raise NameError(f"cannot access local variable '{code.varnames[arg]}' where it is not associated with a value")
                        loc[arg] = MISSING
                    elif op == Op.LOAD_GLOBAL:
                        nm = names[arg]
                        if nm in g:
                            stack.append(g[nm])
                        elif nm in self.global_env.vars:
                            stack.append(self.global_env.vars[nm])
                        else:
                            raise NameError(f"Name '{nm}' is not defined")
                    elif op == Op.STORE_GLOBAL:
                        g[names[arg]] = stack.pop()
                    elif op == Op.DELETE_GLOBAL:
                        nm = names[arg]
                        if nm not in g:
                            raise NameError(f"Name '{nm}' is not defined")
                        del g[nm]
                    elif op == Op.LOAD_DEREF:
                        v = cells[arg].value
                        if v is MISSING:
                            name = code.cellvars[arg] if arg < n_cells else code.freevars[arg - n_cells]
                            raise NameError(f"cannot access free variable '{name}' where it is not associated with a value")
                        stack.append(v)
                    elif op == Op.STORE_DEREF:
                        cells[arg].value = stack.pop()
                    elif op == Op.DELETE_DEREF:
                        if cells[arg].value is MISSING:
                            name = code.cellvars[arg] if arg < n_cells else code.freevars[arg - n_cells]
                            raise NameError(f"cannot access free variable '{name}' where it is not associated with a value")
                        cells[arg].value = MISSING
                    elif op == Op.LOAD_CLOSURE:
                        stack.append(cells[arg])
                    elif op == Op.POP_TOP:
                        stack.pop()
                    elif op == Op.DUP_TOP:
                        stack.append(stack[-1])
                    elif op == Op.ROT_TWO:
                        stack[-1], stack[-2] = stack[-2], stack[-1]
                    elif op == Op.UNARY_OP:
                        v = stack.pop()
                        if arg == "-": stack.append(-v)
                        elif arg == "+": stack.append(+v)
                        elif arg == "~": stack.append(~v)
                        elif arg == "not": stack.append(not self._is_truthy(v))
                    elif op == Op.BINARY_OP:
                        r = stack.pop(); l = stack.pop()
                        fn = FAST_BINOPS.get(arg)
                        if fn is not None:
                            stack.append(fn(l, r))
                        elif arg == "&": stack.append(l & r)
                        elif arg == "|": stack.append(l | r)
                        elif arg == "^": stack.append(l ^ r)
                        elif arg == "<<": stack.append(l << r)
                        elif arg == ">>": stack.append(l >> r)
                        else: raise RuntimeError(f"Unknown operator {arg}")
                    elif op == Op.INPLACE_OP:
                        r = stack.pop(); l = stack.pop()
                        stack.append(FAST_BINOPS[arg](l, r))
                    elif op == Op.COMPARE_OP:
                        r = stack.pop(); l = stack.pop()
                        if arg == "==": stack.append(l == r)
                        elif arg == "!=": stack.append(l != r)
                        elif arg == "<": stack.append(l < r)
                        elif arg == ">": stack.append(l > r)
                        elif arg == "<=": stack.append(l <= r)
                        elif arg == ">=": stack.append(l >= r)
                        elif arg == "in": stack.append(l in r)
                        elif arg == "not in": stack.append(l not in r)
                        elif arg == "is": stack.append(l is r)
                        elif arg == "is not": stack.append(l is not r)
                    elif op == Op.JUMP:
                        frame.pc = arg
                    elif op == Op.JUMP_IF_FALSE:
                        if not self._is_truthy(stack.pop()):
                            frame.pc = arg
                    elif op == Op.JUMP_IF_TRUE:
                        if self._is_truthy(stack.pop()):
                            frame.pc = arg
                    elif op == Op.JUMP_IF_FALSE_OR_POP:
                        if not self._is_truthy(stack[-1]):
                            frame.pc = arg
                        else:
                            stack.pop()
                    elif op == Op.JUMP_IF_TRUE_OR_POP:
                        if self._is_truthy(stack[-1]):
                            frame.pc = arg
                        else:
                            stack.pop()
                    elif op == Op.BUILD_LIST:
                        if arg == 0:
                            stack.append([])
                        else:
                            items = stack[-arg:]
                            del stack[-arg:]
                            stack.append(items)
                    elif op == Op.BUILD_TUPLE:
                        if arg == -1:
                            stack.append(tuple(stack.pop()))
                        elif arg == 0:
                            stack.append(())
                        else:
                            items = tuple(stack[-arg:])
                            del stack[-arg:]
                            stack.append(items)
                    elif op == Op.BUILD_SET:
                        if arg == -1:
                            stack.append(set(stack.pop()))
                        elif arg == 0:
                            stack.append(set())
                        else:
                            items = set(stack[-arg:])
                            del stack[-arg:]
                            stack.append(items)
                    elif op == Op.BUILD_DICT:
                        if arg == 0:
                            stack.append({})
                        else:
                            d = {}
                            pairs = stack[-2 * arg:]
                            del stack[-2 * arg:]
                            for i in range(0, len(pairs), 2):
                                d[pairs[i]] = pairs[i + 1]
                            stack.append(d)
                    elif op == Op.BUILD_SLICE:
                        st = stack.pop(); up = stack.pop(); lo = stack.pop()
                        stack.append(slice(lo, up, st))
                    elif op == Op.LIST_EXTEND:
                        val = stack.pop()
                        if arg: stack[-1].extend(val)
                        else: stack[-1].append(val)
                    elif op == Op.DICT_UPDATE:
                        if arg:
                            mp = stack.pop()
                            stack[-1].update(mp)
                        else:
                            v = stack.pop(); k = stack.pop()
                            stack[-1][k] = v
                    elif op == Op.UNPACK_SEQUENCE:
                        items = list(stack.pop())
                        if len(items) < arg:
                            raise ValueError(f"not enough values to unpack (expected {arg}, got {len(items)})")
                        if len(items) > arg:
                            raise ValueError(f"too many values to unpack (expected {arg})")
                        for item in reversed(items):
                            stack.append(item)
                    elif op == Op.UNPACK_EX:
                        k, after = arg
                        items = list(stack.pop())
                        if len(items) < k + after:
                            raise ValueError(f"not enough values to unpack (expected at least {k + after}, got {len(items)})")
                        mid = items[k:len(items) - after] if after else items[k:]
                        head = items[:k]
                        tail = items[len(items) - after:] if after else []
                        for item in reversed(tail):
                            stack.append(item)
                        stack.append(mid)
                        for item in reversed(head):
                            stack.append(item)
                    elif op == Op.LOAD_ATTR:
                        stack.append(get_attr(stack.pop(), names[arg]))
                    elif op == Op.STORE_ATTR:
                        nm = names[arg]
                        obj = stack.pop(); val = stack.pop()
                        set_attr(obj, nm, val)
                    elif op == Op.DELETE_ATTR:
                        obj = stack.pop()
                        nm = names[arg]
                        if isinstance(obj, UserInstance):
                            del obj.attributes[nm]
                        else:
                            delattr(obj, nm)
                    elif op == Op.LOAD_SUBSCR:
                        idx = stack.pop(); obj = stack.pop()
                        stack.append(get_item(obj, idx))
                    elif op == Op.STORE_SUBSCR:
                        idx = stack.pop(); obj = stack.pop(); val = stack.pop()
                        set_item(obj, idx, val)
                    elif op == Op.DELETE_SUBSCR:
                        idx = stack.pop(); obj = stack.pop()
                        del_item(obj, idx)
                    elif op == Op.GET_ITER:
                        stack.append(iter(stack.pop()))
                    elif op == Op.FOR_ITER:
                        it = stack[-1]
                        try:
                            stack.append(next(it))
                        except StopIteration:
                            stack.pop()
                            frame.pc = arg
                    elif op == Op.CALL_SIMPLE:
                        if arg == 0:
                            callee = stack.pop()
                            stack.append(callee() if type(callee) is _FunctionType else call_any(callee))
                        else:
                            args = stack[-arg:]
                            del stack[-arg:]
                            callee = stack.pop()
                            stack.append(callee(*args) if type(callee) is _FunctionType else call_any(callee, *args))
                    elif op == Op.CALL_EX:
                        kwargs = stack.pop(); args = stack.pop(); callee = stack.pop()
                        stack.append(call_any(callee, *args, **kwargs))
                    elif op == Op.MAKE_FUNCTION:
                        n_def, n_kwdef, n_free, is_method = arg
                        fn_code = stack.pop()
                        free_cells = [stack.pop() for _ in range(n_free)][::-1]
                        kw_defaults = [stack.pop() for _ in range(n_kwdef)][::-1]
                        defaults = [stack.pop() for _ in range(n_def)][::-1]
                        free_cells = [c if isinstance(c, Cell) else Cell(MISSING) for c in free_cells]
                        stack.append(self._make_vm_func(fn_code, g, defaults, kw_defaults, free_cells, is_method, frame.owner_class))
                    elif op == Op.BUILD_CLASS:
                        cname, n_bases, n_free = arg
                        cls_code = stack.pop()
                        free_cells = [stack.pop() for _ in range(n_free)][::-1]
                        free_cells = [c if isinstance(c, Cell) else Cell(MISSING) for c in free_cells]
                        bases = [stack.pop() for _ in range(n_bases)][::-1]
                        for b in bases:
                            if not isinstance(b, UserClass):
                                raise TypeError(f"class {cname}: base '{b}' is not a class")
                        cls_obj = UserClass(cname, bases[0] if bases else None, {}, bases)
                        cls_obj.mro()
                        cls_frame = Frame(cls_code, g, cells=free_cells, owner_class=cls_obj)
                        self._run_frame(cls_frame)
                        for i, vname in enumerate(cls_code.varnames):
                            val = cls_frame.locals[i]
                            if val is not MISSING:
                                if callable(val) or isinstance(val, (PyProperty, PyStaticMethod, PyClassMethod)):
                                    cls_obj.methods[vname] = val
                                else:
                                    cls_obj.attrs[vname] = val
                        stack.append(cls_obj)
                    elif op == Op.RETURN_VALUE:
                        val = stack.pop()
                        if in_subblock:
                            raise ReturnException(val)
                        return val
                    elif op == Op.BREAK_LOOP:
                        raise BreakException()
                    elif op == Op.CONTINUE_LOOP:
                        raise ContinueException()
                    elif op == Op.RAISE_OP:
                        if arg == 0:
                            raise
                        if arg == 2:
                            cause = stack.pop(); exc_val = stack.pop()
                            exc = make_raise(self, exc_val)
                            if isinstance(exc, PyRaise) and exc.inst is not None and isinstance(cause, UserInstance):
                                exc.inst.attributes["__cause__"] = cause
                            raise exc
                        raise make_raise(self, stack.pop())
                    elif op == Op.ASSERT_OP:
                        msg = stack.pop() if arg else "assertion failed"
                        test = stack.pop()
                        if not self._is_truthy(test):
                            raise AssertionError(str(msg))
                    elif op == Op.EXEC_TRY:
                        self._exec_try_vm(arg, frame)
                    elif op == Op.EXEC_WITH:
                        self._exec_with_vm(arg, frame)
                    elif op == Op.IMPORT_NAME:
                        exec_import(self, arg, _FrameEnvBridge(self, frame))
                    elif op in (Op.IMPORT_FROM, Op.IMPORT_STAR):
                        exec_from_import(self, arg, _FrameEnvBridge(self, frame))
                    elif op == Op.EVAL_FSTRING:
                        stack.append(self._eval_fstring_vm(arg, frame))
                    elif op == Op.EVAL_COMP:
                        stack.append(self._eval_comp_vm(arg, frame))
                    elif op == Op.YIELD_VALUE:
                        raise _YieldSignal(stack.pop())
                    elif op == Op.YIELD_FROM:
                        sub = getattr(frame, "_sub_iter", None)
                        if sub is None:
                            source = stack.pop()
                            sub = source if isinstance(source, VMGenerator) else iter(source)
                            frame._sub_iter = sub
                            try:
                                item = next(sub)
                            except StopIteration as stop:
                                frame._sub_iter = None
                                stack.append(stop.value if isinstance(source, VMGenerator) else None)
                                continue
                            frame.pc = pc
                            raise _YieldSignal(item)
                        else:
                            sub_err = getattr(frame, "_sub_err", None)
                            sub_send = getattr(frame, "_sub_send", None)
                            frame._sub_err = None
                            frame._sub_send = None
                            try:
                                if sub_err is not None:
                                    from generators import _GenExit
                                    if isinstance(sub_err, _GenExit):
                                        if hasattr(sub, "close"):
                                            sub.close()
                                        frame._sub_iter = None
                                        raise sub_err
                                    item = sub.throw(sub_err)
                                elif isinstance(sub, VMGenerator):
                                    item = sub.send(sub_send)
                                else:
                                    item = next(sub)
                            except StopIteration as stop:
                                frame._sub_iter = None
                                stack.append(stop.value if isinstance(sub, VMGenerator) else None)
                                continue
                            frame.pc = pc
                            raise _YieldSignal(item)
            except _YieldSignal:
                raise
            except ReturnException as ret:
                if in_subblock:
                    raise
                return ret.value
            except (BreakException, ContinueException) as loop_sig:
                if in_subblock:
                    raise
                # Find innermost loop containing pc
                matched = None
                for lstart, lend, cont_pc, brk_pc in reversed(code.loop_ranges):
                    if lstart <= pc < lend:
                        matched = (cont_pc, brk_pc)
                        break
                if matched is None:
                    raise
                frame.pc = matched[1] if isinstance(loop_sig, BreakException) else matched[0]
                continue
            except Exception as e:
                ln, col = locs[pc] if pc < len(locs) else (0, 0)
                if isinstance(e, PyRaise) and ln and not e.line:
                    e.line = ln
                if not hasattr(e, "_pysubset_loc") and ln:
                    try:
                        e._pysubset_loc = (code.filename, ln, col)
                    except Exception:
                        pass
                raise
        return None

    def _make_vm_func(self, fn_code, g, defaults, kw_defaults, free_cells, is_method=False, owner_cls=None):
        vm = self
        n_params = fn_code.argcount
        kwonly = fn_code.kwonly
        vararg = fn_code.vararg
        kwarg = fn_code.kwarg
        n_cellvars = len(fn_code.cellvars)
        has_super = is_method and owner_cls is not None

        def _bind_frame(*args, **kwargs):
            loc = [MISSING] * len(fn_code.varnames)
            cells = [Cell(MISSING) for _ in range(n_cellvars)] + list(free_cells)
            # Check unexpected kwargs
            if kwargs and not kwarg:
                allowed = set(fn_code.varnames[:n_params]) | {k for k, _ in kwonly}
                for k in kwargs:
                    if k not in allowed:
                        raise TypeError(f"{fn_code.name}() got an unexpected keyword argument '{k}'")

            def _set_var(name, val):
                if name in fn_code.cellvars:
                    cells[fn_code.cellvars.index(name)].value = val
                else:
                    loc[fn_code.varnames.index(name)] = val

            for i in range(n_params):
                pname = fn_code.varnames[i]
                if i < len(args):
                    if pname in kwargs:
                        raise TypeError(f"{fn_code.name}() got multiple values for argument '{pname}'")
                    _set_var(pname, args[i])
                elif pname in kwargs:
                    _set_var(pname, kwargs[pname])
                elif defaults[i] is not MISSING:
                    _set_var(pname, defaults[i])
                else:
                    raise TypeError(f"{fn_code.name}() missing 1 required positional argument: '{pname}'")

            idx = n_params
            for j, (kname, _) in enumerate(kwonly):
                if kname in kwargs:
                    _set_var(kname, kwargs[kname])
                elif kw_defaults[j] is not MISSING:
                    _set_var(kname, kw_defaults[j])
                else:
                    raise TypeError(f"{fn_code.name}() missing required keyword-only argument: '{kname}'")
                idx += 1

            if vararg:
                _set_var(vararg, tuple(args[n_params:]))
            if kwarg:
                used = set(fn_code.varnames[:n_params]) | {k for k, _ in kwonly}
                _set_var(kwarg, {k: v for k, v in kwargs.items() if k not in used})

            if has_super:
                first = args[0] if args else None
                start = first.cls if isinstance(first, UserInstance) else (first if isinstance(first, UserClass) else owner_cls)
                if "super" in fn_code.freevars:
                    s_idx = n_cellvars + fn_code.freevars.index("super")
                    cells[s_idx] = Cell(lambda: UserInstanceProxy(SuperView(owner_cls, start), first))

            return Frame(fn_code, g, loc, cells)

        if fn_code.is_generator:
            def gen_factory(*args, **kwargs):
                return VMGenerator(vm, _bind_frame(*args, **kwargs), fn_code.name)
            return gen_factory

        ln, col = fn_code.locations[0] if fn_code.locations else (0, 0)
        label = (owner_cls.name + "." + fn_code.name) if is_method and owner_cls else fn_code.name
        frame_entry = (fn_code.filename, label, ln, col)

        if not kwonly and not vararg and not kwarg and n_cellvars == 0 and not free_cells and not has_super and all(d is MISSING for d in defaults):
            n_vars = len(fn_code.varnames)
            extra = n_vars - n_params
            tail = [MISSING] * extra
            def fast_vm_func(*args, **kwargs):
                if kwargs or len(args) != n_params:
                    frame = _bind_frame(*args, **kwargs)
                else:
                    frame = Frame(fn_code, g, list(args) + list(tail) if extra else list(args))
                vm.call_stack.append(frame_entry)
                try:
                    return vm._run_frame(frame)
                except Exception as e:
                    if not hasattr(e, "_pysubset_tb"):
                        try:
                            e._pysubset_tb = list(vm.call_stack)
                        except Exception:
                            pass
                    raise
                finally:
                    vm.call_stack.pop()
            return fast_vm_func

        def vm_func(*args, **kwargs):
            frame = _bind_frame(*args, **kwargs)
            vm.call_stack.append(frame_entry)
            try:
                return vm._run_frame(frame)
            except Exception as e:
                if not hasattr(e, "_pysubset_tb"):
                    try:
                        e._pysubset_tb = list(vm.call_stack)
                    except Exception:
                        pass
                raise
            finally:
                vm.call_stack.pop()

        return vm_func

    def _exec_subblock(self, block, frame):
        from compiler import _FuncCompiler
        code = frame.code
        fc = _FuncCompiler(
            code.name, code.filename,
            locals_set=set(code.varnames),
            globals_decl=set(),
            cellvars=code.cellvars,
            freevars=code.freevars,
            is_module=(code.name == "<module>"),
            is_class_body=code.is_class_body,
            allow_loop_exc=True,
        )
        fc.code.varnames = list(code.varnames)
        fc.code.cellvars = list(code.cellvars)
        fc.code.freevars = list(code.freevars)
        fc.compile_block(block)
        sub = Frame(fc.code, frame.globals, frame.locals, frame.cells, frame.owner_class)
        if len(sub.locals) < len(fc.code.varnames):
            sub.locals.extend([MISSING] * (len(fc.code.varnames) - len(sub.locals)))
        return self._run_frame(sub, in_subblock=True)

    def _eval_subexpr(self, expr, frame):
        from compiler import _FuncCompiler
        code = frame.code
        fc = _FuncCompiler(
            code.name, code.filename,
            locals_set=set(code.varnames),
            cellvars=code.cellvars,
            freevars=code.freevars,
            is_module=(code.name == "<module>"),
            is_class_body=code.is_class_body,
        )
        fc.code.varnames = list(code.varnames)
        fc.code.cellvars = list(code.cellvars)
        fc.code.freevars = list(code.freevars)
        fc.compile_expr(expr)
        fc.emit(Op.RETURN_VALUE)
        sub = Frame(fc.code, frame.globals, frame.locals, frame.cells, frame.owner_class)
        if len(sub.locals) < len(fc.code.varnames):
            sub.locals.extend([MISSING] * (len(fc.code.varnames) - len(sub.locals)))
        return self._run_frame(sub)

    def _exec_try_vm(self, node, frame):
        bridge = _FrameEnvBridge(self, frame)
        handlers = node.handlers
        if handlers is None and node.except_block is not None:
            handlers = [(None, node.except_var, node.except_block)]
        handlers = handlers or []
        try:
            try:
                self._exec_subblock(node.try_block, frame)
            except (ReturnException, BreakException, ContinueException):
                raise
            except Exception as e:
                if not handlers:
                    raise
                inst, legacy, host = to_exc_instance(self, e)
                for type_expr, var, block in handlers:
                    if type_expr is not None:
                        if not exc_match(inst, self._eval_subexpr(type_expr, frame)):
                            continue
                    if var:
                        val = legacy if legacy is not None else (strip_line(str(e)) if host and type_expr is None else inst)
                        bridge.set(var, val)
                    self._exec_subblock(block, frame)
                    break
                else:
                    raise
            else:
                if node.else_block is not None:
                    self._exec_subblock(node.else_block, frame)
        finally:
            if node.finally_block is not None:
                self._exec_subblock(node.finally_block, frame)

    def _exec_with_vm(self, node, frame):
        bridge = _FrameEnvBridge(self, frame)
        control = (ReturnException, BreakException, ContinueException)

        def run(i):
            if i == len(node.items):
                self._exec_subblock(node.body, frame)
                return
            ctx_expr, var = node.items[i]
            enter, leave = _cm_parts(self._eval_subexpr(ctx_expr, frame))
            value = enter()
            if var:
                bridge.set(var, value)
            try:
                run(i + 1)
            except control:
                leave(None, None, None)
                raise
            except Exception as e:
                inst = to_exc_instance(self, e)[0]
                if not self._is_truthy(leave(inst.cls, inst, None)):
                    raise
            else:
                leave(None, None, None)

        run(0)

    def _eval_fstring_vm(self, raw, frame):
        from lexer import Lexer, _unescape
        from parser import Parser
        out = []
        lit = []
        i = 0
        n = len(raw)
        while i < n:
            c = raw[i]
            if c == "{":
                if i + 1 < n and raw[i + 1] == "{":
                    lit.append("{"); i += 2; continue
                j = i + 1; depth = 0; quote = None
                while j < n:
                    ch = raw[j]
                    if quote:
                        if ch == quote: quote = None
                    elif ch in "'\"": quote = ch
                    elif ch in "([{": depth += 1
                    elif ch in ")]}":
                        if depth == 0 and ch == "}": break
                        depth -= 1
                    j += 1
                if j >= n:
                    raise SyntaxError("f-string: expecting '}'")
                inner = raw[i + 1:j]
                expr_text = inner; spec = ""; d = 0; q = None
                for k, ch in enumerate(inner):
                    if q:
                        if ch == q: q = None
                    elif ch in "'\"": q = ch
                    elif ch in "([{": d += 1
                    elif ch in ")]}": d -= 1
                    elif d == 0 and ch == ":":
                        expr_text = inner[:k]; spec = inner[k + 1:]; break
                conv = None
                if len(expr_text) >= 2 and expr_text[-2] == "!" and expr_text[-1] in "rsa":
                    conv = expr_text[-1]; expr_text = expr_text[:-2]
                debug = None
                _st = expr_text.rstrip()
                if _st.endswith("=") and not _st.endswith(("==", "!=", "<=", ">=")):
                    debug = expr_text; expr_text = _st[:-1]
                    if conv is None and not spec: conv = "r"
                tree = Parser(Lexer(expr_text).tokenize()).parse()
                if not tree.statements or not hasattr(tree.statements[0], "expr"):
                    raise SyntaxError("f-string: invalid expression")
                val = self._eval_subexpr(tree.statements[0].expr, frame)
                if "{" in spec:
                    spec = self._eval_fstring_vm(spec, frame)
                if conv == "r": val = repr(val)
                elif conv == "s": val = self._to_string(val)
                elif conv == "a": val = ascii(val)
                if spec:
                    if isinstance(val, UserInstance): val = self._to_string(val)
                    piece = format(val, spec)
                else:
                    piece = self._to_string(val)
                if lit:
                    out.append(_unescape("".join(lit))); lit = []
                out.append((debug + piece) if debug is not None else piece)
                i = j + 1; continue
            if c == "}":
                if i + 1 < n and raw[i + 1] == "}":
                    lit.append("}"); i += 2; continue
                raise SyntaxError("f-string: single '}' is not allowed")
            lit.append(c); i += 1
        if lit:
            out.append(_unescape("".join(lit)))
        return "".join(out)

    def _eval_comp_vm(self, node, frame):
        # Use a lightweight Environment chain backed by the VM frame for outer reads
        base_env = _FrameEnvProxy(frame)

        def assign_local(target, value, env):
            if isinstance(target, Var):
                env.set(target.name, value)
            elif isinstance(target, (TupleExpr, ListExpr)):
                items = list(value)
                elems = target.elements
                star = [i for i, t in enumerate(elems) if isinstance(t, Starred)]
                if not star:
                    for t, v in zip(elems, items):
                        assign_local(t, v, env)
                else:
                    k = star[0]; after = len(elems) - k - 1
                    for t, v in zip(elems[:k], items[:k]):
                        assign_local(t, v, env)
                    assign_local(elems[k].value, items[k:len(items) - after], env)
                    for t, v in zip(elems[k + 1:], items[len(items) - after:]):
                        assign_local(t, v, env)

        def eval_in_scope(expr, scope):
            from interpreter import Interpreter
            # Evaluate expression in lexical scope using tree-walker fallback on local scope
            tmp = _ScopeEvaluator(self, scope)
            return tmp.eval(expr)

        if node.kind == "gen":
            clauses = node.clauses
            outer = iter(eval_in_scope(clauses[0][2], base_env))

            def walk_gen(i, scope):
                if i == len(clauses):
                    yield eval_in_scope(node.elt, scope)
                    return
                clause = clauses[i]
                if clause[0] == "for":
                    src = outer if i == 0 else eval_in_scope(clause[2], scope)
                    for item in src:
                        inner = Environment(scope)
                        assign_local(clause[1], item, inner)
                        yield from walk_gen(i + 1, inner)
                elif self._is_truthy(eval_in_scope(clause[1], scope)):
                    yield from walk_gen(i + 1, scope)

            return walk_gen(0, Environment(base_env))

        items = []
        pairs = {}
        clauses = node.clauses

        def walk(i, scope):
            if i == len(clauses):
                if node.kind == "dict":
                    pairs[eval_in_scope(node.elt, scope)] = eval_in_scope(node.elt2, scope)
                else:
                    items.append(eval_in_scope(node.elt, scope))
                return
            clause = clauses[i]
            if clause[0] == "for":
                for item in eval_in_scope(clause[2], scope):
                    inner = Environment(scope)
                    assign_local(clause[1], item, inner)
                    walk(i + 1, inner)
            elif self._is_truthy(eval_in_scope(clause[1], scope)):
                walk(i + 1, scope)

        walk(0, Environment(base_env))
        if node.kind == "dict": return pairs
        if node.kind == "set": return set(items)
        return items


class _FrameEnvProxy:
    def __init__(self, frame):
        self.frame = frame
        self.vars = frame.globals
        self.parent = None

    def get(self, name):
        code = self.frame.code
        if name in code.varnames:
            v = self.frame.locals[code.varnames.index(name)]
            if v is not MISSING:
                return v
        if name in code.cellvars:
            v = self.frame.cells[code.cellvars.index(name)].value
            if v is not MISSING:
                return v
        if name in code.freevars:
            v = self.frame.cells[len(code.cellvars) + code.freevars.index(name)].value
            if v is not MISSING:
                return v
        if name in self.frame.globals:
            return self.frame.globals[name]
        raise NameError(f"Name '{name}' is not defined")


class _EnvDictProxy(dict):
    def __init__(self, env):
        super().__init__()
        self.env = env

    def __contains__(self, key):
        try:
            self.env.get(key)
            return True
        except NameError:
            return False

    def __getitem__(self, key):
        return self.env.get(key)

    def __setitem__(self, key, val):
        self.env.set(key, val)


class _ScopeEvaluator:
    def __init__(self, vm, scope):
        self.vm = vm
        self.scope = scope
        self.global_env = vm.global_env

    def eval(self, expr):
        from interpreter import Interpreter
        # Reuse Interpreter._eval_expr logic bound to self.scope
        interp = Interpreter.__new__(Interpreter)
        interp.global_env = self.vm.global_env
        interp.exception_classes = self.vm.exception_classes
        interp.call_stack = self.vm.call_stack
        interp.sources = self.vm.sources
        interp.current_file = self.vm.current_file
        interp.builtins_snapshot = self.vm.builtins_snapshot
        interp.modules = self.vm.modules
        interp.virtual_modules = self.vm.virtual_modules
        interp.search_paths = self.vm.search_paths
        return interp._eval_expr(expr, self.scope)