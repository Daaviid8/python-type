from typing import *
from collections.abc import Iterable
import sys
import inspect
import functools
import asyncio
from dataclasses import dataclass, fields, is_dataclass
import json
from datetime import datetime, date
from decimal import Decimal
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor
import multiprocessing as mp

class TypeConversionError(Exception):
    """Custom exception for type conversion errors"""
    pass

class BatchValidationResult:
    """Resultado de la validación en batch"""
    def __init__(self):
        self.successful: List[Any] = []
        self.failed: List[Tuple[int, Any, Exception]] = []
        self.success_rate: float = 0.0
        self.total_processed: int = 0
    
    def add_success(self, item: Any):
        self.successful.append(item)
    
    def add_failure(self, index: int, item: Any, error: Exception):
        self.failed.append((index, item, error))
    
    def finalize(self):
        self.total_processed = len(self.successful) + len(self.failed)
        self.success_rate = len(self.successful) / self.total_processed if self.total_processed > 0 else 0.0
    
    def get_summary(self) -> dict:
        return {
            "total_processed": self.total_processed,
            "successful": len(self.successful),
            "failed": len(self.failed),
            "success_rate": f"{self.success_rate:.2%}",
            "errors": [(idx, type(item).__name__, str(error)) for idx, item, error in self.failed]
        }

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

def _validate_single_item(args):
    """Función auxiliar para validación paralela"""
    index, item, target_type, auto_convert = args
    try:
        converted = check_type(item, target_type, auto_convert=auto_convert)
        return (True, index, converted, None)
    except Exception as e:
        return (False, index, item, e)

def batch_check_type(items: List[Any], target_type: Type, auto_convert: bool = True,parallel: bool = None,max_workers: Optional[int] = None,chunk_size: Optional[int] = None,min_parallel_size: int = 50000) -> BatchValidationResult:
    """
    Valida una lista de items contra un tipo específico con alta performance.
    
    Args:
        items: Lista de items a validar
        target_type: Tipo objetivo al que convertir/validar
        auto_convert: Si realizar conversión automática
        parallel: Si usar procesamiento paralelo (None = auto-detect)
        max_workers: Número máximo de workers (None = auto)
        chunk_size: Tamaño de chunk para procesamiento (None = auto)
        min_parallel_size: Tamaño mínimo para activar paralelización automática
    
    Returns:
        BatchValidationResult con resultados de la validación
    """
    result = BatchValidationResult()
    if not items:
        result.finalize()
        return result
    if parallel is None:
        should_parallelize = (len(items) >= min_parallel_size and _is_complex_type(target_type))
        parallel = should_parallelize
    if chunk_size is None:
        if parallel:
            chunk_size = max(1000, len(items) // (max_workers or mp.cpu_count() * 2))
        else:
            chunk_size = len(items)
    if parallel and len(items) > 1000:
        _batch_check_parallel(items, target_type, auto_convert, max_workers, chunk_size, result)
    else:
        _batch_check_sequential_optimized(items, target_type, auto_convert, result)
    result.finalize()
    return result

def _is_complex_type(target_type: Type) -> bool:
    """Determina si un tipo es complejo y se beneficia de paralelización"""
    complex_types = {dict, list, tuple, set}
    origin = get_origin(target_type)
    if origin is not None:
        return origin in complex_types or origin is Union
    try:
        return is_dataclass(target_type) or hasattr(target_type, '__dataclass_fields__')
    except:
        return False

def _batch_check_sequential_optimized(items: List[Any], target_type: Type, auto_convert: bool, result: BatchValidationResult):
    """Validación secuencial ultra-optimizada"""
    converter = _ULTRA_CONVERSION_CACHE.get(target_type)
    is_generic = hasattr(target_type, '__origin__') or get_origin(target_type) is not None
    if not auto_convert:
        for i, item in enumerate(items):
            if type(item) is target_type:
                result.add_success(item)
            else:
                result.add_failure(i, item, TypeConversionError(f"Object is {type(item).__name__}, expected {target_type}"))
        return
    if converter is not None and not is_generic:
        for i, item in enumerate(items):
            if type(item) is target_type:
                result.add_success(item)
            else:
                try:
                    converted = converter(item)
                    result.add_success(converted)
                except (ValueError, TypeError, AttributeError) as e:
                    result.add_failure(i, item, TypeConversionError(f"Cannot convert {type(item).__name__} to {target_type.__name__}: {e}"))
        return
    for i, item in enumerate(items):
        try:
            converted = check_type(item, target_type, auto_convert=auto_convert)
            result.add_success(converted)
        except Exception as e:
            result.add_failure(i, item, e)

def _batch_check_parallel(items: List[Any], target_type: Type, auto_convert: bool, max_workers: Optional[int], chunk_size: int, result: BatchValidationResult):
    """Validación paralela usando ThreadPoolExecutor"""
    if max_workers is None:
        max_workers = min(mp.cpu_count(), len(items) // chunk_size + 1)
    args_list = [(i, item, target_type, auto_convert) for i, item in enumerate(items)]
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = []
        for i in range(0, len(args_list), chunk_size):
            chunk = args_list[i:i + chunk_size]
            future = executor.submit(_process_chunk, chunk)
            futures.append(future)
        for future in futures:
            chunk_results = future.result()
            for success, index, item_or_converted, error in chunk_results:
                if success:
                    result.add_success(item_or_converted)
                else:
                    result.add_failure(index, item_or_converted, error)

def _process_chunk(chunk_args):
    """Procesa un chunk de items"""
    return [_validate_single_item(args) for args in chunk_args]

def batch_validate_schema(items: List[dict], schema: Dict[str, Type],auto_convert: bool = True,parallel: bool = None,max_workers: Optional[int] = None,min_parallel_size: int = 25000) -> BatchValidationResult:
    """
    Valida una lista de diccionarios contra un esquema definido.
    
    Args:
        items: Lista de diccionarios a validar
        schema: Esquema con nombres de campos y tipos esperados
        auto_convert: Si realizar conversión automática
        parallel: Si usar procesamiento paralelo (None = auto-detect)
        max_workers: Número máximo de workers
        min_parallel_size: Tamaño mínimo para paralelización automática
    
    Returns:
        BatchValidationResult con resultados de la validación
    """
    result = BatchValidationResult()
    if not items:
        result.finalize()
        return result
    if parallel is None:
        complex_fields = sum(1 for field_type in schema.values() if _is_complex_type(field_type))
        should_parallelize = (len(items) >= min_parallel_size and complex_fields >= len(schema) * 0.3)
        parallel = should_parallelize
    if parallel and len(items) > 5000:
        _batch_validate_schema_parallel(items, schema, auto_convert, max_workers, result)
    else:
        _batch_validate_schema_sequential_optimized(items, schema, auto_convert, result)
    result.finalize()
    return result

def _batch_validate_schema_sequential_optimized(items: List[dict], schema: Dict[str, Type], auto_convert: bool, result: BatchValidationResult):
    """Validación secuencial ultra-optimizada de esquemas"""
    field_converters = {}
    field_is_generic = {}
    for field_name, field_type in schema.items():
        field_converters[field_name] = _ULTRA_CONVERSION_CACHE.get(field_type)
        field_is_generic[field_name] = hasattr(field_type, '__origin__') or get_origin(field_type) is not None
    schema_keys = set(schema.keys())
    if not auto_convert:
        for i, item in enumerate(items):
            try:
                item_keys = set(item.keys())
                missing_fields = schema_keys - item_keys
                if missing_fields:
                    raise TypeConversionError(f"Missing required fields: {', '.join(missing_fields)}")
                validated_item = {}
                for field_name, field_type in schema.items():
                    field_value = item[field_name]
                    if type(field_value) is field_type:
                        validated_item[field_name] = field_value
                    else:
                        raise TypeConversionError(f"Field '{field_name}' is {type(field_value).__name__}, expected {field_type}")
                result.add_success(validated_item)
            except Exception as e:
                result.add_failure(i, item, e)
        return
    for i, item in enumerate(items):
        try:
            if not schema_keys.issubset(item.keys()):
                missing_fields = schema_keys - item.keys()
                raise TypeConversionError(f"Missing required fields: {', '.join(missing_fields)}")
            validated_item = {}
            for field_name, field_type in schema.items():
                field_value = item[field_name]
                if type(field_value) is field_type:
                    validated_item[field_name] = field_value
                    continue
                converter = field_converters[field_name]
                if converter is not None and not field_is_generic[field_name]:
                    try:
                        validated_item[field_name] = converter(field_value)
                        continue
                    except (ValueError, TypeError, AttributeError) as e:
                        raise TypeConversionError(f"Cannot convert field '{field_name}' from {type(field_value).__name__} to {field_type.__name__}: {e}")
                validated_item[field_name] = check_type(field_value, field_type, auto_convert=True)
            result.add_success(validated_item)
        except Exception as e:
            result.add_failure(i, item, e)

def _batch_validate_schema_parallel(items: List[dict], schema: Dict[str, Type], auto_convert: bool, max_workers: Optional[int], result: BatchValidationResult):
    """Validación paralela de esquemas"""
    if max_workers is None:
        max_workers = min(mp.cpu_count(), len(items) // 100 + 1)
    def validate_item_schema(args):
        index, item = args
        try:
            validated_item = {}
            for field_name, field_type in schema.items():
                if field_name in item:
                    validated_item[field_name] = check_type(item[field_name], field_type, auto_convert=auto_convert)
                else:
                    raise TypeConversionError(f"Missing required field: {field_name}")
            return (True, index, validated_item, None)
        except Exception as e:
            return (False, index, item, e)
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        args_list = [(i, item) for i, item in enumerate(items)]
        futures = [executor.submit(validate_item_schema, args) for args in args_list]
        for future in futures:
            success, index, item_or_validated, error = future.result()
            if success:
                result.add_success(item_or_validated)
            else:
                result.add_failure(index, item_or_validated, error)

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

def batch_to_list_of(items: List[Any], element_type: Type, **kwargs) -> BatchValidationResult:
    """Convierte batch de items a List[element_type]"""
    target_type = list[element_type] if sys.version_info >= (3, 9) else List[element_type]
    return batch_check_type(items, target_type, **kwargs)

def batch_to_dict_of(items: List[Any], key_type: Type, value_type: Type, **kwargs) -> BatchValidationResult:
    """Convierte batch de items a Dict[key_type, value_type]"""
    target_type = dict[key_type, value_type] if sys.version_info >= (3, 9) else Dict[key_type, value_type]
    return batch_check_type(items, target_type, **kwargs)

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
        return f"""Class:     {self.class_name}
Attribute: {self.name}
File:      {filename}
Line:      {line_number}
Expected:  {expected_type}
Received:  {received_type}
Value:     {repr(value)}""".strip()

class StrictJSONEncoder(json.JSONEncoder):
    """
    Encoder JSON personalizado para objetos Strict.
    Maneja automáticamente la serialización de objetos Strict y otros tipos comunes.
    """
    def default(self, obj):
        """Serializa objetos que no son nativamente JSON-serializables."""
        if isinstance(obj, Strict):
            return obj.to_dict()
        if isinstance(obj, (datetime, date)):
            return obj.isoformat()
        if isinstance(obj, Decimal):
            return float(obj)
        if isinstance(obj, set):
            return list(obj)
        if hasattr(obj, 'to_dict') and callable(getattr(obj, 'to_dict')):
            return obj.to_dict()
        if hasattr(obj, '__dict__'):
            return obj.__dict__
        return super().default(obj)

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
    - Serialización automática a JSON
    - Deserialización desde JSON
    
    Ejemplo de uso:
        class Persona(Strict):
            name = str
            age = int
        
        persona = Persona(name="Juan", age=30)
        json_str = persona.to_json()
        persona2 = Persona.from_json(json_str)
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
            raise ValueError(f"Missing required attributes for {self.__class__.__name__}: "
                           f"{', '.join(sorted(missing_attrs))}")

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
            raise ValueError(f"Unknown attributes for {self.__class__.__name__}: "
                           f"{', '.join(sorted(unknown_attrs))}. "
                           f"Available attributes: {', '.join(sorted(self._typed_attributes.keys()))}")

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
            raise AttributeError(f"'{self.__class__.__name__}' object has no attribute '{name}'. "
                               f"Available attributes: {', '.join(sorted(self._typed_attributes.keys()))}")

    def __repr__(self):
        """Representación string de la instancia."""
        attrs = []
        for attr_name in self._typed_attributes:
            value = getattr(self, attr_name, None)
            if value is not None:
                attrs.append(f"{attr_name}={repr(value)}")
        return f"{self.__class__.__name__}({', '.join(attrs)})"

    def to_dict(self, include_class_name: bool = False) -> Dict[str, Any]:
        """
        Convierte el objeto a un diccionario.
        
        Args:
            include_class_name: Si incluir el nombre de la clase en el diccionario
        
        Returns:
            Dict con los atributos del objeto
        """
        result = {}
        if include_class_name:
            result['__class__'] = self.__class__.__name__
        for attr_name in self._typed_attributes:
            value = getattr(self, attr_name, None)
            if value is not None:
                result[attr_name] = self._serialize_value(value)
        return result

    def _serialize_value(self, value: Any) -> Any:
        """
        Serializa un valor para JSON, manejando tipos especiales.
        
        Args:
            value: Valor a serializar
        
        Returns:
            Valor serializable en JSON
        """
        if isinstance(value, Strict):
            return value.to_dict()
        if isinstance(value, list):
            return [self._serialize_value(item) for item in value]
        if isinstance(value, dict):
            return {k: self._serialize_value(v) for k, v in value.items()}
        if isinstance(value, set):
            return list(value)
        if isinstance(value, (datetime, date)):
            return value.isoformat()
        if isinstance(value, Decimal):
            return float(value)
        if hasattr(value, '__dict__') and not isinstance(value, (str, int, float, bool)):
            try:
                return {k: self._serialize_value(v) for k, v in value.__dict__.items()}
            except:
                pass
        return value

    def to_json(self, indent: int = None, include_class_name: bool = False) -> str:
        """
        Convierte el objeto a JSON string.
        
        Args:
            indent: Número de espacios para indentación (None = compacto)
            include_class_name: Si incluir el nombre de la clase
        
        Returns:
            String JSON del objeto
        """
        data = self.to_dict(include_class_name=include_class_name)
        return json.dumps(data, cls=StrictJSONEncoder, indent=indent, ensure_ascii=False)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Strict':
        """
        Crea una instancia desde un diccionario.
        
        Args:
            data: Diccionario con los datos del objeto
        
        Returns:
            Nueva instancia de la clase
        
        Raises:
            ValueError: Si los datos no son válidos
        """
        clean_data = {k: v for k, v in data.items() if k != '__class__'}
        processed_data = {}
        for attr_name, value in clean_data.items():
            if attr_name in cls._typed_attributes:
                expected_type = cls._typed_attributes[attr_name]
                processed_data[attr_name] = cls._deserialize_value(value, expected_type)
            else:
                processed_data[attr_name] = value
        return cls(**processed_data)

    @classmethod
    def _deserialize_value(cls, value: Any, expected_type: Type) -> Any:
        """
        Deserializa un valor desde JSON, manejando tipos especiales.
        
        Args:
            value: Valor a deserializar
            expected_type: Tipo esperado del valor
        
        Returns:
            Valor deserializado
        """
        if value is None:
            return value
        if isinstance(value, expected_type):
            return value
        if isinstance(value, dict) and hasattr(expected_type, '_typed_attributes'):
            return expected_type.from_dict(value)
        if expected_type == list and isinstance(value, list):
            return value
        if expected_type == set and isinstance(value, list):
            return set(value)
        if expected_type == dict and isinstance(value, dict):
            return value
        if expected_type == datetime and isinstance(value, str):
            try:
                return datetime.fromisoformat(value)
            except:
                pass
        if expected_type == date and isinstance(value, str):
            try:
                return date.fromisoformat(value)
            except:
                pass
        if expected_type == Decimal and isinstance(value, (int, float)):
            return Decimal(str(value))
        try:
            return expected_type(value)
        except:
            return value

    @classmethod
    def from_json(cls, json_str: str) -> 'Strict':
        """
        Crea una instancia desde un JSON string.
        
        Args:
            json_str: String JSON con los datos del objeto
        
        Returns:
            Nueva instancia de la clase
        
        Raises:
            ValueError: Si el JSON no es válido
            TypeError: Si los datos no coinciden con los tipos esperados
        """
        try:
            data = json.loads(json_str)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON: {e}")
        if not isinstance(data, dict):
            raise ValueError("JSON must represent an object (dictionary)")
        return cls.from_dict(data)

    def to_pretty_json(self, include_class_name: bool = False) -> str:
        """
        Convierte el objeto a JSON formateado de manera legible.
        
        Args:
            include_class_name: Si incluir el nombre de la clase
        
        Returns:
            String JSON formateado
        """
        return self.to_json(indent=2, include_class_name=include_class_name)

    def save_to_file(self, filename: str, include_class_name: bool = False, pretty: bool = True):
        """
        Guarda el objeto en un archivo JSON.
        
        Args:
            filename: Nombre del archivo
            include_class_name: Si incluir el nombre de la clase
            pretty: Si formatear el JSON de manera legible
        """
        json_str = self.to_json(indent=2 if pretty else None,include_class_name=include_class_name)
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(json_str)

    @classmethod
    def load_from_file(cls, filename: str) -> 'Strict':
        """
        Carga un objeto desde un archivo JSON.
        
        Args:
            filename: Nombre del archivo
        
        Returns:
            Nueva instancia de la clase
        
        Raises:
            FileNotFoundError: Si el archivo no existe
            ValueError: Si el JSON no es válido
        """
        with open(filename, 'r', encoding='utf-8') as f:
            json_str = f.read()
        return cls.from_json(json_str)

    def __eq__(self, other):
        """Compara dos objetos Strict por igualdad."""
        if not isinstance(other, self.__class__):
            return False
        for attr_name in self._typed_attributes:
            if getattr(self, attr_name, None) != getattr(other, attr_name, None):
                return False
        return True

    def __hash__(self):
        """Genera hash del objeto basado en sus atributos."""
        values = []
        for attr_name in sorted(self._typed_attributes.keys()):
            value = getattr(self, attr_name, None)
            if isinstance(value, (list, dict, set)):
                if isinstance(value, list):
                    value = tuple(value)
                elif isinstance(value, dict):
                    value = tuple(sorted(value.items()))
                elif isinstance(value, set):
                    value = tuple(sorted(value))
            values.append(value)
        return hash((self.__class__.__name__, tuple(values)))

class DataclassValidationMixin:
    """
    Mixin que añade validación de tipos a dataclasses.
    Se debe usar junto con @dataclass para obtener validación automática.
    """
    
    def __post_init__(self):
        """
        Método llamado automáticamente por dataclass después de __init__.
        Valida todos los campos del dataclass.
        """
        if hasattr(super(), '__post_init__'):
            super().__post_init__()
        
        self._validate_dataclass_fields()
    
    def _validate_dataclass_fields(self):
        """Valida todos los campos del dataclass."""
        if not is_dataclass(self):
            return
        
        for field in fields(self):
            if field.name.startswith('_'):
                continue
            
            value = getattr(self, field.name)
            expected_type = field.type
            
            if not self._validate_field_type(value, expected_type, field.name):
                frame = inspect.currentframe()
                try:
                    caller_frame = frame.f_back.f_back  # Skip __post_init__ and __init__
                    filename = caller_frame.f_code.co_filename if caller_frame else "unknown"
                    line_number = caller_frame.f_lineno if caller_frame else "unknown"
                    
                    error_msg = self._create_dataclass_error_message(
                        field.name, value, expected_type, filename, line_number
                    )
                    raise TypeError(error_msg)
                finally:
                    del frame
    
    def _validate_field_type(self, value, expected_type, field_name):
        """Valida un campo específico."""
        if value is None:
            origin = get_origin(expected_type)
            args = get_args(expected_type)
            if origin is Union and type(None) in args:
                return True
        
        return _validate_complex_types(value, (expected_type,))
    
    def _create_dataclass_error_message(self, field_name, value, expected_type, filename, line_number):
        """Crea un mensaje de error para dataclass."""
        received_type = type(value).__name__
        expected_type_name = getattr(expected_type, '__name__', str(expected_type))
        
        return f"""Dataclass: {self.__class__.__name__}
Field:     {field_name}
File:      {filename}
Line:      {line_number}
Expected:  {expected_type_name}
Received:  {received_type}
Value:     {repr(value)}""".strip()
    
    def __setattr__(self, name, value):
        """Intercepta la asignación de atributos para validar tipos en dataclass."""
        if not name.startswith('_') and is_dataclass(self):
            # Buscar el campo en el dataclass
            field_types = {f.name: f.type for f in fields(self)}
            if name in field_types:
                expected_type = field_types[name]
                if not self._validate_field_type(value, expected_type, name):
                    frame = inspect.currentframe()
                    try:
                        caller_frame = frame.f_back
                        filename = caller_frame.f_code.co_filename if caller_frame else "unknown"
                        line_number = caller_frame.f_lineno if caller_frame else "unknown"
                        
                        error_msg = self._create_dataclass_error_message(
                            name, value, expected_type, filename, line_number
                        )
                        raise TypeError(error_msg)
                    finally:
                        del frame
        
        super().__setattr__(name, value)

def validated_dataclass(cls=None, *dataclass_args, **dataclass_kwargs):
    """
    Decorator que combina @dataclass con validación automática de tipos.
    
    Usos soportados:
        # Sin paréntesis (solo kwargs por defecto)
        @validated_dataclass
        class Person:
            name: str
            age: int
        
        # Con paréntesis vacíos
        @validated_dataclass()
        class Person:
            name: str
            age: int
        
        # Con argumentos nombrados
        @validated_dataclass(frozen=True, order=True)
        class Person:
            name: str
            age: int
        
        # Con argumentos posicionales y nombrados (como en código 1)
        @validated_dataclass(True, True, frozen=True)  # init=True, repr=True, frozen=True
        class Person:
            name: str
            age: int
    """
    def wrap(base_cls):
        # Aplicar @dataclass con todos los argumentos (posicionales y nombrados)
        dataclass_base = dataclass(base_cls, *dataclass_args, **dataclass_kwargs)
        
        # Crear clase con herencia múltiple
        class Validated(dataclass_base, DataclassValidationMixin):
            pass
        
        # Preservar metadatos de la clase original
        Validated.__name__ = base_cls.__name__
        Validated.__qualname__ = base_cls.__qualname__
        Validated.__module__ = base_cls.__module__
        
        return Validated
    
    # Si cls es None, se llamó con paréntesis: @validated_dataclass() o @validated_dataclass(args...)
    if cls is None:
        return wrap
    # Si cls no es None, se llamó sin paréntesis: @validated_dataclass
    else:
        # Verificar que no se pasaron argumentos posicionales cuando se usa sin paréntesis
        if dataclass_args or dataclass_kwargs:
            raise TypeError(
                "Cannot use positional or keyword arguments when applying "
                "@validated_dataclass directly to a class. Use @validated_dataclass() instead."
            )
        return wrap(cls)
        
import functools
import inspect
import asyncio
import sys
from typing import get_origin, get_args, Union, Dict, Any, Optional

def validate_data(*, strict: bool = True, validate_return: bool = True, custom_types: Optional[Dict[str, Any]] = None, **types_override):
    """
    Decorator for validating function parameters and return types.
    Works with both synchronous and asynchronous functions, including lambdas.
    
    Args:
        strict: If True, validates all parameters with type hints.
                If False, only validates parameters with override or custom_types.
        validate_return: If True, validates the return type against type hints.
        custom_types: Dictionary with custom type mappings for parameters.
        **types_override: Optional dictionary to override specific types.
                         Has priority over type hints and custom_types.
    
    Note: Lambda functions have limitations:
    - No type hints available (must use custom_types or types_override)
    - Parameter names may be generic (arg0, arg1, etc.)
    - Limited debugging information
    """
    def decorator(func):
        is_async = asyncio.iscoroutinefunction(func)
        is_lambda = func.__name__ == '<lambda>'
        
        if is_async:
            @functools.wraps(func)
            async def async_wrapper(*args, **kwargs):
                _validate_parameters(func, args, kwargs, is_lambda)
                result = await func(*args, **kwargs)
                if validate_return:
                    _validate_return_type(func, result, is_lambda)
                return result
            return async_wrapper
        else:
            @functools.wraps(func)
            def sync_wrapper(*args, **kwargs):
                _validate_parameters(func, args, kwargs, is_lambda)
                result = func(*args, **kwargs)
                if validate_return:
                    _validate_return_type(func, result, is_lambda)
                return result
            return sync_wrapper

    def _validate_parameters(func, args, kwargs, is_lambda):
        """Common parameter validation logic for both sync and async functions."""
        sig = inspect.signature(func)
        param_names = list(sig.parameters.keys())
        
        frame = sys._getframe(2)  # Go up 2 frames to get the actual caller
        error_line = frame.f_lineno
        file_path = frame.f_code.co_filename
        
        errors = []
        
        _validate_override_parameters(sig, types_override, func.__name__)
        
        # Determine if it's a class method (not applicable for lambdas)
        is_class_method = not is_lambda and len(args) > 0 and len(param_names) > 0 and param_names[0] in ['self', 'cls']
        
        if is_lambda:
            context = f"Lambda function: {func.__name__}"
        elif is_class_method:
            class_instance = args[0]
            class_name = class_instance.__class__.__name__ if param_names[0] == 'self' else args[0].__name__
            context = f"Method: {class_name}.{func.__name__}()"
        else:
            context = f"Function: {func.__name__}()"
        
        if asyncio.iscoroutinefunction(func):
            context += " [async]"
        
        # Bind arguments
        try:
            bound_args = sig.bind(*args, **kwargs)
            bound_args.apply_defaults()
        except TypeError as e:
            # Handle binding errors more gracefully for lambdas
            if is_lambda:
                raise ValidationError(f"Lambda function signature mismatch: {e}")
            else:
                raise ValidationError(f"Function signature mismatch: {e}")
        
        # Collect types to validate
        types_to_validate = {}
        
        # Add type hints if strict mode is enabled (usually not available for lambdas)
        if strict and not is_lambda:
            for param_name, param in sig.parameters.items():
                if param_name in ['self', 'cls']:
                    continue
                types_from_annotation = _extract_types_from_annotation(param.annotation)
                if types_from_annotation:
                    types_to_validate[param_name] = types_from_annotation
        
        # For lambdas in strict mode, warn that type hints are not available
        if strict and is_lambda and not custom_types and not types_override:
            print(f"Warning: Lambda function has no type hints. Use custom_types or types_override for validation.")
        
        # Add custom types (override annotation types)
        if custom_types:
            for param_name, custom_type in custom_types.items():
                types_to_validate[param_name] = _normalize_types(custom_type)
        
        # Add override types (highest priority)
        for param_name, override_types_param in types_override.items():
            types_to_validate[param_name] = _normalize_types(override_types_param)
        
        # Validate each parameter
        for param_name, param in sig.parameters.items():
            if param_name in ['self', 'cls']:
                continue
            
            if param_name not in types_to_validate:
                continue
            
            if param_name not in bound_args.arguments:
                continue
            
            expected_types = types_to_validate[param_name]
            arg_value = bound_args.arguments[param_name]
            
            # Handle None values for Optional types
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
                
                error_info = {
                    'type': 'positional' if is_positional else 'named',
                    'name': param_name,
                    'position': param_index + 1 if is_positional else None,
                    'expected_type': expected_types_str,
                    'received_type': received_type.__name__,
                    'object_detail': object_detail,
                    'type_source': type_source,
                    'is_lambda': is_lambda
                }
                errors.append(error_info)
        
        if errors:
            error_msg = _create_optimized_error_message(errors, file_path, error_line, context)
            raise ValidationError(error_msg)

    def _validate_return_type(func, result, is_lambda):
        """Common return type validation logic for both sync and async functions."""
        sig = inspect.signature(func)
        
        if sig.return_annotation != inspect.Signature.empty:
            expected_return_type = sig.return_annotation
            if not _validate_complex_types(result, (expected_return_type,)):
                frame = sys._getframe(2)  # Go up 2 frames to get the actual caller
                error_line = frame.f_lineno
                file_path = frame.f_code.co_filename
                
                if is_lambda:
                    context = f"Lambda function: {func.__name__}"
                else:
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
                if is_lambda:
                    error_msg += f"⚠️  Note: Lambda functions have limited debugging info\n"
                error_msg += f"{'='*70}"
                raise ValidationError(error_msg)
        elif is_lambda and validate_return:
            # For lambdas without return annotation, we can't validate return type
            print(f"Warning: Lambda function has no return type annotation. Cannot validate return type.")
    
    return decorator

def create_validator(custom_types: Dict[str, Any], **kwargs):
    """
    Creates a custom validator with specific types.
    Works with both synchronous and asynchronous functions, including lambdas.
    Args:
        custom_types: Dictionary with types to validate
        **kwargs: Additional arguments passed to validate_data
    Returns:
        Configured decorator
    """
    return validate_data(custom_types=custom_types, **kwargs)

def create_lambda_validator(param_types: Dict[str, Any], return_type: Any = None, **kwargs):
    """
    Creates a validator specifically designed for lambda functions.
    
    Args:
        param_types: Dictionary mapping parameter names to expected types
        return_type: Expected return type (optional)
        **kwargs: Additional arguments passed to validate_data
    
    Returns:
        Configured decorator for lambda functions
    
    Example:
        validator = create_lambda_validator({'x': int, 'y': int}, return_type=int)
        add = validator(lambda x, y: x + y)
    """
    decorator_kwargs = {
        'custom_types': param_types,
        'strict': False,  # Lambda functions don't have type hints
        'validate_return': return_type is not None,
        **kwargs
    }
    
    def lambda_decorator(func):
        if return_type is not None:
            # Add return type annotation manually for validation
            func.__annotations__ = getattr(func, '__annotations__', {})
            func.__annotations__['return'] = return_type
        
        return validate_data(**decorator_kwargs)(func)
    
    return lambda_decorator

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
        
        function_type = "Lambda function" if func_name == '<lambda>' else "Function"
        
        error_msg = f"\n{'='*70}\n"
        error_msg += f"DECORATOR CONFIGURATION ERROR\n"
        error_msg += f"{'='*70}\n"
        error_msg += f"{function_type}: {func_name}()\n"
        error_msg += f"Non-existent parameters in override: {non_existent_parameters_sorted}\n"
        error_msg += f"Available parameters in function: {available_parameters}\n"
        error_msg += f"{'='*70}\n"
        error_msg += f"Parameters specified in @validate_data() decorator must\n"
        error_msg += f"correspond exactly with the function parameters.\n"
        if func_name == '<lambda>':
            error_msg += f"For lambda functions, use parameter names like 'x', 'y', etc.\n"
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
    
    # Add lambda-specific warning if any errors are from lambda functions
    if any(error.get('is_lambda', False) for error in errors):
        error_msg += f"⚠️  Note: Lambda functions have limited debugging capabilities\n"
    
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
