# Guía de Usuario - Sistema de Validación de Tipos

## Índice
1. [Introducción](#introducción)
2. [Conversión de Tipos](#conversión-de-tipos)
3. [Clases Strict](#clases-strict)
4. [Dataclasses Validados](#dataclasses-validados)
5. [Validación de Funciones](#validación-de-funciones)
6. [Manejo de Errores](#manejo-de-errores)
7. [Ejemplos Avanzados](#ejemplos-avanzados)

## Introducción

Este sistema proporciona herramientas para validación automática de tipos en Python, similar a TypeScript. Incluye:

- **Conversión automática de tipos**: Convierte datos entre tipos compatibles
- **Clases Strict**: Validación de tipos al estilo TypeScript
- **Dataclasses validados**: Validación automática en dataclasses
- **Decoradores de función**: Validación de parámetros y retorno

## Conversión de Tipos

### Función `convert()`

Convierte objetos entre tipos de forma inteligente:

```python
from typing import List, Dict

# Conversión básica
result = convert([1, 2, 3], tuple)  # (1, 2, 3)
result = convert("hello", list)     # ['hello']

# Conversión a diccionario
pairs = [('a', 1), ('b', 2)]
result = convert(pairs, dict)       # {'a': 1, 'b': 2}

# Desde lista plana
flat_list = ['name', 'Juan', 'age', 30]
result = convert(flat_list, dict)   # {'name': 'Juan', 'age': 30}
```

### Función `check_type()`

Valida y convierte tipos, incluyendo tipos genéricos:

```python
from typing import List, Dict, Union

# Validación básica
result = check_type([1, 2, 3], list)              # [1, 2, 3]
result = check_type("hello", str)                 # "hello"

# Tipos genéricos
result = check_type([1, 2, 3], List[int])         # [1, 2, 3]
result = check_type({"a": 1}, Dict[str, int])     # {"a": 1}

# Conversión automática
result = check_type(5, List[int])                 # [5]
result = check_type([1, 2], tuple)               # (1, 2)

# Tipos Union
result = check_type(42, Union[int, str])          # 42
result = check_type("hello", Union[int, str])     # "hello"
```

### Funciones de Conveniencia

```python
# Convertir a lista tipada
numbers = to_list_of([1, 2, 3], int)             # List[int]
words = to_list_of("hello", str)                 # ['hello']

# Convertir a diccionario tipado
data = to_dict_of([('a', 1), ('b', 2)], str, int)  # Dict[str, int]

# Convertir a conjunto tipado
unique_nums = to_set_of([1, 2, 2, 3], int)       # {1, 2, 3}
```

## Clases Strict

### Definición Básica

```python
class Person(Strict):
    name = str
    age = int
    email = str

# Uso correcto
person = Person(name="Juan", age=30, email="juan@email.com")
print(person)  # Person(name='Juan', age=30, email='juan@email.com')

# Error: tipo incorrecto
try:
    person = Person(name="Juan", age="treinta", email="juan@email.com")
except TypeError as e:
    print(e)
    # Class:     Person
    # Attribute: age
    # File:      /path/to/file.py
    # Line:      15
    # Expected:  int
    # Received:  str
    # Value:     'treinta'
```

### Herencia

```python
class Employee(Person):
    salary = float
    department = str

# Hereda validación de Person
employee = Employee(
    name="Ana",
    age=25,
    email="ana@company.com",
    salary=50000.0,
    department="IT"
)

# Validación en asignación posterior
employee.salary = 55000.0  # OK
employee.salary = "mucho"  # TypeError
```

### Validación Continua

```python
class Product(Strict):
    name = str
    price = float
    in_stock = bool

product = Product(name="Laptop", price=999.99, in_stock=True)

# Validación en tiempo de ejecución
product.price = 1299.99  # OK
product.price = "caro"   # TypeError con detalles
```

## Dataclasses Validados

### Decorador `@validated_dataclass`

```python
from dataclasses import field
from typing import List, Optional

@validated_dataclass
class User:
    name: str
    age: int
    emails: List[str] = field(default_factory=list)
    active: bool = True
    bio: Optional[str] = None

# Uso correcto
user = User(name="Carlos", age=28)
user.emails.append("carlos@email.com")  # OK

# Error en creación
try:
    user = User(name="Carlos", age="veintiocho")
except TypeError as e:
    print(e)
    # Dataclass: User
    # Field:     age
    # File:      /path/to/file.py
    # Line:      25
    # Expected:  int
    # Received:  str
    # Value:     'veintiocho'
```

### Mixin Manual

```python
from dataclasses import dataclass

@dataclass
class Address(DataclassValidationMixin):
    street: str
    city: str
    postal_code: int
    country: str = "España"

address = Address(
    street="Calle Mayor 123",
    city="Madrid",
    postal_code=28001
)

# Validación en asignación
address.postal_code = 28002  # OK
address.postal_code = "28002"  # TypeError
```

## Validación de Funciones

### Decorador Básico

```python
@validate_data()
def calculate_area(width: int, height: int) -> int:
    return width * height

# Uso correcto
result = calculate_area(5, 3)  # 15

# Error en parámetros
try:
    result = calculate_area("5", 3)
except ValidationError as e:
    print(e)
    # ======================================================================
    # TYPE VALIDATION ERROR
    # ======================================================================
    # 📁 File: /path/to/file.py
    # 📍 Line: 45
    # 🔧 Function: calculate_area()
    # ❌ Errors found: 1
    # ======================================================================
    # 
    # 💥 ERROR 1:
    #    Parameter: 'width' (position 1)
    #    ✅ Expected: int (from type hint)
    #    ❌ Received: str
    #    📦 Value: str('5')
```

### Tipos Personalizados

```python
@validate_data(custom_types={'user_id': int, 'data': dict})
def process_user(user_id, data, active=True):
    return f"Processing user {user_id} with {len(data)} items"

# Uso correcto
result = process_user(123, {"name": "Juan", "age": 30})

# Error
try:
    result = process_user("123", {"name": "Juan"})
except ValidationError as e:
    print(e)
```

### Override de Tipos

```python
@validate_data(user_id=int, data=dict, active=bool)
def update_user(user_id, data, active):
    return f"User {user_id} updated"

# Los tipos override tienen prioridad sobre type hints
```

### Funciones Asíncronas

```python
from python_type import validate_data, ValidationError
import asyncio

@validate_data()
async def fetch_user(user_id: int) -> dict:
    # Simular búsqueda async
    await asyncio.sleep(0.1)
    return {"id": user_id, "name": "Usuario"}

async def main():
    # Uso correcto
    try:
        user = await fetch_user(123)
        print("Usuario encontrado:", user)
    except ValidationError as e:
        print("Error de validación (123):", e)

    # Error en parámetros
    try:
        user = await fetch_user("123")  # Provocará un error de validación
        print("Usuario encontrado:", user)
    except ValidationError as e:
        print("Error de validación (\"123\"):", e)

if __name__ == "__main__":
    asyncio.run(main())
```

### Validación de Métodos

```python
class UserService:
    @validate_data()
    def create_user(self, name: str, age: int) -> dict:
        return {"name": name, "age": age}
    
    @validate_data(strict=False, user_id=int)
    def get_user(self, user_id):
        return {"id": user_id}

service = UserService()
user = service.create_user("Ana", 25)  # OK
user = service.create_user("Ana", "25")  # ValidationError
```

## Manejo de Errores

### Tipos de Excepciones

```python
# TypeConversionError: Para errores de conversión
try:
    result = check_type("hello", int)
except TypeConversionError as e:
    print(f"Error de conversión: {e}")

# ValidationError: Para errores de validación de función
try:
    @validate_data()
    def test(x: int):
        pass
    
    test("not_int")
except ValidationError as e:
    print(f"Error de validación: {e}")

# TypeError: Para errores en clases Strict
try:
    class Test(Strict):
        value = int
    
    obj = Test(value="not_int")
except TypeError as e:
    print(f"Error de tipo: {e}")
```

### Captura Específica

```python
def safe_convert(value, target_type):
    try:
        return check_type(value, target_type)
    except TypeConversionError as e:
        print(f"No se pudo convertir {value} a {target_type}: {e}")
        return None
```

## Ejemplos Avanzados

### Sistema de Configuración

```python
from typing import List, Dict, Optional

@validated_dataclass
class DatabaseConfig:
    host: str
    port: int
    database: str
    username: str
    password: str
    ssl: bool = False
    timeout: Optional[int] = None

@validated_dataclass
class AppConfig:
    app_name: str
    debug: bool
    database: DatabaseConfig
    allowed_hosts: List[str] = field(default_factory=list)
    features: Dict[str, bool] = field(default_factory=dict)

# Configuración completa con validación
config = AppConfig(
    app_name="MyApp",
    debug=True,
    database=DatabaseConfig(
        host="localhost",
        port=5432,
        database="mydb",
        username="user",
        password="pass"
    ),
    allowed_hosts=["localhost", "127.0.0.1"],
    features={"feature1": True, "feature2": False}
)
```

### API con Validación

```python
class APIResponse(Strict):
    status_code = int
    data = dict
    message = str

class UserAPI:
    @validate_data()
    def get_user(self, user_id: int) -> APIResponse:
        if user_id <= 0:
            return APIResponse(
                status_code=400,
                data={},
                message="ID de usuario inválido"
            )
        
        return APIResponse(
            status_code=200,
            data={"id": user_id, "name": "Usuario"},
            message="Success"
        )
    
    @validate_data()
    def create_user(self, name: str, age: int, email: str) -> APIResponse:
        user_data = {
            "name": name,
            "age": age,
            "email": email
        }
        
        return APIResponse(
            status_code=201,
            data=user_data,
            message="Usuario creado"
        )

# Uso
api = UserAPI()
response = api.get_user(123)
print(response.data)
```

### Validador Personalizado

```python
# Crear validador específico para ciertos tipos
email_validator = create_validator(
    custom_types={
        'email': str,
        'age': int,
        'active': bool
    },
    strict=False
)

@email_validator
def register_user(email, age, active):
    return f"User registered: {email}, age {age}, active {active}"

# Uso
result = register_user("test@email.com", 25, True)
```

### Procesamiento de Datos

```python
@validate_data()
def process_data(data: List[Dict[str, int]]) -> Dict[str, int]:
    total = {}
    for item in data:
        for key, value in item.items():
            total[key] = total.get(key, 0) + value
    return total

# Datos de entrada validados
data = [
    {"ventas": 100, "gastos": 50},
    {"ventas": 200, "gastos": 75},
    {"ventas": 150, "gastos": 60}
]

result = process_data(data)
print(result)  # {'ventas': 450, 'gastos': 185}
```

## Configuración Avanzada

### Modo No Estricto

```python
@validate_data(strict=False, user_id=int)
def flexible_function(user_id, other_param):
    # Solo valida user_id, ignora other_param
    return f"User: {user_id}"
```

### Validación Solo de Retorno

```python
@validate_data(strict=False, validate_return=True)
def get_number() -> int:
    return 42  # Validará que retorne int
```

### Combinación de Estrategias

```python
@validate_data(
    strict=True,              # Validar type hints
    validate_return=True,     # Validar retorno
    custom_types={'special': str},  # Tipos personalizados
    user_id=int              # Override específico
)
def complex_function(user_id: str, special, name: str) -> Dict[str, str]:
    # user_id será validado como int (override)
    # special será validado como str (custom_types)
    # name será validado como str (type hint)
    return {"user_id": str(user_id), "special": special, "name": name}
```

Este sistema proporciona una validación de tipos robusta y flexible, manteniendo la simplicidad de uso mientras ofrece potentes capacidades de validación automática.
