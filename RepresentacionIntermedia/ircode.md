# Proyecto 4

En este proyecto, convertirá el AST en un código de máquina intermedio basado en un código de 3 direcciones. Hay algunas partes importantes que necesitará para que esto funcione. Lea atentamente antes de comenzar:

## Una máquina "virtual"

Una CPU normalmente consta de registros y un pequeño conjunto basico opcodes para realizar cálculos matemáticos, cargar/almacenar valores desde la memoria y flujo de control básico (ramificaciones, saltos, etc.). Por ejemplo, supongamos que desea evaluar una operación como esta:

    a = 2 + 3 * 4 - 5

En una CPU, podría descomponerse en instrucciones de bajo nivel como esta:

    MOVI   #2, R1
    MOVI   #3, R2
    MOVI   #4, R3
    MULI   R2, R3, R4
    ADDI   R4, R1, R5
    MOVI   #5, R6
    SUBI   R5, R6, R7
    STOREI R7, "a"

Cada instrucción representa una única operación como sumar, multiplicar, etc.
Siempre hay dos operandos de entrada y un destino.

Las CPU también cuentan con un pequeño conjunto de tipos de datos principales, como enteros, bytes y flotantes. Hay instrucciones dedicadas para cada tipo.

Por ejemplo:

    ADDI   R1, R2, R3        ; Integer add
    ADDF   R4, R5, R6        ; Float add

A menudo existe una desconexión entre los tipos utilizados en el lenguaje de programación fuente y el IRCode generado. Por ejemplo, es posible que una máquina de destino solo tenga números enteros y flotantes. Para representar un valor como un booleano, debe representarlo como uno de los tipos nativos, como un número entero. Este es un detalle de implementación del que los usuarios no se preocuparán (nunca lo verán, pero usted tendrá que preocuparse por ello en el compilador).

Aquí hay una especificación del conjunto de instrucciones para nuestro IRCode:

    MOVI   value, target       ;  Load a literal integer
    VARI   name                ;  Declare an integer variable
    ALLOCI name                ;  Allocate an integer variabe on the stack
    LOADI  name, target        ;  Load an integer from a variable
    STOREI target, name        ;  Store an integer into a variable
    ADDI   r1, r2, target      ;  target = r1 + r2
    SUBI   r1, r2, target      ;  target = r1 - r2
    MULI   r1, r2, target      ;  target = r1 * r2
    DIVI   r1, r2, target      ;  target = r1 / r2
    PRINTI source              ;  print source  (debugging)
    CMPI   op, r1, r2, target  ;  Compare r1 op r2 -> target
    AND    r1, r2, target      :  target = r1 & r2
    OR     r1, r2, target      :  target = r1 | r2
    XOR    r1, r2, target      :  target = r1 ^ r2
    ITOF   r1, target          ;  target = float(r1)

    MOVF   value, target       ;  Load a literal float
    VARF   name                ;  Declare a float variable
    ALLOCF name                ;  Allocate a float variable on the stack
    LOADF  name, target        ;  Load a float from a variable
    STOREF target, name        ;  Store a float into a variable
    ADDF   r1, r2, target      ;  target = r1 + r2
    SUBF   r1, r2, target      ;  target = r1 - r2
    MULF   r1, r2, target      ;  target = r1 * r2
    DIVF   r1, r2, target      ;  target = r1 / r2
    PRINTF source              ;  print source (debugging)
    CMPF   op, r1, r2, target  ;  r1 op r2 -> target
    FTOI   r1, target          ;  target = int(r1)

    MOVB   value, target       ; Load a literal byte
    VARB   name                ; Declare a byte variable
    ALLOCB name                ; Allocate a byte variable
    LOADB  name, target        ; Load a byte from a variable
    STOREB target, name        ; Store a byte into a variable
    PRINTB source              ; print source (debugging)
    BTOI   r1, target          ; Convert a byte to an integer
    ITOB   r2, target          ; Truncate an integer to a byte
    CMPB   op, r1, r2, target  ; r1 op r2 -> target

También hay algunas instrucciones de flujo de control.

    LABEL  name                  ; Declare a label
    BRANCH label                 ; Unconditionally branch to label
    CBRANCH test, label1, label2 ; Conditional branch to label1 or label2 depending on test being 0 or not
    CALL   name, arg0, arg1, ... argN, target    ; Call a function name(arg0, ... argn) -> target
    RET    r1                    ; Return a result from a function

## Asignación estática única (SSA)

En una CPU real, hay un número limitado de registros de CPU.
En nuestra memoria virtual, vamos a asumir que la CPU tiene una cantidad infinita de registros disponibles. Además, asumiremos que cada registro sólo se puede asignar una vez.
Este estilo particular se conoce como Asignación única estática (SSA).
A medida que genera instrucciones, mantendrá un contador en ejecución que se incrementa cada vez que necesita una variable temporal.
El ejemplo de la sección anterior ilustra esto.

## Tu tarea

Su tarea es la siguiente: Escriba una clase AST Visitor() que tome un programa y lo aplane en una única secuencia de instrucciones de código SSA representadas como tuplas de la forma

    (operation, operands, ..., destination)

## Pruebas

Los archivos `~/test` contienen texto de entrada junto con resultados de muestra. Trabaje en cada archivo para completar el proyecto.
