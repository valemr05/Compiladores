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

    # Expresión opcional (puede estar vacía)
    @_('expr')
    def opt_expr(self, p):
        return p.expr

    @_('empty')
    def opt_expr(self, p):
        return None

    # Lista de expresiones separadas por coma (para print y llamadas)
    @_('expr_list')
    def opt_expr_list(self, p):
        return p.expr_list

    @_('empty')
    def opt_expr_list(self, p):
        return []

    @_("expr_list ',' expr")
    def expr_list(self, p):
        return p.expr_list + [p.expr]

    @_('expr')
    def expr_list(self, p):
        return [p.expr]

    # ── Nivel 1: asignación ───────────────────────────────────────────────────

    @_('expr1')
    def expr(self, p):
        return p.expr1

    # Asignaciones simples y compuestas
    @_("ID '=' expr1")
    def expr1(self, p):
        return _L(Assign(Identifier(p.ID), p.expr1), p.lineno)

    @_("ID '[' expr ']' '=' expr1")
    def expr1(self, p):
        return _L(Assign(IndexExpr(p.ID, p.expr), p.expr1), p.lineno)

    @_("ID ADDEQ expr1")
    def expr1(self, p):
        target = Identifier(p.ID)
        return _L(Assign(target, BinOp('+', Identifier(p.ID), p.expr1)), p.lineno)

    @_("ID SUBEQ expr1")
    def expr1(self, p):
        target = Identifier(p.ID)
        return _L(Assign(target, BinOp('-', Identifier(p.ID), p.expr1)), p.lineno)

    @_("ID MULEQ expr1")
    def expr1(self, p):
        target = Identifier(p.ID)
        return _L(Assign(target, BinOp('*', Identifier(p.ID), p.expr1)), p.lineno)

    @_("ID DIVEQ expr1")
    def expr1(self, p):
        target = Identifier(p.ID)
        return _L(Assign(target, BinOp('/', Identifier(p.ID), p.expr1)), p.lineno)

    @_("ID MODEQ expr1")
    def expr1(self, p):
        target = Identifier(p.ID)
        return _L(Assign(target, BinOp('%', Identifier(p.ID), p.expr1)), p.lineno)

    @_('expr2')
    def expr1(self, p):
        return p.expr2

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
        return _L(BinOp('<', p.expr4, p.expr5), p.lineno)

    @_('expr4 LE expr5')
    def expr4(self, p):
        return _L(BinOp('<=', p.expr4, p.expr5), p.lineno)

    @_('expr4 GT expr5')
    def expr4(self, p):
        return _L(BinOp('>', p.expr4, p.expr5), p.lineno)

    @_('expr4 GE expr5')
    def expr4(self, p):
        return _L(BinOp('>=', p.expr4, p.expr5), p.lineno)

    @_('expr5')
    def expr4(self, p):
        return p.expr5

    # ── Nivel 5: suma / resta ─────────────────────────────────────────────────

    @_("expr5 '+' expr6")
    def expr5(self, p):
        return _L(BinOp('+', p.expr5, p.expr6), p.lineno)

    @_("expr5 '-' expr6")
    def expr5(self, p):
        return _L(BinOp('-', p.expr5, p.expr6), p.lineno)

    @_('expr6')
    def expr5(self, p):
        return p.expr6

    # ── Nivel 6: multiplicación / división / módulo ───────────────────────────

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

    # ── Nivel 7: exponenciación (asociatividad derecha) ───────────────────────

    @_("expr8 '^' expr7")
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
# VISUALIZACIÓN — Rich Tree
# =============================================================================

def _node_label(node):
    """
    Devuelve una etiqueta compacta y legible para un nodo del AST.
    Los literales y nombres se muestran inline para mayor claridad.
    """
    cls = node.__class__.__name__

    # Nodos con un valor escalar relevante que mostrar inline
    if isinstance(node, (IntLiteral, FloatLiteral, CharLiteral,
                          StringLiteral, BoolLiteral)):
        return f"[bold cyan]{cls}[/bold cyan] [yellow]{node.value!r}[/yellow]"

    if isinstance(node, Identifier):
        return f"[bold green]Identifier[/bold green] [white]{node.name!r}[/white]"

    if isinstance(node, SimpleType):
        return f"[bold blue]SimpleType[/bold blue] [white]{node.name}[/white]"

    if isinstance(node, BinOp):
        return f"[bold magenta]BinOp[/bold magenta] [yellow]{node.op!r}[/yellow]"

    if isinstance(node, UnaryOp):
        return f"[bold magenta]UnaryOp[/bold magenta] [yellow]{node.op!r}[/yellow]"

    if isinstance(node, (VarDecl, VarDeclInit, ConstDecl,
                          ArrayDecl, ArrayDeclInit,
                          FuncDecl, FuncDeclInit)):
        name = getattr(node, 'name', '')
        return f"[bold]{cls}[/bold] [green]{name!r}[/green]"

    if isinstance(node, (CallExpr,)):
        return f"[bold]{cls}[/bold] [green]{node.name!r}[/green]"

    if isinstance(node, Param):
        return f"[bold]{cls}[/bold] [green]{node.name!r}[/green]"

    lineno_str = (f" [dim](l.{node.lineno})[/dim]"
                  if getattr(node, 'lineno', None) else "")
    return f"[bold]{cls}[/bold]{lineno_str}"


def _build_rich_tree(node, tree=None):
    """
    Construye recursivamente un rich.tree.Tree a partir de un nodo del AST.
    Si `tree` es None se crea la raíz; si se pasa, se añaden ramas al nodo dado.
    """
    from rich.tree import Tree

    label = _node_label(node)
    branch = Tree(label) if tree is None else tree.add(label)

    # Iteramos sobre los campos del nodo (excepto 'lineno')
    for field, value in node.__dict__.items():
        if field == 'lineno':
            continue

        if isinstance(value, ASTNode):
            # Campo que es otro nodo: lo expandimos
            _build_rich_tree(value, branch)

        elif isinstance(value, list):
            # Lista de hijos: añadimos un sub-árbol etiquetado con el campo
            if value:                           # omitimos listas vacías
                list_branch = branch.add(f"[dim].{field}[/dim]")
                for item in value:
                    if isinstance(item, ASTNode):
                        _build_rich_tree(item, list_branch)
                    else:
                        list_branch.add(f"[yellow]{item!r}[/yellow]")

        else:
            # Valor escalar: solo se muestra si no está ya en la etiqueta del nodo
            _is_in_label = field in ('name', 'op', 'value') and (
                isinstance(node, (Identifier, BinOp, UnaryOp,
                                   IntLiteral, FloatLiteral, CharLiteral,
                                   StringLiteral, BoolLiteral,
                                   SimpleType, Param,
                                   VarDecl, VarDeclInit, ConstDecl,
                                   ArrayDecl, ArrayDeclInit,
                                   FuncDecl, FuncDeclInit, CallExpr))
            )
            if not _is_in_label and value is not None:
                branch.add(f"[dim].{field}[/dim] = [yellow]{value!r}[/yellow]")

    return branch if tree is None else tree


def show_rich_tree(ast):
    """
    Muestra el AST como árbol en la terminal usando Rich Tree.
    Punto de entrada público para la visualización en consola.
    """
    from rich.console import Console
    from rich.tree    import Tree

    console = Console()
    console.print()
    console.rule("[bold]AST — Rich Tree[/bold]")

    if ast is None:
        console.print("[red]AST vacío (None)[/red]")
        return

    tree = _build_rich_tree(ast)
    console.print(tree)
    console.print()


# =============================================================================
# VISUALIZACIÓN — Graphviz
# =============================================================================

# =============================================================================
# GRAPHVIZ — estilo fiel a la imagen de referencia
#
# Dos tipos de nodo:
#   • Nodo AST  → rectángulo redondeado, relleno azul claro (#AED6F1), texto negro
#   • Hoja escalar → óvalo blanco, borde negro, texto negro
# Las aristas llevan el nombre del campo como etiqueta.
# =============================================================================

# Nombres cortos que se muestran en el nodo (sin prefijo de clase)
_SHORT_NAMES = {
    'FuncDeclInit': 'DeclInit',
    'VarDeclInit':  'DeclInit',
    'ArrayDeclInit':'DeclInit',
    'FuncDecl':     'FuncDecl',
    'VarDecl':      'VarDecl',
    'ArrayDecl':    'ArrayDecl',
    'ConstDecl':    'ConstDecl',
    'FuncType':     'FuncType',
    'ArrayType':    'ArrayType',
    'ArrayTypeSized':'ArrayType',
    'SimpleType':   'SimpleType',
    'Param':        'Param',
    'Block':        'Block',
    'IfStmt':       'If',
    'WhileStmt':    'While',
    'ForStmt':      'For',
    'PrintStmt':    'Print',
    'ReturnStmt':   'Return',
    'BreakStmt':    'Break',
    'ContinueStmt': 'Continue',
    'ExprStmt':     'ExprStmt',
    'Assign':       'Assign',
    'BinOp':        'BinOp',
    'UnaryOp':      'UnaryOp',
    'CallExpr':     'Call',
    'IndexExpr':    'Index',
    'Identifier':   'Name',
    'IntLiteral':   'Literal',
    'FloatLiteral': 'Literal',
    'CharLiteral':  'Literal',
    'StringLiteral':'Literal',
    'BoolLiteral':  'Literal',
    'Program':      'Program',
    'DerefExpr':    'Deref',
}

# Campos escalares que cada clase expone como hojas
# (todos los demás campos escalares se ignoran o ya son ASTNode/list)
_SCALAR_FIELDS = {
    'FuncDeclInit':  ['name'],
    'VarDeclInit':   ['name'],
    'ArrayDeclInit': ['name'],
    'FuncDecl':      ['name'],
    'VarDecl':       ['name'],
    'ArrayDecl':     ['name'],
    'ConstDecl':     ['name'],
    'SimpleType':    ['name'],
    'Param':         ['name'],
    'Identifier':    ['name'],
    'CallExpr':      ['name'],
    'IndexExpr':     ['name'],
    'BinOp':         ['op'],
    'UnaryOp':       ['op'],
    'IntLiteral':    ['value'],
    'FloatLiteral':  ['value'],
    'CharLiteral':   ['value'],
    'StringLiteral': ['value'],
    'BoolLiteral':   ['value'],
}

# Etiquetas amigables para los campos al mostrarse en aristas
_FIELD_LABELS = {
    'name':       'name',
    'vartype':    'typ',
    'arrtype':    'typ',
    'functype':   'typ',
    'paramtype':  'typ',
    'elem_type':  'elem',
    'ret_type':   'ret',
    'params':     'params',
    'value':      'value',
    'body':       'body',
    'stmts':      'stmts',
    'decls':      'decls',
    'exprs':      'values',
    'args':       'args',
    'elements':   'elems',
    'cond':       'cond',
    'then_branch':'then',
    'else_branch':'else',
    'init':       'init',
    'update':     'update',
    'target':     'target',
    'left':       'left',
    'right':      'right',
    'operand':    'operand',
    'index':      'index',
    'size':       'size',
    'op':         'op',
}


def _leaf(dot, text):
    """Crea un nodo hoja (óvalo blanco) y devuelve su id."""
    import uuid
    nid = 'n' + str(uuid.uuid4()).replace('-', '')
    # Escapar caracteres HTML especiales
    safe = (str(text)
            .replace('&', '&amp;')
            .replace('<', '&lt;')
            .replace('>', '&gt;')
            .replace('"', '&quot;'))
    dot.node(nid, label=safe,
             shape='ellipse',
             style='',
             fillcolor='white',
             fontcolor='black',
             fontname='Helvetica',
             fontsize='11',
             color='black')
    return nid


def _ast_node(dot, label):
    """Crea un nodo AST (rectángulo redondeado azul) y devuelve su id."""
    import uuid
    nid = 'n' + str(uuid.uuid4()).replace('-', '')
    dot.node(nid, label=label,
             shape='box',
             style='filled,rounded',
             fillcolor="#9EEBAF",
             fontcolor='black',
             fontname='Helvetica',
             fontsize='11',
             color="#1E5040",
             margin='0.18,0.10')
    return nid


def _edge(dot, src, dst, label=''):
    """Añade una arista con etiqueta de campo."""
    dot.edge(src, dst,
             label=label,
             fontsize='9',
             fontcolor='#424242',
             color='black')


def _build_graphviz(node, dot, parent_id=None, edge_label=''):
    """
    Recorre el AST y construye el grafo con el estilo de la imagen de referencia.
    - Nodos AST: rectángulos redondeados azules con el nombre corto de la clase.
    - Hojas escalares: óvalos blancos con el valor.
    - Aristas: etiquetadas con el nombre del campo.
    """
    cls   = node.__class__.__name__
    label = _SHORT_NAMES.get(cls, cls)
    nid   = _ast_node(dot, label)

    if parent_id is not None:
        _edge(dot, parent_id, nid, edge_label)

    # ── 1. Campos escalares propios de esta clase ─────────────────────────────
    for field in _SCALAR_FIELDS.get(cls, []):
        val = getattr(node, field, None)
        if val is None:
            continue
        # Mostrar None explícito solo si es significativo (e.g. return sin valor)
        leaf_id = _leaf(dot, val)
        flabel  = _FIELD_LABELS.get(field, field)
        _edge(dot, nid, leaf_id, flabel)

    # ── 2. Campos estructurales (ASTNode o lista) ─────────────────────────────
    skip = set(_SCALAR_FIELDS.get(cls, []))   # ya procesados arriba

    for field, value in node.__dict__.items():
        if field in ('lineno',) or field in skip:
            continue

        flabel = _FIELD_LABELS.get(field, field)

        if isinstance(value, ASTNode):
            _build_graphviz(value, dot, nid, flabel)

        elif isinstance(value, list):
            for item in value:
                if isinstance(item, ASTNode):
                    _build_graphviz(item, dot, nid, flabel)
                # escalares sueltos en listas (raro, pero por si acaso)
                elif item is not None:
                    leaf_id = _leaf(dot, item)
                    _edge(dot, nid, leaf_id, flabel)

        elif value is None and field in ('else_branch', 'value',
                                          'init', 'cond', 'update'):
            # Mostrar None explícito solo para campos opcionales relevantes
            leaf_id = _leaf(dot, 'None')
            _edge(dot, nid, leaf_id, flabel)

    return nid


def save_graphviz(ast, output='ast', fmt='png', view=False):
    """
    Genera el grafo Graphviz del AST y lo guarda/renderiza.

    Parámetros
    ----------
    ast    : nodo raíz del AST (Program)
    output : nombre base del archivo de salida (sin extensión)
    fmt    : formato de imagen: 'png', 'svg', 'pdf', etc.
    view   : si True abre el archivo generado con el visor del SO
    """
    try:
        from graphviz import Digraph
    except ImportError:
        rich.print("[red]graphviz no instalado. Ejecuta:  pip install graphviz[/red]")
        return

    dot = Digraph(name='AST', comment='Árbol de Sintaxis Abstracta — B-Minor')
    dot.attr(
        rankdir='TB',
        bgcolor='white',
        fontname='Helvetica',
        splines='polyline',
        nodesep='0.45',
        ranksep='0.65',
    )

    if ast is None:
        rich.print("[red]AST vacío (None) — no se genera el grafo.[/red]")
        return

    _build_graphviz(ast, dot)

    out_path = dot.render(output, format=fmt, view=view, cleanup=True)
    rich.print(f"[green]✔  Grafo Graphviz guardado en:[/green] [bold]{out_path}[/bold]")
    return out_path


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
    import argparse

    ap = argparse.ArgumentParser(
        description='Parser B-Minor con visualización de AST',
        epilog=(
            'Ejemplos:\n'
            '  python parser.py prog.bminor          # ambas visualizaciones\n'
            '  python parser.py prog.bminor --rich   # solo Rich Tree\n'
            '  python parser.py prog.bminor --gv     # solo Graphviz\n'
            '  python parser.py prog.bminor --gv --gv-fmt svg --view'
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ap.add_argument('filename',             help='Archivo fuente .bminor')
    ap.add_argument('--rich',  action='store_true',
                    help='Mostrar el AST como Rich Tree en consola')
    ap.add_argument('--gv',    action='store_true',
                    help='Generar el grafo Graphviz del AST')
    ap.add_argument('--gv-out', default='ast',
                    help='Nombre base del archivo Graphviz (default: ast)')
    ap.add_argument('--gv-fmt', default='png',
                    help='Formato Graphviz: png, svg, pdf… (default: png)')
    ap.add_argument('--view',   action='store_true',
                    help='Abrir el grafo generado con el visor del SO')
    args = ap.parse_args()

    # Si el usuario no especifica ningún modo, se activan ambos por defecto
    run_rich = args.rich or (not args.rich and not args.gv)
    run_gv   = args.gv   or (not args.rich and not args.gv)

    rich.print(f"\n{'='*60}")
    rich.print(f"  Analizando: {args.filename}")
    rich.print(f"{'='*60}\n")

    txt = open(args.filename, encoding='utf-8').read()
    ast = parse(txt)

    if not errors_detected():
        rich.print("✔  Análisis sintáctico exitoso — sin errores.\n")

        # ── Visualización en consola (Rich Tree) ──────────────────────────────
        if run_rich:
            show_rich_tree(ast)

        # ── Grafo Graphviz ────────────────────────────────────────────────────
        if run_gv:
            save_graphviz(ast,
                          output=args.gv_out,
                          fmt=args.gv_fmt,
                          view=args.view)
    else:
        rich.print(f"\n✘  Se encontraron {errors_detected()} error(es) sintáctico(s).")