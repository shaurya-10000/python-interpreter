# Exceptions: try/except/raise
try:
    raise("Something broke!")
except as e:
    print("Caught: " + e)

# Nested try
try:
    try:
        raise("inner")
    except as e:
        print("inner caught: " + e)
        raise("outer")
except as e:
    print("outer caught: " + e)

# try that does NOT raise
try:
    print("all good")
except as e:
    print("should not print")
