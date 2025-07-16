# Python-Type

A powerful and flexible Python decorator library for runtime type validation using type hints and custom type specifications.

## Features

- **Automatic Type Validation**: Leverages Python type hints for seamless parameter validation
- **Custom Type Overrides**: Override specific parameter types without modifying function signatures
- **Complex Type Support**: Validates generic types like `List[int]`, `Dict[str, int]`, `Union[int, str]`, etc.
- **Flexible Modes**: Choose between strict validation (all parameters) or selective validation
- **Return Type Validation**: Validate function return types with a separate decorator
- **Detailed Error Messages**: Clear, formatted error messages with file location and parameter details
- **Class Method Support**: Works with both functions and class methods (`self` and `cls` parameters)
- **Multiple Type Support**: Allow parameters to accept multiple types using tuples or Union types
- **Custom Validators**: Create reusable validators with specific type configurations

## Installation

```bash
!pip install python-type
from python-type import *
```

## Requirements

- Python 3.7+
- No external dependencies (uses only standard library)

## Quick Start

### Basic Usage with Type Hints

```python
from your_module import validate_data

@validate_data()
def greet(name: str, age: int, active: bool = True) -> str:
    return f"Hello {name}, you are {age} years old"

# This will work
greet("John", 25)

# This will raise ValidationError
greet(123, "twenty")  # Wrong types
```

### Custom Type Overrides

```python
@validate_data(age=(int, str))  # Allow both int and str for age
def process_age(name: str, age: int) -> str:
    return f"{name} is {age} years old"

# Both of these work
process_age("Alice", 30)     # int
process_age("Bob", "25")     # str
```

### Complex Type Validation

```python
from typing import List, Dict, Union

@validate_data()
def process_data(
    users: List[str], 
    config: Dict[str, int], 
    status: Union[str, int] = "active"
) -> bool:
    return len(users) > 0

# Valid calls
process_data(["user1", "user2"], {"setting": 1})
process_data(["user1"], {"setting": 1}, "inactive")
process_data(["user1"], {"setting": 1}, 404)
```

### Selective Validation (Non-Strict Mode)

```python
@validate_data(strict=False, age=int)  # Only validate 'age' parameter
def flexible_function(name, age, other_param):
    return f"{name} is {age} years old"

# Only 'age' is validated, other parameters can be any type
flexible_function("John", 25, ["any", "type", "here"])
```

### Return Type Validation

```python
from your_module import validate_return_type

@validate_return_type
def calculate_sum(a: int, b: int) -> int:
    return a + b  # Must return an int

@validate_return_type
def get_user_data(user_id: int) -> Dict[str, str]:
    return {"name": "John", "email": "john@example.com"}
```

### Custom Validators

```python
from your_module import create_validator

# Create a reusable validator
user_validator = create_validator({
    'email': str,
    'age': int,
    'active': bool
})

@user_validator
def process_user(email, age, active):
    return f"User {email} is {age} years old and {'active' if active else 'inactive'}"
```

## Advanced Features

### Supported Generic Types

- `List[T]` - Validates list elements
- `Dict[K, V]` - Validates dictionary keys and values
- `Tuple[T1, T2, ...]` - Validates tuple elements by position
- `Set[T]` - Validates set elements
- `Union[T1, T2, ...]` - Allows multiple types
- Custom generic types that follow typing conventions

### Class Method Support

```python
class UserManager:
    @validate_data()
    def create_user(self, name: str, age: int) -> str:
        return f"Created user {name}, age {age}"
    
    @validate_data()
    @classmethod
    def from_config(cls, config: Dict[str, str]) -> 'UserManager':
        return cls()
```

### Error Messages

The library provides detailed, formatted error messages that include:

```
======================================================================
TYPE VALIDATION ERROR
======================================================================
📁 File: /path/to/your/file.py
📍 Line: 42
🔧 Function: my_function()
❌ Errors found: 1
======================================================================

💥 ERROR 1:
   Parameter: 'age' (position 2)
   ✅ Expected: int (from type hint)
   ❌ Received: str
   📦 Value: str('twenty')
======================================================================
```

### Override Parameter Validation

The decorator validates that all override parameters exist in the function:

```python
# This will raise a configuration error
@validate_data(non_existent_param=int)
def my_function(name: str, age: int):
    pass
```

## Exception Handling

The library raises `ValidationError` (a subclass of `ValueError`) when validation fails:

```python
from your_module import ValidationError

try:
    my_function("wrong", "types")
except ValidationError as e:
    print(e)  # Detailed error message with emojis and formatting
```

## API Reference

### `validate_data(*, strict: bool = True, **types_override)`

Main decorator for parameter validation.

**Parameters:**
- `strict` (bool): If True, validates all parameters with type hints. If False, only validates parameters with overrides.
- `**types_override`: Keyword arguments to override specific parameter types.

**Returns:**
- Configured decorator function

### `validate_return_type(func)`

Decorator to validate function return types based on type hints.

**Parameters:**
- `func`: Function to decorate

**Returns:**
- Wrapped function with return type validation

### `create_validator(custom_types: Dict[str, Any])`

Creates a custom validator with specific types.

**Parameters:**
- `custom_types`: Dictionary mapping parameter names to expected types

**Returns:**
- Configured decorator function

### `ValidationError`

Custom exception class for type validation errors. Inherits from `ValueError`.

## Use Cases

- **API Development**: Validate request parameters automatically
- **Data Processing**: Ensure data types are correct before processing
- **Function Contracts**: Enforce type contracts in critical functions
- **Debugging**: Catch type-related bugs early in development
- **Testing**: Validate that functions receive expected types

## Why TypedPython?

- **Zero Runtime Overhead**: Only validates when decorators are applied
- **Non-Intrusive**: Works with existing code without modification
- **Flexible**: Choose between automatic type hint validation or manual specification
- **Production Ready**: Comprehensive error handling and edge case coverage
- **Developer Friendly**: Clear error messages with emojis help debug issues quickly
- **Comprehensive**: Supports complex generic types, class methods, and custom validators

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is licensed under the MIT License.
