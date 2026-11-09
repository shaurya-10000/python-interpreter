_EMPTY = frozenset()


class Environment:
    def __init__(self, parent=None):
        self.vars = {}
        self.parent = parent
        self.global_names = _EMPTY
        self.nonlocal_names = _EMPTY

    def get(self, name):
        e = self
        while e is not None:
            v = e.vars
            if name in v:
                return v[name]
            e = e.parent
        raise NameError(f"Name '{name}' is not defined")

    def set(self, name, value):
        if name in self.global_names:
            root = self
            while root.parent:
                root = root.parent
            root.vars[name] = value
        elif name in self.nonlocal_names:
            e = self.parent
            while e is not None and name not in e.vars:
                e = e.parent
            if e is None:
                raise NameError(f"no binding for nonlocal '{name}' found")
            e.vars[name] = value
        else:
            self.vars[name] = value
