import threading
from ast_nodes import ClassDef, FuncDef, Lambda, YieldExpr, YieldFromExpr
from environment import Environment
from runtime import ReturnException, UserInstance, make_raise

_gen_tls = threading.local()
_GEN_STACK_BYTES = 8 * 1024 * 1024


class _GenExit(BaseException):
    pass


class _GenCore:
    def __init__(self, interp, node, env, name):
        self.interp = interp
        self.node = node
        self.env = env
        self.name = name
        self.line = getattr(node, "line", 0)
        self.thread = None
        self.state = "created"
        self.resume = threading.Semaphore(0)
        self.yielded = threading.Semaphore(0)
        self.send_value = None
        self.throw = None
        self.out = None
        self.stack = []


def _gen_thread_main(core):
    interp = core.interp
    _gen_tls.core = core
    try:
        interp.call_stack.append((core.name, core.line))
        try:
            interp._eval_block(core.node.body, core.env)
            core.out = ("return", None)
        except ReturnException as ret:
            core.out = ("return", ret.value)
    except _GenExit:
        core.out = ("return", None)
    except BaseException as e:
        core.out = ("raise", e)
    finally:
        core.yielded.release()


def _gen_step(core, value=None, exc=None):
    if core.state == "running":
        raise ValueError("generator already executing")
    if core.state == "done":
        if exc is not None:
            raise exc
        raise StopIteration
    interp = core.interp
    core.send_value = value
    core.throw = exc
    saved = interp.call_stack
    interp.call_stack = core.stack
    core.state = "running"
    if core.thread is None:
        previous = None
        try:
            previous = threading.stack_size(_GEN_STACK_BYTES)
        except (ValueError, RuntimeError):
            previous = None
        thread = threading.Thread(target=_gen_thread_main, args=(core,), daemon=True)
        core.thread = thread
        try:
            thread.start()
        except RuntimeError:
            interp.call_stack = saved
            core.state = "done"
            raise RuntimeError("could not start a helper thread for this generator")
        finally:
            if previous is not None:
                try:
                    threading.stack_size(previous)
                except (ValueError, RuntimeError):
                    pass
    else:
        core.resume.release()
    core.yielded.acquire()
    interp.call_stack = saved
    kind, payload = core.out
    core.out = None
    if kind == "yield":
        core.state = "suspended"
        return payload
    core.state = "done"
    if kind == "return":
        raise StopIteration(payload)
    if isinstance(payload, StopIteration):
        raise RuntimeError("generator raised StopIteration") from payload
    raise payload


def _gen_suspend(core, value):
    core.out = ("yield", value)
    core.yielded.release()
    core.resume.acquire()
    if core.throw is not None:
        err = core.throw
        core.throw = None
        raise err
    sent = core.send_value
    core.send_value = None
    return sent


class PyGenerator:
    def __init__(self, interp, node, env, name):
        self._core = _GenCore(interp, node, env, name)

    def __iter__(self):
        return self

    def __next__(self):
        return _gen_step(self._core)

    def send(self, value=None):
        core = self._core
        if core.state == "created" and value is not None:
            raise TypeError("can't send non-None value to a just-started generator")
        return _gen_step(core, value)

    def throw(self, exc, val=None, tb=None):
        core = self._core
        target = val if isinstance(val, UserInstance) else exc
        err = make_raise(core.interp, target)
        if core.state == "created":
            core.state = "done"
            raise err
        return _gen_step(core, None, err)

    def close(self):
        core = self._core
        if core.state == "created":
            core.state = "done"
            return None
        if core.state == "done":
            return None
        if core.state == "running":
            raise ValueError("generator already executing")
        try:
            _gen_step(core, None, _GenExit())
        except StopIteration:
            return None
        except _GenExit:
            return None
        raise RuntimeError("generator ignored GeneratorExit")

    def __repr__(self):
        return "<generator object " + self._core.name + ">"


PyGenerator.__name__ = "generator"


def _contains_yield(node):
    stack = [node]
    while stack:
        n = stack.pop()
        if isinstance(n, (YieldExpr, YieldFromExpr)):
            return True
        if isinstance(n, (FuncDef, Lambda, ClassDef)):
            continue
        if isinstance(n, (list, tuple)):
            stack.extend(n)
        elif hasattr(n, "__dataclass_fields__"):
            for f in n.__dataclass_fields__:
                stack.append(getattr(n, f))
    return False


def is_generator_def(fnode):
    flag = getattr(fnode, "_is_gen", None)
    if flag is None:
        flag = _contains_yield(fnode.body)
        fnode._is_gen = flag
    return flag


def _current_core(interp):
    core = getattr(_gen_tls, "core", None)
    if core is None or core.interp is not interp:
        raise SyntaxError("'yield' outside function")
    return core


def eval_yield(interp, node, env):
    core = _current_core(interp)
    value = interp._eval_expr(node.value, env) if node.value is not None else None
    return _gen_suspend(core, value)


def eval_yield_from(interp, node, env):
    core = _current_core(interp)
    source = interp._eval_expr(node.value, env)
    if isinstance(source, PyGenerator):
        sub = source._core
        try:
            item = _gen_step(sub)
        except StopIteration as stop:
            return stop.value
        while True:
            try:
                sent = _gen_suspend(core, item)
            except _GenExit:
                source.close()
                raise
            except Exception as e:
                try:
                    item = _gen_step(sub, None, e)
                except StopIteration as stop:
                    return stop.value
                continue
            try:
                item = _gen_step(sub, sent)
            except StopIteration as stop:
                return stop.value
    for item in source:
        _gen_suspend(core, item)
    return None


def comp_gen(interp, node, env, assign_fn):
    clauses = node.clauses
    outer = iter(interp._eval_expr(clauses[0][2], env))

    def walk(i, scope):
        if i == len(clauses):
            yield interp._eval_expr(node.elt, scope)
            return
        clause = clauses[i]
        if clause[0] == "for":
            source = outer if i == 0 else interp._eval_expr(clause[2], scope)
            for item in source:
                inner = Environment(scope)
                assign_fn(interp, clause[1], item, inner)
                yield from walk(i + 1, inner)
        elif interp._is_truthy(interp._eval_expr(clause[1], scope)):
            yield from walk(i + 1, scope)

    return walk(0, Environment(env))