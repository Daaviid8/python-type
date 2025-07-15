from typing import *
from collections.abc import Iterable
import sys
import inspect
import functools
import asyncio

class TypeConversionError(Exception):
    """Custom exception for type conversion errors"""
    pass

def convert(obj, target_type):
    """
    Converts 'obj' to 'target_type' quickly and efficiently.
    For dicts:
      - If 'obj' is a list or tuple of pairs (lists/tuples of length 2), converts to dict.
      - If 'obj' is a list or tuple of even length, converts using even elements as keys and odd elements as values.
      - If it doesn't meet criteria, raises ValueError.
    For other iterable types (except str), calls target_type(obj).
    For non-iterable objects or strings, wraps in list and then converts.
    """
    if target_type is dict:
        if isinstance(obj, (list, tuple)) and obj:
            if all(isinstance(p, (list, tuple)) and len(p) == 2 for p in obj):
                return dict(map(tuple, obj))
            elif len(obj) % 2 == 0:
                return dict(zip(obj[::2], obj[1::2]))
        raise ValueError(f"Cannot convert {type(obj).__name__} to dict")
    else:
        if isinstance(obj, Iterable) and not isinstance(obj, str):
            return target_type(obj)
        else:
            return target_type([obj])

def _convert_generic_type(obj: Any, target_type: Type) -> Any:
    """
    Converts objects to generic types like List[int], Dict[str, int], etc.
    """
    origin = get_origin(target_type)
    args = get_args(target_type)
    if origin is None:
        return _convert_simple_type(obj, target_type)
    if origin in (list, tuple, set):
        if not isinstance(obj, Iterable) or isinstance(obj, str):
            obj = [obj]
        if args:
            converted_items = [check_type(item, args[0], auto_convert=True) for item in obj]
        else:
            converted_items = list(obj)
        return origin(converted_items)
    elif origin is dict:
        if not isinstance(obj, dict):
            obj = convert(obj, dict)
        if len(args) == 2:
            key_type, value_type = args
            return {check_type(k, key_type, auto_convert=True): check_type(v, value_type, auto_convert=True) for k, v in obj.items()}
        else:
            return dict(obj)
    elif origin is Union:
        for arg_type in args:
            try:
                return check_type(obj, arg_type, auto_convert=True)
            except TypeConversionError:
                continue
        type_names = [getattr(arg, '__name__', str(arg)) for arg in args]
        raise TypeConversionError(f"Cannot convert {type(obj).__name__} to any of {type_names}")
    else:
        try:
            return origin(obj)
        except (ValueError, TypeError, AttributeError) as e:
            raise TypeConversionError(f"Cannot convert {type(obj).__name__} to {target_type}: {e}")

def _convert_simple_type(obj: Any, target_type: Type) -> Any:
    """
    Converts objects to simple types using the optimized cache.
    """
    converter = _ULTRA_CONVERSION_CACHE.get(target_type)
    if converter is not None:
        try:
            return converter(obj)
        except (ValueError, TypeError, AttributeError) as e:
            raise TypeConversionError(f"Cannot convert {type(obj).__name__} to {target_type.__name__}: {e}")
    try:
        return target_type(obj)
    except (ValueError, TypeError, AttributeError) as e:
        raise TypeConversionError(f"Cannot convert {type(obj).__name__} to {target_type.__name__}: {e}")

_ULTRA_CONVERSION_CACHE = {
    int: int,
    float: float,
    str: str,
    bool: bool,
    list: lambda obj: obj if isinstance(obj, list) else [obj],
    tuple: lambda obj: obj if isinstance(obj, tuple) else (obj,) if not isinstance(obj, Iterable) or isinstance(obj, str) else tuple(obj),
    set: lambda obj: obj if isinstance(obj, set) else {obj},
    dict: lambda obj: convert(obj, dict)
}

def check_type(obj: Any, target_type: Type, auto_convert: bool = True) -> Any:
    """
    Ultra-optimized version of check_type with support for generic types.
    Now handles complex types like List[int], Dict[str, int], Union[int, str], etc.
    """
    if type(obj) is target_type:
        return obj
    if not auto_convert:
        raise TypeConversionError(f"Object is {type(obj).__name__}, expected {target_type}")
    if hasattr(target_type, '__origin__') or get_origin(target_type) is not None:
        return _convert_generic_type(obj, target_type)
    return _convert_simple_type(obj, target_type)

def to_list_of(obj: Any, element_type: Type) -> list:
    """Converts obj to List[element_type]"""
    if sys.version_info >= (3, 9):
        return check_type(obj, list[element_type])
    else:
        from typing import List
        return check_type(obj, List[element_type])

def to_dict_of(obj: Any, key_type: Type, value_type: Type) -> dict:
    """Converts obj to Dict[key_type, value_type]"""
    if sys.version_info >= (3, 9):
        return check_type(obj, dict[key_type, value_type])
    else:
        from typing import Dict
        return check_type(obj, Dict[key_type, value_type])

def to_set_of(obj: Any, element_type: Type) -> set:
    """Converts obj to Set[element_type]"""
    if sys.version_info >= (3, 9):
        return check_type(obj, set[element_type])
    else:
        from typing import Set
        return check_type(obj, Set[element_type])

class TypedAttribute:
    """
    Descriptor que maneja la validación de tipos para atributos de clases Strict.
    
    Este descriptor se encarga de:
    - Validar el tipo del valor al asignarlo
    - Generar mensajes de error detallados con información de debugging
    - Mantener el valor del atributo en el diccionario de la instancia
    """
    
    def __init__(self, name: str, expected_type: Type, class_name: str):
        self.name = name
        self.expected_type = expected_type
        self.class_name = class_name
        self.private_name = f"__{name}"
    
    def __get__(self, instance, owner):
        """Obtiene el valor del atributo."""
        if instance is None:
            return self
        return getattr(instance, self.private_name, None)
    
    def __set__(self, instance, value):
        """Establece el valor del atributo con validación de tipo."""
        if not isinstance(value, self.expected_type):
            frame = inspect.currentframe()
            try:
                caller_frame = frame.f_back
                while caller_frame and self._is_internal_frame(caller_frame):
                    caller_frame = caller_frame.f_back
                if caller_frame:
                    filename = caller_frame.f_code.co_filename
                    line_number = caller_frame.f_lineno
                else:
                    filename = "unknown"
                    line_number = "unknown"
                error_msg = self._create_error_message(value, filename, line_number)
                raise TypeError(error_msg)
            finally:
                del frame
        setattr(instance, self.private_name, value)
    
    def _is_internal_frame(self, frame):
        """Determina si un frame es interno de la implementación de Strict."""
        code = frame.f_code
        filename = code.co_filename
        function_name = code.co_name
        internal_functions = {'__init__', '__setattr__', '__set__', '_validate_kwargs','_create_error_message', '_is_internal_frame'}
        return (function_name in internal_functions or 'Strict' in str(frame.f_locals.get('self', '')))
    
    def _create_error_message(self, value, filename, line_number):
        """Crea un mensaje de error detallado y legible."""
        received_type = type(value).__name__
        expected_type = self.expected_type.__name__
        return f"""
╔══════════════════════════════════════════════════════════════════════════════════════╗
║                                   TYPE ERROR                                         ║
╠══════════════════════════════════════════════════════════════════════════════════════╣
║ Class:     {self.class_name:<60} ║
║ Attribute: {self.name:<60} ║
║ File:      {filename:<60} ║
║ Line:      {line_number:<60} ║
║ Expected:  {expected_type:<60} ║
║ Received:  {received_type:<60} ║
║ Value:     {repr(value):<60} ║
╚══════════════════════════════════════════════════════════════════════════════════════╝
        """.strip()


class StrictMeta(type):
    """
    Metaclase para la clase Strict que procesa las declaraciones de tipo.
    
    Esta metaclase:
    - Identifica los atributos tipados en la definición de clase
    - Crea descriptores TypedAttribute para cada atributo tipado
    - Maneja la herencia de atributos tipados de clases base
    - Almacena información de tipos para validación
    """
    
    def __new__(mcs, name, bases, namespace, **kwargs):
        base_typed_attrs = {}
        for base in bases:
            if hasattr(base, '_typed_attributes'):
                base_typed_attrs.update(base._typed_attributes)
        typed_attrs = {}
        for attr_name, attr_value in list(namespace.items()):
            if isinstance(attr_value, type) and not attr_name.startswith('_'):
                typed_attrs[attr_name] = attr_value
                namespace[attr_name] = TypedAttribute(attr_name, attr_value, name)
        all_typed_attrs = {**base_typed_attrs, **typed_attrs}
        namespace['_typed_attributes'] = all_typed_attrs
        return super().__new__(mcs, name, bases, namespace, **kwargs)

class Strict(metaclass=StrictMeta):
    """
    Clase base que permite definir clases con campos tipados al estilo TypeScript.
    
    Características:
    - Validación automática de tipos en la creación e instancia
    - Mensajes de error detallados con información de debugging
    - Soporte para herencia de tipos
    - Constructor automático con argumentos de palabra clave
    - Validación continua en asignaciones posteriores
    
    Ejemplo de uso:
        class Persona(Strict):
            name = str
            age = int
        
        persona = Persona(name="Juan", age=30)  # OK
        persona.age = "treinta"  # TypeError con detalles
    """
    
    def __init__(self, **kwargs):
        """
        Constructor que valida y asigna los valores proporcionados.
        
        Args:
            **kwargs: Argumentos de palabra clave con los valores para los atributos
        
        Raises:
            TypeError: Si algún valor no coincide con el tipo esperado
            ValueError: Si faltan atributos requeridos o se proporcionan atributos no declarados
        """
        self._validate_kwargs(kwargs)
        for attr_name, value in kwargs.items():
            setattr(self, attr_name, value)
        missing_attrs = set(self._typed_attributes.keys()) - set(kwargs.keys())
        if missing_attrs:
            raise ValueError(f"Missing required attributes for {self.__class__.__name__}: " f"{', '.join(sorted(missing_attrs))}")
    
    def _validate_kwargs(self, kwargs):
        """
        Valida que los argumentos proporcionados sean válidos.
        
        Args:
            kwargs: Diccionario de argumentos a validar
        
        Raises:
            ValueError: Si se proporcionan atributos no declarados
        """
        unknown_attrs = set(kwargs.keys()) - set(self._typed_attributes.keys())
        if unknown_attrs:
            raise ValueError(f"Unknown attributes for {self.__class__.__name__}: " f"{', '.join(sorted(unknown_attrs))}. " f"Available attributes: {', '.join(sorted(self._typed_attributes.keys()))}")
    
    def __setattr__(self, name, value):
        """
        Intercepta la asignación de atributos para validar tipos.
        
        Args:
            name: Nombre del atributo
            value: Valor a asignar
        """
        if name.startswith('_'):
            super().__setattr__(name, value)
            return
        if name in self._typed_attributes:
            super().__setattr__(name, value)
        else:
            raise AttributeError(f"'{self.__class__.__name__}' object has no attribute '{name}'. " f"Available attributes: {', '.join(sorted(self._typed_attributes.keys()))}")
    
    def __repr__(self):
        """Representación string de la instancia."""
        attrs = []
        for attr_name in self._typed_attributes:
            value = getattr(self, attr_name, None)
            if value is not None:
                attrs.append(f"{attr_name}={repr(value)}")
        return f"{self.__class__.__name__}({', '.join(attrs)})"

def validate_data(*, strict: bool = True, validate_return: bool = True,custom_types: Optional[Dict[str, Any]] = None,**types_override):
    """
    Decorator for validating function parameters and return types.
    Works with both synchronous and asynchronous functions.
    
    Args:
        strict: If True, validates all parameters with type hints.
                If False, only validates parameters with override or custom_types.
        validate_return: If True, validates the return type against type hints.
        custom_types: Dictionary with custom type mappings for parameters.
        **types_override: Optional dictionary to override specific types.
                         Has priority over type hints and custom_types.
    
    Examples:
    
    Basic use (uses type hints automatically):
    @validate_data()
    def my_function(name: str, age: int, price: float) -> str:
        return f"{name} is {age} years old"
    
    @validate_data()
    async def async_function(name: str, age: int) -> str:
        await asyncio.sleep(0.1)  # Simulate async operation
        return f"{name} is {age} years old"
    
    With override (overwrites specific type hints):
    @validate_data(age=(int, str))  # Allows int or str for age
    def my_function(name: str, age: int, price: float) -> str:
        return f"{name} is {age} years old"
    
    Not strict (only validates overrides):
    @validate_data(strict=False, age=int)
    def my_function(name, age, price) -> str:  # Only validates 'age'
        return f"{name} is {age} years old"
    
    Without return validation:
    @validate_data(validate_return=False)
    async def sum_numbers(a: int, b: int) -> int:
        return a + b
    
    With custom types:
    @validate_data(custom_types={'email': str, 'age': int, 'active': bool})
    async def process_user(email, age, active):
        await asyncio.sleep(0.1)
        return f"User {email} processed"
    
    All options combined:
    @validate_data(strict=True, validate_return=True, custom_types={'base_price': float},discount=(int, float))
    async def calculate_price(base_price: float, discount: int, tax: float) -> float:
        await asyncio.sleep(0.1)
        return base_price * (1 - discount/100) * (1 + tax/100)
    """
    def decorator(func):
        is_async = asyncio.iscoroutinefunction(func)
        if is_async:
            @functools.wraps(func)
            async def async_wrapper(*args, **kwargs):
                _validate_parameters(func, args, kwargs)
                result = await func(*args, **kwargs)
                if validate_return:
                    _validate_return_type(func, result)
                return result
            return async_wrapper
        else:
            @functools.wraps(func)
            def sync_wrapper(*args, **kwargs):
                _validate_parameters(func, args, kwargs)
                result = func(*args, **kwargs)
                if validate_return:
                    _validate_return_type(func, result)
                return result
            return sync_wrapper
    
    def _validate_parameters(func, args, kwargs):
        """Common parameter validation logic for both sync and async functions."""
        sig = inspect.signature(func)
        param_names = list(sig.parameters.keys())
        frame = sys._getframe(2)  # Go up 2 frames to get the actual caller
        error_line = frame.f_lineno
        file_path = frame.f_code.co_filename
        errors = []
        _validate_override_parameters(sig, types_override, func.__name__)
        is_class_method = len(args) > 0 and len(param_names) > 0 and param_names[0] in ['self', 'cls']
        if is_class_method:
            class_instance = args[0]
            class_name = class_instance.__class__.__name__ if param_names[0] == 'self' else args[0].__name__
            context = f"Method: {class_name}.{func.__name__}()"
        else:
            context = f"Function: {func.__name__}()"
        if asyncio.iscoroutinefunction(func):
            context += " [async]"
        bound_args = sig.bind(*args, **kwargs)
        bound_args.apply_defaults()
        types_to_validate = {}
        if strict:
            for param_name, param in sig.parameters.items():
                if param_name in ['self', 'cls']:
                    continue
                types_from_annotation = _extract_types_from_annotation(param.annotation)
                if types_from_annotation:
                    types_to_validate[param_name] = types_from_annotation
        if custom_types:
            for param_name, custom_type in custom_types.items():
                types_to_validate[param_name] = _normalize_types(custom_type)
        for param_name, override_types_param in types_override.items():
            types_to_validate[param_name] = _normalize_types(override_types_param)
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
                object_detail = _create_object_detail(arg_value, received_type)
                expected_types_str = " | ".join([getattr(type_, '__name__', str(type_)) for type_ in expected_types])
                if param_name in types_override:
                    type_source = "override"
                elif custom_types and param_name in custom_types:
                    type_source = "custom_types"
                else:
                    type_source = "type hint"
                error_info = {'type': 'positional' if is_positional else 'named','name': param_name,'position': param_index + 1 if is_positional else None,'expected_type': expected_types_str,'received_type': received_type.__name__,'object_detail': object_detail,'type_source': type_source}
                errors.append(error_info)
        if errors:
            error_msg = _create_optimized_error_message(errors, file_path, error_line, context)
            raise ValidationError(error_msg)
    
    def _validate_return_type(func, result):
        """Common return type validation logic for both sync and async functions."""
        sig = inspect.signature(func)
        if sig.return_annotation != inspect.Signature.empty:
            expected_return_type = sig.return_annotation
            if not _validate_complex_types(result, (expected_return_type,)):
                frame = sys._getframe(2)  # Go up 2 frames to get the actual caller
                error_line = frame.f_lineno
                file_path = frame.f_code.co_filename
                is_class_method = hasattr(func, '__self__')
                if is_class_method:
                    class_name = func.__self__.__class__.__name__
                    context = f"Method: {class_name}.{func.__name__}()"
                else:
                    context = f"Function: {func.__name__}()"
                if asyncio.iscoroutinefunction(func):
                    context += " [async]"
                error_msg = f"\n{'='*70}\n"
                error_msg += f"RETURN TYPE VALIDATION ERROR\n"
                error_msg += f"{'='*70}\n"
                error_msg += f"📁 File: {file_path}\n"
                error_msg += f"📍 Line: {error_line}\n"
                error_msg += f"🔧 {context}\n"
                error_msg += f"✅ Expected type: {getattr(expected_return_type, '__name__', str(expected_return_type))}\n"
                error_msg += f"❌ Received type: {type(result).__name__}\n"
                error_msg += f"📦 Value: {repr(result)}\n"
                error_msg += f"{'='*70}"
                raise ValidationError(error_msg)
    return decorator

def create_validator(custom_types: Dict[str, Any], **kwargs):
    """
    Creates a custom validator with specific types.
    Works with both synchronous and asynchronous functions.
    
    Args:
        custom_types: Dictionary with types to validate
        **kwargs: Additional arguments passed to validate_data
    
    Returns:
        Configured decorator
    
    Examples:
    
    Create a validator for user data:
    user_validator = create_validator({
        'email': str,
        'age': int,
        'active': bool
    })
    
    @user_validator
    def process_user(email, age, active):
        return f"User {email} processed"
    
    @user_validator
    async def async_process_user(email, age, active):
        await asyncio.sleep(0.1)
        return f"User {email} processed"
    
    Create a validator with additional options:
    strict_validator = create_validator(
        {'price': float, 'quantity': int},
        strict=False,
        validate_return=False
    )
    
    @strict_validator
    async def calculate_total(price, quantity):
        await asyncio.sleep(0.1)
        return price * quantity
    """
    return validate_data(custom_types=custom_types, **kwargs)

class ValidationError(ValueError):
    """Custom exception for type validation errors."""
    pass

def _normalize_types(types):
    """Normalizes types to a tuple format."""
    if isinstance(types, (list, tuple)):
        return tuple(types)
    return (types,)

def _extract_types_from_annotation(annotation):
    """Extracts types from type annotation."""
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

def _create_object_detail(arg, received_type):
    """Creates detailed object representation for error messages."""
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

def _validate_override_parameters(sig, types_override, func_name):
    """Validates that all parameters specified in the override exist in the function."""
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
    """Creates an optimized and more readable error message."""
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
    """Validates complex types like List[int], Dict[str, int], etc."""
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
