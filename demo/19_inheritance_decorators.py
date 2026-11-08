class Animal:
    count = 0

    def __init__(self, name):
        self.name = name
        Animal.count += 1

    def speak(self):
        return self.name + " makes a sound"

    def describe(self):
        return "I am " + self.name + ": " + self.speak()

    @staticmethod
    def kingdom():
        return "Animalia"

    @classmethod
    def create(cls, name):
        return cls(name)


class Dog(Animal):
    def speak(self):
        return self.name + " barks"


class Cat(Animal):
    def speak(self):
        return super().speak() + " (purrs)"


d = Dog("Rex")
c = Cat.create("Tom")
print(d.describe())
print(c.describe())
print(Animal.kingdom(), d.kingdom())
print(Animal.count)
print(isinstance(d, Animal), isinstance(d, Cat), isinstance(c, Animal))
print(issubclass(Dog, Animal), issubclass(Animal, Dog))
print(type(d).__name__, type(d) == Dog, type(5) == int)


class Flyer:
    def move(self):
        return "fly"

    def who(self):
        return "Flyer"


class Swimmer:
    def move(self):
        return "swim"

    def who(self):
        return "Swimmer"


class Duck(Flyer, Swimmer):
    def who(self):
        return "Duck>" + super().who()


duck = Duck()
print(duck.move(), duck.who())
print(isinstance(duck, Swimmer), issubclass(Duck, Flyer))


class Base:
    def hello(self):
        return ["Base"]


class Left(Base):
    def hello(self):
        return ["Left"] + super().hello()


class Right(Base):
    def hello(self):
        return ["Right"] + super().hello()


class Bottom(Left, Right):
    def hello(self):
        return ["Bottom"] + super().hello()


print(Bottom().hello())


class A:
    def __init__(self, **kw):
        self.log = ["A"]


class B(A):
    def __init__(self, **kw):
        super().__init__(**kw)
        self.log.append("B")


print(B(x=1).log)


class Temperature:
    def __init__(self, celsius):
        self._c = celsius

    @property
    def celsius(self):
        return self._c

    @celsius.setter
    def celsius(self, value):
        if value < -273:
            raise ValueError("below absolute zero")
        self._c = value

    @property
    def fahrenheit(self):
        return self._c * 9 / 5 + 32


t = Temperature(25)
print(t.celsius, t.fahrenheit)
t.celsius = 100
print(t.celsius, t.fahrenheit)
try:
    t.celsius = -300
except ValueError as e:
    print("error:", e)
try:
    t.fahrenheit = 1
except AttributeError:
    print("read-only")
print(hasattr(t, "celsius"), getattr(t, "fahrenheit"))


def shout(fn):
    def wrapper(*args):
        return fn(*args).upper() + "!"
    return wrapper


@shout
def greet(name):
    return "hello " + name


print(greet("bob"))


def repeat(times):
    def decorate(fn):
        def wrapper(*args):
            return fn(*args) * times
        return wrapper
    return decorate


@repeat(3)
def ping():
    return "ping"


print(ping())


def inc(fn):
    def wrapper(*args):
        return fn(*args) + 1
    return wrapper


def twice(fn):
    def wrapper(*args):
        return fn(fn(*args))
    return wrapper


@twice
@inc
def base(x):
    return x


print(base(1))


def tracing(fn):
    def wrapper(*args):
        return "t:" + str(fn(*args))
    return wrapper


class Math:
    @tracing
    def double(self, x):
        return x * 2


print(Math().double(4))


class Config(object):
    """A documented class."""
    debug = False
    level = 3


print(Config.level, Config().debug)
print(hasattr(Config(), "level"), hasattr(Config(), "zzz"))
