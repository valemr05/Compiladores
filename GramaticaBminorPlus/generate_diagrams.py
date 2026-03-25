"""
Railroad Diagram Generator – Gramática completa
================================================
Genera diagramas SVG estilo "railroad" (syntax diagrams) para cada
regla de la gramática, sin dependencias externas.

Salida:
  out/svg/<nombre_regla>.svg   – un archivo SVG por regla
  out/index.md                 – atlas compatible con Obsidian
"""

import os
import math
from typing import List, Union
from typing import Optional as Opt_type

# ─────────────────────────────────────────────────────────────
# PRIMITIVAS SVG
# ─────────────────────────────────────────────────────────────

# Constantes de diseño
FONT        = "Consolas, 'Courier New', monospace"
FONT_SIZE   = 13
PADDING     = 10          # padding interno de las cajas
BOX_H       = 28          # altura de caja terminal/no-terminal
ARC_R       = 12          # radio de arco de esquinas
LINE_H      = BOX_H       # altura de línea del riel
GAP_H       = 14          # espacio vertical entre ramas de Choice
GAP_W       = 20          # espacio horizontal entre items de Sequence
MARGIN_X    = 30          # margen izquierdo/derecho del diagrama
MARGIN_Y    = 20          # margen superior/inferior

def text_width(s: str) -> int:
    """Estimación del ancho en píxeles de una cadena monoespaciada."""
    return max(len(s) * 8 + PADDING * 2, 30)

# ─────────────────────────────────────────────────────────────
# NODOS DEL DIAGRAMA (árbol de layout)
# ─────────────────────────────────────────────────────────────

class Node:
    """Base para todos los nodos del diagrama."""
    def __init__(self):
        self.width  = 0   # ancho total
        self.height = 0   # alto total
        self.entry  = 0   # offset Y desde top hasta el riel de entrada
        self.exit   = 0   # offset Y desde top hasta el riel de salida (igual a entry para horizontal)

    def layout(self):
        """Calcula width, height, entry, exit."""
        raise NotImplementedError

    def render(self, x: int, y: int, svg: list):
        """
        Dibuja el nodo a partir de (x, y) siendo y el top del bounding box.
        Escribe strings SVG en la lista `svg`.
        """
        raise NotImplementedError


class Terminal(Node):
    """
    Caja redondeada con texto – representa un token terminal.
    Se dibuja con rectángulo de esquinas redondeadas y fondo claro.
    """
    def __init__(self, label: str):
        super().__init__()
        self.label = label

    def layout(self):
        self.width  = text_width(self.label)
        self.height = BOX_H
        self.entry  = BOX_H // 2
        self.exit   = self.entry

    def render(self, x, y, svg):
        rx = 5
        ry = 5
        fill   = "#ddeeff"
        stroke = "#336699"
        cx = x + self.width / 2
        cy = y + self.height / 2
        svg.append(
            f'<rect x="{x}" y="{y}" width="{self.width}" height="{self.height}" '
            f'rx="{rx}" ry="{ry}" fill="{fill}" stroke="{stroke}" stroke-width="1.5"/>'
        )
        svg.append(
            f'<text x="{cx:.1f}" y="{cy + FONT_SIZE//3:.1f}" '
            f'text-anchor="middle" font-family="{FONT}" font-size="{FONT_SIZE}" fill="#003366">'
            f'{_escape(self.label)}</text>'
        )


class NonTerminal(Node):
    """
    Caja rectangular – representa un no-terminal (referencia a regla).
    Sin esquinas redondeadas, fondo blanco.
    """
    def __init__(self, label: str):
        super().__init__()
        self.label = label

    def layout(self):
        self.width  = text_width(self.label)
        self.height = BOX_H
        self.entry  = BOX_H // 2
        self.exit   = self.entry

    def render(self, x, y, svg):
        fill   = "#ffffff"
        stroke = "#444444"
        cx = x + self.width / 2
        cy = y + self.height / 2
        svg.append(
            f'<rect x="{x}" y="{y}" width="{self.width}" height="{self.height}" '
            f'fill="{fill}" stroke="{stroke}" stroke-width="1.5"/>'
        )
        svg.append(
            f'<text x="{cx:.1f}" y="{cy + FONT_SIZE//3:.1f}" '
            f'text-anchor="middle" font-family="{FONT}" font-size="{FONT_SIZE}" '
            f'font-style="italic" fill="#222222">'
            f'{_escape(self.label)}</text>'
        )


class Epsilon(Node):
    """Flecha directa – representa la producción vacía (ε)."""
    def layout(self):
        self.width  = 40
        self.height = BOX_H
        self.entry  = BOX_H // 2
        self.exit   = self.entry

    def render(self, x, y, svg):
        mid_y = y + self.entry
        svg.append(f'<text x="{x + self.width/2:.1f}" y="{mid_y + FONT_SIZE//3:.1f}" '
                   f'text-anchor="middle" font-family="{FONT}" font-size="{FONT_SIZE}" fill="#888">ε</text>')
        _hline(x, x + self.width, mid_y, svg)


class Sequence(Node):
    """
    Concatenación horizontal de nodos.
    El riel de entrada/salida está en la misma altura.
    """
    def __init__(self, children: List[Node]):
        super().__init__()
        self.children = children

    def layout(self):
        for c in self.children:
            c.layout()
        # Todos los rieles se alinean; tomamos el entry máximo
        max_entry = max(c.entry for c in self.children) if self.children else 0
        total_h   = 0
        for c in self.children:
            bottom = max_entry - c.entry + c.height
            total_h = max(total_h, bottom)
        self.entry  = max_entry
        self.exit   = max_entry
        self.height = total_h
        self.width  = sum(c.width for c in self.children) + GAP_W * max(0, len(self.children) - 1)

    def render(self, x, y, svg):
        max_entry = self.entry
        cx = x
        for i, c in enumerate(self.children):
            cy = y + (max_entry - c.entry)
            c.render(cx, cy, svg)
            # Línea de conexión entre elementos
            if i < len(self.children) - 1:
                lx0 = cx + c.width
                lx1 = cx + c.width + GAP_W
                mid_y = y + max_entry
                _hline(lx0, lx1, mid_y, svg)
                _arrowhead(lx1, mid_y, svg)
            cx += c.width + GAP_W


class Choice(Node):
    """
    Alternativas verticales (|).
    La rama 0 es la línea principal (más alta).
    Las ramas adicionales van por debajo conectadas con arcos.
    """
    def __init__(self, children: List[Node]):
        super().__init__()
        self.children = children

    def layout(self):
        for c in self.children:
            c.layout()
        # Ancho = máximo de todos los hijos + espacio para arcos laterales
        max_w = max(c.width for c in self.children) if self.children else 0
        self.width = max_w + ARC_R * 4

        # Rama principal (primera) define la altura de entrada
        first = self.children[0]
        self.entry = first.entry + ARC_R

        total_h = first.height + ARC_R
        for c in self.children[1:]:
            total_h += GAP_H + c.height
        total_h += ARC_R
        self.height = total_h
        self.exit   = self.entry

    def render(self, x, y, svg):
        first      = self.children[0]
        rail_y     = y + self.entry     # y absoluta del riel principal
        arc        = ARC_R

        # ─── Rama principal ─────────────────────────────────────────
        inner_x    = x + arc * 2
        inner_w    = self.width - arc * 4

        # Conexión izquierda  y derecha en el riel para la rama 0
        first_top  = y + arc
        first_cx   = inner_x + (inner_w - first.width) // 2
        _hline(x, first_cx, rail_y, svg)
        first.render(first_cx, first_top, svg)
        _hline(first_cx + first.width, inner_x + inner_w, rail_y, svg)

        # ─── Ramas alternativas ──────────────────────────────────────
        cur_y = first_top + first.height + GAP_H

        for idx, c in enumerate(self.children[1:], 1):
            c_rail_y = cur_y + c.entry  # y absoluta del riel de esta rama
            c_cx     = inner_x + (inner_w - c.width) // 2

            # Arco bajando por la izquierda: del riel principal hacia c_rail_y
            _arc_down_left (x,                 rail_y,   c_rail_y, arc, svg)
            _hline          (x + arc,           c_cx,     c_rail_y, svg)
            c.render(c_cx, cur_y, svg)
            _hline          (c_cx + c.width,    x + self.width - arc,  c_rail_y, svg)
            _arc_up_right   (x + self.width,    c_rail_y, rail_y,   arc, svg)

            cur_y += c.height + GAP_H

        # Flechas en el riel principal
        _arrowhead(inner_x + (inner_w - first.width)//2 + first.width + 2, rail_y, svg)


class Optional(Node):
    """
    Nodo opcional – equivale a Choice([child, Epsilon()]).
    Muestra el hijo con un bypass encima.
    """
    def __init__(self, child: Node):
        super().__init__()
        self.child = child

    def layout(self):
        self.child.layout()
        arc = ARC_R
        self.width  = self.child.width + arc * 4
        self.entry  = self.child.entry + arc
        self.exit   = self.entry
        self.height = self.child.height + arc * 2

    def render(self, x, y, svg):
        arc     = ARC_R
        rail_y  = y + self.entry
        cx      = x + arc * 2
        bypass_y = y                        # tope del bypass (encima del riel)

        # Rama principal (child) — en el riel
        self.child.render(cx, y + arc, svg)
        _hline(x + arc, cx, rail_y, svg)
        _hline(cx + self.child.width, x + self.width - arc, rail_y, svg)
        _arrowhead(cx + 2, rail_y, svg)

        # Bypass superior (ε) — sale del riel, sube, cruza, baja de vuelta
        _arc_up_left        (x,              rail_y,  bypass_y, arc, svg)
        _hline              (x + arc,        x + self.width - arc, bypass_y, svg)
        _arc_up_right_bypass(x + self.width, bypass_y, rail_y,  arc, svg)
        _arrowhead(x + self.width // 2, bypass_y, svg, direction="right")


class Repeat(Node):
    """
    Nodo de repetición (1 o más veces).
    El hijo se recorre hacia adelante; el arco de vuelta va por abajo.
    """
    def __init__(self, child: Node, separator: Opt_type[Node] = None):
        super().__init__()
        self.child     = child
        self.separator = separator

    def layout(self):
        self.child.layout()
        arc = ARC_R
        sep_w = 0
        if self.separator:
            self.separator.layout()
            sep_w = self.separator.width
        back_h = GAP_H * 2
        self.width  = max(self.child.width, sep_w) + arc * 4
        self.entry  = self.child.entry + arc
        self.exit   = self.entry
        self.height = self.child.height + arc + back_h

    def render(self, x, y, svg):
        arc    = ARC_R
        rail_y = y + self.entry
        cx     = x + arc * 2
        back_y = y + self.height - arc

        # Dibuja el hijo
        self.child.render(cx, y + arc, svg)
        _hline(x + arc,               cx,                    rail_y, svg)
        _hline(cx + self.child.width,  x + self.width - arc, rail_y, svg)
        _arrowhead(cx + 2, rail_y, svg)

        # Arco de retorno por debajo:
        # Izquierdo: baja del riel al back_y
        _arc_down_left(x, rail_y, back_y, arc, svg)
        _hline(x + arc, x + self.width - arc, back_y, svg)
        # Derecho: sube de back_y al riel
        _arc_down_right(x + self.width, back_y, rail_y, arc, svg)
        _arrowhead(x + arc + 2, back_y, svg, direction="left")

        if self.separator:
            sep_cx = x + arc * 2 + (self.child.width - self.separator.width) // 2
            self.separator.render(sep_cx, back_y - self.separator.entry, svg)


# ─────────────────────────────────────────────────────────────
# HELPERS SVG (líneas, arcos, flechas)
# ─────────────────────────────────────────────────────────────

def _escape(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

def _hline(x0, x1, y, svg):
    if x1 > x0:
        svg.append(f'<line x1="{x0:.1f}" y1="{y:.1f}" x2="{x1:.1f}" y2="{y:.1f}" '
                   f'stroke="#555" stroke-width="1.5"/>')

def _vline(x, y0, y1, svg):
    if y1 > y0:
        svg.append(f'<line x1="{x:.1f}" y1="{y0:.1f}" x2="{x:.1f}" y2="{y1:.1f}" '
                   f'stroke="#555" stroke-width="1.5"/>')

def _arrowhead(x, y, svg, direction="right"):
    s = 5
    if direction == "right":
        pts = f"{x},{y} {x-s},{y-s//2} {x-s},{y+s//2}"
    else:
        pts = f"{x},{y} {x+s},{y-s//2} {x+s},{y+s//2}"
    svg.append(f'<polygon points="{pts}" fill="#555"/>')

def _arc(x1, y1, x2, y2, cx, cy, svg):
    """Arco Bezier cuadrático de (x1,y1) a (x2,y2) con punto de control (cx,cy)."""
    svg.append(f'<path d="M {x1:.1f} {y1:.1f} Q {cx:.1f} {cy:.1f} {x2:.1f} {y2:.1f}" '
               f'fill="none" stroke="#555" stroke-width="1.5"/>')

def _arc_down_left(x, rail_y, branch_y, arc, svg):
    """
    Conector izquierdo: sale del riel principal (x, rail_y) baja hasta la rama (x+arc, branch_y).
    Traza: línea vertical de rail_y → branch_y-arc, luego arco esquina inferior-derecha.
    """
    _vline(x, rail_y, branch_y - arc, svg)
    _arc(x, branch_y - arc,  x + arc, branch_y,  x, branch_y, svg)

def _arc_up_right(x, branch_y, rail_y, arc, svg):
    """
    Conector derecho: sale de la rama (x-arc, branch_y) y sube al riel principal (x, rail_y).
    Traza: arco esquina inferior-derecha, luego línea vertical de rail_y hacia abajo hasta branch_y+arc.
    branch_y > rail_y (la rama está debajo del riel), entonces rail_y < branch_y+arc → _vline OK.
    """
    _arc(x - arc, branch_y,  x, branch_y + arc,  x, branch_y, svg)
    _vline(x, rail_y, branch_y + arc, svg)  # FIX: rail_y primero (es menor), branch_y+arc después

def _arc_up_left(x, rail_y, bypass_y, arc, svg):
    """
    Bypass izquierdo para Optional: sale del riel (x, rail_y) sube al bypass (x+arc, bypass_y).
    Traza: línea vertical de rail_y → bypass_y+arc, luego arco esquina superior-derecha.
    """
    _vline(x, bypass_y + arc, rail_y, svg)
    _arc(x, bypass_y + arc,  x + arc, bypass_y,  x, bypass_y, svg)

def _arc_up_right_bypass(x, bypass_y, rail_y, arc, svg):
    """
    Bypass derecho para Optional: sale del bypass (x-arc, bypass_y) baja al riel (x, rail_y).
    Traza: arco esquina superior-derecha, luego línea vertical bypass_y+arc → rail_y.
    """
    _arc(x - arc, bypass_y,  x, bypass_y + arc,  x, bypass_y, svg)
    _vline(x, bypass_y + arc, rail_y, svg)

def _arc_down_right(x, back_y, rail_y, arc, svg):
    """
    Arco de retorno derecho para Repeat: sale de back (x-arc, back_y) sube a rail (x, rail_y).
    Traza: arco esquina inferior-derecha desde back_y, luego línea vertical hasta rail_y.
    """
    _arc(x - arc, back_y,  x, back_y - arc,  x, back_y, svg)
    _vline(x, rail_y, back_y - arc, svg)


# ─────────────────────────────────────────────────────────────
# CONSTRUCTOR DEL DIAGRAMA COMPLETO
# ─────────────────────────────────────────────────────────────

def build_diagram(rule_name: str, root: Node) -> str:
    """
    Construye el SVG completo para una regla.
    Incluye líneas de entrada/salida del riel principal y el título.
    """
    root.layout()

    inner_w = root.width
    inner_h = root.height

    title_h = 22
    total_w = inner_w + MARGIN_X * 2 + ARC_R * 4   # espacio para líneas de riel
    total_h = inner_h + MARGIN_Y * 2 + title_h

    svg = []
    svg.append(f'<svg xmlns="http://www.w3.org/2000/svg" '
               f'width="{total_w}" height="{total_h}" '
               f'viewBox="0 0 {total_w} {total_h}">')
    svg.append('<rect width="100%" height="100%" fill="#fafafa" rx="8" ry="8"/>')

    # Título
    svg.append(f'<text x="{MARGIN_X}" y="{title_h - 4}" '
               f'font-family="{FONT}" font-size="14" font-weight="bold" fill="#222">'
               f'{_escape(rule_name)}</text>')

    # Riel
    node_x = MARGIN_X + ARC_R * 2
    node_y = MARGIN_Y + title_h
    rail_y = node_y + root.entry

    # Líneas de entrada/salida
    _hline(MARGIN_X, node_x, rail_y, svg)
    _arrowhead(node_x, rail_y, svg)
    _hline(node_x + inner_w, total_w - MARGIN_X, rail_y, svg)

    # Marcas de inicio y fin
    svg.append(f'<circle cx="{MARGIN_X}" cy="{rail_y}" r="5" fill="#555"/>')
    svg.append(f'<circle cx="{total_w - MARGIN_X}" cy="{rail_y}" r="5" fill="#555" '
               f'stroke="#555" stroke-width="2"/>')
    svg.append(f'<circle cx="{total_w - MARGIN_X}" cy="{rail_y}" r="3" fill="#fafafa"/>')

    # Nodo
    root.render(node_x, node_y, svg)

    svg.append('</svg>')
    return '\n'.join(svg)


# ─────────────────────────────────────────────────────────────
# DEFINICIÓN DE LA GRAMÁTICA
# ─────────────────────────────────────────────────────────────
#
# Convenciones:
#   T("token")    → Terminal
#   NT("regla")   → NonTerminal
#   Seq([...])    → Sequence
#   Ch([...])     → Choice
#   Opt(nodo)     → Optional (0 o 1 veces)
#   Rep(nodo)     → Repeat   (1 o más)
#   Eps()         → Epsilon

def T(s):  return Terminal(s)
def NT(s): return NonTerminal(s)
def Seq(children): return Sequence(children)
def Ch(children):  return Choice(children)
def Opt(c):        return Optional(c)
def Rep(c, sep=None): return Repeat(c, sep)
def Eps():         return Epsilon()


GRAMMAR = {

    # ── Programa ─────────────────────────────────────────────
    "prog": Seq([NT("decl_list"), T("EOF")]),

    # ── Listas de declaraciones ───────────────────────────────
    # Gramática: decl_list ::= ε | decl decl_list
    # Recursión derecha: la segunda rama es decl seguido de decl_list (recursiva)
    "decl_list": Ch([
        Eps(),
        Seq([NT("decl"), NT("decl_list")]),
    ]),

    # ── Declaración ──────────────────────────────────────────
    "decl": Ch([
        Seq([T("ID"), T(":"), NT("type_simple"), T(";")]),
        Seq([T("ID"), T(":"), NT("type_array_sized"), T(";")]),
        Seq([T("ID"), T(":"), NT("type_func"), T(";")]),
        NT("decl_init"),
        NT("class_decl"),
    ]),

    # ── Declaración con inicialización ───────────────────────
    "decl_init": Ch([
        Seq([T("ID"), T(":"), NT("type_simple"), T("="), NT("expr"), T(";")]),
        Seq([T("ID"), T(":"), NT("type_array_sized"), T("="),
             T("{"), NT("opt_expr_list"), T("}"), T(";")]),
        Seq([T("ID"), T(":"), NT("type_func"), T("="),
             T("{"), NT("opt_stmt_list"), T("}")]),
    ]),

    # ── Clases ───────────────────────────────────────────────
    "class_decl": Seq([
        T("CLASS"), T("ID"), T("{"), NT("class_body"), T("}")
    ]),

    # Gramática: class_body ::= ε | class_member class_body
    # Recursión derecha: class_member seguido de class_body (recursiva)
    "class_body": Ch([
        Eps(),
        Seq([NT("class_member"), NT("class_body")]),
    ]),

    "class_member": NT("decl"),

    # ── lval ─────────────────────────────────────────────────
    "lval": Ch([
        T("ID"),
        Seq([T("ID"), NT("index")]),
    ]),

    "lval_obj": Ch([
        Seq([NT("lval_obj"), T("."), T("ID")]),
        NT("lval"),
    ]),

    # ── Sentencias ────────────────────────────────────────────
    "opt_stmt_list": Ch([
        Eps(),
        NT("stmt_list"),
    ]),

    "stmt_list": Ch([
        NT("stmt"),
        Seq([NT("stmt"), NT("stmt_list")]),
    ]),

    "stmt": Ch([
        NT("open_stmt"),
        NT("closed_stmt"),
    ]),

    "closed_stmt": Ch([
        NT("if_stmt_closed"),
        NT("for_stmt_closed"),
        NT("simple_stmt"),
        NT("while_stmt_closed"),
    ]),

    "open_stmt": Ch([
        NT("if_stmt_open"),
        NT("for_stmt_open"),
        NT("while_stmt_open"),
    ]),

    # ── If ───────────────────────────────────────────────────
    "if_cond": Seq([T("IF"), T("("), NT("opt_expr"), T(")")]),

    "if_stmt_closed": Seq([
        NT("if_cond"), NT("closed_stmt"), T("ELSE"), NT("closed_stmt")
    ]),

    "if_stmt_open": Ch([
        Seq([NT("if_cond"), NT("stmt")]),
        Seq([NT("if_cond"), NT("closed_stmt"), T("ELSE"), NT("if_stmt_open")]),
    ]),

    # ── For ──────────────────────────────────────────────────
    "for_header": Seq([
        T("FOR"), T("("),
        NT("opt_expr"), T(";"),
        NT("opt_expr"), T(";"),
        NT("opt_expr"),
        T(")")
    ]),

    "for_stmt_open":   Seq([NT("for_header"), NT("open_stmt")]),
    "for_stmt_closed": Seq([NT("for_header"), NT("closed_stmt")]),

    # ── While ────────────────────────────────────────────────
    "while_stmt_closed": Seq([T("WHILE"), T("("), NT("opt_expr"), T(")"), NT("closed_stmt")]),
    "while_stmt_open":   Seq([T("WHILE"), T("("), NT("opt_expr"), T(")"), NT("open_stmt")]),

    # ── Simple statements ─────────────────────────────────────
    "simple_stmt": Ch([
        NT("print_stmt"),
        NT("return_stmt"),
        NT("block_stmt"),
        NT("decl"),
        Seq([NT("expr"), T(";")]),
    ]),

    "print_stmt":  Seq([T("PRINT"),  NT("opt_expr_list"), T(";")]),
    "return_stmt": Seq([T("RETURN"), NT("opt_expr"),      T(";")]),
    "block_stmt":  Seq([T("{"), NT("stmt_list"), T("}")]),

    # ── Expresiones ──────────────────────────────────────────
    "opt_expr_list": Ch([
        Eps(),
        NT("expr_list"),
    ]),

    "expr_list": Ch([
        NT("expr"),
        Seq([NT("expr"), T(","), NT("expr_list")]),
    ]),

    "opt_expr": Ch([
        Eps(),
        NT("expr"),
    ]),

    "expr": NT("expr_cond"),

    # ── Ternario ─────────────────────────────────────────────
    "expr_cond": Ch([
        Seq([NT("expr1"), T("?"), NT("expr"), T(":"), NT("expr_cond")]),
        NT("expr1"),
    ]),

    # ── Asignaciones ─────────────────────────────────────────
    "expr1": Ch([
        Seq([NT("lval_obj"), T("="),  NT("expr1")]),
        Seq([NT("lval_obj"), T("+="), NT("expr1")]),
        Seq([NT("lval_obj"), T("-="), NT("expr1")]),
        Seq([NT("lval_obj"), T("*="), NT("expr1")]),
        Seq([NT("lval_obj"), T("/="), NT("expr1")]),
        NT("expr2"),
    ]),

    # ── Operadores binarios (precedencia) ─────────────────────
    "expr2": Ch([
        Seq([NT("expr2"), T("LOR"), NT("expr3")]),
        NT("expr3"),
    ]),

    "expr3": Ch([
        Seq([NT("expr3"), T("LAND"), NT("expr4")]),
        NT("expr4"),
    ]),

    "expr4": Ch([
        Seq([NT("expr4"), T("EQ"), NT("expr5")]),
        Seq([NT("expr4"), T("NE"), NT("expr5")]),
        Seq([NT("expr4"), T("LT"), NT("expr5")]),
        Seq([NT("expr4"), T("LE"), NT("expr5")]),
        Seq([NT("expr4"), T("GT"), NT("expr5")]),
        Seq([NT("expr4"), T("GE"), NT("expr5")]),
        NT("expr5"),
    ]),

    "expr5": Ch([
        Seq([NT("expr5"), T("+"), NT("expr6")]),
        Seq([NT("expr5"), T("-"), NT("expr6")]),
        NT("expr6"),
    ]),

    "expr6": Ch([
        Seq([NT("expr6"), T("*"), NT("expr7")]),
        Seq([NT("expr6"), T("/"), NT("expr7")]),
        Seq([NT("expr6"), T("%"), NT("expr7")]),
        NT("expr7"),
    ]),

    "expr7": Ch([
        Seq([NT("expr7"), T("^"), NT("expr8")]),
        NT("expr8"),
    ]),

    "expr8": Ch([
        Seq([T("INC"), NT("expr8")]),
        Seq([T("DEC"), NT("expr8")]),
        Seq([T("-"), NT("expr8")]),
        Seq([T("NOT"), NT("expr8")]),
        NT("expr9"),
    ]),

    "expr9": Ch([
        Seq([NT("expr9"), T("INC")]),
        Seq([NT("expr9"), T("DEC")]),
        Seq([NT("expr9"), T("."), T("ID")]),
        Seq([NT("expr9"), T("."), T("ID"), T("("), NT("opt_expr_list"), T(")")]),
        NT("group"),
    ]),

    # ── Group / factor / index ────────────────────────────────
    "group": Ch([
        Seq([T("("), NT("expr"), T(")")]),
        Seq([T("ID"), T("("), NT("opt_expr_list"), T(")")]),
        Seq([T("ID"), NT("index")]),
        NT("factor"),
        Seq([T("NEW"), T("ID"), T("("), NT("opt_expr_list"), T(")")]),
    ]),

    "index_list": Ch([
        Seq([NT("index_list"), NT("index")]),
        NT("index"),
    ]),

    "index": Seq([T("["), NT("expr"), T("]")]),

    "factor": Ch([
        T("ID"),
        T("INTEGER_LITERAL"),
        T("FLOAT_LITERAL"),
        T("CHAR_LITERAL"),
        T("STRING_LITERAL"),
        T("TRUE"),
        T("FALSE"),
    ]),

    # ── Tipos ─────────────────────────────────────────────────
    "type_simple": Ch([
        T("INTEGER"), T("FLOAT"), T("BOOLEAN"),
        T("CHAR"), T("STRING"), T("VOID"), T("ID"),
    ]),

    "type_array": Ch([
        Seq([T("ARRAY"), T("["), T("]"), NT("type_simple")]),
        Seq([T("ARRAY"), T("["), T("]"), NT("type_array")]),
    ]),

    "type_array_sized": Ch([
        Seq([T("ARRAY"), NT("index"), NT("type_simple")]),
        Seq([T("ARRAY"), NT("index"), NT("type_array_sized")]),
    ]),

    "type_func": Ch([
        Seq([T("FUNCTION"), NT("type_simple"),       T("("), NT("opt_param_list"), T(")")]),
        Seq([T("FUNCTION"), NT("type_array_sized"),  T("("), NT("opt_param_list"), T(")")]),
    ]),

    "opt_param_list": Ch([
        Eps(),
        NT("param_list"),
    ]),

    "param_list": Ch([
        NT("param"),
        Seq([NT("param_list"), T(","), NT("param")]),
    ]),

    "param": Ch([
        Seq([T("ID"), T(":"), NT("type_simple")]),
        Seq([T("ID"), T(":"), NT("type_array")]),
        Seq([T("ID"), T(":"), NT("type_array_sized")]),
    ]),
}

# ─────────────────────────────────────────────────────────────
# CATEGORÍAS PARA EL ÍNDICE
# ─────────────────────────────────────────────────────────────

SECTIONS = {
    "Programa y Declaraciones": [
        "prog", "decl_list", "decl", "decl_init",
        "class_decl", "class_body", "class_member",
    ],
    "Valores Izquierdo (lval)": [
        "lval", "lval_obj",
    ],
    "Sentencias": [
        "opt_stmt_list", "stmt_list", "stmt",
        "closed_stmt", "open_stmt",
        "if_cond", "if_stmt_closed", "if_stmt_open",
        "for_header", "for_stmt_open", "for_stmt_closed",
        "while_stmt_closed", "while_stmt_open",
        "simple_stmt", "print_stmt", "return_stmt", "block_stmt",
    ],
    "Expresiones (precedencia ascendente)": [
        "opt_expr_list", "expr_list", "opt_expr",
        "expr", "expr_cond",
        "expr1",
        "expr2", "expr3", "expr4", "expr5",
        "expr6", "expr7", "expr8", "expr9",
        "group", "index_list", "index", "factor",
    ],
    "Tipos": [
        "type_simple", "type_array", "type_array_sized",
        "type_func", "opt_param_list", "param_list", "param",
    ],
}


# ─────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────

def main():
    out_svg = "out/svg"
    os.makedirs(out_svg, exist_ok=True)

    generated = {}
    errors = {}

    for name, root in GRAMMAR.items():
        try:
            svg_content = build_diagram(name, root)
            path = os.path.join(out_svg, f"{name}.svg")
            with open(path, "w", encoding="utf-8") as f:
                f.write(svg_content)
            generated[name] = path
            print(f"  OK  {name}.svg")
        except Exception as e:
            errors[name] = str(e)
            print(f"  ERROR  {name}: {e}")

    # ── index.md ───────────────────────────────────────────────
    lines = [
        "# Atlas de Diagramas de Sintaxis",
        "",
        "> Generado automáticamente · cada diagrama corresponde a una regla de la gramática.",
        "> **Leyenda:** cajas redondeadas = terminales · cajas rectangulares = no terminales",
        "",
    ]

    for section, rules in SECTIONS.items():
        lines.append(f"## {section}")
        lines.append("")
        for r in rules:
            if r in generated:
                lines.append(f"### `{r}`")
                lines.append(f"![[svg/{r}.svg]]")
                lines.append("")
        lines.append("---")
        lines.append("")

    with open("out/index.md", "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    print(f"\n{len(generated)} diagramas generados en out/svg/")
    if errors:
        print(f"ADVERTENCIA: {len(errors)} errores: {list(errors.keys())}")
    print("Indice: out/index.md")


if __name__ == "__main__":
    main()
