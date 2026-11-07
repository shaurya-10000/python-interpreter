class Environment:
    def __init__(self, parent=None):
        self.vars = {}
        self.parent = parent
        self.global_names = set()
        self.nonlocal_names = set()

    def get(self, name):
        if name in self.vars:
            return self.vars[name]
        if self.parent:
            return self.parent.get(name)
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
