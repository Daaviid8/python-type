# Python-Type Validation Library

Una biblioteca completa de validación de tipos para Python que proporciona herramientas avanzadas para validar tipos de datos de forma eficiente y con mensajes de error detallados. (Valida tipos de instancias existentes y crea instancias tipadas)

## Características Principales

- 🚀 **Validación ultra-rápida** con cache optimizado
- 📦 **Procesamiento en batch** con paralelización automática
- 🔧 **Conversión automática** de tipos
- 📊 **Validación de esquemas** para diccionarios
- 🎯 **Decoradores de validación** para funciones síncronas y asíncronas
- 🏗️ **Clases Strict** al estilo TypeScript
- 🔄 **Soporte para dataclasses** con validación automática
- 📝 **Mensajes de error detallados** con información de debugging

## Instalación

```python
# Simplemente copia el código en tu proyecto
from python_type import *
```

## Ejemplos de Uso

### 1. Validación Básica de Tipos

```python
from python_type import check_type

# Validación simple
result = check_type(42, int)  # Retorna 42
result = check_type("hello", str)  # Retorna "hello"

# Conversión automática
result = check_type("42", int)  # Convierte y retorna 42
result = check_type([1, 2, 3], tuple)  # Convierte y retorna (1, 2, 3)
```

### 2. Validación de Tipos Genéricos

```python
from typing import List, Dict, Union

# Listas tipadas
numbers = check_type([1, 2, 3], List[int])
mixed_list = check_type(["1", "2", "3"], List[int])  # Convierte strings a ints

# Diccionarios tipados
data = check_type({"a": 1, "b": 2}, Dict[str, int])

# Tipos Union
value = check_type(42, Union[int, str])  # Acepta int o str
```

### 3. Validación en Batch (Alto Rendimiento)

```python
from python_type import batch_check_type

# Validar miles de elementos en paralelo
items = [1, 2, 3, "4", "5"] * 10000
result = batch_check_type(items, int, auto_convert=True)

print(f"Procesados: {result.total_processed}")
print(f"Exitosos: {len(result.successful)}")
print(f"Fallidos: {len(result.failed)}")
print(f"Tasa de éxito: {result.success_rate:.2%}")
```

### 4. Validación de Esquemas

```python
from python_type import batch_validate_schema

# Definir esquema
schema = {
    "name": str,
    "age": int,
    "email": str,
    "tags": List[str]
}

# Validar datos
data = [
    {"name": "Juan", "age": 25, "email": "juan@example.com", "tags": ["dev", "python"]},
    {"name": "María", "age": "30", "email": "maria@example.com", "tags": ["design"]},
]

result = batch_validate_schema(data, schema, auto_convert=True)
```

### 5. Decorador de Validación para Funciones

```python
from python_type import validate_data

@validate_data()
def calculate_total(items: List[int], tax_rate: float = 0.1) -> float:
    subtotal = sum(items)
    return subtotal * (1 + tax_rate)

# Uso normal
total = calculate_total([100, 200, 300], 0.15)

# Conversión automática
total = calculate_total(["100", "200", "300"], "0.15")  # Convierte strings
```

### 6. Validación de Funciones Asíncronas

```python
import asyncio
from python_type import validate_data

@validate_data()
async def fetch_user_data(user_id: int, include_profile: bool = True) -> Dict[str, Any]:
    # Simulación de operación asíncrona
    await asyncio.sleep(0.1)
    return {"id": user_id, "name": f"User_{user_id}", "profile": include_profile}

# Uso
async def main():
    data = await fetch_user_data("123", "true")  # Convierte automáticamente
    print(data)

asyncio.run(main())
```

### 7. Validación de Funciones Lambda

```python
from python_type import create_lambda_validator

# Crear validador para lambda
validator = create_lambda_validator({'x': int, 'y': int}, return_type=int)

# Aplicar a función lambda
add = validator(lambda x, y: x + y)

result = add("10", "20")  # Convierte strings a ints, retorna 30
```

### 8. Clases Strict (Estilo TypeScript)

```python
from type_validation import Strict

class User(Strict):
    name = str
    age = int
    email = str
    tags = List[str]

# Crear instancia
user = User(
    name="Juan Pérez",
    age=30,
    email="juan@example.com",
    tags=["developer", "python"]
)

# Serialización JSON
json_str = user.to_json()
print(json_str)

# Deserialización
user2 = User.from_json(json_str)

# Validación continua
user.age = "31"  # Se convierte automáticamente a int
```

### 9. Herencia en Clases Strict

```python
class Person(Strict):
    name = str
    age = int

class Employee(Person):
    employee_id = int
    department = str
    salary = float

# Hereda validación de Person
employee = Employee(
    name="Ana García",
    age=28,
    employee_id=12345,
    department="IT",
    salary=75000.0
)
```

### 10. Dataclasses con Validación

```python
from dataclasses import field
from python_type import validated_dataclass

@validated_dataclass
class Product:
    name: str
    price: float
    tags: List[str] = field(default_factory=list)
    in_stock: bool = True

# Validación automática
product = Product(
    name="Laptop",
    price="999.99",  # Se convierte a float
    tags=["electronics", "computers"]
)

# Validación en asignaciones posteriores
product.price = "1299.99"  # Se convierte automáticamente
```

### 11. Validación Personalizada con Tipos Custom

```python
from python_type import create_validator

# Crear validador personalizado
custom_validator = create_validator({
    'data': Dict[str, List[int]],
    'metadata': Dict[str, Any]
})

@custom_validator
def process_complex_data(data, metadata):
    return {"processed": True, "data": data, "meta": metadata}

# Uso con conversión automática
result = process_complex_data(
    data={"numbers": ["1", "2", "3"]},  # Convierte strings a ints
    metadata={"version": "1.0"}
)
```

## Manejo de Errores

La biblioteca proporciona mensajes de error detallados y útiles:

```python
try:
    result = check_type("not_a_number", int)
except TypeConversionError as e:
    print(e)  # Mensaje detallado sobre el error de conversión
```

### Ejemplo de Error Detallado

```
======================================================================
TYPE VALIDATION ERROR
======================================================================
📁 File: /path/to/your/file.py
📍 Line: 42
🔧 Function: calculate_total()
❌ Errors found: 1
======================================================================

💥 ERROR 1:
   Parameter: 'items' (position 1)
   ✅ Expected: List[int] (from type hint)
   ❌ Received: str
   📦 Value: str('not a list')
======================================================================
```

## Configuración de Paralelización

```python
# Control manual de paralelización
result = batch_check_type(
    items=large_dataset,
    target_type=MyClass,
    parallel=True,
    max_workers=8,
    chunk_size=1000
)
```

## Serialización y Persistencia

```python
# Guardar en archivo
user.save_to_file("user_data.json", pretty=True)

# Cargar desde archivo
user = User.load_from_file("user_data.json")

# JSON formateado
pretty_json = user.to_pretty_json()
```

## Características Avanzadas

### Cache de Conversión Ultra-Optimizado

La biblioteca utiliza un cache interno que acelera significativamente las conversiones de tipos comunes.

### Detección Automática de Paralelización

El sistema detecta automáticamente cuándo es beneficioso usar procesamiento paralelo basado en:
- Tamaño del dataset
- Complejidad de los tipos
- Recursos disponibles del sistema

### Soporte Completo para Typing

Compatible con todas las características del módulo `typing` de Python:
- `List[T]`, `Dict[K, V]`, `Set[T]`, `Tuple[T, ...]`
- `Union[T1, T2]`, `Optional[T]`
- Tipos anidados como `Dict[str, List[int]]`

## Requisitos

- Python 3.7+
- No dependencias externas (solo biblioteca estándar)

## Rendimiento

La biblioteca está optimizada para alto rendimiento:
- Validación secuencial: ~1M operaciones/segundo
- Validación en batch: ~10M operaciones/segundo (con paralelización)
- Cache de conversiones para tipos comunes
- Procesamiento paralelo automático para datasets grandes

## Casos de Uso Recomendados

- **APIs REST**: Validación de datos de entrada
- **Procesamiento de datos**: Validación de datasets grandes
- **Microservicios**: Validación de mensajes entre servicios
- **ETL Pipelines**: Validación de datos durante transformaciones
- **Configuración de aplicaciones**: Validación de archivos de configuración

## Contribución

Esta biblioteca está diseñada para ser extensible y fácil de modificar. Los puntos principales de extensión son:

1. **Conversores personalizados**: Agregar al `_ULTRA_CONVERSION_CACHE`
2. **Tipos complejos**: Extender `_validate_complex_types`
3. **Mensajes de error**: Personalizar `_create_optimized_error_message`

## Licencia

MIT License
