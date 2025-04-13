# Sample code for testing the code review bot

# Example 1: Basic function with potential issues
def calculate_average(numbers):
    sum = 0
    for num in numbers:
        sum += num
    return sum / len(numbers)

# Example 2: Improved version of the same function
def calculate_average_improved(numbers):
    if not numbers:
        return 0
    return sum(numbers) / len(numbers)

# Example 3: Class with potential security issues
class User:
    def __init__(self, username, password):
        self.username = username
        self.password = password  # Storing plain text password is a security risk
        
    def login(self, input_password):
        return self.password == input_password

# Example 4: Improved version of the User class
class SecureUser:
    def __init__(self, username, password):
        self.username = username
        self._hashed_password = self._hash_password(password)
        
    def _hash_password(self, password):
        # In a real application, use a proper hashing library
        return hash(password)
        
    def verify_password(self, input_password):
        return self._hashed_password == self._hash_password(input_password)

# Example 5: Function with performance issues
def find_duplicates(items):
    duplicates = []
    for i in range(len(items)):
        for j in range(i + 1, len(items)):
            if items[i] == items[j]:
                duplicates.append(items[i])
    return duplicates

# Example 6: Improved version using set
def find_duplicates_improved(items):
    seen = set()
    duplicates = set()
    for item in items:
        if item in seen:
            duplicates.add(item)
        else:
            seen.add(item)
    return list(duplicates)

# Example 7: Code with poor error handling
def divide_numbers(a, b):
    return a / b

# Example 8: Improved version with proper error handling
def divide_numbers_safe(a, b):
    try:
        return a / b
    except ZeroDivisionError:
        raise ValueError("Cannot divide by zero")
    except TypeError:
        raise ValueError("Both arguments must be numbers")

# Example 9: Function with potential memory issues
def process_large_data(data):
    result = []
    for item in data:
        processed = item * 2  # Memory intensive operation
        result.append(processed)
    return result

# Example 10: Improved version using generator
def process_large_data_improved(data):
    for item in data:
        yield item * 2 