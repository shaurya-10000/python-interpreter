class Animal:
    def __init__(self, name):
        self.name = name
        
    def speak(self):
        return self.name + " makes a sound."

    def __str__(self):
        return "Animal: " + self.name

class Dog(Animal):
    def __init__(self, name, breed):
        super().__init__(name)
        self.breed = breed
        
    def speak(self):
        return self.name + " barks!"

dog = Dog("Buddy", "Labrador")
print(dog.speak())
print(dog)
print(dog.name)
print(dog.breed)
