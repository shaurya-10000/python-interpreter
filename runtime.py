import operator
from modules import PyModule

MISSING = object()


class ReturnException(Exception):
    def __init__(self, value):
        self.value = value


class BreakException(Exception):
    pass


class ContinueException(Exception):
    pass


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
            return sequence_iter(self)
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
    setattr(UserInstance, "__i" + _op + "__", _delegate("__i" + _op + "__"))
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


class SuperView:
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


def class_attr(cls, name):
    for c in cls.mro():
        attrs = getattr(c, "attrs", None)
        if attrs and name in attrs:
            return attrs[name]
    return MISSING


def instance_truth(val):
    method = val.cls.get_method("__bool__")
    if method is not None:
        return bool(method(val))
    method = val.cls.get_method("__len__")
    if method is not None:
        return method(val) != 0
    return True


def sequence_iter(obj):
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


def bind_member(member, instance, cls):
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


def get_attr(obj, name):
    if isinstance(obj, PyModule):
        return obj.get(name)
    if isinstance(obj, UserInstance):
        if name == "__class__":
            return obj.cls
        member = obj.cls.get_method(name)
        if isinstance(member, PyProperty):
            return bind_member(member, obj, obj.cls)
        if name in obj.attributes:
            return obj.attributes[name]
        if member is not None:
            return bind_member(member, obj, obj.cls)
        found = class_attr(obj.cls, name)
        if found is not MISSING:
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
        return bind_member(member, obj.instance, start)
    if isinstance(obj, UserClass):
        found = class_attr(obj, name)
        if found is not MISSING:
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


def set_attr(obj, name, value):
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


def get_item(obj, index):
    if isinstance(obj, UserInstance):
        method = obj.cls.get_method("__getitem__")
        if method is None:
            raise TypeError(f"'{obj.cls.name}' object is not subscriptable")
        return method(obj, index)
    return obj[index]


def set_item(obj, index, value):
    if isinstance(obj, UserInstance):
        method = obj.cls.get_method("__setitem__")
        if method is None:
            raise TypeError(f"'{obj.cls.name}' object does not support item assignment")
        method(obj, index, value)
        return
    obj[index] = value


def del_item(obj, index):
    if isinstance(obj, UserInstance):
        method = obj.cls.get_method("__delitem__")
        if method is None:
            raise TypeError(f"'{obj.cls.name}' object doesn't support item deletion")
        method(obj, index)
        return
    del obj[index]


def call_any(callee, *args, **kwargs):
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


def new_instance(cls, *args):
    inst = UserInstance(cls)
    init = cls.get_method("__init__")
    if init:
        init(inst, *args)
    return inst


def is_exc_instance(interp, inst):
    base = interp.exception_classes["Exception"]
    return base in inst.cls.mro()


def make_raise(interp, val):
    if isinstance(val, UserClass):
        val = new_instance(val)
    if isinstance(val, UserInstance):
        if not is_exc_instance(interp, val):
            return TypeError("exceptions must derive from Exception")
        return PyRaise(inst=val)
    return PyRaise(legacy=val)


def strip_line(msg):
    return msg.split(" at line ", 1)[0] if " at line " in msg else msg


def to_exc_instance(interp, e):
    """Return (instance, legacy_text_or_None, is_host_error)."""
    classes = interp.exception_classes
    if isinstance(e, PyRaise):
        if e.inst is not None:
            return e.inst, None, False
        return new_instance(classes["Exception"], e.message()), e.message(), False
    cls = classes["Exception"]
    for t in type(e).__mro__:
        c = classes.get(t.__name__)
        if c is not None:
            cls = c
            break
    if isinstance(e, KeyError) and e.args:
        a = e.args[0]
        msg = strip_line(a) if isinstance(a, str) and " at line " in a else repr(a)
    else:
        msg = strip_line(str(e))
    return new_instance(cls, msg), None, True


def exc_match(inst, spec):
    if isinstance(spec, tuple):
        return any(exc_match(inst, s) for s in spec)
    if isinstance(spec, UserClass):
        return spec in inst.cls.mro()
    raise TypeError("except clause needs an exception class or a tuple of them")


def exec_try(interp, node, env):
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
            inst, legacy, host = to_exc_instance(interp, e)
            for type_expr, var, block in handlers:
                if type_expr is not None:
                    if not exc_match(inst, interp._eval_expr(type_expr, env)):
                        continue
                if var:
                    if legacy is not None:
                        val = legacy
                    elif host and type_expr is None:
                        val = strip_line(str(e))
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


def exec_with(interp, node, env):
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
            inst = to_exc_instance(interp, e)[0]
            if not interp._is_truthy(leave(inst.cls, inst, None)):
                raise
        else:
            leave(None, None, None)

    run(0)


INPLACE_OPS = {
    "+=": operator.iadd, "-=": operator.isub, "*=": operator.imul, "/=": operator.itruediv,
    "//=": operator.ifloordiv, "%=": operator.imod, "**=": operator.ipow,
    "&=": operator.iand, "|=": operator.ior, "^=": operator.ixor,
    "<<=": operator.ilshift, ">>=": operator.irshift,
}

FAST_BINOPS = {
    "+": operator.add, "-": operator.sub, "*": operator.mul, "/": operator.truediv,
    "//": operator.floordiv, "%": operator.mod, "**": operator.pow,
    "==": operator.eq, "!=": operator.ne, "<": operator.lt, ">": operator.gt,
    "<=": operator.le, ">=": operator.ge,
    **INPLACE_OPS,
}