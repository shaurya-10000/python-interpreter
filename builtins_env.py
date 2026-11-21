from ast_nodes import Const, Attribute
from modules import builtin_open
from runtime import (
    MISSING, BuiltinType, PyClassMethod, PyProperty, PyStaticMethod,
    UserClass, UserInstance, get_attr, set_attr,
)


def setup_exceptions(interp):
    def exc_init(this, *args):
        this.attributes["args"] = tuple(args)
        if len(args) == 1:
            this.attributes["message"] = str(args[0])
        elif args:
            this.attributes["message"] = str(tuple(args))
        else:
            this.attributes["message"] = ""

    def exc_str(this, *a):
        return str(this.attributes.get("message", ""))

    base = UserClass("Exception", None, {"__init__": exc_init, "__str__": exc_str})
    classes = {"Exception": base}
    tree = [
        ("ArithmeticError", "Exception"), ("ZeroDivisionError", "ArithmeticError"), ("OverflowError", "ArithmeticError"),
        ("LookupError", "Exception"), ("KeyError", "LookupError"), ("IndexError", "LookupError"),
        ("ValueError", "Exception"), ("TypeError", "Exception"), ("NameError", "Exception"),
        ("AttributeError", "Exception"), ("RuntimeError", "Exception"),
        ("NotImplementedError", "RuntimeError"), ("RecursionError", "RuntimeError"),
        ("AssertionError", "Exception"), ("StopIteration", "Exception"),
        ("ImportError", "Exception"), ("ModuleNotFoundError", "ImportError"),
        ("OSError", "Exception"), ("FileNotFoundError", "OSError"),
        ("PermissionError", "OSError"), ("FileExistsError", "OSError"),
        ("IsADirectoryError", "OSError"),
    ]
    for name, parent in tree:
        c = UserClass(name, classes[parent], {})
        classes[name] = c
    interp.exception_classes = classes
    for name, c in classes.items():
        interp.global_env.set(name, c)


def setup_builtins(interp):
    env = interp.global_env

    object_cls = UserClass("object", None, {})
    env.set("object", object_cls)
    env.set("True", True)
    env.set("False", False)
    env.set("None", None)
    env.set("NotImplemented", NotImplemented)

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

    by_pytype = {}
    for type_name, py_type, ctor in (
        ("int", int, _int), ("str", str, _str), ("float", float, _float), ("bool", bool, _bool),
        ("list", list, _list), ("tuple", tuple, _tuple), ("set", set, _set), ("dict", dict, _dict),
    ):
        wrapped = BuiltinType(type_name, py_type, ctor)
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

    def _pick(fn, args, key, default):
        items = list(args[0]) if len(args) == 1 else list(args)
        if not items:
            if default is MISSING:
                raise ValueError("min()/max() arg is an empty sequence")
            return default
        return fn(items, key=key)

    def _next(it, default=MISSING):
        try:
            return next(it)
        except StopIteration:
            if default is MISSING:
                raise
            return default

    def _getattr(obj, name, default=MISSING):
        try:
            return get_attr(obj, name)
        except AttributeError:
            if default is MISSING:
                raise
            return default

    def _hasattr(obj, name):
        try:
            get_attr(obj, name)
            return True
        except AttributeError:
            return False

    env.set("print", _print)
    env.set("input", lambda prompt="": input(prompt))
    env.set("open", builtin_open)
    env.set("len", _len)
    env.set("repr", lambda x: repr(x))
    env.set("range", lambda *args: list(range(*args)))
    env.set("isinstance", _isinstance)
    env.set("issubclass", _issubclass)
    env.set("property", lambda fget=None, fset=None: PyProperty(fget, fset))
    env.set("staticmethod", lambda fn: PyStaticMethod(fn))
    env.set("classmethod", lambda fn: PyClassMethod(fn))
    env.set("sorted", lambda xs, key=None, reverse=False: sorted(xs, key=key, reverse=reverse))
    env.set("reversed", lambda xs: list(reversed(xs)))
    env.set("min", lambda *args, key=None, default=MISSING: _pick(min, args, key, default))
    env.set("max", lambda *args, key=None, default=MISSING: _pick(max, args, key, default))
    env.set("sum", lambda xs, start=0: sum(xs, start))
    env.set("abs", lambda x: abs(x))
    env.set("any", lambda xs: any(xs))
    env.set("all", lambda xs: all(xs))
    env.set("enumerate", lambda xs, start=0: enumerate(xs, start))
    env.set("zip", lambda *xs: zip(*xs))
    env.set("map", lambda f, *xs: map(f, *xs))
    env.set("filter", lambda f, xs: filter(f, xs))
    env.set("round", lambda x, n=None: round(x) if n is None else round(x, n))
    env.set("pow", lambda a, b, m=None: pow(a, b) if m is None else pow(a, b, m))
    env.set("divmod", lambda a, b: divmod(a, b))
    env.set("chr", lambda n: chr(n))
    env.set("ord", lambda c: ord(c))
    env.set("format", lambda v, spec="": format(v, spec))
    env.set("hash", lambda x: hash(x))
    env.set("id", lambda x: id(x))
    env.set("callable", lambda x: callable(x) or isinstance(x, UserClass)
            or (isinstance(x, UserInstance) and x.cls.get_method("__call__") is not None))
    env.set("iter", lambda x: iter(x))
    env.set("next", _next)
    env.set("getattr", _getattr)
    env.set("hasattr", _hasattr)
    env.set("setattr", lambda obj, name, value: set_attr(obj, name, value))