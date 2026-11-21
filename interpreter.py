import os
from types import FunctionType as _FunctionType

from ast_nodes import *
from builtins_env import setup_builtins, setup_exceptions
from environment import Environment
from generators import PyGenerator, comp_gen, eval_yield, eval_yield_from, is_generator_def
from modules import exec_from_import, exec_import
from runtime import (
    FAST_BINOPS, INPLACE_OPS, MISSING, BreakException, ContinueException,
    PyRaise, ReturnException, SuperView, UserClass, UserInstance,
    UserInstanceProxy, call_any, del_item, exec_try, exec_with, get_attr,
    get_item, instance_truth, make_raise, set_attr, set_item,
)


class Interpreter:
    def __init__(self):
        self.global_env = Environment()
        self.call_stack = []
        setup_exceptions(self)
        setup_builtins(self)
        self.builtins_snapshot = dict(self.global_env.vars)
        self.modules = {}
        self.virtual_modules = {}
        self.search_paths = [os.getcwd()]
        self.global_env.set("__name__", "__main__")

    def set_script(self, path):
        path = os.path.abspath(path)
        self.global_env.set("__file__", path)
        folder = os.path.dirname(path)
        self.search_paths = [folder] + [p for p in self.search_paths if p != folder]

    def register_module(self, name, source):
        self.virtual_modules[name] = source
        self.modules.pop(name, None)

    def run(self, ast):
        try:
            self._eval_block(ast, self.global_env)
        except (BreakException, ContinueException):
            print("Runtime Error: 'break'/'continue' outside loop")
        except Exception as e:
            print(f"Runtime Error: {e}")
            tb = getattr(e, "_pysubset_tb", None) or self.call_stack
            for fname, fline in reversed(tb):
                print(f"  in {fname}() at line {fline}")

    def _eval_block(self, block, env):
        for stmt in block.statements:
            self._eval_statement(stmt, env)

    def _eval_statement(self, node, env):
        try:
            self._eval_statement_inner(node, env)
        except (ReturnException, BreakException, ContinueException):
            raise
        except Exception as e:
            line = getattr(node, "line", 0)
            if isinstance(e, PyRaise):
                if line and not e.line:
                    e.line = line
                raise
            if line and " at line " not in str(e):
                raise type(e)(str(e) + f" at line {line}") from None
            raise

    def _eval_statement_inner(self, node, env):
        t = type(node)
        if t is ExprStmt:
            self._eval_expr(node.expr, env)
            return
        if t is Assign and type(node.target) is Var:
            env.set(node.target.name, self._eval_expr(node.value, env))
            return
        if t is IfStmt:
            c = self._eval_expr(node.condition, env)
            if c is True or (c is not False and self._is_truthy(c)):
                self._eval_block(node.then_branch, env)
                return
            for cond, body in node.elif_branches:
                if self._is_truthy(self._eval_expr(cond, env)):
                    self._eval_block(body, env)
                    return
            if node.else_branch:
                self._eval_block(node.else_branch, env)
            return
        if t is ReturnStmt:
            raise ReturnException(self._eval_expr(node.value, env) if node.value else None)

        if isinstance(node, PrintStmt):
            print(self._to_string(self._eval_expr(node.expr, env)))
        elif isinstance(node, Assign):
            _assign_to(self, node.target, self._eval_expr(node.value, env), env)
        elif isinstance(node, TryStmt):
            exec_try(self, node, env)
        elif isinstance(node, AssertStmt):
            if not self._is_truthy(self._eval_expr(node.test, env)):
                msg = self._eval_expr(node.msg, env) if node.msg is not None else "assertion failed"
                raise AssertionError(str(msg))
        elif isinstance(node, RaiseStmt):
            if node.value is None:
                raise
            _exc = make_raise(self, self._eval_expr(node.value, env))
            if getattr(node, "cause", None) is not None:
                _cause = self._eval_expr(node.cause, env)
                if isinstance(_exc, PyRaise) and _exc.inst is not None and isinstance(_cause, UserInstance):
                    _exc.inst.attributes["__cause__"] = _cause
            raise _exc
        elif isinstance(node, WhileStmt):
            broke = False
            while self._is_truthy(self._eval_expr(node.condition, env)):
                try:
                    self._eval_block(node.body, env)
                except BreakException:
                    broke = True
                    break
                except ContinueException:
                    continue
            if not broke and node.else_body is not None:
                self._eval_block(node.else_body, env)
        elif isinstance(node, ForStmt):
            iterable = self._eval_expr(node.iterable, env)
            broke = False
            for item in iterable:
                if isinstance(node.target, Var):
                    env.set(node.target.name, item)
                elif isinstance(node.target, (ListExpr, TupleExpr)):
                    for i, target_expr in enumerate(node.target.elements):
                        if isinstance(target_expr, Var):
                            env.set(target_expr.name, item[i])
                try:
                    self._eval_block(node.body, env)
                except BreakException:
                    broke = True
                    break
                except ContinueException:
                    continue
            if not broke and node.else_body is not None:
                self._eval_block(node.else_body, env)
        elif isinstance(node, FuncDef):
            evaluated_defaults = [self._eval_expr(d, env) if d is not None else None for d in node.defaults]
            evaluated_kwonly = [(k, self._eval_expr(d, env) if d is not None else MISSING) for k, d in (getattr(node, "kwonly", None) or [])]
            frame_entry = (node.name, getattr(node, "line", 0))
            is_gen = is_generator_def(node)

            def func(*args, **kwargs):
                func_env = Environment(env)
                if kwargs:
                    _check_kwargs(node.name, list(node.params) + _kwonly_names(node), kwargs, node.kwarg)
                if node.kwarg:
                    func_env.set(node.kwarg, {k: v for k, v in kwargs.items() if k not in node.params and k not in _kwonly_names(node)})
                if node.vararg:
                    func_env.set(node.vararg, tuple(args[len(node.params):]))
                if evaluated_kwonly:
                    _bind_kwonly(node, func_env, kwargs, evaluated_kwonly)
                for i, param in enumerate(node.params):
                    if i < len(args) or param in kwargs:
                        func_env.set(param, args[i] if i < len(args) else kwargs[param])
                    elif evaluated_defaults[i] is not None:
                        func_env.set(param, evaluated_defaults[i])
                    else:
                        func_env.set(param, None)
                if is_gen:
                    return PyGenerator(self, node, func_env, node.name)
                self.call_stack.append(frame_entry)
                try:
                    try:
                        self._eval_block(node.body, func_env)
                    except ReturnException as ret:
                        return ret.value
                    return None
                except (BreakException, ContinueException):
                    raise
                except Exception as e:
                    if not hasattr(e, "_pysubset_tb"):
                        try:
                            e._pysubset_tb = list(self.call_stack)
                        except Exception:
                            pass
                    raise
                finally:
                    self.call_stack.pop()

            for _d in reversed(node.decorators or []):
                func = call_any(self._eval_expr(_d, env), func)
            env.set(node.name, func)
        elif isinstance(node, BreakStmt):
            raise BreakException()
        elif isinstance(node, ContinueStmt):
            raise ContinueException()
        elif isinstance(node, GlobalStmt):
            env.global_names = env.global_names | set(node.names)
        elif isinstance(node, DelStmt):
            for t in node.targets:
                if isinstance(t, Var):
                    if t.name not in env.vars:
                        raise NameError(f"Name '{t.name}' is not defined")
                    del env.vars[t.name]
                elif isinstance(t, Subscript):
                    del_item(self._eval_expr(t.obj, env), self._eval_expr(t.index, env))
                elif isinstance(t, Attribute):
                    obj = self._eval_expr(t.obj, env)
                    if isinstance(obj, UserInstance):
                        del obj.attributes[t.name]
                    else:
                        delattr(obj, t.name)
                else:
                    raise SyntaxError("cannot delete this expression")
        elif isinstance(node, NonlocalStmt):
            env.nonlocal_names = env.nonlocal_names | set(node.names)
        elif isinstance(node, ChainAssign):
            val = self._eval_expr(node.value, env)
            for t in node.targets:
                _assign_to(self, t, val, env)
        elif isinstance(node, WithStmt):
            exec_with(self, node, env)
        elif isinstance(node, ImportStmt):
            exec_import(self, node, env)
        elif isinstance(node, FromImportStmt):
            exec_from_import(self, node, env)
        elif isinstance(node, PassStmt):
            pass
        elif isinstance(node, ClassDef):
            _exec_classdef(self, node, env)
        else:
            raise NotImplementedError(f"Statement not implemented: {type(node).__name__}")

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

    def _eval_expr(self, node, env):
        t = type(node)
        if t is Number or t is String or t is Bool or t is Const:
            return node.value
        if t is NoneType:
            return None
        if t is Var:
            return env.get(node.name)
        if t is BinOp:
            f = FAST_BINOPS.get(node.op)
            if f is not None:
                return f(self._eval_expr(node.left, env), self._eval_expr(node.right, env))
            if node.op == "and":
                l_val = self._eval_expr(node.left, env)
                return self._eval_expr(node.right, env) if self._is_truthy(l_val) else l_val
            if node.op == "or":
                l_val = self._eval_expr(node.left, env)
                return l_val if self._is_truthy(l_val) else self._eval_expr(node.right, env)
            left = self._eval_expr(node.left, env)
            right = self._eval_expr(node.right, env)
            op = node.op
            if op == "in": return left in right
            if op == "not in": return left not in right
            if op == "is": return left is right
            if op == "is not": return left is not right
            if op == "&": return left & right
            if op == "|": return left | right
            if op == "^": return left ^ right
            if op == "<<": return left << right
            if op == ">>": return left >> right
            raise RuntimeError(f"Unknown operator {op}")
        if t is Call:
            plain = getattr(node, "_plain", None)
            if plain is None:
                plain = (not node.kwargs and not node.kw_splats
                         and not any(type(a) is Starred for a in node.args))
                node._plain = plain
            callee = self._eval_expr(node.callee, env)
            if plain:
                args = [self._eval_expr(a, env) for a in node.args]
                if type(callee) is _FunctionType:
                    return callee(*args)
                return call_any(callee, *args)
            args = _eval_elems(self, node.args, env)
            kwargs = {k: self._eval_expr(v, env) for k, v in (node.kwargs or {}).items()}
            for _sp in (node.kw_splats or []):
                kwargs.update(self._eval_expr(_sp, env))
            return call_any(callee, *args, **kwargs)
        if t is Attribute:
            return get_attr(self._eval_expr(node.obj, env), node.name)
        if t is Subscript:
            return get_item(self._eval_expr(node.obj, env), self._eval_expr(node.index, env))
        if t is NamedExpr:
            _v = self._eval_expr(node.value, env)
            env.set(node.name, _v)
            return _v
        if t is FString:
            return _eval_fstring(self, node.value, env)
        if t is ListExpr:
            return _eval_elems(self, node.elements, env)
        if t is TupleExpr:
            return tuple(_eval_elems(self, node.elements, env))
        if t is SetExpr:
            return set(_eval_elems(self, node.elements, env))
        if t is DictExpr:
            return _eval_dict(self, node, env)
        if t is UnaryOp:
            val = self._eval_expr(node.operand, env)
            if node.op == "-": return -val
            if node.op == "+": return +val
            if node.op == "~": return ~val
            if node.op == "not": return not self._is_truthy(val)
        if t is Comp:
            return _eval_comp(self, node, env)
        if t is IfExpr:
            if self._is_truthy(self._eval_expr(node.cond, env)):
                return self._eval_expr(node.then, env)
            return self._eval_expr(node.other, env)
        if t is SliceExpr:
            lo = self._eval_expr(node.lower, env) if node.lower is not None else None
            up = self._eval_expr(node.upper, env) if node.upper is not None else None
            st = self._eval_expr(node.step, env) if node.step is not None else None
            return slice(lo, up, st)
        if t is Lambda:
            lam_defaults = [self._eval_expr(d, env) if d is not None else None for d in (node.defaults or [None] * len(node.params))]
            def lam(*args, **kw):
                lam_env = Environment(env)
                for i, p in enumerate(node.params):
                    if i < len(args):
                        lam_env.set(p, args[i])
                    elif p in kw:
                        lam_env.set(p, kw[p])
                    else:
                        lam_env.set(p, lam_defaults[i])
                if getattr(node, "vararg", None):
                    lam_env.set(node.vararg, tuple(args[len(node.params):]))
                if getattr(node, "kwarg", None):
                    lam_env.set(node.kwarg, {k: v for k, v in kw.items() if k not in node.params})
                return self._eval_expr(node.body, lam_env)
            return lam
        if t is YieldExpr:
            return eval_yield(self, node, env)
        if t is YieldFromExpr:
            return eval_yield_from(self, node, env)
        if t is Starred:
            raise SyntaxError("can't use starred expression here")
        raise NotImplementedError(f"Expression not implemented: {t.__name__}")


def _check_kwargs(fname, params, kwargs, kwarg=None):
    for k in kwargs:
        if k not in params and not kwarg:
            raise TypeError(f"{fname}() got an unexpected keyword argument '{k}'")


def _kwonly_names(fnode):
    return [k for k, _ in (getattr(fnode, "kwonly", None) or [])]


def _bind_kwonly(fnode, scope, kwargs, vals):
    for k, default in vals:
        if k in kwargs:
            scope.set(k, kwargs[k])
        elif default is not MISSING:
            scope.set(k, default)
        else:
            raise TypeError(f"{fnode.name}() missing required keyword-only argument: '{k}'")


def _eval_elems(interp, elements, env):
    out = []
    for e in elements:
        if isinstance(e, Starred):
            out.extend(interp._eval_expr(e.value, env))
        else:
            out.append(interp._eval_expr(e, env))
    return out


def _eval_dict(interp, node, env):
    result = {}
    for k, v in zip(node.keys, node.values):
        if k is None:
            result.update(interp._eval_expr(v, env))
        else:
            result[interp._eval_expr(k, env)] = interp._eval_expr(v, env)
    return result


def _assign_to(interp, target, value, env):
    if isinstance(target, Var):
        env.set(target.name, value)
    elif isinstance(target, Subscript):
        obj = interp._eval_expr(target.obj, env)
        set_item(obj, interp._eval_expr(target.index, env), value)
    elif isinstance(target, Attribute):
        obj = interp._eval_expr(target.obj, env)
        set_attr(obj, target.name, value)
    elif isinstance(target, (TupleExpr, ListExpr)):
        items = list(value)
        elems = target.elements
        star = [i for i, t in enumerate(elems) if isinstance(t, Starred)]
        if len(star) > 1:
            raise SyntaxError("multiple starred expressions in assignment")
        if not star:
            if len(items) < len(elems):
                raise ValueError(f"not enough values to unpack (expected {len(elems)}, got {len(items)})")
            if len(items) > len(elems):
                raise ValueError(f"too many values to unpack (expected {len(elems)})")
            for t, v in zip(elems, items):
                _assign_to(interp, t, v, env)
        else:
            k = star[0]
            after = len(elems) - k - 1
            if len(items) < len(elems) - 1:
                raise ValueError(f"not enough values to unpack (expected at least {len(elems) - 1}, got {len(items)})")
            for t, v in zip(elems[:k], items[:k]):
                _assign_to(interp, t, v, env)
            _assign_to(interp, elems[k].value, items[k:len(items) - after], env)
            for t, v in zip(elems[k + 1:], items[len(items) - after:]):
                _assign_to(interp, t, v, env)
    else:
        raise SyntaxError("cannot assign to this expression")


def _eval_comp(interp, node, env):
    if node.kind == "gen":
        return comp_gen(interp, node, env, _assign_to)
    items = []
    pairs = {}
    clauses = node.clauses

    def emit(scope):
        if node.kind == "dict":
            key = interp._eval_expr(node.elt, scope)
            pairs[key] = interp._eval_expr(node.elt2, scope)
        else:
            items.append(interp._eval_expr(node.elt, scope))

    def walk(i, scope):
        if i == len(clauses):
            emit(scope)
            return
        clause = clauses[i]
        if clause[0] == "for":
            for item in interp._eval_expr(clause[2], scope):
                inner = Environment(scope)
                _assign_to(interp, clause[1], item, inner)
                walk(i + 1, inner)
        elif interp._is_truthy(interp._eval_expr(clause[1], scope)):
            walk(i + 1, scope)

    walk(0, Environment(env))
    if node.kind == "dict":
        return pairs
    if node.kind == "set":
        return set(items)
    return items


def _eval_fstring(interp, raw, env):
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
                lit.append("{")
                i += 2
                continue
            j = i + 1
            depth = 0
            quote = None
            while j < n:
                ch = raw[j]
                if quote:
                    if ch == quote:
                        quote = None
                elif ch in "'\"":
                    quote = ch
                elif ch in "([{":
                    depth += 1
                elif ch in ")]}":
                    if depth == 0 and ch == "}":
                        break
                    depth -= 1
                j += 1
            if j >= n:
                raise SyntaxError("f-string: expecting '}'")
            inner = raw[i + 1:j]
            expr_text = inner
            spec = ""
            d = 0
            q = None
            for k, ch in enumerate(inner):
                if q:
                    if ch == q:
                        q = None
                elif ch in "'\"":
                    q = ch
                elif ch in "([{":
                    d += 1
                elif ch in ")]}":
                    d -= 1
                elif d == 0 and ch == ":":
                    expr_text = inner[:k]
                    spec = inner[k + 1:]
                    break
            conv = None
            if len(expr_text) >= 2 and expr_text[-2] == "!" and expr_text[-1] in "rsa":
                conv = expr_text[-1]
                expr_text = expr_text[:-2]
            debug = None
            _st = expr_text.rstrip()
            if _st.endswith("=") and not _st.endswith(("==", "!=", "<=", ">=")):
                debug = expr_text
                expr_text = _st[:-1]
                if conv is None and not spec:
                    conv = "r"
            tree = Parser(Lexer(expr_text).tokenize()).parse()
            if not tree.statements or not hasattr(tree.statements[0], "expr"):
                raise SyntaxError("f-string: invalid expression")
            val = interp._eval_expr(tree.statements[0].expr, env)
            if "{" in spec:
                spec = _eval_fstring(interp, spec, env)
            if conv == "r":
                val = repr(val)
            elif conv == "s":
                val = interp._to_string(val)
            elif conv == "a":
                val = ascii(val)
            if spec:
                if isinstance(val, UserInstance):
                    val = interp._to_string(val)
                piece = format(val, spec)
            else:
                piece = interp._to_string(val)
            if lit:
                out.append(_unescape("".join(lit)))
                lit = []
            out.append((debug + piece) if debug is not None else piece)
            i = j + 1
            continue
        if c == "}":
            if i + 1 < n and raw[i + 1] == "}":
                lit.append("}")
                i += 2
                continue
            raise SyntaxError("f-string: single '}' is not allowed")
        lit.append(c)
        i += 1
    if lit:
        out.append(_unescape("".join(lit)))
    return "".join(out)


def _make_method(interp, m, owner, class_env, defaults):
    kwarg = getattr(m, "kwarg", None)
    label = owner.name + "." + m.name
    frame_entry = (label, getattr(m, "line", 0))
    is_gen = is_generator_def(m)
    kwonly_vals = [(k, interp._eval_expr(d, class_env) if d is not None else MISSING) for k, d in (getattr(m, "kwonly", None) or [])]

    def method_func(*args, **kwargs):
        if kwargs:
            _check_kwargs(m.name, list(m.params) + _kwonly_names(m), kwargs, kwarg)
        scope = Environment(class_env)
        if kwarg:
            scope.set(kwarg, {k: v for k, v in kwargs.items() if k not in m.params and k not in _kwonly_names(m)})
        if m.vararg:
            scope.set(m.vararg, tuple(args[len(m.params):]))
        if kwonly_vals:
            _bind_kwonly(m, scope, kwargs, kwonly_vals)
        for i, param in enumerate(m.params):
            if i < len(args):
                scope.set(param, args[i])
            elif param in kwargs:
                scope.set(param, kwargs[param])
            elif defaults[i] is not None:
                scope.set(param, defaults[i])
            else:
                scope.set(param, None)
        first = args[0] if args else None
        if isinstance(first, UserInstance):
            start = first.cls
        elif isinstance(first, UserClass):
            start = first
        else:
            start = owner
        scope.set("super", lambda: UserInstanceProxy(SuperView(owner, start), first))
        if is_gen:
            return PyGenerator(interp, m, scope, label)
        interp.call_stack.append(frame_entry)
        try:
            try:
                interp._eval_block(m.body, scope)
            except ReturnException as ret:
                return ret.value
            return None
        except (BreakException, ContinueException):
            raise
        except Exception as e:
            if not hasattr(e, "_pysubset_tb"):
                try:
                    e._pysubset_tb = list(interp.call_stack)
                except Exception:
                    pass
            raise
        finally:
            interp.call_stack.pop()

    return method_func


def _exec_classdef(interp, node, env):
    names = node.bases if node.bases is not None else ([node.parent_class] if node.parent_class else [])
    bases = []
    for base_name in names:
        base = env.get(base_name)
        if not isinstance(base, UserClass):
            raise TypeError(f"class {node.name}: base '{base_name}' is not a class")
        bases.append(base)
    cls_obj = UserClass(node.name, bases[0] if bases else None, {}, bases)
    cls_obj.mro()
    body = Environment(env)
    for stmt in (node.attrs or []):
        value = interp._eval_expr(stmt.value, body)
        body.set(stmt.target.name, value)
        cls_obj.attrs[stmt.target.name] = value
    for m in node.methods:
        defaults = [interp._eval_expr(d, body) if d is not None else None for d in m.defaults]
        member = _make_method(interp, m, cls_obj, env, defaults)
        for deco in reversed(getattr(m, "decorators", None) or []):
            member = call_any(interp._eval_expr(deco, body), member)
        body.set(m.name, member)
        cls_obj.methods[m.name] = member
    env.set(node.name, cls_obj)