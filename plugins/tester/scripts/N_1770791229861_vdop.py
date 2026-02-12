from sys import argv
greeting = argv[1] if len(argv) > 1 else ""
print(greeting.strip() + "!")