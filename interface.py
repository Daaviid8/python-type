import inspect
import traceback
from typing import Any, Dict, Type, get_type_hints

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
        return (function_name in internal_functions or 
                'Strict' in str(frame.f_locals.get('self', '')))
    
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
