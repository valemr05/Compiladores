# 📘 Taller: Visualización del AST en B-Minor

**Curso:** Compiladores\
**Duración:** 2 sesiones (4--6 horas)

------------------------------------------------------------------------

## 🎯 Objetivo

Construir una herramienta que:

1.  Reciba un programa en B-Minor\
2.  Realice el análisis sintáctico\
3.  Si no hay errores:
    -   Genere el AST\
    -   Lo visualice con:
        -   Rich Tree\
        -   Graphviz

------------------------------------------------------------------------

## 🧠 Conceptos clave

-   AST\
-   Recorridos DFS\
-   Visualización de estructuras

------------------------------------------------------------------------

## 🧩 Parte 1 -- Requisitos

``` bash
pip install rich graphviz
```

Debe contar con:

-   lexer.py\
-   parse.py\
-   model.py
-   error.py

------------------------------------------------------------------------

## 🧩 Parte 2 -- Diseño del AST

Ejemplo:

``` python
from dataclasses import dataclass

@dataclass
class BinaryOp:
    op: str
    left: object
    right: object
```

------------------------------------------------------------------------

## 🌳 Parte 3 -- Rich Tree

Ejemplo esperado:

    Program
    ├── Function
    │   └── Return
    │       └── BinaryOp(+)

Implementar:

``` python
from rich.tree import Tree

def build_rich_tree(node):
    label = type(node).__name__
    tree = Tree(label)

    for field, value in vars(node).items():
        if isinstance(value, list):
            for item in value:
                tree.add(build_rich_tree(item))
        elif hasattr(value, "__dict__"):
            tree.add(build_rich_tree(value))
        else:
            tree.add(f"{field}: {value}")

    return tree
```

------------------------------------------------------------------------

## 🧠 Parte 4 -- Graphviz

Implementar:

``` python
from graphviz import Digraph
import uuid

def build_graphviz(node, dot, parent_id=None):
    node_id = str(uuid.uuid4())
    label = type(node).__name__

    dot.node(node_id, label)

    if parent_id:
        dot.edge(parent_id, node_id)

    for field, value in vars(node).items():
        if isinstance(value, list):
            for item in value:
                build_graphviz(item, dot, node_id)
        elif hasattr(value, "__dict__"):
            build_graphviz(value, dot, node_id)

    return dot
```

------------------------------------------------------------------------

## 🔄 Parte 5 -- Integración

``` python
def main():
    source = open("test.bminor").read()
    ast = parse(source)

    if ast:
        print(build_rich_tree(ast))

        dot = Digraph()
        build_graphviz(ast, dot)
        dot.render("ast", format="png")
```

------------------------------------------------------------------------

## 🧪 Parte 6 -- Pruebas

-   Código válido → muestra AST\
-   Error → mensaje

------------------------------------------------------------------------

## 🎯 Entregables

-   Código fuente\
-   Archivo .bminor\
-   Imagen del AST

------------------------------------------------------------------------

## 📊 Rúbrica

  Criterio       Peso
  -------------- ------
  AST correcto   30%
  Rich           20%
  Graphviz       20%
  Integración    15%
  Código         10%
  Pruebas        5%

------------------------------------------------------------------------

## 💡 Preguntas

1.  ¿Qué elimina el AST del parse tree?\
2.  ¿Ventajas de Graphviz vs Rich?\
3.  Uso del AST en semántica
