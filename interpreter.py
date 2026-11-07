from ast_nodes import *
from environment import Environment

class ReturnException(Exception):
    def __init__(self, value):
        self.value = value
class BreakException(Exception): pass
class ContinueException(Exception): pass

class Interpreter:
    def __init__(self):
        self.global_env = Environment()
        self._setup_builtins()

    def _setup_builtins(self):
        self.global_env.set("print", lambda *args: print(*args))
        self.global_env.set("len", lambda x: len(x))
        self.global_env.set("range", lambda *args: list(range(*args)))
        self.global_env.set("str", lambda x: str(x))
        self.global_env.set("int", lambda x: int(x))
        self.global_env.set("float", lambda x: float(x))
        self.global_env.set("type", lambda x: type(x).__name__)
        self.global_env.set("True", True)
        self.global_env.set("False", False)
        self.global_env.set("None", None)

    def run(self, ast: Block):
        try:
            self._eval_block(ast, self.global_env)
        except Exception as e:
            print(f"Runtime Error: {e}")

    def _eval_block(self, block: Block, env: Environment):
        for stmt in block.statements:
            self._eval_statement(stmt, env)

    def _eval_statement(self, node, env: Environment):
        if isinstance(node, ExprStmt):
            self._eval_expr(node.expr, env)
        elif isinstance(node, PrintStmt):
            print(self._eval_expr(node.expr, env))
        elif isinstance(node, Assign):
            val = self._eval_expr(node.value, env)
            if isinstance(node.target, Var):
                env.set(node.target.name, val)
            elif isinstance(node.target, Subscript):
                obj = self._eval_expr(node.target.obj, env)
                idx = self._eval_expr(node.target.index, env)
                obj[idx] = val # Will throw TypeError if object doesn't support it (e.g., strings)
            elif isinstance(node.target, Attribute):
                obj = self._eval_expr(node.target.obj, env)
                setattr(obj, node.target.name, val)
        elif isinstance(node, IfStmt):
            if self._is_truthy(self._eval_expr(node.condition, env)):
                self._eval_block(node.then_branch, env)
                return
            for cond, body in node.elif_branches:
                if self._is_truthy(self._eval_expr(cond, env)):
                    self._eval_block(body, env)
                    return
            if node.else_branch:
                self._eval_block(node.else_branch, env)
        elif isinstance(node, WhileStmt):
            while self._is_truthy(self._eval_expr(node.condition, env)):
                try: self._eval_block(node.body, env)
                except BreakException: break
                except ContinueException: continue
        elif isinstance(node, ForStmt):
            iterable = self._eval_expr(node.iterable, env)
            for item in iterable:
                if isinstance(node.target, Var):
                    env.set(node.target.name, item)
                elif isinstance(node.target, ListExpr): # Unpacking: for k, v in dict.items()
                    for i, target_expr in enumerate(node.target.elements):
                        if isinstance(target_expr, Var):
                            env.set(target_expr.name, item[i])
                try: self._eval_block(node.body, env)
                except BreakException: break
                except ContinueException: continue
        elif isinstance(node, FuncDef):
            def func(*args):
                func_env = Environment(env)
                for i, param in enumerate(node.params):
                    func_env.set(param, args[i] if i < len(args) else None)
                try: self._eval_block(node.body, func_env)
                except ReturnException as ret: return ret.value
                return None
            env.set(node.name, func)
        elif isinstance(node, ReturnStmt):
            val = self._eval_expr(node.value, env) if node.value else None
            raise ReturnException(val)
        elif isinstance(node, BreakStmt): raise BreakException()
        elif isinstance(node, ContinueStmt): raise ContinueException()
        elif isinstance(node, PassStmt): pass
        else: raise NotImplementedError(f"Statement not implemented: {type(node).__name__}")

    def _is_truthy(self, val):
        if val is None or val is False: return False
        if isinstance(val, (int, float)) and val == 0: return False
        if isinstance(val, (str, list, dict)) and len(val) == 0: return False
        return True

    def _eval_expr(self, node, env: Environment):
        if isinstance(node, Number): return node.value
        if isinstance(node, String): return node.value
        if isinstance(node, Bool): return node.value
        if isinstance(node, NoneType): return None
        if isinstance(node, Var): return env.get(node.name)
        
        # --- NEW: Lists and Dictionaries ---
        if isinstance(node, ListExpr):
            return [self._eval_expr(e, env) for e in node.elements]
        if isinstance(node, DictExpr):
            return {self._eval_expr(k, env): self._eval_expr(v, env) for k, v in zip(node.keys, node.values)}
        if isinstance(node, Subscript):
            obj = self._eval_expr(node.obj, env)
            idx = self._eval_expr(node.index, env)
            return obj[idx]
        if isinstance(node, Attribute):
            obj = self._eval_expr(node.obj, env)
            return getattr(obj, node.name)
            
        if isinstance(node, BinOp):
            left = self._eval_expr(node.left, env)
            right = self._eval_expr(node.right, env)
            op = node.op
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
            callee = self._eval_expr(node.callee, env)
            args = [self._eval_expr(arg, env) for arg in node.args]
            if not callable(callee):
                raise TypeError(f"'{type(callee).__name__}' object is not callable")
            return callee(*args)
            
        raise NotImplementedError(f"Expression not implemented: {type(node).__name__}")
