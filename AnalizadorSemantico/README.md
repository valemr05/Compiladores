# Analizador Semántico B-Minor

Compilador de B-Minor en Python — fase de análisis semántico.

## Cómo ejecutar el analizador semántico

```bash
python3 main.py checker typechecker/good0.bminor
python3 main.py checker typechecker/bad0.bminor
```

También se acepta la forma corta:

```bash
python3 main.py typechecker/good0.bminor
```

**Salida en caso exitoso:**
```
semantic check: success
```

**Salida en caso de error:**
```
error:3: no se puede inicializar 'a' de tipo integer con un valor de tipo float
semantic check: failed
```

---

## Estructura del proyecto

```
Analizador semantico/
├── lexer.py        # Analizador léxico (sly)
├── parser.py       # Analizador sintáctico (sly) → produce AST
├── model.py        # Nodos del AST
├── errors.py       # Módulo de reporte de errores léxicos/sintácticos
├── symtab.py       # Tabla de símbolos (ChainMap)
├── checker.py      # Analizador semántico (Visitor con multimethod)
├── typesys.py      # Sistema de tipos y tablas de operadores
├── main.py         # Punto de entrada
└── typechecker/    # Archivos de prueba (.bminor)
    ├── good0.bminor … good9.bminor
    └── bad0.bminor  … bad9.bminor
```

---

## Tabla de símbolos (`symtab.py`)

La tabla de símbolos está implementada con **`ChainMap`** de Python, lo que permite:

- **Crear un alcance nuevo** (`Symtab(name, parent=scope_padre)`)
- **Insertar símbolos** en el alcance actual (`add(name, symbol)`)
- **Buscar con alcance léxico** (`get(name)`) — recorre la cadena de ChainMaps automáticamente
- **Detectar redeclaraciones** — lanza `SymbolDefinedError` si el mismo nombre ya existe en el alcance actual
- **Detectar conflictos de tipo** — lanza `SymbolConflictError` si el símbolo ya existe con tipo distinto
- **Depurar** — `Symtab.print()` muestra el árbol completo de alcances con `rich`

Cada símbolo es un `Symbol(name, kind, type, node, mutable)` con campos:

| Campo      | Descripción                              |
|------------|------------------------------------------|
| `name`     | Nombre del identificador                 |
| `kind`     | `'var'`, `'const'`, `'param'`, `'func'` |
| `type`     | Tipo semántico (string o `FunctionInfo`) |
| `node`     | Nodo del AST asociado                    |
| `mutable`  | `False` para constantes                  |

---

## Visitor con `multimethod` (`checker.py`)

El análisis semántico usa el **patrón Visitor** implementado con `multimethod`:

```python
from multimethod import multimeta

class Visitor(metaclass=multimeta):
    pass

class Checker(Visitor):
    def visit(self, n: Program):   ...
    def visit(self, n: VarDecl):   ...
    def visit(self, n: BinOp):     ...
    # ... un método visit() por cada nodo del AST
```

`multimeta` resuelve automáticamente el despacho basado en el tipo del argumento, evitando `isinstance` manuales y haciendo el código extensible.

---

## Sistema de tipos (`typesys.py`)

Tipos primitivos soportados:

| Tipo      | Ejemplo B-Minor |
|-----------|-----------------|
| `integer` | `42`, `-1`      |
| `float`   | `3.14`          |
| `boolean` | `true`, `false` |
| `char`    | `'a'`           |
| `string`  | `"hello"`       |
| `void`    | (retorno vacío) |

También se soportan **arreglos** (`array[]T`) y **funciones** con su firma completa.

### Tabla de operadores binarios

| Operador        | Tipos permitidos       | Tipo resultado |
|-----------------|------------------------|----------------|
| `+`, `-`, `*`   | `integer, integer`     | `integer`      |
| `/`, `%`        | `integer, integer`     | `integer`      |
| `+`, `-`, `*`   | `float, float`         | `float`        |
| `/`, `%`        | `float, float`         | `float`        |
| `<`, `<=`, `>`, `>=` | `integer, integer` | `boolean`    |
| `<`, `<=`, `>`, `>=` | `float, float`     | `boolean`    |
| `==`, `!=`      | tipos compatibles      | `boolean`      |
| `&&`, `\|\|`    | `boolean, boolean`     | `boolean`      |
| `+`             | `string, string`       | `string`       |

### Operadores unarios

| Operador | Tipo operando | Tipo resultado |
|----------|--------------|----------------|
| `-`, `+` | `integer`    | `integer`      |
| `-`, `+` | `float`      | `float`        |
| `!`      | `boolean`    | `boolean`      |
| `++`, `--` | `integer` o `float` | mismo tipo |

---

## Chequeos semánticos implementados

| Nº | Verificación                                               |
|----|------------------------------------------------------------|
| 1  | Uso de variable/función no declarada                       |
| 2  | Redeclaración en el mismo alcance                          |
| 3  | Inicialización con tipo incompatible (`x: integer = 3.14`) |
| 4  | Asignación incompatible (`x = true` cuando `x: integer`)  |
| 5  | Asignación a constante                                     |
| 6  | Operadores binarios con tipos inválidos                    |
| 7  | Operadores unarios con tipos inválidos                     |
| 8  | Condición de `if`, `while`, `for` debe ser `boolean`       |
| 9  | Índice de arreglo debe ser `integer`                       |
| 10 | Acceso a índice sobre variable que no es arreglo           |
| 11 | Llamada a función con número incorrecto de argumentos      |
| 12 | Llamada a función con tipos de argumentos incorrectos      |
| 13 | `return` con tipo incompatible al declarado                |
| 14 | `return` vacío en función no-`void`                        |
| 15 | `return` con valor en función `void`                       |
| 16 | `break` y `continue` fuera de un ciclo                     |
| 17 | Función sin `return` garantizado (cuando no es `void`)     |
| 18 | Tamaño de arreglo debe ser `integer`                       |
| 19 | Cantidad de elementos inicializadores distinta del tamaño  |
| 20 | Elementos del arreglo con tipo incompatible al base        |
| 21 | Llamada a algo que no es función                           |
| 22 | Alcances léxicos: bloques `{}`, funciones, parámetros, `for` |
| 23 | Sombreado de variables en alcances internos (permitido)    |

---

## Aspectos pendientes

- Verificación exhaustiva de que **toda ruta** de ejecución de una función retorna (actualmente solo se verifica la ruta más externa).
- Soporte de conversión implícita (actualmente no existe — lenguaje fuertemente tipado sin coerción).
- Arreglos multidimensionales: el tipo `array[]array[]T` es soportado a nivel de tabla de símbolos, pero la verificación de acceso multinivel no está completamente implementada.

---

## Dependencias

```
pip install multimethod rich sly
```
