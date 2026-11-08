PI = 3.14159


def area(r):
    return PI * r * r


class Circle:
    def __init__(self, r):
        self.r = r

    def area(self):
        return area(self.r)

    def __repr__(self):
        return "Circle(" + str(self.r) + ")"


print("geometry loaded:", __name__)
