import inspect
from typing import Any, Dict, Type, get_type_hints
from types import GenericAlias


class TypedError(Exception):
    """Excepción personalizada para errores de tipo"""
    def __init__(self, message: str, field: str, expected_type: str, received_type: str, location: str):
        self.field = field
        self.expected_type = expected_type
        self.received_type = received_type
        self.location = location
        super().__init__(message)


class TypedMeta(type):
    """Metaclase que gestiona la validación de tipos"""
    
    def __new__(mcs, name, bases, namespace, **kwargs):
        # Obtener anotaciones de tipo
        annotations = namespace.get('__annotations__', {})
        
        # Crear la clase
        cls = super().__new__(mcs, name, bases, namespace)
        
        # Almacenar información de tipos
        cls._typed_fields = annotations
        cls._typed_required = set(annotations.keys())
        
        return cls
    
    def __call__(cls, *args, **kwargs):
        """Crear instancia con validación de tipos"""
        instance = super().__call__()
        
        # Obtener el frame de llamada para mostrar ubicación del error
        frame = inspect.currentframe().f_back
        location = f"{frame.f_code.co_filename}:{frame.f_lineno}"
        
        # Procesar argumentos posicionales
        field_names = list(cls._typed_fields.keys())
        for i, arg in enumerate(args):
            if i < len(field_names):
                field_name = field_names[i]
                kwargs[field_name] = arg
        
        # Validar que se proporcionen todos los campos requeridos
        missing_fields = cls._typed_required - set(kwargs.keys())
        if missing_fields:
            raise TypedError(
                f"Campos requeridos faltantes: {', '.join(missing_fields)}",
                field=', '.join(missing_fields),
                expected_type="required",
                received_type="missing",
                location=location
            )
        
        # Validar tipos y asignar valores
        for field_name, value in kwargs.items():
            if field_name in cls._typed_fields:
                expected_type = cls._typed_fields[field_name]
                cls._validate_and_set(instance, field_name, value, expected_type, location)
        
        return instance
    
    def _validate_and_set(cls, instance, field_name, value, expected_type, location):
        """Validar tipo y asignar valor"""
        if not cls._is_valid_type(value, expected_type):
            raise TypedError(
                f"Error de tipo en '{field_name}' en {location}:\n"
                f"  Campo: {field_name}\n"
                f"  Tipo esperado: {cls._format_type(expected_type)}\n"
                f"  Tipo obtenido: {type(value).__name__}\n"
                f"  Valor: {repr(value)}",
                field=field_name,
                expected_type=cls._format_type(expected_type),
                received_type=type(value).__name__,
                location=location
            )
        
        # Asignar valor de forma inmutable
        object.__setattr__(instance, field_name, value)
    
    def _is_valid_type(cls, value, expected_type):
        """Verificar si el valor coincide con el tipo esperado"""
        # Manejar tipos básicos
        if expected_type in (int, str, float, bool, list, dict, tuple, set):
            return isinstance(value, expected_type)
        
        # Manejar tipos genéricos (List, Dict, etc.)
        if hasattr(expected_type, '__origin__'):
            origin = expected_type.__origin__
            if origin is list:
                if not isinstance(value, list):
                    return False
                if hasattr(expected_type, '__args__') and expected_type.__args__:
                    item_type = expected_type.__args__[0]
                    return all(cls._is_valid_type(item, item_type) for item in value)
                return True
            elif origin is dict:
                if not isinstance(value, dict):
                    return False
                if hasattr(expected_type, '__args__') and len(expected_type.__args__) == 2:
                    key_type, value_type = expected_type.__args__
                    return all(
                        cls._is_valid_type(k, key_type) and cls._is_valid_type(v, value_type)
                        for k, v in value.items()
                    )
                return True
            elif origin is tuple:
                if not isinstance(value, tuple):
                    return False
                if hasattr(expected_type, '__args__') and expected_type.__args__:
                    if len(expected_type.__args__) == len(value):
                        return all(
                            cls._is_valid_type(v, t) 
                            for v, t in zip(value, expected_type.__args__)
                        )
                return True
        
        # Manejar clases personalizadas
        if inspect.isclass(expected_type):
            return isinstance(value, expected_type)
        
        return False
    
    def _format_type(cls, type_hint):
        """Formatear el tipo para mostrar en errores"""
        if hasattr(type_hint, '__name__'):
            return type_hint.__name__
        return str(type_hint)


class typed(metaclass=TypedMeta):
    """Clase base para crear interfaces tipadas"""
    
    def __new__(cls, *args, **kwargs):
        if cls is typed:
            raise TypeError("No se puede instanciar 'typed' directamente")
        return super().__new__(cls)
    
    def __setattr__(self, name, value):
        """Prevenir modificación después de la inicialización (inmutabilidad)"""
        if hasattr(self, '_initialized') and self._initialized:
            raise AttributeError(f"No se puede modificar '{name}': los objetos tipados son inmutables")
        super().__setattr__(name, value)
    
    def __init__(self):
        """Marcar como inicializado para inmutabilidad"""
        object.__setattr__(self, '_initialized', True)
    
    def __repr__(self):
        """Representación legible del objeto"""
        fields = []
        for field_name in self._typed_fields:
            if hasattr(self, field_name):
                value = getattr(self, field_name)
                fields.append(f"{field_name}={repr(value)}")
        return f"{self.__class__.__name__}({', '.join(fields)})"
    
    def __eq__(self, other):
        """Comparación de igualdad"""
        if not isinstance(other, self.__class__):
            return False
        return all(
            getattr(self, field, None) == getattr(other, field, None)
            for field in self._typed_fields
        )
    
    def __hash__(self):
        """Hash para usar en sets y como keys de dict"""
        return hash(tuple(
            getattr(self, field, None) for field in sorted(self._typed_fields.keys())
        ))


# Ejemplos de uso
if __name__ == "__main__":
    from typing import List, Dict
    
    # Ejemplo 1: Clase básica
    class Objeto(typed):
        id: int
        name: str
        active: bool
    
    # Ejemplo 2: Clase con tipos complejos
    class Usuario(typed):
        id: int
        name: str
        tags: List[str]
        metadata: Dict[str, str]
    
    # Ejemplo 3: Clase con otros objetos tipados
    class Producto(typed):
        id: int
        name: str
        price: float
        owner: Usuario
    
    print("=== Ejemplos de uso correcto ===")
    
    # Crear objetos válidos
    obj1 = Objeto(1, "test", True)
    print(f"obj1: {obj1}")
    
    obj2 = Objeto(id=2, name="test2", active=False)
    print(f"obj2: {obj2}")
    
    user = Usuario(1, "Juan", ["admin", "user"], {"role": "admin"})
    print(f"user: {user}")
    
    product = Producto(1, "Laptop", 999.99, user)
    print(f"product: {product}")
    
    print("\n=== Ejemplos de errores ===")
    
    # Probar errores de tipo
    try:
        obj_bad = Objeto("string", "test", True)  # id debe ser int
    except TypedError as e:
        print(f"Error: {e}")
    
    try:
        user_bad = Usuario(1, "Juan", "should_be_list", {})  # tags debe ser List[str]
    except TypedError as e:
        print(f"Error: {e}")
    
    try:
        obj_missing = Objeto(1, "test")  # falta active
    except TypedError as e:
        print(f"Error: {e}")
    
    print("\n=== Prueba de inmutabilidad ===")
    try:
        obj1.id = 999  # Debería fallar
    except AttributeError as e:
        print(f"Error de inmutabilidad: {e}")
    
    print("\n=== Comparación y hash ===")
    obj3 = Objeto(1, "test", True)
    print(f"obj1 == obj3: {obj1 == obj3}")
    print(f"hash(obj1): {hash(obj1)}")
    print(f"obj1 in {{obj3}}: {obj1 in {obj3}}")
