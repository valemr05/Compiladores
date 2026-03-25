# parser.py
# Analizador Sintáctico para B-Minor
# Usa: lexer.py y errors.py del profesor + model.py (nodos del AST)
#
# USO:
#   python parser.py archivo.bminor

import logging
import sly

from lexer   import Lexer
from errors  import error, errors_detected
from model   import *
import rich 


# =============================================================================
# HELPER — asigna número de línea a un nodo y lo retorna
# =============================================================================

def _L(node, lineno):
    node.lineno = lineno
    return node


# =============================================================================
# PARSER
# =============================================================================

class Parser(sly.Parser):

    log = logging.getLogger()
    log.setLevel(logging.ERROR)

    # 1 conflicto shift-reduce esperado por el dangling-else (if sin else)
    expected_shift_reduce = 1

    debugfile = 'grammar.txt'

    tokens = Lexer.tokens

    # =========================================================================
    # PROGRAMA
    # =========================================================================

    @_('decl_list')
    def prog(self, p):
        """Punto de entrada: el programa es una lista de declaraciones."""
        return _L(Program(p.decl_list), getattr(p, 'lineno', 0))

    # =========================================================================
    # LISTAS DE DECLARACIONES
    # =========================================================================

    @_('decl decl_list')
    def decl_list(self, p):
        return [p.decl] + p.decl_list

    @_('empty')
    def decl_list(self, p):
        return []

    # =========================================================================
    # DECLARACIONES
    # =========================================================================

    # Variable simple sin inicialización:   x : integer;
    @_("ID ':' type_simple ';'")
    def decl(self, p):
        return _L(VarDecl(p.ID, p.type_simple), p.lineno)

    # Arreglo sin inicialización:   a : array[10] integer;
    @_("ID ':' type_array_sized ';'")
    def decl(self, p):
        return _L(ArrayDecl(p.ID, p.type_array_sized), p.lineno)

    # Prototipo de función (sin cuerpo):   f : function integer(params);
    @_("ID ':' type_func ';'")
    def decl(self, p):
        return _L(FuncDecl(p.ID, p.type_func), p.lineno)

    # Declaración con inicialización (delega a decl_init)
    @_('decl_init')
    def decl(self, p):
        return p.decl_init

    # -------------------------------------------------------------------------
    # DECLARACIONES CON INICIALIZACIÓN
    # -------------------------------------------------------------------------

    # Variable con valor inicial:   x : integer = expr;
    @_("ID ':' type_simple '=' expr ';'")
    def decl_init(self, p):
        return _L(VarDeclInit(p.ID, p.type_simple, p.expr), p.lineno)

    # Constante:   PI : constant = expr;
    @_("ID ':' CONSTANT '=' expr ';'")
    def decl_init(self, p):
        return _L(ConstDecl(p.ID, p.expr), p.lineno)

    # Arreglo con lista de valores:   a : array[2] integer = {1, 2};
    @_("ID ':' type_array_sized '=' '{' opt_expr_list '}' ';'")
    def decl_init(self, p):
        return _L(ArrayDeclInit(p.ID, p.type_array_sized, p.opt_expr_list), p.lineno)

    # Definición de función con cuerpo:   f : function integer() = { stmts }
    @_("ID ':' type_func '=' '{' opt_stmt_list '}'")
    def decl_init(self, p):
        return _L(FuncDeclInit(p.ID, p.type_func, p.opt_stmt_list), p.lineno)

    # =========================================================================
    # SENTENCIAS
    # =========================================================================

    @_('stmt_list')
    def opt_stmt_list(self, p):
        return p.stmt_list

    @_('empty')
    def opt_stmt_list(self, p):
        return []

    @_('stmt stmt_list')
    def stmt_list(self, p):
        return [p.stmt] + p.stmt_list

    @_('stmt')
    def stmt_list(self, p):
        return [p.stmt]

    # Una sentencia puede ser abierta (IF sin ELSE) o cerrada
    @_('open_stmt')
    @_('closed_stmt')
    def stmt(self, p):
        return p[0]

    # Sentencias cerradas: todas sus ramas están completamente especificadas
    @_('if_stmt_closed')
    @_('for_stmt_closed')
    @_('while_stmt_closed')
    @_('simple_stmt')
    def closed_stmt(self, p):
        return p[0]

    # Sentencias abiertas: tienen un IF sin ELSE en alguna rama interna
    @_('if_stmt_open')
    @_('for_stmt_open')
    @_('while_stmt_open')
    def open_stmt(self, p):
        return p[0]

    # -------------------------------------------------------------------------
    # IF
    # -------------------------------------------------------------------------

    # Cabecera del IF — se separa para ser reutilizada sin duplicar código
    @_("IF '(' opt_expr ')'")
    def if_cond(self, p):
        return p.opt_expr

    # IF-ELSE completamente cerrado
    @_('if_cond closed_stmt ELSE closed_stmt')
    def if_stmt_closed(self, p):
        return _L(IfStmt(p.if_cond, p.closed_stmt0, p.closed_stmt1), p.lineno)

    # IF sin ELSE (dangling-else)
    @_('if_cond stmt')
    def if_stmt_open(self, p):
        return _L(IfStmt(p.if_cond, p.stmt), p.lineno)

    # IF-ELSE donde la rama ELSE es otro IF abierto (else-if chain)
    @_('if_cond closed_stmt ELSE if_stmt_open')
    def if_stmt_open(self, p):
        return _L(IfStmt(p.if_cond, p.closed_stmt, p.if_stmt_open), p.lineno)

    # -------------------------------------------------------------------------
    # FOR
    # -------------------------------------------------------------------------

    # Cabecera del FOR: for(init; cond; update)
    @_("FOR '(' opt_expr ';' opt_expr ';' opt_expr ')'")
    def for_header(self, p):
        return (p.opt_expr0, p.opt_expr1, p.opt_expr2)

    @_('for_header open_stmt')
    def for_stmt_open(self, p):
        init, cond, update = p.for_header
        return ForStmt(init, cond, update, p.open_stmt)

    @_('for_header closed_stmt')
    def for_stmt_closed(self, p):
        init, cond, update = p.for_header
        return ForStmt(init, cond, update, p.closed_stmt)

    # -------------------------------------------------------------------------
    # WHILE
    # -------------------------------------------------------------------------

    @_("WHILE '(' opt_expr ')'")
    def while_cond(self, p):
        return p.opt_expr

    @_('while_cond open_stmt')
    def while_stmt_open(self, p):
        return WhileStmt(p.while_cond, p.open_stmt)

    @_('while_cond closed_stmt')
    def while_stmt_closed(self, p):
        return WhileStmt(p.while_cond, p.closed_stmt)

    # -------------------------------------------------------------------------
    # SENTENCIAS SIMPLES
    # -------------------------------------------------------------------------

    @_('print_stmt')
    @_('return_stmt')
    @_('break_stmt')
    @_('continue_stmt')
    @_('block_stmt')
    @_('decl')
    @_("expr ';'")
    def simple_stmt(self, p):
        if hasattr(p, 'expr'):
            return _L(ExprStmt(p.expr), p.lineno)
        return p[0]

    # PRINT:   print expr, expr, ...; 
    @_("PRINT opt_expr_list ';'")
    def print_stmt(self, p):
        return _L(PrintStmt(p.opt_expr_list), p.lineno)

    # RETURN:  return [expr];
    @_("RETURN opt_expr ';'")
    def return_stmt(self, p):
        return _L(ReturnStmt(p.opt_expr), p.lineno)

    # BREAK
    @_("BREAK ';'")
    def break_stmt(self, p):
        return _L(BreakStmt(), p.lineno)

    # CONTINUE
    @_("CONTINUE ';'")
    def continue_stmt(self, p):
        return _L(ContinueStmt(), p.lineno)

    # BLOQUE:  { stmt* }
    @_("'{' stmt_list '}'")
    def block_stmt(self, p):
        return _L(Block(p.stmt_list), p.lineno)

    # =========================================================================
    # EXPRESIONES
    # Jerarquía de precedencia construida por niveles (menor → mayor prioridad):
    #   expr → expr1 (asignación)
    #        → expr2 (||)
    #        → expr3 (&&)
    #        → expr4 (==, !=, <, <=, >, >=)
    #        → expr5 (+, -)
    #        → expr6 (*, /)
    #        → expr7 (^  exponenciación)
    #        → expr8 (unarios: -, !)
    #        → expr9 → group → factor
    # =========================================================================

    # ── Listas de expresiones ─────────────────────────────────────────────────

    @_('empty')
    def opt_expr_list(self, p):
        return []

    @_('expr_list')
    def opt_expr_list(self, p):
        return p.expr_list

    @_("expr ',' expr_list")
    def expr_list(self, p):
        return [p.expr] + p.expr_list

    @_('expr')
    def expr_list(self, p):
        return [p.expr]

    @_('empty')
    def opt_expr(self, p):
        return None

    @_('expr')
    def opt_expr(self, p):
        return p.expr

    # ── Nivel 0: expresión raíz ───────────────────────────────────────────────

    @_('expr1')
    def expr(self, p):
        return p.expr1

    # ── Nivel 1: asignación ───────────────────────────────────────────────────

    @_("lval '=' expr1")
    def expr1(self, p):
        return _L(Assign(p.lval, p.expr1), p.lineno)

    @_('expr2')
    def expr1(self, p):
        return p.expr2

    # ── LValues (lado izquierdo válido de una asignación) ─────────────────────

    @_('ID')
    def lval(self, p):
        return _L(Identifier(p.ID), p.lineno)

    @_("ID '[' expr ']'")
    def lval(self, p):
        return _L(IndexExpr(p.ID, p.expr), p.lineno)

    # ── Nivel 2: OR lógico ────────────────────────────────────────────────────

    @_('expr2 LOR expr3')
    def expr2(self, p):
        return _L(BinOp('||', p.expr2, p.expr3), p.lineno)

    @_('expr3')
    def expr2(self, p):
        return p.expr3

    # ── Nivel 3: AND lógico ───────────────────────────────────────────────────

    @_('expr3 LAND expr4')
    def expr3(self, p):
        return _L(BinOp('&&', p.expr3, p.expr4), p.lineno)

    @_('expr4')
    def expr3(self, p):
        return p.expr4

    # ── Nivel 4: comparaciones ────────────────────────────────────────────────

    @_('expr4 EQ expr5')
    def expr4(self, p):
        return _L(BinOp('==', p.expr4, p.expr5), p.lineno)

    @_('expr4 NE expr5')
    def expr4(self, p):
        return _L(BinOp('!=', p.expr4, p.expr5), p.lineno)

    @_('expr4 LT expr5')
    def expr4(self, p):
        return _L(BinOp('<',  p.expr4, p.expr5), p.lineno)

    @_('expr4 LE expr5')
    def expr4(self, p):
        return _L(BinOp('<=', p.expr4, p.expr5), p.lineno)

    @_('expr4 GT expr5')
    def expr4(self, p):
        return _L(BinOp('>',  p.expr4, p.expr5), p.lineno)

    @_('expr4 GE expr5')
    def expr4(self, p):
        return _L(BinOp('>=', p.expr4, p.expr5), p.lineno)

    @_('expr5')
    def expr4(self, p):
        return p.expr5

    # ── Nivel 5: suma y resta ─────────────────────────────────────────────────

    @_("expr5 '+' expr6")
    def expr5(self, p):
        return _L(BinOp('+', p.expr5, p.expr6), p.lineno)

    @_("expr5 '-' expr6")
    def expr5(self, p):
        return _L(BinOp('-', p.expr5, p.expr6), p.lineno)

    @_('expr6')
    def expr5(self, p):
        return p.expr6

    # ── Nivel 6: multiplicación y división ───────────────────────────────────

    @_("expr6 '*' expr7")
    def expr6(self, p):
        return _L(BinOp('*', p.expr6, p.expr7), p.lineno)

    @_("expr6 '/' expr7")
    def expr6(self, p):
        return _L(BinOp('/', p.expr6, p.expr7), p.lineno)

    @_("expr6 '%' expr7")
    def expr6(self, p):
        return _L(BinOp('%', p.expr6, p.expr7), p.lineno)

    @_('expr7')
    def expr6(self, p):
        return p.expr7

    # ── Nivel 7: exponenciación ───────────────────────────────────────────────

    @_("expr7 '^' expr8")
    def expr7(self, p):
        return _L(BinOp('^', p.expr7, p.expr8), p.lineno)

    @_('expr8')
    def expr7(self, p):
        return p.expr8

    # ── Nivel 8: operadores unarios ───────────────────────────────────────────

    @_("'-' expr8")
    def expr8(self, p):
        return _L(UnaryOp('-', p.expr8), p.lineno)

    @_("'!' expr8")
    def expr8(self, p):
        return _L(UnaryOp('!', p.expr8), p.lineno)

    @_('expr9')
    def expr8(self, p):
        return p.expr9

    # ── Nivel 9 ───────────────────────────────────────────────────────────────

    @_('postfix')
    def expr9(self, p):
        return p.postfix

    # Postfijos: i++  i--
    @_('primary')
    def postfix(self, p):
        return p.primary

    @_('postfix INC')
    def postfix(self, p):
        return _L(UnaryOp('++', p.postfix), p.lineno)

    @_('postfix DEC')
    def postfix(self, p):
        return _L(UnaryOp('--', p.postfix), p.lineno)

    # Prefijos: ++i  --i
    @_('prefix')
    def primary(self, p):
        return p.prefix

    @_('INC prefix')
    def prefix(self, p):
        return _L(UnaryOp('pre++', p.prefix), p.lineno)

    @_('DEC prefix')
    def prefix(self, p):
        return _L(UnaryOp('pre--', p.prefix), p.lineno)

    @_('group')
    def prefix(self, p):
        return p.group

    # ── Group / agrupaciones ──────────────────────────────────────────────────

    # Expresión entre paréntesis:   (expr)
    @_("'(' expr ')'")
    def group(self, p):
        return p.expr

    # Llamada a función:   f(args)
    @_("ID '(' opt_expr_list ')'")
    def group(self, p):
        return _L(CallExpr(p.ID, p.opt_expr_list), p.lineno)

    # Acceso a arreglo:   a[i]
    @_("ID '[' expr ']'")
    def group(self, p):
        return _L(IndexExpr(p.ID, p.expr), p.lineno)

    # Factor simple (literal o identificador)
    @_('factor')
    def group(self, p):
        return p.factor

    # ── Índice de arreglo (regla auxiliar) ───────────────────────────────────

    @_("'[' expr ']'")
    def index(self, p):
        return p.expr

    # =========================================================================
    # FACTORES (hojas del árbol de expresiones)
    # =========================================================================

    @_('ID')
    def factor(self, p):
        return _L(Identifier(p.ID), p.lineno)

    @_('INTEGER_LITERAL')
    def factor(self, p):
        return _L(IntLiteral(p.INTEGER_LITERAL), p.lineno)

    @_('FLOAT_LITERAL')
    def factor(self, p):
        return _L(FloatLiteral(p.FLOAT_LITERAL), p.lineno)

    @_('CHAR_LITERAL')
    def factor(self, p):
        return _L(CharLiteral(p.CHAR_LITERAL), p.lineno)

    @_('STRING_LITERAL')
    def factor(self, p):
        return _L(StringLiteral(p.STRING_LITERAL), p.lineno)

    @_('TRUE')
    def factor(self, p):
        return _L(BoolLiteral(True), p.lineno)

    @_('FALSE')
    def factor(self, p):
        return _L(BoolLiteral(False), p.lineno)

    # =========================================================================
    # TIPOS
    # =========================================================================

    # Tipo primitivo: INTEGER | FLOAT | BOOLEAN | CHAR | STRING | VOID
    @_('INTEGER')
    @_('FLOAT')
    @_('BOOLEAN')
    @_('CHAR')
    @_('STRING')
    @_('VOID')
    def type_simple(self, p):
        return _L(SimpleType(p[0]), p.lineno)

    # Tipo arreglo sin tamaño:   array[] type
    @_("ARRAY '[' ']' type_simple")
    @_("ARRAY '[' ']' type_array")
    def type_array(self, p):
        return _L(ArrayType(p[3]), p.lineno)

    # Tipo arreglo con tamaño:   array[expr] type
    @_("ARRAY '[' expr ']' type_simple")
    @_("ARRAY '[' expr ']' type_array_sized")
    def type_array_sized(self, p):
        return _L(ArrayTypeSized(p.expr, p[4]), p.lineno)

    # Tipo función:   function ret_type(params)
    @_("FUNCTION type_simple '(' opt_param_list ')'")
    @_("FUNCTION type_array_sized '(' opt_param_list ')'")
    def type_func(self, p):
        return _L(FuncType(p[1], p.opt_param_list), p.lineno)

    # ── Parámetros ────────────────────────────────────────────────────────────

    @_('empty')
    def opt_param_list(self, p):
        return []

    @_('param_list')
    def opt_param_list(self, p):
        return p.param_list

    @_("param_list ',' param")
    def param_list(self, p):
        return p.param_list + [p.param]

    @_('param')
    def param_list(self, p):
        return [p.param]

    @_("ID ':' type_simple")
    def param(self, p):
        return _L(Param(p.ID, p.type_simple), p.lineno)

    @_("ID ':' type_array")
    def param(self, p):
        return _L(Param(p.ID, p.type_array), p.lineno)

    @_("ID ':' type_array_sized")
    def param(self, p):
        return _L(Param(p.ID, p.type_array_sized), p.lineno)

    # =========================================================================
    # UTILIDAD: EMPTY
    # =========================================================================

    @_('')
    def empty(self, p):
        """Producción vacía — para listas y elementos opcionales."""
        return None

    # =========================================================================
    # MANEJO DE ERRORES
    # =========================================================================

    def error(self, p):
        lineno = p.lineno if p else 'EOF'
        value  = repr(p.value) if p else 'EOF'
        error(f'Error de sintaxis en {value}', lineno)


# =============================================================================
# UTILIDADES DE IMPRESIÓN DEL AST
# =============================================================================

def print_ast(node, indent=0):
    """Imprime el AST con indentación para facilitar la lectura."""
    prefix = '  ' * indent
    if node is None:
        rich.print(f"{prefix}None")
        return
    if isinstance(node, list):
        for item in node:
            print_ast(item, indent)
        return
    if isinstance(node, ASTNode):
        lineno_str = f" [línea {node.lineno}]" if node.lineno else ""
        rich.print(f"{prefix}{node.__class__.__name__}{lineno_str}")
        for key, val in node.__dict__.items():
            if key == 'lineno':
                continue
            rich.print(f"{prefix}  .{key}:")
            if isinstance(val, (list, ASTNode)):
                print_ast(val, indent + 2)
            else:
                rich.print(f"{prefix}    {val!r}")
    else:
        rich.print(f"{prefix}{node!r}")


# =============================================================================
# FUNCIÓN DE PARSEO
# =============================================================================

def parse(txt):
    """Recibe código fuente B-Minor y devuelve el AST."""
    l = Lexer()
    p = Parser()
    return p.parse(l.tokenize(txt))


# =============================================================================
# PUNTO DE ENTRADA
# =============================================================================

if __name__ == '__main__':
    import sys

    if len(sys.argv) != 2:
        raise SystemExit("Uso: python parser.py <archivo.bminor>")

    filename = sys.argv[1]
    rich.print(f"\n{'='*60}")
    rich.print(f"  Analizando: {filename}")
    rich.print(f"{'='*60}\n")

    txt = open(filename, encoding='utf-8').read()
    ast = parse(txt)

    if not errors_detected():
        rich.print("✔  Análisis sintáctico exitoso — sin errores.\n")
        rich.print("── AST ──────────────────────────────────────────────────")
        print_ast(ast)
    else:
        rich.print(f"\n✘  Se encontraron {errors_detected()} error(es) sintáctico(s).")
