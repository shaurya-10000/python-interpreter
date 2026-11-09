from ast_nodes import *
from environment import Environment

class ReturnException(Exception):
    def __init__(self, value): self.value = value
class BreakException(Exception): pass
class ContinueException(Exception): pass

def _c3(cls):
    seqs = [list(b.mro()) for b in cls.bases] + [list(cls.bases)]
    result = [cls]
    while True:
        seqs = [s for s in seqs if s]
        if not seqs:
            return result
        for s in seqs:
            cand = s[0]
            if not any(cand in t[1:] for t in seqs):
                break
        else:
            names = ", ".join(b.name for b in cls.bases)
            raise TypeError("Cannot create a consistent method resolution order (MRO) for bases " + names)
        result.append(cand)
        for s in seqs:
            if s[0] is cand:
                del s[0]


class UserClass:
    def __init__(self, name, parent, methods, bases=None):
        self.name = name
        self.parent = parent
        self.methods = methods
        self.bases = list(bases) if bases is not None else ([parent] if parent is not None else [])
        self.attrs = {}
        self._mro_cache = None

    def mro(self):
        if self._mro_cache is None:
            self._mro_cache = _c3(self)
        return self._mro_cache

    def get_method(self, name):
        for c in self.mro():
            if name in c.methods:
                return c.methods[name]
        return None

    def __repr__(self):
        return "<class '" + self.name + "'>"


def _delegate(user_name):
    def op(self, *args):
        method = self.cls.get_method(user_name)
        if method is None:
            return NotImplemented
        return method(self, *args)
    return op


def _delegate_unary(user_name, symbol):
    def op(self):
        method = self.cls.get_method(user_name)
        if method is None:
            raise TypeError("bad operand type for " + symbol + ": '" + self.cls.name + "'")
        return method(self)
    return op


class UserInstance:
    def __init__(self, cls):
        self.cls = cls
        self.attributes = {}

    def __repr__(self):
        method = self.cls.get_method("__repr__")
        if method is None:
            return "<" + self.cls.name + " instance>"
        result = method(self)
        if not isinstance(result, str):
            raise TypeError("__repr__ returned non-string (type " + type(result).__name__ + ")")
        return result

    def __eq__(self, other):
        method = self.cls.get_method("__eq__")
        if method is None:
            return self is other
        return method(self, other)

    def __hash__(self):
        method = self.cls.get_method("__hash__")
        if method is not None:
            return method(self)
        if self.cls.get_method("__eq__") is not None:
            raise TypeError("unhashable type: '" + self.cls.name + "'")
        return object.__hash__(self)

    def __iter__(self):
        method = self.cls.get_method("__iter__")
        if method is not None:
            result = method(self)
            if isinstance(result, UserInstance):
                return result
            return iter(result)
        if self.cls.get_method("__getitem__") is not None:
            return _sequence_iter(self)
        raise TypeError("'" + self.cls.name + "' object is not iterable")

    def __next__(self):
        method = self.cls.get_method("__next__")
        if method is None:
            raise TypeError("'" + self.cls.name + "' object is not an iterator")
        try:
            return method(self)
        except PyRaise as e:
            if e.inst is not None and any(c.name == "StopIteration" for c in e.inst.cls.mro()):
                raise StopIteration from None
            raise

    def __contains__(self, item):
        method = self.cls.get_method("__contains__")
        if method is not None:
            return bool(method(self, item))
        for value in self:
            if value is item or value == item:
                return True
        return False


for _op in ("add", "sub", "mul", "truediv", "floordiv", "mod", "pow", "and", "or", "xor", "lshift", "rshift"):
    setattr(UserInstance, "__" + _op + "__", _delegate("__" + _op + "__"))
    setattr(UserInstance, "__r" + _op + "__", _delegate("__r" + _op + "__"))
for _op in ("lt", "le", "gt", "ge"):
    setattr(UserInstance, "__" + _op + "__", _delegate("__" + _op + "__"))
for _op, _symbol in (("neg", "-"), ("pos", "+"), ("invert", "~"), ("abs", "abs()")):
    setattr(UserInstance, "__" + _op + "__", _delegate_unary("__" + _op + "__", "unary " + _symbol))
setattr(UserInstance, "__int__", _delegate_unary("__int__", "int()"))
setattr(UserInstance, "__float__", _delegate_unary("__float__", "float()"))


class UserInstanceProxy:
    def __init__(self, parent_cls, instance):
        self.parent_cls = parent_cls
        self.instance = instance

class Interpreter:
    def __init__(self):
        self.global_env = Environment(); self._setup_builtins(); self._setup_builtins_v2(); self._setup_exceptions(); self._setup_builtins_v3(); self._setup_modules()
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
        t = type(node)
        if t is ReturnStmt:
            raise ReturnException(self._eval_expr(node.value, env) if node.value else None)
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
        if isinstance(node, ExprStmt): self._eval_expr(node.expr, env)
        elif isinstance(node, PrintStmt):
            val = self._eval_expr(node.expr, env)
            print(self._to_string(val))
        elif isinstance(node, Assign):
            val = self._eval_expr(node.value, env)
            if isinstance(node.target, Var): env.set(node.target.name, val)
            elif isinstance(node.target, Subscript):
                obj = self._eval_expr(node.target.obj, env)
                _set_item(obj, self._eval_expr(node.target.index, env), val)
            elif isinstance(node.target, Attribute):
                obj = self._eval_expr(node.target.obj, env)
                _set_attr(self, obj, node.target.name, val)
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
            _exc = _make_raise(self, self._eval_expr(node.value, env))
            if getattr(node, "cause", None) is not None:
                _cause = self._eval_expr(node.cause, env)
                if isinstance(_exc, PyRaise) and _exc.inst is not None and isinstance(_cause, UserInstance):
                    _exc.inst.attributes["__cause__"] = _cause
            raise _exc
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
            evaluated_kwonly = [(k, self._eval_expr(d, env) if d is not None else _MISSING) for k, d in (getattr(node, 'kwonly', None) or [])]
            frame_entry = (node.name, getattr(node, 'line', 0))
            def func(*args, **kwargs):
                func_env = Environment(env)
                if kwargs: _check_kwargs(node.name, list(node.params) + _kwonly_names(node), kwargs, node.kwarg)
                if node.kwarg: func_env.set(node.kwarg, {k: v for k, v in kwargs.items() if k not in node.params and k not in _kwonly_names(node)})
                if node.vararg: func_env.set(node.vararg, tuple(args[len(node.params):]))
                if evaluated_kwonly: _bind_kwonly(node, func_env, kwargs, evaluated_kwonly)
                for i, param in enumerate(node.params):
                    if i < len(args) or param in kwargs: func_env.set(param, args[i] if i < len(args) else kwargs[param])
                    elif evaluated_defaults[i] is not None: func_env.set(param, evaluated_defaults[i])
                    else: func_env.set(param, None)
                self.call_stack.append(frame_entry)
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
            for _d in reversed(node.decorators or []):
                func = _call_any(self, self._eval_expr(_d, env), func)
            env.set(node.name, func)
        elif isinstance(node, ReturnStmt):
            raise ReturnException(self._eval_expr(node.value, env) if node.value else None)
        elif isinstance(node, BreakStmt): raise BreakException()
        elif isinstance(node, ContinueStmt): raise ContinueException()
        elif isinstance(node, GlobalStmt): env.global_names = env.global_names | set(node.names)
        elif isinstance(node, DelStmt):
            for t in node.targets:
                if isinstance(t, Var):
                    if t.name not in env.vars: raise NameError(f"Name '{t.name}' is not defined")
                    del env.vars[t.name]
                elif isinstance(t, Subscript):
                    _del_item(self._eval_expr(t.obj, env), self._eval_expr(t.index, env))
                elif isinstance(t, Attribute):
                    obj = self._eval_expr(t.obj, env)
                    if isinstance(obj, UserInstance): del obj.attributes[t.name]
                    else: delattr(obj, t.name)
                else: raise SyntaxError("cannot delete this expression")
        elif isinstance(node, NonlocalStmt): env.nonlocal_names = env.nonlocal_names | set(node.names)
        elif isinstance(node, ChainAssign):
            val = self._eval_expr(node.value, env)
            for t in node.targets:
                self._eval_statement_inner(Assign(t, Const(val), line=node.line), env)
        elif isinstance(node, WithStmt): _exec_with(self, node, env)
        elif isinstance(node, ImportStmt): _exec_import(self, node, env)
        elif isinstance(node, FromImportStmt): _exec_from_import(self, node, env)
        elif isinstance(node, PassStmt): pass
        elif isinstance(node, ClassDef):
            _exec_classdef(self, node, env)
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
            return repr(val)
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

    def _setup_builtins_v3(self):
        env = self.global_env

        object_cls = UserClass("object", None, {})
        env.set("object", object_cls)
        env.set("NotImplemented", NotImplemented)

        by_pytype = {}
        for type_name, py_type in (("int", int), ("str", str), ("float", float), ("bool", bool),
                                   ("list", list), ("tuple", tuple), ("set", set), ("dict", dict)):
            wrapped = BuiltinType(type_name, py_type, env.get(type_name))
            env.set(type_name, wrapped)
            by_pytype[py_type] = wrapped
        extra_types = {}

        def _type(x):
            if isinstance(x, UserInstance):
                return x.cls
            if isinstance(x, (UserClass, BuiltinType)):
                return type_obj
            found = by_pytype.get(type(x))
            if found is None:
                found = extra_types.get(type(x))
                if found is None:
                    found = BuiltinType(type(x).__name__, type(x))
                    extra_types[type(x)] = found
            return found
        type_obj = BuiltinType("type", type, _type)
        env.set("type", type_obj)

        def _isinstance(obj, cls):
            if isinstance(cls, tuple):
                return any(_isinstance(obj, c) for c in cls)
            if isinstance(cls, UserClass):
                if cls is object_cls:
                    return True
                if isinstance(obj, UserInstance):
                    return cls in obj.cls.mro()
                return False
            if isinstance(cls, BuiltinType):
                if cls.pytype is type:
                    return isinstance(obj, (UserClass, BuiltinType))
                if isinstance(obj, (UserInstance, UserClass, BuiltinType)):
                    return False
                return isinstance(obj, cls.pytype)
            raise TypeError("isinstance() arg 2 must be a class or a tuple of classes")
        env.set("isinstance", _isinstance)

        def _issubclass(sub, parent):
            if isinstance(parent, tuple):
                return any(_issubclass(sub, p) for p in parent)
            if isinstance(parent, UserClass):
                if parent is object_cls:
                    return isinstance(sub, UserClass)
                return isinstance(sub, UserClass) and parent in sub.mro()
            if isinstance(parent, BuiltinType) and isinstance(sub, BuiltinType):
                return issubclass(sub.pytype, parent.pytype)
            return False
        env.set("issubclass", _issubclass)

        env.set("property", lambda fget=None, fset=None: PyProperty(fget, fset))
        env.set("staticmethod", lambda fn: PyStaticMethod(fn))
        env.set("classmethod", lambda fn: PyClassMethod(fn))

        def _len(x):
            if isinstance(x, UserInstance):
                method = x.cls.get_method("__len__")
                if method is None:
                    raise TypeError("object of type '" + x.cls.name + "' has no len()")
                n = method(x)
                if not isinstance(n, int):
                    raise TypeError("'" + type(n).__name__ + "' object cannot be interpreted as an integer")
                if n < 0:
                    raise ValueError("__len__() should return >= 0")
                return n
            return len(x)
        env.set("len", _len)

        env.set("callable", lambda x: callable(x) or isinstance(x, UserClass)
                or (isinstance(x, UserInstance) and x.cls.get_method("__call__") is not None))

        def _setattr(obj, name, value):
            _set_attr(self, obj, name, value)
        env.set("setattr", _setattr)

    def _setup_modules(self):
        env = self.global_env
        for name, parent in (("ImportError", "Exception"), ("ModuleNotFoundError", "ImportError"),
                             ("OSError", "Exception"), ("FileNotFoundError", "OSError"),
                             ("PermissionError", "OSError"), ("FileExistsError", "OSError"),
                             ("IsADirectoryError", "OSError")):
            cls = UserClass(name, self.exception_classes[parent], {})
            self.exception_classes[name] = cls
            env.set(name, cls)
        env.set("open", _builtin_open)
        self.builtins_snapshot = dict(env.vars)
        self.modules = {}
        self.virtual_modules = {}
        self.search_paths = [_os.getcwd()]
        env.set("__name__", "__main__")

    def set_script(self, path):
        path = _os.path.abspath(path)
        self.global_env.set("__file__", path)
        folder = _os.path.dirname(path)
        self.search_paths = [folder] + [p for p in self.search_paths if p != folder]

    def register_module(self, name, source):
        self.virtual_modules[name] = source
        self.modules.pop(name, None)

    def _is_truthy(self, val):
        if val is None or val is False: return False
        if isinstance(val, (int, float)) and val == 0: return False
        if isinstance(val, (str, list, dict, set, tuple, frozenset)) and len(val) == 0: return False
        if isinstance(val, UserInstance): return _instance_truth(val)
        return True

    def _eval_expr(self, node, env):
        t = type(node)
        if t is Number or t is String or t is Bool:
            return node.value
        if t is Var:
            e = env
            name = node.name
            while e is not None:
                v = e.vars
                if name in v:
                    return v[name]
                e = e.parent
            raise NameError(f"Name '{name}' is not defined")
        if t is BinOp:
            f = _FAST_BINOPS.get(node.op)
            if f is not None:
                return f(self._eval_expr(node.left, env), self._eval_expr(node.right, env))
        elif t is Call:
            plain = getattr(node, "_plain", None)
            if plain is None:
                plain = (not node.kwargs and not node.kw_splats
                         and not any(type(a) is Starred for a in node.args))
                node._plain = plain
            if plain:
                callee = self._eval_expr(node.callee, env)
                args = [self._eval_expr(a, env) for a in node.args]
                if type(callee) is _FunctionType:
                    return callee(*args)
                return _call_plain(callee, args)
        elif t is Attribute:
            return _get_attr(self, self._eval_expr(node.obj, env), node.name)
        elif t is Subscript:
            return _get_item(self._eval_expr(node.obj, env), self._eval_expr(node.index, env))
        if isinstance(node, NamedExpr):
            _v = self._eval_expr(node.value, env)
            env.set(node.name, _v)
            return _v
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
        if isinstance(node, Subscript): return _get_item(self._eval_expr(node.obj, env), self._eval_expr(node.index, env))
        if isinstance(node, Attribute):
            return _get_attr(self, self._eval_expr(node.obj, env), node.name)
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
                if getattr(node, "vararg", None): lam_env.set(node.vararg, tuple(args[len(node.params):]))
                if getattr(node, "kwarg", None): lam_env.set(node.kwarg, {k: v for k, v in kw.items() if k not in node.params})
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
            if node.op in _INPLACE:
                return _INPLACE[node.op](self._eval_expr(node.left, env), self._eval_expr(node.right, env))
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
            if isinstance(callee, UserInstance):
                dunder_call = callee.cls.get_method("__call__")
                if dunder_call is not None: return dunder_call(callee, *args, **kwargs)
            if not callable(callee): raise TypeError(f"'{type(callee).__name__}' object is not callable")
            return callee(*args, **kwargs)
        raise NotImplementedError(f"Expression not implemented: {type(node).__name__}")


def _check_kwargs(fname, params, kwargs, kwarg=None):
    for k in kwargs:
        if k not in params and not kwarg:
            raise TypeError(f"{fname}() got an unexpected keyword argument '{k}'")


_MISSING = object()

def _class_attr(cls, name):
    for c in cls.mro():
        attrs = getattr(c, "attrs", None)
        if attrs and name in attrs:
            return attrs[name]
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
    return base in inst.cls.mro()

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
        return spec in inst.cls.mro()
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
        _set_item(obj, interp._eval_expr(target.index, env), value)
    elif isinstance(target, Attribute):
        obj = interp._eval_expr(target.obj, env)
        _set_attr(interp, obj, target.name, value)
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
            debug = None
            _st = expr_text.rstrip()
            if _st.endswith("=") and not _st.endswith(("==", "!=", "<=", ">=")):
                debug = expr_text
                expr_text = _st[:-1]
                if conv is None and not spec:
                    conv = "r"
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
            out.append((debug + piece) if debug is not None else piece)
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


class PyProperty:
    def __init__(self, fget=None, fset=None):
        self.fget = fget
        self.fset = fset

    def getter(self, fn):
        return PyProperty(fn, self.fset)

    def setter(self, fn):
        return PyProperty(self.fget, fn)

    def __repr__(self):
        return "<property>"


class PyStaticMethod:
    def __init__(self, fn):
        self.fn = fn


class PyClassMethod:
    def __init__(self, fn):
        self.fn = fn


class BuiltinType:
    def __init__(self, name, pytype, fn=None):
        self.name = name
        self.pytype = pytype
        self.fn = fn
        self.__name__ = name

    def __call__(self, *args, **kwargs):
        if self.fn is None:
            raise TypeError("cannot create '" + self.name + "' instances")
        return self.fn(*args, **kwargs)

    def __repr__(self):
        return "<class '" + self.name + "'>"


def _object_init(self, *args, **kwargs):
    return None


class _SuperView:
    """Resolves super().name by walking the instance's MRO after the defining class."""
    def __init__(self, owner, start):
        self.owner = owner
        self.start = start

    def get_method(self, name):
        mro = self.start.mro()
        if self.owner in mro:
            rest = mro[mro.index(self.owner) + 1:]
        else:
            rest = self.owner.mro()[1:]
        for c in rest:
            if name in c.methods:
                return c.methods[name]
        if name == "__init__":
            return _object_init
        return None


def _instance_truth(val):
    method = val.cls.get_method("__bool__")
    if method is not None:
        return bool(method(val))
    method = val.cls.get_method("__len__")
    if method is not None:
        return method(val) != 0
    return True


def _sequence_iter(obj):
    method = obj.cls.get_method("__getitem__")
    i = 0
    while True:
        try:
            value = method(obj, i)
        except IndexError:
            return
        except PyRaise as e:
            if e.inst is not None and any(c.name == "IndexError" for c in e.inst.cls.mro()):
                return
            raise
        yield value
        i += 1


def _bind_member(member, instance, cls):
    if isinstance(member, PyStaticMethod):
        return member.fn
    if isinstance(member, PyClassMethod):
        fn = member.fn
        return lambda *a, **k: fn(cls, *a, **k)
    if isinstance(member, PyProperty):
        if member.fget is None:
            raise AttributeError("unreadable attribute")
        return member.fget(instance)
    return lambda *a, **k: member(instance, *a, **k)


def _get_attr(interp, obj, name):
    if isinstance(obj, PyModule):
        return obj.get(name)
    if isinstance(obj, UserInstance):
        if name == "__class__":
            return obj.cls
        member = obj.cls.get_method(name)
        if isinstance(member, PyProperty):
            return _bind_member(member, obj, obj.cls)
        if name in obj.attributes:
            return obj.attributes[name]
        if member is not None:
            return _bind_member(member, obj, obj.cls)
        found = _class_attr(obj.cls, name)
        if found is not _MISSING:
            return found
        hook = obj.cls.get_method("__getattr__")
        if hook is not None:
            return hook(obj, name)
        raise AttributeError(f"'{obj.cls.name}' object has no attribute '{name}'")
    if isinstance(obj, UserInstanceProxy):
        member = obj.parent_cls.get_method(name)
        if member is None:
            raise AttributeError(f"Parent class has no attribute '{name}'")
        start = obj.instance.cls if isinstance(obj.instance, UserInstance) else obj.instance
        return _bind_member(member, obj.instance, start)
    if isinstance(obj, UserClass):
        found = _class_attr(obj, name)
        if found is not _MISSING:
            return found
        member = obj.get_method(name)
        if member is None:
            if name == "__name__":
                return obj.name
            raise AttributeError(f"type object '{obj.name}' has no attribute '{name}'")
        if isinstance(member, PyStaticMethod):
            return member.fn
        if isinstance(member, PyClassMethod):
            fn = member.fn
            return lambda *a, **k: fn(obj, *a, **k)
        return member
    if isinstance(obj, (str, list, dict)):
        if hasattr(obj, name):
            return getattr(obj, name)
        raise AttributeError(f"'{type(obj).__name__}' object has no attribute '{name}'")
    return getattr(obj, name)


def _set_attr(interp, obj, name, value):
    if isinstance(obj, PyModule):
        obj.env.vars[name] = value
        return
    if isinstance(obj, UserInstance):
        member = obj.cls.get_method(name)
        if isinstance(member, PyProperty):
            if member.fset is None:
                raise AttributeError(f"property '{name}' of '{obj.cls.name}' object has no setter")
            member.fset(obj, value)
            return
        obj.attributes[name] = value
    elif isinstance(obj, UserClass):
        obj.attrs[name] = value
    else:
        setattr(obj, name, value)


def _get_item(obj, index):
    if isinstance(obj, UserInstance):
        method = obj.cls.get_method("__getitem__")
        if method is None:
            raise TypeError(f"'{obj.cls.name}' object is not subscriptable")
        return method(obj, index)
    return obj[index]


def _set_item(obj, index, value):
    if isinstance(obj, UserInstance):
        method = obj.cls.get_method("__setitem__")
        if method is None:
            raise TypeError(f"'{obj.cls.name}' object does not support item assignment")
        method(obj, index, value)
        return
    obj[index] = value


def _del_item(obj, index):
    if isinstance(obj, UserInstance):
        method = obj.cls.get_method("__delitem__")
        if method is None:
            raise TypeError(f"'{obj.cls.name}' object doesn't support item deletion")
        method(obj, index)
        return
    del obj[index]


def _call_any(interp, callee, *args, **kwargs):
    if isinstance(callee, UserClass):
        instance = UserInstance(callee)
        init = callee.get_method("__init__")
        if init is not None:
            init(instance, *args, **kwargs)
        return instance
    if isinstance(callee, UserInstance):
        method = callee.cls.get_method("__call__")
        if method is None:
            raise TypeError(f"'{callee.cls.name}' object is not callable")
        return method(callee, *args, **kwargs)
    if not callable(callee):
        raise TypeError(f"'{type(callee).__name__}' object is not callable")
    return callee(*args, **kwargs)


def _make_method(interp, m, owner, class_env, defaults):
    kwarg = getattr(m, "kwarg", None)
    label = owner.name + "." + m.name
    frame_entry = (label, getattr(m, "line", 0))
    kwonly_vals = [(k, interp._eval_expr(d, class_env) if d is not None else _MISSING) for k, d in (getattr(m, 'kwonly', None) or [])]

    def method_func(*args, **kwargs):
        if kwargs: _check_kwargs(m.name, list(m.params) + _kwonly_names(m), kwargs, kwarg)
        scope = Environment(class_env)
        if kwarg:
            scope.set(kwarg, {k: v for k, v in kwargs.items() if k not in m.params and k not in _kwonly_names(m)})
        if m.vararg:
            scope.set(m.vararg, tuple(args[len(m.params):]))
        if kwonly_vals: _bind_kwonly(m, scope, kwargs, kwonly_vals)
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
        scope.set("super", lambda: UserInstanceProxy(_SuperView(owner, start), first))
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
            member = _call_any(interp, interp._eval_expr(deco, body), member)
        body.set(m.name, member)
        cls_obj.methods[m.name] = member
    env.set(node.name, cls_obj)


import operator as _operator

_INPLACE = {
    "+=": _operator.iadd, "-=": _operator.isub, "*=": _operator.imul, "/=": _operator.itruediv,
    "//=": _operator.ifloordiv, "%=": _operator.imod, "**=": _operator.ipow,
    "&=": _operator.iand, "|=": _operator.ior, "^=": _operator.ixor,
    "<<=": _operator.ilshift, ">>=": _operator.irshift,
}

for _n in ("add", "sub", "mul", "truediv", "floordiv", "mod", "pow", "and", "or", "xor", "lshift", "rshift"):
    setattr(UserInstance, "__i" + _n + "__", _delegate("__i" + _n + "__"))


def _kwonly_names(fnode):
    return [k for k, _ in (getattr(fnode, "kwonly", None) or [])]


def _bind_kwonly(fnode, scope, kwargs, vals):
    for k, default in vals:
        if k in kwargs:
            scope.set(k, kwargs[k])
        elif default is not _MISSING:
            scope.set(k, default)
        else:
            raise TypeError(f"{fnode.name}() missing required keyword-only argument: '{k}'")


import os as _os
import importlib as _importlib

_ALLOWED_HOST = {
    "math", "cmath", "random", "time", "datetime", "string", "json", "re", "itertools", "functools",
    "collections", "statistics", "operator", "copy", "textwrap", "decimal", "fractions", "heapq",
    "bisect", "io", "hashlib", "base64", "calendar", "pprint",
}


def _builtin_open(path, mode="r", buffering=-1, encoding=None, newline=None):
    if "b" not in mode and encoding is None:
        encoding = "utf-8"
    return open(path, mode, buffering, encoding=encoding, newline=newline)


class PyModule:
    def __init__(self, name, path, env):
        self.name = name
        self.path = path
        self.env = env

    def get(self, name):
        if name in self.env.vars:
            return self.env.vars[name]
        raise AttributeError(f"module '{self.name}' has no attribute '{name}'")

    def __repr__(self):
        return f"<module '{self.name}' from '{self.path}'>"


PyModule.__name__ = "module"


def _new_module_env(interp, name, path):
    env = Environment()
    env.vars.update(interp.builtins_snapshot)
    env.vars["__name__"] = name
    env.vars["__file__"] = path
    return env


def _find_module_source(interp, name):
    if name in interp.virtual_modules:
        return interp.virtual_modules[name], "<" + name + ">"
    rel = name.replace(".", _os.sep)
    for base in interp.search_paths:
        for candidate in (_os.path.join(base, rel + ".py"), _os.path.join(base, rel, "__init__.py")):
            if _os.path.isfile(candidate):
                with open(candidate, encoding="utf-8") as fh:
                    return fh.read(), candidate
    return None


def _load_module(interp, name):
    cached = interp.modules.get(name)
    if cached is not None:
        return cached
    found = _find_module_source(interp, name)
    if found is not None:
        source, path = found
        from lexer import Lexer as _Lx
        from parser import Parser as _Ps
        env = _new_module_env(interp, name, path)
        mod = PyModule(name, path, env)
        interp.modules[name] = mod
        try:
            try:
                tree = _Ps(_Lx(source).tokenize()).parse()
            except SyntaxError as ex:
                raise SyntaxError(f"in module '{name}': {ex}") from None
            interp._eval_block(tree, env)
        except BaseException:
            interp.modules.pop(name, None)
            raise
        return mod
    if name.split(".")[0] in _ALLOWED_HOST:
        try:
            mod = _importlib.import_module(name)
        except ImportError:
            raise ModuleNotFoundError(f"No module named '{name}'") from None
        interp.modules[name] = mod
        return mod
    raise ModuleNotFoundError(f"No module named '{name}'")


def _import_chain(interp, dotted):
    parts = dotted.split(".")
    mods = []
    for i in range(len(parts)):
        mod = _load_module(interp, ".".join(parts[:i + 1]))
        if mods and isinstance(mods[-1], PyModule):
            mods[-1].env.vars[parts[i]] = mod
        mods.append(mod)
    return mods


def _exec_import(interp, node, env):
    for dotted, alias in node.names:
        mods = _import_chain(interp, dotted)
        if alias:
            env.set(alias, mods[-1])
        else:
            env.set(dotted.split(".")[0], mods[0])


def _import_name(interp, mod, modname, name):
    try:
        if isinstance(mod, PyModule):
            return mod.get(name)
        return getattr(mod, name)
    except AttributeError:
        pass
    try:
        return _load_module(interp, modname + "." + name)
    except ModuleNotFoundError:
        pass
    raise ImportError(f"cannot import name '{name}' from '{modname}'")


def _module_public_names(interp, mod):
    if isinstance(mod, PyModule):
        table = mod.env.vars
        if "__all__" in table:
            return list(table["__all__"])
        snap = interp.builtins_snapshot
        return [k for k, v in table.items() if not k.startswith("_") and not (k in snap and snap[k] is v)]
    exported = getattr(mod, "__all__", None)
    if exported is not None:
        return list(exported)
    return [k for k in dir(mod) if not k.startswith("_")]


def _exec_from_import(interp, node, env):
    mod = _import_chain(interp, node.module)[-1]
    if node.names is None:
        for name in _module_public_names(interp, mod):
            env.set(name, _import_name(interp, mod, node.module, name))
        return
    for name, alias in node.names:
        env.set(alias or name, _import_name(interp, mod, node.module, name))


def _cm_parts(mgr):
    if isinstance(mgr, UserInstance):
        enter = mgr.cls.get_method("__enter__")
        leave = mgr.cls.get_method("__exit__")
        if enter is None or leave is None:
            raise TypeError(f"'{mgr.cls.name}' object does not support the context manager protocol")
        return (lambda: enter(mgr)), (lambda t, v, tb: leave(mgr, t, v, tb))
    enter = getattr(mgr, "__enter__", None)
    leave = getattr(mgr, "__exit__", None)
    if enter is None or leave is None:
        raise TypeError(f"'{type(mgr).__name__}' object does not support the context manager protocol")
    return enter, leave


def _exec_with(interp, node, env):
    control = (ReturnException, BreakException, ContinueException)

    def run(i):
        if i == len(node.items):
            interp._eval_block(node.body, env)
            return
        ctx_expr, var = node.items[i]
        enter, leave = _cm_parts(interp._eval_expr(ctx_expr, env))
        value = enter()
        if var:
            env.set(var, value)
        try:
            run(i + 1)
        except control:
            leave(None, None, None)
            raise
        except Exception as e:
            inst = _to_exc_instance(interp, e)[0]
            if not interp._is_truthy(leave(inst.cls, inst, None)):
                raise
        else:
            leave(None, None, None)

    run(0)


from types import FunctionType as _FunctionType

_FAST_BINOPS = {
    "+": _operator.add, "-": _operator.sub, "*": _operator.mul, "/": _operator.truediv,
    "//": _operator.floordiv, "%": _operator.mod, "**": _operator.pow,
    "==": _operator.eq, "!=": _operator.ne, "<": _operator.lt, ">": _operator.gt,
    "<=": _operator.le, ">=": _operator.ge,
}
_FAST_BINOPS.update(_INPLACE)


def _call_plain(callee, args):
    if isinstance(callee, UserClass):
        instance = UserInstance(callee)
        init_method = callee.get_method("__init__")
        if init_method:
            init_method(instance, *args)
        return instance
    if isinstance(callee, UserInstance):
        dunder_call = callee.cls.get_method("__call__")
        if dunder_call is not None:
            return dunder_call(callee, *args)
    if not callable(callee):
        raise TypeError(f"'{type(callee).__name__}' object is not callable")
    return callee(*args)
