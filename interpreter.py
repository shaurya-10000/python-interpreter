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
        self.global_env = Environment(); self._setup_builtins()

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

    def run(self, ast):
        try: self._eval_block(ast, self.global_env)
        except Exception as e: print(f"Runtime Error: {e}")

    def _eval_block(self, block, env):
        for stmt in block.statements: self._eval_statement(stmt, env)

    def _eval_statement(self, node, env):
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
        elif isinstance(node, TryStmt):
            try: self._eval_block(node.try_block, env)
            except Exception as e:
                if node.except_var: env.set(node.except_var, str(e))
                self._eval_block(node.except_block, env)
        elif isinstance(node, RaiseStmt): raise Exception(self._eval_expr(node.value, env))
        elif isinstance(node, IfStmt):
            if self._is_truthy(self._eval_expr(node.condition, env)):
                self._eval_block(node.then_branch, env); return
            for cond, body in node.elif_branches:
                if self._is_truthy(self._eval_expr(cond, env)):
                    self._eval_block(body, env); return
            if node.else_branch: self._eval_block(node.else_branch, env)
        elif isinstance(node, WhileStmt):
            while self._is_truthy(self._eval_expr(node.condition, env)):
                try: self._eval_block(node.body, env)
                except BreakException: break
                except ContinueException: continue
        elif isinstance(node, ForStmt):
            iterable = self._eval_expr(node.iterable, env)
            for item in iterable:
                if isinstance(node.target, Var): env.set(node.target.name, item)
                elif isinstance(node.target, ListExpr):
                    for i, target_expr in enumerate(node.target.elements):
                        if isinstance(target_expr, Var): env.set(target_expr.name, item[i])
                try: self._eval_block(node.body, env)
                except BreakException: break
                except ContinueException: continue
        elif isinstance(node, FuncDef):
            def func(*args):
                func_env = Environment(env)
                if node.vararg: func_env.set(node.vararg, list(args[len(node.params):]))
                for i, param in enumerate(node.params):
                    if i < len(args): func_env.set(param, args[i])
                    elif node.defaults[i] is not None: func_env.set(param, self._eval_expr(node.defaults[i], env))
                    else: func_env.set(param, None)
                try: self._eval_block(node.body, func_env)
                except ReturnException as ret: return ret.value
                return None
            env.set(node.name, func)
        elif isinstance(node, ReturnStmt):
            raise ReturnException(self._eval_expr(node.value, env) if node.value else None)
        elif isinstance(node, BreakStmt): raise BreakException()
        elif isinstance(node, ContinueStmt): raise ContinueException()
        elif isinstance(node, PassStmt): pass
        elif isinstance(node, ClassDef):
            parent = None
            if node.parent_class: parent = env.get(node.parent_class)
            methods = {}
            for method in node.methods:
                def make_method(m, parent_cls):
                    def method_func(*args):
                        method_env = Environment(env)
                        self_instance = args[0] if args else None
                        if m.params:
                            method_env.set(m.params[0], self_instance)
                            if m.vararg: method_env.set(m.vararg, list(args[1+len(m.params):]))
                            for i, param in enumerate(m.params[1:]):
                                if i+1 < len(args): method_env.set(param, args[i+1])
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
                methods[method.name] = make_method(method, parent)
            env.set(node.name, UserClass(node.name, parent, methods))
        else: raise NotImplementedError(f"Statement not implemented: {type(node).__name__}")

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

    def _is_truthy(self, val):
        if val is None or val is False: return False
        if isinstance(val, (int, float)) and val == 0: return False
        if isinstance(val, (str, list, dict)) and len(val) == 0: return False
        return True

    def _eval_expr(self, node, env):
        if isinstance(node, Number): return node.value
        if isinstance(node, String): return node.value
        if isinstance(node, Bool): return node.value
        if isinstance(node, NoneType): return None
        if isinstance(node, Var): return env.get(node.name)
        if isinstance(node, ListExpr): return [self._eval_expr(e, env) for e in node.elements]
        if isinstance(node, DictExpr): return {self._eval_expr(k, env): self._eval_expr(v, env) for k, v in zip(node.keys, node.values)}
        if isinstance(node, Subscript): return self._eval_expr(node.obj, env)[self._eval_expr(node.index, env)]
        if isinstance(node, Attribute):
            obj = self._eval_expr(node.obj, env); name = node.name
            if isinstance(obj, UserInstanceProxy):
                method = obj.parent_cls.get_method(name)
                if method: return lambda *args: method(obj.instance, *args)
                raise AttributeError(f"Parent class has no attribute '{name}'")
            if isinstance(obj, (str, list, dict)):
                if hasattr(obj, name): return getattr(obj, name)
                raise AttributeError(f"'{type(obj).__name__}' object has no attribute '{name}'")
            if isinstance(obj, UserInstance):
                if name in obj.attributes: return obj.attributes[name]
                method = obj.cls.get_method(name)
                if method: return lambda *args: method(obj, *args)
                raise AttributeError(f"'{obj.cls.name}' object has no attribute '{name}'")
            return getattr(obj, name)
        if isinstance(node, BinOp):
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
            if op == "and": return self._is_truthy(left) and self._is_truthy(right)
            if op == "or": return self._is_truthy(left) or self._is_truthy(right)
            raise RuntimeError(f"Unknown operator {op}")
        if isinstance(node, UnaryOp):
            val = self._eval_expr(node.operand, env)
            if node.op == "-": return -val
            if node.op == "+": return +val
            if node.op == "not": return not self._is_truthy(val)
        if isinstance(node, Call):
            callee = self._eval_expr(node.callee, env); args = [self._eval_expr(arg, env) for arg in node.args]
            if isinstance(callee, UserClass):
                instance = UserInstance(callee)
                init_method = callee.get_method("__init__")
                if init_method: init_method(instance, *args)
                return instance
            if not callable(callee): raise TypeError(f"'{type(callee).__name__}' object is not callable")
            return callee(*args)
        raise NotImplementedError(f"Expression not implemented: {type(node).__name__}")
