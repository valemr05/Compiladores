# Taller: Optimización de IR en B-Minor — niveles `-O1` y `-O2`

## 1. Contexto

En esta actividad los estudiantes implementarán dos niveles de optimización para la representación intermedia generada por `ircode.py`.

El generador produce una IR de tres direcciones con temporales tipo `R1`, `R2`, `R3`, etc., etiquetas tipo `Lthen1`, `Lend2`, y una estructura de programa basada en:

```python
@dataclass
class IRProgram:
    globals: list[Instruction]
    functions: list[IRFunction]

@dataclass
class IRFunction:
    name: str
    params: list[tuple[str, Type]]
    return_type: Type
    instructions: list[Instruction]
```

Cada instrucción se representa como una tupla de Python:

```python
("MOVI", 2, "R1")
("ADDI", "R1", "R2", "R3")
("STOREI", "R3", "x")
("CBRANCH", "R4", "Lthen1", "Lelse2")
("LABEL", "Lthen1")
("RET", "R5")
```

La meta del taller es construir un optimizador educativo, seguro y progresivo, activado desde línea de comandos con:

```bash
python iroptimizer.py programa.bminor -O1
python iroptimizer.py programa.bminor -O2
```

Si no se entrega opción de optimización, se debe asumir `-O0`, es decir, sin optimización.

---

## 2. Niveles esperados

| Nivel | Nombre sugerido | Objetivo |
|---|---|---|
| `-O0` | Sin optimización | Genera la IR tal como sale de `IRCodeGen`. |
| `-O1` | Optimización local simple | Aplica transformaciones seguras instrucción por instrucción o de ventana pequeña. |
| `-O2` | Optimización local con flujo de datos básico | Incluye `-O1` y agrega eliminación de temporales muertos y propagación local más cuidadosa. |

Regla importante:

> `-O2` debe incluir todas las optimizaciones de `-O1`.

---

# 3. Especificación de `-O1`

## 3.1. Objetivo de `-O1`

El nivel `-O1` debe realizar optimizaciones locales seguras sin construir CFG, sin dominadores y sin SSA formal.

Debe recorrer la lista de instrucciones de cada función y aplicar transformaciones como:

1. **Constant folding**
2. **Simplificación algebraica**
3. **Simplificación de comparaciones constantes**
4. **Simplificación de ramas condicionales constantes**
5. **Eliminación de código inalcanzable después de `BRANCH` o `RET`**
6. **Eliminación de saltos al `LABEL` inmediatamente siguiente**

---

## 3.2. Constant folding

Convierte operaciones con operandos constantes en una sola instrucción `MOV`.

### Ejemplo de entrada

```text
MOVI 2, R1
MOVI 3, R2
ADDI R1, R2, R3
PRINTI R3
```

### Salida esperada

```text
MOVI 2, R1
MOVI 3, R2
MOVI 5, R3
PRINTI R3
```

Operaciones mínimas que deben soportarse:

```text
ADDI, SUBI, MULI, DIVI
ADDF, SUBF, MULF, DIVF
AND, OR, XOR
CMPI, CMPF, CMPB
```

Para división entre cero, **no se debe optimizar**. La instrucción original debe conservarse.

---

## 3.3. Simplificación algebraica

Debe reconocer identidades simples:

| Entrada | Salida |
|---|---|
| `x + 0` | `x` |
| `0 + x` | `x` |
| `x - 0` | `x` |
| `x * 1` | `x` |
| `1 * x` | `x` |
| `x * 0` | `0` |
| `0 * x` | `0` |
| `x / 1` | `x` |

Como la IR base no tiene una instrucción `MOV` registro-a-registro, se recomienda aplicar estas reglas solo cuando el valor de `x` ya sea conocido como constante.

### Ejemplo

```text
MOVI 10, R1
MOVI 0, R2
ADDI R1, R2, R3
PRINTI R3
```

Puede optimizarse a:

```text
MOVI 10, R1
MOVI 0, R2
MOVI 10, R3
PRINTI R3
```

---

## 3.4. Comparaciones constantes

Si ambos operandos de una comparación son constantes, la comparación se reemplaza por `MOVI 1` o `MOVI 0`.

### Ejemplo

```text
MOVI 4, R1
MOVI 5, R2
CMPI <, R1, R2, R3
```

Resultado:

```text
MOVI 4, R1
MOVI 5, R2
MOVI 1, R3
```

---

## 3.5. Simplificación de ramas condicionales

Si la condición de `CBRANCH` es constante:

```text
CBRANCH R1, Ltrue, Lfalse
```

Y `R1` vale `1`, se reemplaza por:

```text
BRANCH Ltrue
```

Si `R1` vale `0`, se reemplaza por:

```text
BRANCH Lfalse
```

---

## 3.6. Código inalcanzable

Después de una instrucción incondicional:

```text
BRANCH L1
```

O después de:

```text
RET R1
```

Toda instrucción hasta el siguiente `LABEL` es inalcanzable y debe eliminarse.

### Ejemplo

```text
BRANCH L1
MOVI 99, R9
PRINTI R9
LABEL L1
MOVI 1, R1
```

Resultado:

```text
BRANCH L1
LABEL L1
MOVI 1, R1
```

---

## 3.7. Salto al siguiente label

Si existe:

```text
BRANCH L1
LABEL L1
```

El `BRANCH` se puede eliminar:

```text
LABEL L1
```

---

# 4. Especificación de `-O2`

## 4.1. Objetivo de `-O2`

El nivel `-O2` debe incluir todo `-O1` y agregar optimizaciones locales más fuertes.

Mínimo esperado:

1. Todo lo de `-O1`
2. Eliminación de definiciones de temporales no usados
3. Separación conceptual por bloques básicos
4. Manejo conservador de instrucciones con efectos laterales

---

## 4.2. Eliminación de temporales muertos

Una instrucción puede eliminarse si:

1. Define un temporal `Rk`
2. Ese temporal nunca se usa después
3. La instrucción no tiene efectos laterales

### Ejemplo

```text
MOVI 2, R1
MOVI 3, R2
ADDI R1, R2, R3
MOVI 99, R4
PRINTI R3
```

Resultado:

```text
MOVI 2, R1
MOVI 3, R2
ADDI R1, R2, R3
PRINTI R3
```

La instrucción `MOVI 99, R4` se elimina porque `R4` nunca se usa.

---

## 4.3. Instrucciones puras

Son candidatas a eliminación si su resultado no se usa:

```text
MOVI, MOVF, MOVB, ADDR
ADDI, SUBI, MULI, DIVI
ADDF, SUBF, MULF, DIVF
AND, OR, XOR
CMPI, CMPF, CMPB
PHI
LOADI, LOADF, LOADB, LOADS
```

Aunque `LOAD` lee memoria, para este taller se puede tratar como pura si solo produce un temporal y no modifica el estado.

---

## 4.4. Instrucciones que NO se deben eliminar aunque parezcan inútiles

No se deben eliminar automáticamente:

```text
STOREI, STOREF, STOREB, STORES
PRINTI, PRINTF, PRINTB, PRINTS
CALL
BRANCH
CBRANCH
RET
LABEL
DATAS
```

Razón: pueden modificar memoria, producir salida, alterar el flujo de control o representar datos globales.

---

## 4.5. Análisis hacia atrás

Para eliminar temporales muertos se recomienda recorrer las instrucciones desde el final hacia el inicio.

Idea general:

```python
used = set()
result = []

for inst in reversed(instructions):
    dst = defined_temp(inst)
    args = used_temps(inst)

    if dst is not None and dst not in used and is_pure_definition(inst):
        continue

    if dst is not None:
        used.discard(dst)

    used.update(args)
    result.append(inst)

result.reverse()
```

---

# 5. Código de inicio para los estudiantes

El siguiente archivo puede entregarse como `iroptimizer_starter.py`.

Los estudiantes deben completar los métodos marcados con `TODO`.

```python
from __future__ import annotations

from typing import Any, Optional

from ircode import IRProgram, IRFunction, Instruction, IRCodeGen


class IROptimizer:
    def __init__(self, level: int = 0):
        self.level = level

    @classmethod
    def optimize(cls, program: IRProgram, level: int = 0) -> IRProgram:
        return cls(level).visit_program(program)

    def visit_program(self, program: IRProgram) -> IRProgram:
        if self.level <= 0:
            return program

        new_globals = list(program.globals)
        new_functions: list[IRFunction] = []

        for fn in program.functions:
            new_insts = self.optimize_instruction_list(fn.instructions)
            new_functions.append(
                IRFunction(
                    name=fn.name,
                    params=list(fn.params),
                    return_type=fn.return_type,
                    instructions=new_insts,
                )
            )

        return IRProgram(globals=new_globals, functions=new_functions)

    def optimize_instruction_list(self, instructions: list[Instruction]) -> list[Instruction]:
        insts = list(instructions)

        if self.level >= 1:
            insts = self.constant_fold_and_simplify(insts)
            insts = self.remove_unreachable(insts)
            insts = self.remove_branch_to_next_label(insts)

        if self.level >= 2:
            insts = self.remove_unused_temp_definitions(insts)

        return insts

    # -------------------------------------------------
    # Nivel O1
    # -------------------------------------------------

    def constant_fold_and_simplify(self, instructions: list[Instruction]) -> list[Instruction]:
        const: dict[str, Any] = {}
        out: list[Instruction] = []

        for inst in instructions:
            op = inst[0]

            if op in {"MOVI", "MOVF", "MOVB"} and len(inst) == 3:
                value, dst = inst[1], inst[2]
                const[dst] = value
                out.append(inst)
                continue

            if op in {"ADDI", "SUBI", "MULI", "DIVI", "ADDF", "SUBF", "MULF", "DIVF"} and len(inst) == 4:
                a, b, dst = inst[1], inst[2], inst[3]

                # TODO 1:
                # Si a y b son constantes, evaluar la operación.
                # Reemplazar por MOVI o MOVF.
                # No optimizar división por cero.

                # TODO 2:
                # Aplicar reglas algebraicas simples.

                const.pop(dst, None)
                out.append(inst)
                continue

            if op in {"CMPI", "CMPF", "CMPB"} and len(inst) == 5:
                cmp_oper, a, b, dst = inst[1], inst[2], inst[3], inst[4]

                # TODO 3:
                # Si a y b son constantes, reemplazar por MOVI 1 o MOVI 0.

                const.pop(dst, None)
                out.append(inst)
                continue

            if op == "CBRANCH" and len(inst) == 4:
                test, true_label, false_label = inst[1], inst[2], inst[3]

                # TODO 4:
                # Si test es constante, reemplazar por BRANCH true_label o false_label.

                out.append(inst)
                continue

            # Instrucciones conservadoras.
            if len(inst) >= 2 and isinstance(inst[-1], str) and inst[-1].startswith("R"):
                const.pop(inst[-1], None)

            out.append(inst)

        return out

    def remove_unreachable(self, instructions: list[Instruction]) -> list[Instruction]:
        out: list[Instruction] = []
        unreachable = False

        for inst in instructions:
            op = inst[0]

            # TODO 5:
            # Si llega un LABEL, termina la zona inalcanzable.
            # Si estamos en zona inalcanzable, descartar la instrucción.
            # Si se ve BRANCH o RET, marcar unreachable = True.

            out.append(inst)

        return out

    def remove_branch_to_next_label(self, instructions: list[Instruction]) -> list[Instruction]:
        out: list[Instruction] = []
        i = 0

        while i < len(instructions):
            inst = instructions[i]

            # TODO 6:
            # Si inst es BRANCH Lx y la siguiente instrucción es LABEL Lx,
            # eliminar el BRANCH.

            out.append(inst)
            i += 1

        return out

    # -------------------------------------------------
    # Nivel O2
    # -------------------------------------------------

    def remove_unused_temp_definitions(self, instructions: list[Instruction]) -> list[Instruction]:
        used: set[str] = set()
        result_reversed: list[Instruction] = []

        for inst in reversed(instructions):
            dst = self.defined_temp(inst)
            args = self.used_temps(inst)

            # TODO 7:
            # Si dst no es None, dst no está en used y la instrucción es pura,
            # eliminarla.

            # TODO 8:
            # Actualizar used correctamente.

            result_reversed.append(inst)

        return list(reversed(result_reversed))

    def defined_temp(self, inst: Instruction) -> Optional[str]:
        op = inst[0]

        if op in {"MOVI", "MOVF", "MOVB", "ADDR"} and len(inst) == 3:
            return inst[2] if isinstance(inst[2], str) and inst[2].startswith("R") else None

        if op in {"ADDI", "SUBI", "MULI", "DIVI", "ADDF", "SUBF", "MULF", "DIVF", "AND", "OR", "XOR"} and len(inst) == 4:
            return inst[3] if isinstance(inst[3], str) and inst[3].startswith("R") else None

        if op in {"CMPI", "CMPF", "CMPB"} and len(inst) == 5:
            return inst[4] if isinstance(inst[4], str) and inst[4].startswith("R") else None

        if op.startswith("LOAD") and len(inst) == 3:
            return inst[2] if isinstance(inst[2], str) and inst[2].startswith("R") else None

        return None

    def used_temps(self, inst: Instruction) -> set[str]:
        op = inst[0]

        if op in {"MOVI", "MOVF", "MOVB", "LABEL", "BRANCH", "DATAS", "ADDR"}:
            return set()

        if op.startswith("STORE"):
            return self.temps_in(inst[1:2])

        if op.startswith("PRINT"):
            return self.temps_in(inst[1:])

        if op == "CBRANCH":
            return self.temps_in(inst[1:2])

        if op == "RET":
            return self.temps_in(inst[1:])

        if op in {"ADDI", "SUBI", "MULI", "DIVI", "ADDF", "SUBF", "MULF", "DIVF", "AND", "OR", "XOR"}:
            return self.temps_in(inst[1:3])

        if op in {"CMPI", "CMPF", "CMPB"}:
            return self.temps_in(inst[2:4])

        return self.temps_in(inst[1:])

    def temps_in(self, values) -> set[str]:
        return {x for x in values if isinstance(x, str) and x.startswith("R")}

    def is_pure_definition(self, inst: Instruction) -> bool:
        op = inst[0]
        return (
            op in {
                "MOVI", "MOVF", "MOVB", "ADDR",
                "ADDI", "SUBI", "MULI", "DIVI",
                "ADDF", "SUBF", "MULF", "DIVF",
                "AND", "OR", "XOR",
                "CMPI", "CMPF", "CMPB",
            }
            or op.startswith("LOAD")
        )

    # -------------------------------------------------
    # Helpers
    # -------------------------------------------------

    def eval_cmp(self, oper: str, a: Any, b: Any) -> bool:
        if oper == "==":
            return a == b
        if oper == "!=":
            return a != b
        if oper == "<":
            return a < b
        if oper == "<=":
            return a <= b
        if oper == ">":
            return a > b
        if oper == ">=":
            return a >= b
        raise NotImplementedError(f"Comparador no soportado: {oper}")
```

---

# 6. CLI sugerida

El script debe aceptar niveles con estilo de compilador:

```bash
python iroptimizer.py archivo.bminor -O0
python iroptimizer.py archivo.bminor -O1
python iroptimizer.py archivo.bminor -O2
```

También puede aceptar, por compatibilidad:

```bash
python iroptimizer.py archivo.bminor -O 2
python iroptimizer.py archivo.bminor 2
```

Función sugerida:

```python
def parse_opt_level(value: str) -> int:
    text = str(value).strip()

    if text.startswith("-O"):
        text = text[2:]
    elif text.startswith("O"):
        text = text[1:]

    if not text.isdigit():
        raise ValueError(f"Nivel de optimización inválido: {value!r}")

    level = int(text)

    if level < 0 or level > 4:
        raise ValueError("El nivel de optimización debe estar entre 0 y 4")

    return level
```

Para este taller solo se califican `-O1` y `-O2`, pero se deja la interfaz preparada para `-O3` y `-O4`.

---

# 7. Programa B-Minor de prueba

```c
main: function void () = {
    x: integer = 2 + 3 * 4;
    y: integer = x + 0;

    if 1 < 2 {
        print y;
    } else {
        print 999;
    }

    z: integer = 100;
    print x;
}
```

El optimizador debería detectar:

1. `3 * 4` puede convertirse en `12`.
2. `2 + 12` puede convertirse en `14`.
3. `1 < 2` puede convertirse en `1`.
4. El `CBRANCH` puede convertirse en un `BRANCH` directo.
5. Algunas instrucciones de la rama no tomada pueden quedar inalcanzables.
6. En `-O2`, temporales que no se usan pueden eliminarse.

---

# 8. Pruebas unitarias mínimas

Se recomienda que los estudiantes creen pruebas sobre listas de instrucciones sin depender del parser.

```python
from iroptimizer import IROptimizer
from ircode import IRFunction, IRProgram


def optimize_insts(insts, level):
    fn = IRFunction("main", [], None, insts)
    program = IRProgram([], [fn])
    opt = IROptimizer.optimize(program, level=level)
    return opt.functions[0].instructions


def test_constant_folding_addi():
    insts = [
        ("MOVI", 2, "R1"),
        ("MOVI", 3, "R2"),
        ("ADDI", "R1", "R2", "R3"),
        ("PRINTI", "R3"),
    ]

    out = optimize_insts(insts, level=1)

    assert ("MOVI", 5, "R3") in out


def test_dead_temp_o2():
    insts = [
        ("MOVI", 2, "R1"),
        ("MOVI", 99, "R2"),
        ("PRINTI", "R1"),
    ]

    out = optimize_insts(insts, level=2)

    assert ("MOVI", 99, "R2") not in out
```

---

# 9. Entregables

Cada grupo debe entregar:

1. `iroptimizer.py` completo.
2. Un archivo `.bminor` de prueba para `-O1`.
3. Un archivo `.bminor` de prueba para `-O2`.
4. Capturas o salida textual comparando:
   - IR original
   - IR con `-O1`
   - IR con `-O2`
5. Una explicación breve de las optimizaciones implementadas.

---

# 10. Rúbrica sugerida

| Criterio | Puntos |
|---|---:|
| `-O0` conserva la IR original | 10 |
| `-O1` implementa constant folding | 15 |
| `-O1` implementa simplificación algebraica | 15 |
| `-O1` simplifica ramas constantes | 15 |
| `-O1` elimina código inalcanzable simple | 10 |
| `-O2` incluye todo `-O1` | 10 |
| `-O2` elimina temporales muertos correctamente | 15 |
| Pruebas y ejemplos claros | 10 |
| **Total** | **100** |

---

# 11. Recomendaciones para evitar errores

1. No eliminar `PRINT`, `STORE`, `CALL`, `RET`, `BRANCH`, `CBRANCH`, `LABEL` ni `DATAS`.
2. No optimizar división por cero.
3. No asumir que una variable cargada con `LOADI x, R1` tiene valor constante.
4. Tratar los `CALL` de manera conservadora.
5. Recordar que `-O2` debe ejecutar primero las transformaciones de `-O1`.
6. Validar siempre que el programa optimizado produzca la misma salida que el original.

---

# 12. Extensiones opcionales

Para estudiantes avanzados:

1. Eliminar `LABEL` no usados.
2. Eliminar ramas `else` imposibles después de una condición constante.
3. Agregar `MODI` para evitar bajar `%` como `DIVI`, `MULI`, `SUBI`.
4. Construir bloques básicos explícitos.
5. Preparar `-O3` con optimización sobre CFG.
6. Preparar `-O4` con SSA, `PHI`, dominadores y propagación global.

