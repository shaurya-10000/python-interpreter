import importlib
import os
from environment import Environment

ALLOWED_HOST = {
    "math", "cmath", "random", "time", "datetime", "string", "json", "re", "itertools", "functools",
    "collections", "statistics", "operator", "copy", "textwrap", "decimal", "fractions", "heapq",
    "bisect", "io", "hashlib", "base64", "calendar", "pprint", "contextlib",
}


def builtin_open(path, mode="r", buffering=-1, encoding=None, newline=None):
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
    if os.path.basename(path) == "__init__.py" or any(k.startswith(name + ".") for k in interp.virtual_modules):
        env.vars["__package__"] = name
    elif "." in name:
        env.vars["__package__"] = name.rsplit(".", 1)[0]
    else:
        env.vars["__package__"] = ""
    return env


def _find_module_source(interp, name):
    if name in interp.virtual_modules:
        return interp.virtual_modules[name], "<" + name + ">"
    rel = name.replace(".", os.sep)
    for base in interp.search_paths:
        for candidate in (os.path.join(base, rel + ".py"), os.path.join(base, rel, "__init__.py")):
            if os.path.isfile(candidate):
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
        from lexer import Lexer
        from parser import Parser
        interp.register_source(path, source)
        env = _new_module_env(interp, name, path)
        mod = PyModule(name, path, env)
        interp.modules[name] = mod
        prev_file = interp.current_file
        interp.current_file = path
        try:
            try:
                tree = Parser(Lexer(source, filename=path).tokenize(), filename=path).parse()
            except SyntaxError as ex:
                raise SyntaxError(f"in module '{name}': {ex}") from None
            interp._eval_block(tree, env)
        except BaseException:
            interp.modules.pop(name, None)
            raise
        finally:
            interp.current_file = prev_file
        return mod
    if name.split(".")[0] in ALLOWED_HOST:
        try:
            mod = importlib.import_module(name)
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


def exec_import(interp, node, env):
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


def _resolve_relative_module(node, env):
    level = getattr(node, "level", 0)
    if level == 0:
        return node.module
    pkg = env.vars.get("__package__")
    if pkg is None:
        mod_name = env.vars.get("__name__", "")
        pkg = mod_name.rsplit(".", 1)[0] if "." in mod_name else ""
    if not pkg:
        raise ImportError("attempted relative import with no known parent package")
    parts = pkg.split(".")
    if level - 1 > len(parts):
        raise ImportError("attempted relative import beyond top-level package")
    base_parts = parts[:len(parts) - (level - 1)]
    if node.module:
        base_parts.append(node.module)
    return ".".join(base_parts)


def exec_from_import(interp, node, env):
    target_module = _resolve_relative_module(node, env)
    mod = _import_chain(interp, target_module)[-1]
    if node.names is None:
        for name in _module_public_names(interp, mod):
            env.set(name, _import_name(interp, mod, target_module, name))
        return
    for name, alias in node.names:
        env.set(alias or name, _import_name(interp, mod, target_module, name))