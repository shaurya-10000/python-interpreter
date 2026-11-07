class Environment:
    def __init__(self, parent=None):
        self.vars = {}
        self.parent = parent
        self.global_names = set()

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
        else:
            self.vars[name] = value
