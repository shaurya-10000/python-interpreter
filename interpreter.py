from ast_nodes import *
from environment import Environment

class ReturnException(Exception):
    def __init__(self, value): self.value = value
class BreakException(Exception): pass
class ContinueException(Exception): pass

class UserClass:
    def __init__(self, name, parent, methods):
        self.name = name
        self.parent = parent
        self.methods = methods

    def get_method(self, name):
        if name in self.methods: return self.methods[name]
        if self.parent: return self.parent.get_method(name)
        return None

class UserInstance:
    def __init__(self, cls):
        self.cls = cls
        self.attributes = {}

class UserInstanceProxy:
    def __init__(self, parent_cls, instance):
        self.parent_cls = parent_cls
        self.instance = instance

class Interpreter:
    def __init__(self):
        self.global_env = Environment(); self._setup_builtins(); self._setup_builtins_v2(); self._setup_exceptions()
        self.call_stack = []

    def _setup_builtins(self):
        self.global_env.set("print", lambda *args: print(*[self._to_string(a) for a in args]))
        self.global_env.set("len", lambda x: len(x))
        self.global_env.set("range", lambda *args: list(range(*args)))
        self.global_env.set("str", lambda x: str(x))
        self.global_env.set("int", lambda x: int(x))
        self.global_env.set("float", lambda x: float(x))
        self.global_env.set("type", lambda x: type(x).__name__)
        self.global_env.set("True", True)
        self.global_env.set("False", False)
        self.global_env.set("None", None)
        self.global_env.set("input", lambda prompt="": input(prompt))
        self.global_env.set("enumerate", lambda x: list(enumerate(x)))
        self.global_env.set("zip", lambda *xs: list(zip(*xs)))
        self.global_env.set("sum", lambda xs: sum(xs))
        self.global_env.set("min", lambda *xs: min(*xs))
        self.global_env.set("max", lambda *xs: max(*xs))
        self.global_env.set("abs", lambda x: abs(x))
        self.global_env.set("sorted", lambda xs: sorted(xs))
        self.global_env.set("reversed", lambda xs: list(reversed(xs)))
        self.global_env.set("any", lambda xs: any(xs))
        self.global_env.set("all", lambda xs: all(xs))
        self.global_env.set("map", lambda f, xs: list(map(f, xs)))
        self.global_env.set("filter", lambda f, xs: list(filter(f, xs)))
        self.global_env.set("bool", lambda x: bool(x))
        self.global_env.set("repr", lambda x: repr(x))

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
        for stmt in block.statements: self._eval_statement(stmt, env)

    def _eval_statement(self, node, env):
        try:
            self._eval_statement_inner(node, env)
        except (ReturnException, BreakException, ContinueException):
            raise
        except Exception as e:
            line = getattr(node, 'line', 0)
            if isinstance(e, PyRaise):
                if line and not e.line: e.line = line
                raise
            if line and ' at line ' not in str(e):
                raise type(e)(str(e) + f' at line {line}') from None
            raise

    def _eval_statement_inner(self, node, env):
        if isinstance(node, ExprStmt): self._eval_expr(node.expr, env)
        elif isinstance(node, PrintStmt):
            val = self._eval_expr(node.expr, env)
            print(self._to_string(val))
        elif isinstance(node, Assign):
            val = self._eval_expr(node.value, env)
            if isinstance(node.target, Var): env.set(node.target.name, val)
            elif isinstance(node.target, Subscript):
                obj = self._eval_expr(node.target.obj, env)
                obj[self._eval_expr(node.target.index, env)] = val
            elif isinstance(node.target, Attribute):
                obj = self._eval_expr(node.target.obj, env)
                if isinstance(obj, UserInstance): obj.attributes[node.target.name] = val
                else: setattr(obj, node.target.name, val)
            elif isinstance(node.target, (TupleExpr, ListExpr)):
                _assign_to(self, node.target, val, env)
        elif isinstance(node, TryStmt):
            _exec_try(self, node, env)
        elif isinstance(node, AssertStmt):
            if not self._is_truthy(self._eval_expr(node.test, env)):
                msg = self._eval_expr(node.msg, env) if node.msg is not None else "assertion failed"
                raise AssertionError(str(msg))
        elif isinstance(node, RaiseStmt):
            if node.value is None: raise
            raise _make_raise(self, self._eval_expr(node.value, env))
        elif isinstance(node, IfStmt):
            if self._is_truthy(self._eval_expr(node.condition, env)):
                self._eval_block(node.then_branch, env); return
            for cond, body in node.elif_branches:
                if self._is_truthy(self._eval_expr(cond, env)):
                    self._eval_block(body, env); return
            if node.else_branch: self._eval_block(node.else_branch, env)
        elif isinstance(node, WhileStmt):
            broke = False
            while self._is_truthy(self._eval_expr(node.condition, env)):
                try: self._eval_block(node.body, env)
                except BreakException: broke = True; break
                except ContinueException: continue
            if not broke and node.else_body is not None:
                self._eval_block(node.else_body, env)
        elif isinstance(node, ForStmt):
            iterable = self._eval_expr(node.iterable, env)
            broke = False
            for item in iterable:
                if isinstance(node.target, Var): env.set(node.target.name, item)
                elif isinstance(node.target, (ListExpr, TupleExpr)):
                    for i, target_expr in enumerate(node.target.elements):
                        if isinstance(target_expr, Var): env.set(target_expr.name, item[i])
                try: self._eval_block(node.body, env)
                except BreakException: broke = True; break
                except ContinueException: continue
            if not broke and node.else_body is not None:
                self._eval_block(node.else_body, env)
        elif isinstance(node, FuncDef):
            evaluated_defaults = [self._eval_expr(d, env) if d is not None else None for d in node.defaults]
            def func(*args, **kwargs):
                func_env = Environment(env); _check_kwargs(node.name, node.params, kwargs, node.kwarg)
                if node.kwarg: func_env.set(node.kwarg, {k: v for k, v in kwargs.items() if k not in node.params})
                if node.vararg: func_env.set(node.vararg, list(args[len(node.params):]))
                for i, param in enumerate(node.params):
                    if i < len(args) or param in kwargs: func_env.set(param, args[i] if i < len(args) else kwargs[param])
                    elif evaluated_defaults[i] is not None: func_env.set(param, evaluated_defaults[i])
                    else: func_env.set(param, None)
                self.call_stack.append((node.name, getattr(node, 'line', 0)))
                try:
                    try: self._eval_block(node.body, func_env)
                    except ReturnException as ret: return ret.value
                    return None
                except (BreakException, ContinueException):
                    raise
                except Exception as e:
                    if not hasattr(e, "_pysubset_tb"):
                        try: e._pysubset_tb = list(self.call_stack)
                        except Exception: pass
                    raise
                finally:
                    self.call_stack.pop()
            env.set(node.name, func)
        elif isinstance(node, ReturnStmt):
            raise ReturnException(self._eval_expr(node.value, env) if node.value else None)
        elif isinstance(node, BreakStmt): raise BreakException()
        elif isinstance(node, ContinueStmt): raise ContinueException()
        elif isinstance(node, GlobalStmt): env.global_names.update(node.names)
        elif isinstance(node, DelStmt):
            for t in node.targets:
                if isinstance(t, Var):
                    if t.name not in env.vars: raise NameError(f"Name '{t.name}' is not defined")
                    del env.vars[t.name]
                elif isinstance(t, Subscript):
                    del self._eval_expr(t.obj, env)[self._eval_expr(t.index, env)]
                elif isinstance(t, Attribute):
                    obj = self._eval_expr(t.obj, env)
                    if isinstance(obj, UserInstance): del obj.attributes[t.name]
                    else: delattr(obj, t.name)
                else: raise SyntaxError("cannot delete this expression")
        elif isinstance(node, NonlocalStmt): env.nonlocal_names.update(node.names)
        elif isinstance(node, ChainAssign):
            val = self._eval_expr(node.value, env)
            for t in node.targets:
                self._eval_statement_inner(Assign(t, Const(val), line=node.line), env)
        elif isinstance(node, PassStmt): pass
        elif isinstance(node, ClassDef):
            parent = None
            if node.parent_class: parent = env.get(node.parent_class)
            methods = {}
            for method in node.methods:
                def make_method(m, parent_cls, class_env):
                    def method_func(*args, **kwargs):
                        method_env = Environment(class_env); _check_kwargs(m.name, m.params, kwargs, getattr(m, 'kwarg', None))
                        if getattr(m, 'kwarg', None): method_env.set(m.kwarg, {k: v for k, v in kwargs.items() if k not in m.params})
                        self_instance = args[0] if args else None
                        if m.params:
                            method_env.set(m.params[0], self_instance)
                            if m.vararg: method_env.set(m.vararg, list(args[1+len(m.params):]))
                            for i, param in enumerate(m.params[1:]):
                                if i+1 < len(args) or param in kwargs: method_env.set(param, args[i+1] if i+1 < len(args) else kwargs[param])
                                elif m.defaults[i+1] is not None: method_env.set(param, self._eval_expr(m.defaults[i+1], env))
                                else: method_env.set(param, None)
                        if parent_cls and self_instance:
                            def super_func():
                                return UserInstanceProxy(parent_cls, self_instance)
                            method_env.set("super", super_func)
                        try: self._eval_block(m.body, method_env)
                        except ReturnException as ret: return ret.value
                        return None
                    return method_func
                methods[method.name] = make_method(method, parent, env)
            cls_obj = UserClass(node.name, parent, methods)
            cls_obj.attrs = {}
            for a in (node.attrs or []):
                cls_obj.attrs[a.target.name] = self._eval_expr(a.value, env)
            env.set(node.name, cls_obj)
        else: raise NotImplementedError(f"Statement not implemented: {type(node).__name__}")

    def _eval_fstring(self, raw, env):
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

    def _to_string(self, val):
        if isinstance(val, UserInstance):
            str_method = val.cls.get_method('__str__')
            if str_method:
                try:
                    result = str_method(val)
                    if result is not None:
                        return str(result)
                except Exception as e:
                    return f'<error: {e}>'
            return f'<{val.cls.name} instance>'
        return str(val)

    def _setup_builtins_v2(self):
        env = self.global_env
        interp = self
        _M = object()
        types = {}

        def reg(name, fn, pytype=None):
            env.set(name, fn)
            if pytype is not None:
                types[fn] = pytype

        def _print(*args, sep=" ", end="\n", file=None, flush=False):
            sep = " " if sep is None else sep
            end = "\n" if end is None else end
            print(sep.join(interp._to_string(a) for a in args), end=end)

        def _str(x=""): return interp._to_string(x)
        def _int(x=0, base=None): return int(x) if base is None else int(x, base)
        def _float(x=0.0): return float(x)
        def _bool(x=False): return interp._is_truthy(x)
        def _list(x=()): return list(x)
        def _tuple(x=()): return tuple(x)
        def _set(x=()): return set(x)
        def _dict(*a, **kw): return dict(*a, **kw)

        reg("print", _print)
        reg("str", _str, str)
        reg("int", _int, int)
        reg("float", _float, float)
        reg("bool", _bool, bool)
        reg("list", _list, list)
        reg("tuple", _tuple, tuple)
        reg("set", _set, set)
        reg("dict", _dict, dict)

        def _isinstance(obj, cls):
            if isinstance(cls, tuple):
                return any(_isinstance(obj, c) for c in cls)
            if isinstance(cls, UserClass):
                if not isinstance(obj, UserInstance):
                    return False
                c = obj.cls
                while c is not None:
                    if c is cls:
                        return True
                    c = c.parent
                return False
            t = types.get(cls)
            if t is None:
                raise TypeError("isinstance() arg 2 must be a class or a tuple of classes")
            if isinstance(obj, UserInstance):
                return False
            return isinstance(obj, t)
        reg("isinstance", _isinstance)

        def _sorted(xs, key=None, reverse=False): return sorted(xs, key=key, reverse=reverse)
        def _reversed(xs): return list(reversed(xs))
        def _pick(fn, args, key, default):
            items = list(args[0]) if len(args) == 1 else list(args)
            if not items:
                if default is _M:
                    raise ValueError("min()/max() arg is an empty sequence")
                return default
            return fn(items, key=key)
        def _min(*args, key=None, default=_M): return _pick(min, args, key, default)
        def _max(*args, key=None, default=_M): return _pick(max, args, key, default)
        def _sum(xs, start=0): return sum(xs, start)
        def _enumerate(xs, start=0): return list(enumerate(xs, start))
        def _zip(*xs): return list(zip(*xs))
        def _map(f, *xs): return list(map(f, *xs))
        def _filter(f, xs): return list(filter(f, xs))
        reg("sorted", _sorted); reg("reversed", _reversed)
        reg("min", _min); reg("max", _max); reg("sum", _sum)
        reg("enumerate", _enumerate); reg("zip", _zip)
        reg("map", _map); reg("filter", _filter)

        def _round(x, n=None): return round(x) if n is None else round(x, n)
        def _pow(a, b, m=None): return pow(a, b) if m is None else pow(a, b, m)
        reg("round", _round); reg("pow", _pow)
        reg("divmod", lambda a, b: divmod(a, b))
        reg("chr", lambda n: chr(n)); reg("ord", lambda c: ord(c))
        reg("format", lambda v, spec="": format(v, spec))
        reg("hash", lambda x: hash(x)); reg("id", lambda x: id(x))
        reg("callable", lambda x: callable(x) or isinstance(x, UserClass))
        reg("iter", lambda x: iter(x))

        def _next(it, default=_M):
            try:
                return next(it)
            except StopIteration:
                if default is _M:
                    raise
                return default
        reg("next", _next)

        def _getattr(obj, name, default=_M):
            try:
                return interp._eval_expr(Attribute(Const(obj), name), interp.global_env)
            except AttributeError:
                if default is _M:
                    raise
                return default
        def _hasattr(obj, name):
            try:
                interp._eval_expr(Attribute(Const(obj), name), interp.global_env)
                return True
            except AttributeError:
                return False
        def _setattr(obj, name, v):
            if isinstance(obj, UserInstance):
                obj.attributes[name] = v
            else:
                setattr(obj, name, v)
        reg("getattr", _getattr); reg("hasattr", _hasattr); reg("setattr", _setattr)

    def _setup_exceptions(self):
        def exc_init(this, *args):
            this.attributes["args"] = tuple(args)
            if len(args) == 1: this.attributes["message"] = str(args[0])
            elif args: this.attributes["message"] = str(tuple(args))
            else: this.attributes["message"] = ""
        def exc_str(this, *a):
            return str(this.attributes.get("message", ""))
        base = UserClass("Exception", None, {"__init__": exc_init, "__str__": exc_str})
        base.attrs = {}
        classes = {"Exception": base}
        tree = [
            ("ArithmeticError", "Exception"), ("ZeroDivisionError", "ArithmeticError"), ("OverflowError", "ArithmeticError"),
            ("LookupError", "Exception"), ("KeyError", "LookupError"), ("IndexError", "LookupError"),
            ("ValueError", "Exception"), ("TypeError", "Exception"), ("NameError", "Exception"),
            ("AttributeError", "Exception"), ("RuntimeError", "Exception"),
            ("NotImplementedError", "RuntimeError"), ("RecursionError", "RuntimeError"),
            ("AssertionError", "Exception"), ("StopIteration", "Exception"),
        ]
        for name, parent in tree:
            c = UserClass(name, classes[parent], {})
            c.attrs = {}
            classes[name] = c
        self.exception_classes = classes
        for name, c in classes.items():
            self.global_env.set(name, c)

    def _is_truthy(self, val):
        if val is None or val is False: return False
        if isinstance(val, (int, float)) and val == 0: return False
        if isinstance(val, (str, list, dict)) and len(val) == 0: return False
        return True

    def _eval_expr(self, node, env):
        if isinstance(node, Const): return node.value
        if isinstance(node, Number): return node.value
        if isinstance(node, String): return node.value
        if isinstance(node, FString): return _eval_fstring2(self, node.value, env)
        if isinstance(node, Bool): return node.value
        if isinstance(node, NoneType): return None
        if isinstance(node, Var): return env.get(node.name)
        if isinstance(node, ListExpr): return _eval_elems(self, node.elements, env)
        if isinstance(node, TupleExpr): return tuple(_eval_elems(self, node.elements, env))
        if isinstance(node, SetExpr): return set(_eval_elems(self, node.elements, env))
        if isinstance(node, ListComp):
            iterable = self._eval_expr(node.iterable, env)
            result = []
            for item in iterable:
                loop_env = Environment(env)
                loop_env.set(node.target, item)
                if node.condition is None or self._is_truthy(self._eval_expr(node.condition, loop_env)):
                    result.append(self._eval_expr(node.expr, loop_env))
            return result
        if isinstance(node, DictExpr): return _eval_dict(self, node, env)
        if isinstance(node, Subscript): return self._eval_expr(node.obj, env)[self._eval_expr(node.index, env)]
        if isinstance(node, Attribute):
            obj = self._eval_expr(node.obj, env); name = node.name
            if isinstance(obj, UserInstanceProxy):
                method = obj.parent_cls.get_method(name)
                if method: return lambda *args, **kw: method(obj.instance, *args, **kw)
                raise AttributeError(f"Parent class has no attribute '{name}'")
            if isinstance(obj, (str, list, dict)):
                if hasattr(obj, name): return getattr(obj, name)
                raise AttributeError(f"'{type(obj).__name__}' object has no attribute '{name}'")
            if isinstance(obj, UserInstance):
                if name in obj.attributes: return obj.attributes[name]
                method = obj.cls.get_method(name)
                if method: return lambda *args, **kw: method(obj, *args, **kw)
                _ca = _class_attr(obj.cls, name)
                if _ca is not _MISSING: return _ca
                raise AttributeError(f"'{obj.cls.name}' object has no attribute '{name}'")
            if isinstance(obj, UserClass):
                v = _class_attr(obj, name)
                if v is not _MISSING: return v
                m = obj.get_method(name)
                if m: return m
                raise AttributeError(f"type object '{obj.name}' has no attribute '{name}'")
            return getattr(obj, name)
        if isinstance(node, Comp): return _eval_comp(self, node, env)
        if isinstance(node, Starred): raise SyntaxError("can't use starred expression here")
        if isinstance(node, IfExpr):
            if self._is_truthy(self._eval_expr(node.cond, env)): return self._eval_expr(node.then, env)
            return self._eval_expr(node.other, env)
        if isinstance(node, SliceExpr):
            lo = self._eval_expr(node.lower, env) if node.lower is not None else None
            up = self._eval_expr(node.upper, env) if node.upper is not None else None
            st = self._eval_expr(node.step, env) if node.step is not None else None
            return slice(lo, up, st)
        if isinstance(node, Lambda):
            lam_defaults = [self._eval_expr(d, env) if d is not None else None for d in (node.defaults or [None] * len(node.params))]
            def lam(*args, **kw):
                lam_env = Environment(env)
                for i, p in enumerate(node.params):
                    if i < len(args): lam_env.set(p, args[i])
                    elif p in kw: lam_env.set(p, kw[p])
                    else: lam_env.set(p, lam_defaults[i])
                return self._eval_expr(node.body, lam_env)
            return lam
        if isinstance(node, DictComp):
            result = {}
            for item in self._eval_expr(node.iterable, env):
                loop_env = Environment(env)
                loop_env.set(node.target, item)
                if node.condition is None or self._is_truthy(self._eval_expr(node.condition, loop_env)):
                    result[self._eval_expr(node.key, loop_env)] = self._eval_expr(node.value, loop_env)
            return result
        if isinstance(node, BinOp):
            if node.op == "and":
                l_val = self._eval_expr(node.left, env)
                return self._eval_expr(node.right, env) if self._is_truthy(l_val) else l_val
            if node.op == "or":
                l_val = self._eval_expr(node.left, env)
                return l_val if self._is_truthy(l_val) else self._eval_expr(node.right, env)
            left = self._eval_expr(node.left, env); right = self._eval_expr(node.right, env); op = node.op
            if op == "+": return left + right
            if op == "-": return left - right
            if op == "*": return left * right
            if op == "/": return left / right
            if op == "//": return left // right
            if op == "%": return left % right
            if op == "**": return left ** right
            if op == "==": return left == right
            if op == "!=": return left != right
            if op == "<": return left < right
            if op == ">": return left > right
            if op == "<=": return left <= right
            if op == ">=": return left >= right
            if op == "in": return left in right
            if op == "not in": return left not in right
            if op == "is": return left is right
            if op == "is not": return left is not right
            if op == "&": return left & right
            if op == "|": return left | right
            if op == "^": return left ^ right
            if op == "<<": return left << right
            if op == ">>": return left >> right
            if op == "and": return right if self._is_truthy(left) else left
            if op == "or": return left if self._is_truthy(left) else right
            raise RuntimeError(f"Unknown operator {op}")
        if isinstance(node, UnaryOp):
            val = self._eval_expr(node.operand, env)
            if node.op == "-": return -val
            if node.op == "+": return +val
            if node.op == "~": return ~val
            if node.op == "not": return not self._is_truthy(val)
        if isinstance(node, Call):
            callee = self._eval_expr(node.callee, env); args = _eval_elems(self, node.args, env)
            kwargs = {k: self._eval_expr(v, env) for k, v in (node.kwargs or {}).items()}
            for _sp in (node.kw_splats or []):
                kwargs.update(self._eval_expr(_sp, env))
            if isinstance(callee, UserClass):
                instance = UserInstance(callee)
                init_method = callee.get_method("__init__")
                if init_method: init_method(instance, *args, **kwargs)
                return instance
            if not callable(callee): raise TypeError(f"'{type(callee).__name__}' object is not callable")
            return callee(*args, **kwargs)
        raise NotImplementedError(f"Expression not implemented: {type(node).__name__}")


def _check_kwargs(fname, params, kwargs, kwarg=None):
    for k in kwargs:
        if k not in params and not kwarg:
            raise TypeError(f"{fname}() got an unexpected keyword argument '{k}'")


_MISSING = object()

def _class_attr(cls, name):
    c = cls
    while c is not None:
        attrs = getattr(c, "attrs", None)
        if attrs and name in attrs:
            return attrs[name]
        c = c.parent
    return _MISSING


class PyRaise(Exception):
    def __init__(self, inst=None, legacy=None):
        super().__init__()
        self.inst = inst
        self.legacy = legacy
        self.line = 0

    def message(self):
        if self.inst is not None:
            return str(self.inst.attributes.get("message", ""))
        return str(self.legacy)

    def __str__(self):
        if self.inst is not None:
            m = self.message()
            text = (self.inst.cls.name + ": " + m) if m else self.inst.cls.name
        else:
            text = self.message()
        return text + (" at line " + str(self.line) if self.line else "")


def _new_instance(cls, *args):
    inst = UserInstance(cls)
    init = cls.get_method("__init__")
    if init:
        init(inst, *args)
    return inst

def _is_exc_instance(interp, inst):
    base = interp.exception_classes["Exception"]
    c = inst.cls
    while c is not None:
        if c is base:
            return True
        c = c.parent
    return False

def _make_raise(interp, val):
    if isinstance(val, UserClass):
        val = _new_instance(val)
    if isinstance(val, UserInstance):
        if not _is_exc_instance(interp, val):
            return TypeError("exceptions must derive from Exception")
        return PyRaise(inst=val)
    return PyRaise(legacy=val)

def _strip_line(msg):
    return msg.split(" at line ", 1)[0] if " at line " in msg else msg

def _to_exc_instance(interp, e):
    """Return (instance, legacy_text_or_None, is_host_error)."""
    classes = interp.exception_classes
    if isinstance(e, PyRaise):
        if e.inst is not None:
            return e.inst, None, False
        return _new_instance(classes["Exception"], e.message()), e.message(), False
    cls = classes["Exception"]
    for t in type(e).__mro__:
        c = classes.get(t.__name__)
        if c is not None:
            cls = c
            break
    if isinstance(e, KeyError) and e.args:
        a = e.args[0]
        msg = _strip_line(a) if isinstance(a, str) and " at line " in a else repr(a)
    else:
        msg = _strip_line(str(e))
    return _new_instance(cls, msg), None, True

def _exc_match(inst, spec):
    if isinstance(spec, tuple):
        return any(_exc_match(inst, s) for s in spec)
    if isinstance(spec, UserClass):
        c = inst.cls
        while c is not None:
            if c is spec:
                return True
            c = c.parent
        return False
    raise TypeError("except clause needs an exception class or a tuple of them")

def _exec_try(interp, node, env):
    control = (ReturnException, BreakException, ContinueException)
    handlers = node.handlers
    if handlers is None and node.except_block is not None:
        handlers = [(None, node.except_var, node.except_block)]
    handlers = handlers or []
    try:
        try:
            interp._eval_block(node.try_block, env)
        except control:
            raise
        except Exception as e:
            if not handlers:
                raise
            inst, legacy, host = _to_exc_instance(interp, e)
            for type_expr, var, block in handlers:
                if type_expr is not None:
                    if not _exc_match(inst, interp._eval_expr(type_expr, env)):
                        continue
                if var:
                    if legacy is not None:
                        val = legacy
                    elif host and type_expr is None:
                        val = _strip_line(str(e))
                    else:
                        val = inst
                    env.set(var, val)
                interp._eval_block(block, env)
                break
            else:
                raise
        else:
            if node.else_block is not None:
                interp._eval_block(node.else_block, env)
    finally:
        if node.finally_block is not None:
            interp._eval_block(node.finally_block, env)


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
            key = interp._eval_expr(k, env)
            result[key] = interp._eval_expr(v, env)
    return result


def _assign_to(interp, target, value, env):
    if isinstance(target, Var):
        env.set(target.name, value)
    elif isinstance(target, Subscript):
        obj = interp._eval_expr(target.obj, env)
        obj[interp._eval_expr(target.index, env)] = value
    elif isinstance(target, Attribute):
        obj = interp._eval_expr(target.obj, env)
        if isinstance(obj, UserInstance): obj.attributes[target.name] = value
        else: setattr(obj, target.name, value)
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
    if node.kind == "dict": return pairs
    if node.kind == "set": return set(items)
    if node.kind == "gen": return iter(items)
    return items


def _eval_fstring2(interp, raw, env):
    from lexer import Lexer as _L, _unescape
    from parser import Parser as _P
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
            expr_text = inner
            spec = ""
            d = 0; q = None
            for k, ch in enumerate(inner):
                if q:
                    if ch == q: q = None
                elif ch in "'\"": q = ch
                elif ch in "([{": d += 1
                elif ch in ")]}": d -= 1
                elif d == 0 and ch == ":":
                    expr_text = inner[:k]
                    spec = inner[k + 1:]
                    break
            conv = None
            if len(expr_text) >= 2 and expr_text[-2] == "!" and expr_text[-1] in "rsa":
                conv = expr_text[-1]
                expr_text = expr_text[:-2]
            tree = _P(_L(expr_text).tokenize()).parse()
            if not tree.statements or not hasattr(tree.statements[0], "expr"):
                raise SyntaxError("f-string: invalid expression")
            val = interp._eval_expr(tree.statements[0].expr, env)
            if "{" in spec:
                spec = _eval_fstring2(interp, spec, env)
            if conv == "r": val = repr(val)
            elif conv == "s": val = interp._to_string(val)
            elif conv == "a": val = ascii(val)
            if spec:
                if isinstance(val, UserInstance):
                    val = interp._to_string(val)
                piece = format(val, spec)
            else:
                piece = interp._to_string(val)
            if lit:
                out.append(_unescape("".join(lit)))
                lit = []
            out.append(piece)
            i = j + 1
            continue
        if c == "}":
            if i + 1 < n and raw[i + 1] == "}":
                lit.append("}"); i += 2; continue
            raise SyntaxError("f-string: single '}' is not allowed")
        lit.append(c)
        i += 1
    if lit:
        out.append(_unescape("".join(lit)))
    return "".join(out)
