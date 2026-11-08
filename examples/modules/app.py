import geometry
from geometry import Circle, area as circle_area
import utils.text
from utils.text import shout
import utils.text as t
import math
from math import sqrt
import io


def main():
    c = Circle(2)
    print(c, round(c.area(), 2), round(circle_area(1), 2))
    print(geometry.PI)
    print(shout("hi"), utils.text.count_words("a b c"), t.shout("x"))
    print(utils.VERSION)
    print(sqrt(16), math.floor(2.5))
    with io.StringIO() as out:
        out.write(shout("done"))
        print(out.getvalue())
    print(__name__)


if __name__ == "__main__":
    main()
