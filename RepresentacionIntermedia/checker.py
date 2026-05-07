from __future__ import annotations

from dataclasses import dataclass
import errors
from platform import node
from typing import Any, Optional
from multimethod import multimeta

from symtab import Symtab
from model import *
from typesys import check_binop, check_unaryop


class Visitor(metaclass=multimeta):
    pass


@dataclass(eq=True)
class Symbol:
    name: str
    kind: str           # var, const, param, func
    type: Any
    node: Any = None
    mutable: bool = True

    def __repr__(self):
        return f"Symbol(name={self.name!r}, kind={self.kind!r}, type={self.type!r})"


@dataclass(eq=True)
class FunctionInfo:
    ret_type: Any
    param_types: list[Any]

    def __repr__(self):
        params = ", ".join(map(str, self.param_types))
        return f"function({params}) -> {self.ret_type}"


class Checker(Visitor):
    def __init__(self):
        self.errors: list[str] = []
        self.symtab: Optional[Symtab] = None
        self.current_function: Optional[FunctionInfo] = None
        self.current_function_name: Optional[str] = None
        self.loop_depth = 0

    @classmethod
    def check(cls, node):
        checker = cls()
        checker.open_scope("global")
        checker.visit(node)
        return checker

    # -------------------------------------------------
    # Utilidades
    # -------------------------------------------------
    def error(self, node, message: str):
        lineno = getattr(node, "lineno", None)
        
        # 🟢 Llama a nuestra función mágica visual!
        errors.error(message, lineno) 
        
        # Opcional: lo sigue guardando en su lista por si su código lo usa
        self.errors.append(message)

    def ok(self) -> bool:
        return len(self.errors) == 0

    def open_scope(self, name: str):
        if self.symtab is None:
            self.symtab = Symtab(name)
        else:
            self.symtab = Symtab(name, parent=self.symtab)

    def close_scope(self):
        if self.symtab is not None:
            self.symtab = self.symtab.parent

    def define(self, node, name: str, symbol: Symbol):
        try:
            self.symtab.add(name, symbol)
        except Symtab.SymbolDefinedError:
            self.error(node, f"redeclaración de '{name}' en el mismo alcance")
        except Symtab.SymbolConflictError:
            self.error(node, f"conflicto de símbolo '{name}'")

    def lookup(self, node, name: str):
        sym = self.symtab.get(name) if self.symtab else None
        if sym is None:
            self.error(node, f"símbolo '{name}' no definido")
        return sym

    def type_name(self, typ):
        if typ is None:
            return None
        if isinstance(typ, str):
            return typ
        if isinstance(typ, SimpleType):
            return typ.name
        if isinstance(typ, ArrayType):
            return f"array[]{self.type_name(typ.elem_type)}"
        if isinstance(typ, ArrayTypeSized):
            return f"array[]{self.type_name(typ.elem_type)}"
        if isinstance(typ, FuncType):
            return FunctionInfo(
                ret_type=self.type_name(typ.ret_type),
                param_types=[self.type_name(p.paramtype) for p in typ.params],
            )
        if isinstance(typ, FunctionInfo):
            return typ
        return typ

    def same_type(self, a, b) -> bool:
        return self.type_name(a) == self.type_name(b)

    def visit_list(self, items):
        for item in items:
            self.visit(item)

    def is_array_type(self, typ) -> bool:
        t = self.type_name(typ)
        return isinstance(t, str) and t.startswith("array[]")

    def array_elem_type(self, typ):
        t = self.type_name(typ)
        if isinstance(t, str) and t.startswith("array[]"):
            return t[len("array[]"):]
        return None

    def lvalue_info(self, node):
        if isinstance(node, Identifier):
            sym = getattr(node, "sym", None)
            return sym, getattr(node, "type", None)
        if isinstance(node, IndexExpr):
            sym = getattr(node, "sym", None)
            return sym, getattr(node, "type", None)
        return None, getattr(node, "type", None)

    def requires_mutable_lvalue(self, node, opname: str):
        sym, _ = self.lvalue_info(node)
        if not isinstance(node, (Identifier, IndexExpr)):
            self.error(node, f"el operador {opname} requiere una variable o acceso a arreglo modificable")
            return False
        if sym is not None and not sym.mutable:
            shown = getattr(node, 'name', '?')
            self.error(node, f"no se puede aplicar {opname} a '{shown}' porque es constante")
            return False
        return True

    def stmt_guarantees_return(self, stmt) -> bool:
        if isinstance(stmt, ReturnStmt):
            return True
        if isinstance(stmt, Block):
            for s in stmt.stmts:
                if self.stmt_guarantees_return(s):
                    return True
            return False
        if isinstance(stmt, IfStmt):
            return (
                stmt.then_branch is not None
                and stmt.else_branch is not None
                and self.stmt_guarantees_return(stmt.then_branch)
                and self.stmt_guarantees_return(stmt.else_branch)
            )
        return False

    # -------------------- declarations --------------------

    def visit(self, n: Program):
        self.visit_list(n.decls)

    def visit(self, n: VarDecl):
        vartype = self.type_name(n.vartype)
        n.type = vartype
        self.define(n, n.name, Symbol(n.name, "var", vartype, node=n, mutable=True))

    def visit(self, n: VarDeclInit):
        vartype = self.type_name(n.vartype)
        n.type = vartype
        self.visit(n.value)
        if not self.same_type(vartype, getattr(n.value, "type", None)):
            self.error(n, f"no se puede inicializar '{n.name}' de tipo {vartype} con un valor de tipo {getattr(n.value, 'type', None)}")
        self.define(n, n.name, Symbol(n.name, "var", vartype, node=n, mutable=True))

    def visit(self, n: ConstDecl):
        self.visit(n.value)
        n.type = getattr(n.value, "type", None)
        self.define(n, n.name, Symbol(n.name, "const", n.type, node=n, mutable=False))

    def visit(self, n: ArrayDecl):
        self.visit(n.arrtype.size)
        if getattr(n.arrtype.size, "type", None) != "integer":
            self.error(n.arrtype.size, "el tamaño del arreglo debe ser integer")
        arrtype = self.type_name(n.arrtype)
        n.type = arrtype
        self.define(n, n.name, Symbol(n.name, "var", arrtype, node=n, mutable=True))

    def visit(self, n: ArrayDeclInit):
        self.visit(n.arrtype.size)
        if getattr(n.arrtype.size, "type", None) != "integer":
            self.error(n.arrtype.size, "el tamaño del arreglo debe ser integer")

        arrtype = self.type_name(n.arrtype)
        elem_type = self.type_name(n.arrtype.elem_type)
        n.type = arrtype

        # Si el tamaño es literal entero, validar cantidad de elementos
        if isinstance(n.arrtype.size, IntLiteral):
            expected_count = n.arrtype.size.value
            if len(n.elements) != expected_count:
                self.error(n, f"el arreglo '{n.name}' declara tamaño {expected_count} pero recibió {len(n.elements)} elemento(s)")

        for elem in n.elements:
            self.visit(elem)
            if not self.same_type(elem_type, getattr(elem, "type", None)):
                self.error(elem, f"elemento de arreglo incompatible: se esperaba {elem_type} y se recibió {getattr(elem, 'type', None)}")

        self.define(n, n.name, Symbol(n.name, "var", arrtype, node=n, mutable=True))

    def _register_function_symbol(self, n):
        ftype = self.type_name(n.functype)
        self.define(n, n.name, Symbol(n.name, "func", ftype, node=n, mutable=False))
        return ftype

    def visit(self, n: FuncDecl):
        self._register_function_symbol(n)

    def visit(self, n: FuncDeclInit):
        finfo = self._register_function_symbol(n)
        old_function = self.current_function
        old_name = self.current_function_name
        self.current_function = finfo
        self.current_function_name = n.name

        self.open_scope(f"function {n.name}")
        for p in n.functype.params:
            self.visit(p)
        self.visit_list(n.body)
        self.close_scope()

        if finfo.ret_type != "void" and not any(self.stmt_guarantees_return(stmt) for stmt in n.body):
            self.error(n, f"la función '{n.name}' debe garantizar un return de tipo {finfo.ret_type}")

        self.current_function = old_function
        self.current_function_name = old_name

    def visit(self, n: Param):
        ptype = self.type_name(n.paramtype)
        n.type = ptype
        self.define(n, n.name, Symbol(n.name, "param", ptype, node=n, mutable=True))

    # -------------------- statements --------------------

    def visit(self, n: Block):
        self.open_scope("block")
        self.visit_list(n.stmts)
        self.close_scope()

    def visit(self, n: PrintStmt):
        for expr in n.exprs:
            self.visit(expr)

    def visit(self, n: ReturnStmt):
        if self.current_function is None:
            self.error(n, "return fuera de una función")
            return

        expected = self.current_function.ret_type
        if n.value is None:
            if expected != "void":
                self.error(n, f"la función '{self.current_function_name}' debe retornar {expected} y se encontró return vacío")
            return

        self.visit(n.value)
        got = getattr(n.value, "type", None)
        if not self.same_type(expected, got):
            self.error(n, f"return incompatible en '{self.current_function_name}': se esperaba {expected} y se recibió {got}")

    def visit(self, n: BreakStmt):
        if self.loop_depth == 0:
            self.error(n, "break fuera de un ciclo")

    def visit(self, n: ContinueStmt):
        if self.loop_depth == 0:
            self.error(n, "continue fuera de un ciclo")

    def visit(self, n: IfStmt):
        self.visit(n.cond)
        if getattr(n.cond, "type", None) != "boolean":
            self.error(n.cond, f"la condición del if debe ser boolean y se recibió {getattr(n.cond, 'type', None)}")
        self.visit(n.then_branch)
        if n.else_branch is not None:
            self.visit(n.else_branch)

    def visit(self, n: WhileStmt):
        self.visit(n.cond)
        if getattr(n.cond, "type", None) != "boolean":
            self.error(n.cond, f"la condición del while debe ser boolean y se recibió {getattr(n.cond, 'type', None)}")
        self.loop_depth += 1
        self.visit(n.body)
        self.loop_depth -= 1

    def visit(self, n: ForStmt):
        self.open_scope("for")
        if n.init is not None:
            self.visit(n.init)
        if n.cond is not None:
            self.visit(n.cond)
            if getattr(n.cond, "type", None) != "boolean":
                self.error(n.cond, f"la condición del for debe ser boolean y se recibió {getattr(n.cond, 'type', None)}")
        if n.update is not None:
            self.visit(n.update)
        self.loop_depth += 1
        self.visit(n.body)
        self.loop_depth -= 1
        self.close_scope()

    def visit(self, n: ExprStmt):
        self.visit(n.expr)

    # -------------------- expressions --------------------

    def visit(self, n: Assign):
        self.visit(n.target)
        self.visit(n.value)

        target_type = getattr(n.target, "type", None)
        value_type = getattr(n.value, "type", None)
        n.type = target_type

        if isinstance(n.target, (Identifier, IndexExpr)):
            sym = getattr(n.target, "sym", None)
            if sym is not None and not sym.mutable:
                shown = getattr(n.target, 'name', '?')
                self.error(n, f"no se puede asignar a '{shown}' porque es constante")
        else:
            self.error(n, "el lado izquierdo de una asignación debe ser una variable o acceso a arreglo")

        if not self.same_type(target_type, value_type):
            self.error(n, f"asignación incompatible: no se puede asignar {value_type} a {target_type}")

    def visit(self, n: BinOp):
        self.visit(n.left)
        self.visit(n.right)

        ltype = getattr(n.left, "type", None)
        rtype = getattr(n.right, "type", None)
        result = check_binop(n.op, ltype, rtype)
        if result is None:
            self.error(n, f"operación inválida: {ltype} {n.op} {rtype}")
            n.type = None
        else:
            n.type = result

    def visit(self, n: UnaryOp):
        self.visit(n.operand)
        otype = getattr(n.operand, "type", None)

        if n.op in ("++", "--", "pre++", "pre--"):
            self.requires_mutable_lvalue(n.operand, n.op)
            if otype not in ("integer", "float"):
                self.error(n, f"el operador {n.op} requiere integer o float y recibió {otype}")
                n.type = None
            else:
                n.type = otype
            return

        result = check_unaryop(n.op, otype)
        if result is None:
            self.error(n, f"operación unaria inválida: {n.op}{otype}")
            n.type = None
        else:
            n.type = result

    def visit(self, n: CallExpr):
        sym = self.lookup(n, n.name)
        for arg in n.args:
            self.visit(arg)

        if sym is None:
            n.type = None
            return

        if sym.kind != "func":
            self.error(n, f"'{n.name}' no es una función")
            n.type = None
            return

        finfo = sym.type
        if len(n.args) != len(finfo.param_types):
            self.error(n, f"la función '{n.name}' espera {len(finfo.param_types)} argumentos pero recibió {len(n.args)}")
        else:
            for i, (arg, expected) in enumerate(zip(n.args, finfo.param_types), start=1):
                got = getattr(arg, "type", None)
                if not self.same_type(expected, got):
                    self.error(arg, f"argumento {i} incompatible en llamada a '{n.name}': se esperaba {expected} y se recibió {got}")

        n.sym = sym
        n.type = finfo.ret_type

    def visit(self, n: IndexExpr):
        sym = self.lookup(n, n.name)
        self.visit(n.index)

        if getattr(n.index, "type", None) != "integer":
            self.error(n.index, f"el índice del arreglo debe ser integer y se recibió {getattr(n.index, 'type', None)}")

        if sym is None:
            n.type = None
            return

        if not self.is_array_type(sym.type):
            self.error(n, f"'{n.name}' no es un arreglo")
            n.type = None
            return

        n.sym = sym
        n.type = self.array_elem_type(sym.type)

    def visit(self, n: Identifier):
        sym = self.lookup(n, n.name)
        n.sym = sym
        n.type = sym.type if sym else None

    def visit(self, n: DerefExpr):
        self.visit(n.expr)
        n.type = getattr(n.expr, "type", None)

    # -------------------- literals --------------------

    def visit(self, n: IntLiteral):
        n.type = "integer"

    def visit(self, n: FloatLiteral):
        n.type = "float"

    def visit(self, n: CharLiteral):
        n.type = "char"

    def visit(self, n: StringLiteral):
        n.type = "string"

    def visit(self, n: BoolLiteral):
        n.type = "boolean"

    # -------------------- fallback --------------------

    def visit(self, n: object):
        raise NotImplementedError(f"visit no implementado para {type(n).__name__}")
