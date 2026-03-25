

# Analizador Léxico — B-Minor+

Proyecto desarrollado para el curso de Compiladores. Implementa un analizador léxico para el lenguaje **B-Minor+** usando Python y la biblioteca `sly`.

Desarrollador por: 
Sebastian Ramirez Valencia
Juan Esteban Villegas Montoya
Valeria Muñoz Ramirez

---

## Descripción del proyecto

Un analizador léxico (lexer) es la primera fase de un compilador. Su función es leer el código fuente como texto plano y convertirlo en una secuencia de **tokens**, que son las unidades mínimas con significado del lenguaje (palabras reservadas, identificadores, operadores, literales, etc.).

El lexer de B-Minor+ reconoce los siguientes tipos de tokens:

| Categoría | Tokens |
|---|---|
| Palabras reservadas | `constant`, `print`, `return`, `break`, `continue`, `if`, `else`, `while`, `function`, `true`, `false` |
| Identificadores | `ID` — inician con letra o `_`, seguidos de letras, dígitos o `_` |
| Literales enteros | `ENTERO` — ej: `123` |
| Literales flotantes | `FLOTANTE` — ej: `1.23`, `.5`, `3.` |
| Literales de carácter | `CHAR` — ej: `'a'`, `'\n'`, `'\xAF'`, `'\''` |
| Operadores | aritméticos, relacionales, lógicos y `^` |
| Símbolos varios | `=`, `;`, `(`, `)`, `{`, `}`, `,`, `` ` `` |

El lexer también **ignora** comentarios de línea (`//`) y de bloque (`/* ... */`), y reporta los siguientes errores:

- `linea N: Carácter 'c' ilegal`
- `linea N: Constante de carácter sin terminación`
- `linea N: Comentario sin terminación`

---

## Decisiones de diseño

### Biblioteca sly
Se eligió `sly` por su sintaxis declarativa basada en decoradores y atributos de clase, lo que hace el código más legible y cercano a la definición formal de un lexer.

### Orden de las reglas
En `sly`, el orden en que se definen los tokens importa. Los operadores de dos caracteres (`<=`, `>=`, `==`, `!=`, `&&`, `||`) se definen **antes** que los de un carácter (`<`, `>`, `=`, `!`) para evitar que se partan en dos tokens.

De la misma forma, `FLOTANTE` se define antes que `ENTERO` para que `3.14` no sea tokenizado como `ENTERO` + `.` + `ENTERO`.

### Comentarios sin terminar
Se usaron dos expresiones regulares para comentarios de bloque: una que exige el cierre `*/` (comentario válido) y otra que acepta cualquier cosa desde `/*` sin cerrarse (error). La segunda actúa como red de seguridad y reporta el error correspondiente.

### Keywords con diccionario interno
Las palabras reservadas se manejan mediante el diccionario interno de `sly` sobre la regla `ID`. Esto permite que el lexer primero reconozca cualquier texto como `ID` y luego lo reclasifique si coincide con una keyword, evitando conflictos de orden.

### Recuperación ante errores
El método `error()` imprime el carácter ilegal y avanza un solo carácter (`self.index += 1`), lo que permite que el lexer **continúe tokenizando** el resto del código en lugar de detenerse ante el primer error.

---

## Cómo correr las pruebas

Las pruebas unitarias están integradas directamente en `bMinorLexer.py`. Para ejecutarlas:

```bash
python bMinorLexer.py test
```

Se ejecutan **18 pruebas** que cubren:

- Los tres formatos de literal flotante
- Identificadores simples y con guion bajo
- Todas las palabras reservadas
- Que una keyword como prefijo (`ifelse`) sea reconocida como `ID`
- Literales `CHAR` válidos e inválidos
- Operadores de dos caracteres que no se parten
- El token `DEREF` (comilla invertida)
- Comentarios ignorados correctamente
- Mensajes de error para comentario sin terminar, carácter sin terminar y carácter ilegal
- Recuperación del lexer tras un error

Salida esperada:

```
Ran 18 tests in 0.000s
OK
```

Para correr el lexer en modo demo con código de prueba:

```bash
python bMinorLexer.py
```
