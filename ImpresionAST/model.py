# model.py
# Nodos del Árbol de Sintaxis Abstracta (AST) para B-Minor
# Cada clase representa un constructo del lenguaje.

# =============================================================================
# CLASE BASE
# =============================================================================

class ASTNode:
    """Clase base para todos los nodos del AST."""
    lineno = None

    def __repr__(self):
        fields = ', '.join(
            f'{k}={v!r}' for k, v in self.__dict__.items() if k != 'lineno'
        )
        return f'{self.__class__.__name__}({fields})'

# =============================================================================
# PROGRAMA
# =============================================================================

class Program(ASTNode):
    """
    Raíz del árbol. Contiene la lista de declaraciones del programa.
    Ejemplo:  x: integer;  f: function void() = { ... }
    """
    def __init__(self, decls):
        self.decls = decls          # list[decl*]

# =============================================================================
# DECLARACIONES
# =============================================================================

class VarDecl(ASTNode):
    """
    Declaración de variable simple sin inicialización.
    Ejemplo:  x : integer;
    """
    def __init__(self, name, vartype):
        self.name    = name         # str
        self.vartype = vartype      # SimpleType


class VarDeclInit(ASTNode):
    """
    Declaración de variable simple con inicialización.
    Ejemplo:  y : integer = 123;
    """
    def __init__(self, name, vartype, value):
        self.name    = name         # str
        self.vartype = vartype      # SimpleType
        self.value   = value        # Expr


class ConstDecl(ASTNode):
    """
    Declaración de constante.
    Ejemplo:  PI : constant = 3.14;
    """
    def __init__(self, name, value):
        self.name  = name           # str
        self.value = value          # Expr


class ArrayDecl(ASTNode):
    """
    Declaración de arreglo sin inicialización.
    Ejemplo:  a : array [10] integer;
    """
    def __init__(self, name, arrtype):
        self.name    = name         # str
        self.arrtype = arrtype      # ArrayTypeSized


class ArrayDeclInit(ASTNode):
    """
    Declaración de arreglo con inicialización por lista.
    Ejemplo:  a : array [2] boolean = {true, false};
    """
    def __init__(self, name, arrtype, elements):
        self.name     = name        # str
        self.arrtype  = arrtype     # ArrayTypeSized
        self.elements = elements    # list[Expr]


class FuncDecl(ASTNode):
    """
    Prototipo de función (sin cuerpo).
    Ejemplo:  f : function integer(x: integer);
    """
    def __init__(self, name, functype):
        self.name     = name        # str
        self.functype = functype    # FuncType


class FuncDeclInit(ASTNode):
    """
    Definición de función con cuerpo.
    Ejemplo:  main : function integer() = { return 0; }
    """
    def __init__(self, name, functype, body):
        self.name     = name        # str
        self.functype = functype    # FuncType
        self.body     = body        # list[Stmt]


# =============================================================================
# TIPOS
# =============================================================================

class SimpleType(ASTNode):
    """
    Tipo primitivo del lenguaje.
    Valores posibles: 'integer', 'float', 'boolean', 'char', 'string', 'void'
    """
    def __init__(self, name):
        self.name = name            # str


class ArrayType(ASTNode):
    """
    Tipo arreglo sin tamaño explícito (usado en parámetros).
    Ejemplo:  array [] integer
    """
    def __init__(self, elem_type):
        self.elem_type = elem_type  # SimpleType | ArrayType


class ArrayTypeSized(ASTNode):
    """
    Tipo arreglo con tamaño explícito.
    Ejemplo:  array [10] integer
    """
    def __init__(self, size, elem_type):
        self.size      = size       # Expr
        self.elem_type = elem_type  # SimpleType | ArrayTypeSized


class FuncType(ASTNode):
    """
    Tipo función con tipo de retorno y lista de parámetros.
    Ejemplo:  function integer (x: integer, y: string)
    """
    def __init__(self, ret_type, params):
        self.ret_type = ret_type    # SimpleType | ArrayTypeSized
        self.params   = params      # list[Param]


class Param(ASTNode):
    """
    Parámetro formal de una función.
    Ejemplo:  x : integer
    """
    def __init__(self, name, paramtype):
        self.name      = name       # str
        self.paramtype = paramtype  # SimpleType | ArrayType | ArrayTypeSized


# =============================================================================
# SENTENCIAS
# =============================================================================

class Block(ASTNode):
    """
    Bloque de sentencias encerrado en llaves.
    Ejemplo:  { stmt1; stmt2; }
    """
    def __init__(self, stmts):
        self.stmts = stmts          # list[Stmt]


class PrintStmt(ASTNode):
    """
    Sentencia print con lista de expresiones.
    Ejemplo:  print x, "\\n";
    """
    def __init__(self, exprs):
        self.exprs = exprs          # list[Expr]


class ReturnStmt(ASTNode):
    """
    Sentencia return con expresión opcional.
    Ejemplo:  return 0;   |   return;
    """
    def __init__(self, value=None):
        self.value = value          # Expr | None


class BreakStmt(ASTNode):
    """Sentencia break; — sale del bucle más cercano."""
    pass


class ContinueStmt(ASTNode):
    """Sentencia continue; — salta a la siguiente iteración."""
    pass


class IfStmt(ASTNode):
    """
    Sentencia if con rama else opcional.
    Ejemplo:  if (cond) { ... } else { ... }
    """
    def __init__(self, cond, then_branch, else_branch=None):
        self.cond        = cond         # Expr
        self.then_branch = then_branch  # Stmt
        self.else_branch = else_branch  # Stmt | None


class WhileStmt(ASTNode):
    """
    Sentencia while.
    Ejemplo:  while (x > 0) { x = x - 1; }
    """
    def __init__(self, cond, body):
        self.cond = cond            # Expr
        self.body = body            # Stmt


class ForStmt(ASTNode):
    """
    Sentencia for con init, condición y actualización opcionales.
    Ejemplo:  for (i=0; i<10; i=i+1) { ... }
    """
    def __init__(self, init, cond, update, body):
        self.init   = init          # Expr | None
        self.cond   = cond          # Expr | None
        self.update = update        # Expr | None
        self.body   = body          # Stmt


class ExprStmt(ASTNode):
    """
    Sentencia de expresión (expresión usada como sentencia).
    Ejemplo:  x = 5;   |   f(x);
    """
    def __init__(self, expr):
        self.expr = expr            # Expr


# =============================================================================
# EXPRESIONES
# =============================================================================

class Assign(ASTNode):
    """
    Asignación simple.
    Ejemplo:  x = expr
    """
    def __init__(self, target, value):
        self.target = target        # Identifier | IndexExpr
        self.value  = value         # Expr


class BinOp(ASTNode):
    """
    Operación binaria.
    Operadores posibles: +, -, *, /, ^, ==, !=, <, <=, >, >=, &&, ||
    """
    def __init__(self, op, left, right):
        self.op    = op             # str
        self.left  = left           # Expr
        self.right = right          # Expr


class UnaryOp(ASTNode):
    """
    Operación unaria.
    Operadores posibles: - (negación aritmética), ! (negación lógica)
    """
    def __init__(self, op, operand):
        self.op      = op           # str
        self.operand = operand      # Expr


class CallExpr(ASTNode):
    """
    Llamada a función.
    Ejemplo:  f(x, y)
    """
    def __init__(self, name, args):
        self.name = name            # str
        self.args = args            # list[Expr]


class IndexExpr(ASTNode):
    """
    Acceso a elemento de arreglo.
    Ejemplo:  a[i]
    """
    def __init__(self, name, index):
        self.name  = name           # str
        self.index = index          # Expr


class Identifier(ASTNode):
    """
    Referencia a una variable por nombre.
    Ejemplo:  x
    """
    def __init__(self, name):
        self.name = name            # str


class DerefExpr(ASTNode):
    """
    Desreferencia con operador backtick.
    Ejemplo:  `expr
    """
    def __init__(self, expr):
        self.expr = expr            # Expr


# =============================================================================
# LITERALES
# =============================================================================

class IntLiteral(ASTNode):
    """Literal entero. Ejemplo: 42"""
    def __init__(self, value):
        self.value = int(value)


class FloatLiteral(ASTNode):
    """Literal flotante. Ejemplo: 3.14"""
    def __init__(self, value):
        self.value = float(value)


class CharLiteral(ASTNode):
    """Literal de carácter. Ejemplo: 'a'"""
    def __init__(self, value):
        self.value = value          # str


class StringLiteral(ASTNode):
    """Literal de cadena de texto. Ejemplo: "hello" """
    def __init__(self, value):
        self.value = value          # str (sin comillas externas)


class BoolLiteral(ASTNode):
    """Literal booleano. Ejemplo: true | false"""
    def __init__(self, value):
        self.value = value          # bool: True | False
