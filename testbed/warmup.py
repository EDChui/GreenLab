import sys

def fibonacci(n):
    if n <= 0:
        return 0
    elif n == 1:
        return 1
    else:
        return fibonacci(n - 1) + fibonacci(n - 2)

def main():
    if len(sys.argv) != 2:
        print("Usage: python warmup.py <n>")
        sys.exit(1)

    try:
        n = int(sys.argv[1])
    except ValueError:
        print("Please provide a valid integer.")
        sys.exit(1)

    print(f"First {n} Fibonacci numbers:")
    for i in range(n):
        print(fibonacci(i), end=' ')
    print()

if __name__ == "__main__":
    main()
