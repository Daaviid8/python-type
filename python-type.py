import inspect
import sys
import functools
from typing import Union, Dict, Any, Tuple, List, get_origin, get_args, Optional

def validate_data(*, strict: bool = True, **types_override):
    """
    Decorator for validating function parameters against type hints or overrides.
    
    Args:
        strict: If True, validates all parameters with type hints.
                If False, only validates parameters with override.
        **types_override: Optional dictionary to override specific types.
                         The decorator has priority over type hints.
    
    Basic use (uses type hints automatically):
    @validate_data()
    def my_function(name: str, age: int, price: float) -> str:
        pass
    
    With override (overwrites specific type hints):
    @validate_data(age=(int, str))  # Allows int or str for age
    def my_function(name: str, age: int, price: float) -> str:
        pass
    
    Not strict (only validates overrides):
    @validate_data(strict=False, age=int)
    def my_function(name, age, price) -> str:  # Only validates 'age'
        pass
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            sig = inspect.signature(func)
            param_names = list(sig.parameters.keys())
            frame = sys._getframe(1)
            error_line = frame.f_lineno
            file_path = frame.f_code.co_filename
            errors = []
            _validate_override_parameters(sig, types_override, func.__name__)
            
            def normalize_types(types):
                if isinstance(types, (list, tuple)):
                    return tuple(types)
                return (types,)
            
            def extract_types_from_annotation(annotation):
                if annotation == inspect.Parameter.empty:
                    return None
                origin = get_origin(annotation)
                args = get_args(annotation)
                if origin is Union:
                    return args
                if origin is Union and len(args) == 2 and type(None) in args:
                    return tuple(arg for arg in args if arg is not type(None))
                if origin is not None:
                    return (origin,)
                return (annotation,)
            
            def create_object_detail(arg, received_type):
                if hasattr(arg, '__dict__'):
                    return f"{received_type.__name__}({arg.__dict__})"
                elif isinstance(arg, (list, tuple, set)):
                    if len(arg) <= 5:
                        return f"{received_type.__name__}({list(arg)})"
                    else:
                        return f"{received_type.__name__}([{', '.join(map(str, list(arg)[:3]))}, ...]) with {len(arg)} elements"
                elif isinstance(arg, dict):
                    if len(arg) <= 3:
                        return f"{received_type.__name__}({dict(arg)})"
                    else:
                        first_items = dict(list(arg.items())[:3])
                        return f"{received_type.__name__}({first_items}...) with {len(arg)} elements"
                elif isinstance(arg, str):
                    if len(arg) <= 50:
                        return f"{received_type.__name__}('{arg}')"
                    else:
                        return f"{received_type.__name__}('{arg[:47]}...') with {len(arg)} characters"
                else:
                    return f"{received_type.__name__}({repr(arg)})"
            
            is_class_method = len(args) > 0 and len(param_names) > 0 and param_names[0] in ['self', 'cls']
            if is_class_method:
                class_instance = args[0]
                class_name = class_instance.__class__.__name__ if param_names[0] == 'self' else args[0].__name__
                context = f"Method: {class_name}.{func.__name__}()"
                position_offset = 1
            else:
                context = f"Function: {func.__name__}()"
                position_offset = 0
            
            bound_args = sig.bind(*args, **kwargs)
            bound_args.apply_defaults()
            types_to_validate = {}
            
            if strict:
                for param_name, param in sig.parameters.items():
                    if param_name in ['self', 'cls']:
                        continue
                    types_from_annotation = extract_types_from_annotation(param.annotation)
                    if types_from_annotation:
                        types_to_validate[param_name] = types_from_annotation
            
            for param_name, override_types_param in types_override.items():
                types_to_validate[param_name] = normalize_types(override_types_param)
            
            for param_name, param in sig.parameters.items():
                if param_name in ['self', 'cls']:
                    continue
                if param_name not in types_to_validate:
                    continue
                if param_name not in bound_args.arguments:
                    continue
                
                expected_types = types_to_validate[param_name]
                arg_value = bound_args.arguments[param_name]
                
                if arg_value is None and type(None) in expected_types:
                    continue
                
                received_type = type(arg_value)
                
                if not _validate_complex_types(arg_value, expected_types):
                    param_index = param_names.index(param_name)
                    is_positional = param_index < len(args)
                    object_detail = create_object_detail(arg_value, received_type)
                    expected_types_str = " | ".join([getattr(type_, '__name__', str(type_)) for type_ in expected_types])
                    type_source = "override" if param_name in types_override else "type hint"
                    
                    error_info = {
                        'type': 'positional' if is_positional else 'named',
                        'name': param_name,
                        'position': param_index + 1 if is_positional else None,
                        'expected_type': expected_types_str,
                        'received_type': received_type.__name__,
                        'object_detail': object_detail,
                        'type_source': type_source
                    }
                    errors.append(error_info)
            
            if errors:
                error_msg = _create_optimized_error_message(errors, file_path, error_line, context)
                raise ValidationError(error_msg)
            
            return func(*args, **kwargs)
        return wrapper
    return decorator

class ValidationError(ValueError):
    """Custom exception for type validation errors."""
    pass

def _validate_override_parameters(sig, types_override, func_name):
    """
    Validates that all parameters specified in the override exist in the function.
    
    Args:
        sig: Function signature
        types_override: Dictionary with override types
        func_name: Function name for error
    
    Raises:
        ValueError: If any override parameter doesn't exist in the function
    """
    param_names = set(sig.parameters.keys())
    param_names.discard('self')
    param_names.discard('cls')
    override_parameters = set(types_override.keys())
    non_existent_parameters = override_parameters - param_names
    
    if non_existent_parameters:
        available_parameters = sorted(param_names)
        non_existent_parameters_sorted = sorted(non_existent_parameters)
        error_msg = f"\n{'='*70}\n"
        error_msg += f"DECORATOR CONFIGURATION ERROR\n"
        error_msg += f"{'='*70}\n"
        error_msg += f"Function: {func_name}()\n"
        error_msg += f"Non-existent parameters in override: {non_existent_parameters_sorted}\n"
        error_msg += f"Available parameters in function: {available_parameters}\n"
        error_msg += f"{'='*70}\n"
        error_msg += f"Parameters specified in @validate_data() decorator must\n"
        error_msg += f"correspond exactly with the function parameters.\n"
        error_msg += f"{'='*70}"
        raise ValueError(error_msg)

def _create_optimized_error_message(errors, file_path, error_line, context):
    """
    Creates an optimized and more readable error message.
    
    Args:
        errors: List of found errors
        file_path: File where the error occurred
        error_line: Line where the error occurred
        context: Function/method context
    
    Returns:
        str: Formatted error message
    """
    error_msg = f"\n{'='*70}\n"
    error_msg += f"TYPE VALIDATION ERROR\n"
    error_msg += f"{'='*70}\n"
    error_msg += f"📁 File: {file_path}\n"
    error_msg += f"📍 Line: {error_line}\n"
    error_msg += f"🔧 {context}\n"
    error_msg += f"❌ Errors found: {len(errors)}\n"
    error_msg += f"{'='*70}\n"
    
    for i, error in enumerate(errors, 1):
        error_msg += f"\n💥 ERROR {i}:\n"
        if error['type'] == 'positional':
            error_msg += f"   Parameter: '{error['name']}' (position {error['position']})\n"
        else:
            error_msg += f"   Parameter: '{error['name']}' (named argument)\n"
        error_msg += f"   ✅ Expected: {error['expected_type']} (from {error['type_source']})\n"
        error_msg += f"   ❌ Received: {error['received_type']}\n"
        error_msg += f"   📦 Value: {error['object_detail']}\n"
    
    error_msg += f"\n{'='*70}"
    return error_msg

def _validate_complex_types(arg_value, expected_types):
    """
    Validates complex types like List[int], Dict[str, int], etc.
    
    Args:
        arg_value: Value to validate
        expected_types: Expected types
    
    Returns:
        bool: True if validation passes
    """
    for expected_type in expected_types:
        origin = get_origin(expected_type)
        args = get_args(expected_type)
        
        if origin is None:
            if isinstance(arg_value, expected_type):
                return True
            continue
        
        if not isinstance(arg_value, origin):
            continue
        
        if origin is list and args:
            if all(isinstance(item, args[0]) for item in arg_value):
                return True
        elif origin is dict and len(args) == 2:
            if all(isinstance(k, args[0]) and isinstance(v, args[1]) 
                   for k, v in arg_value.items()):
                return True
        elif origin is tuple and args:
            if len(arg_value) == len(args):
                if all(isinstance(val, expected_type) 
                       for val, expected_type in zip(arg_value, args)):
                    return True
        elif origin is set and args:
            if all(isinstance(item, args[0]) for item in arg_value):
                return True
        elif origin is Union:
            if any(isinstance(arg_value, arg) for arg in args):
                return True
        else:
            if isinstance(arg_value, origin):
                return True
    
    return False

def validate_return_type(func):
    """
    Decorator to validate the return type of a function.
    
    Example:
    @validate_return_type
    def sum(a: int, b: int) -> int:
        return a + b
    """
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        result = func(*args, **kwargs)
        sig = inspect.signature(func)
        
        if sig.return_annotation != inspect.Signature.empty:
            expected_type = sig.return_annotation
            if not _validate_complex_types(result, (expected_type,)):
                frame = sys._getframe(1)
                error_line = frame.f_lineno
                file_path = frame.f_code.co_filename
                
                error_msg = f"\n{'='*70}\n"
                error_msg += f"RETURN TYPE VALIDATION ERROR\n"
                error_msg += f"{'='*70}\n"
                error_msg += f"📁 File: {file_path}\n"
                error_msg += f"📍 Line: {error_line}\n"
                error_msg += f"🔧 Function: {func.__name__}()\n"
                error_msg += f"✅ Expected type: {getattr(expected_type, '__name__', str(expected_type))}\n"
                error_msg += f"❌ Received type: {type(result).__name__}\n"
                error_msg += f"📦 Value: {repr(result)}\n"
                error_msg += f"{'='*70}"
                raise ValidationError(error_msg)
        
        return result
    return wrapper

def create_validator(custom_types: Dict[str, Any]):
    """
    Creates a custom validator with specific types.
    
    Args:
        custom_types: Dictionary with types to validate
    
    Returns:
        Configured decorator
    
    Example:
    validator = create_validator({
        'email': str,
        'age': int,
        'active': bool
    })
    
    @validator
    def process_user(email, age, active):
        pass
    """
    def decorator(func):
        return validate_data(**custom_types)(func)
    return decorator
