from typing import Any, Type, Union, Dict, Callable, get_origin, get_args
from collections.abc import Iterable
import sys

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
