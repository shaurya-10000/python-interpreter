class Animal:
    def __init__(self, name):
        self.name = name
        
    def speak(self):
        print(self.name + " makes a sound.")

class Cat:
    def __init__(self, name):
        self.name = name
        
    def speak(self):
        print(self.name + " says Meow!")

animals = [Animal("Generic"), Cat("Whiskers")]

for a in animals:
    a.speak()

def fibonacci(n):
    if n <= 1:
        return n
    return fibonacci(n - 1) + fibonacci(n - 2)

print("Fibonacci sequence:")
for i in range(10):
    print(fibonacci(i))
