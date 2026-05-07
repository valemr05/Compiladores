from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional
from rich import print

from model import *

# ===================================================
# IR model
# ===================================================

Instruction = tuple


@dataclass
class Storage:
    """
    Describe dónde vive un símbolo durante la generación de IR.

    El objetivo es que el estudiante tenga una estructura simple para
    consultar tipo y categoría del símbolo (global, parámetro, constante).
    """
    name: str
    ty: str
    is_global: bool = False
    is_param: bool = False
    is_const: bool = False


@dataclass
class IRFunction:
    name: str
    params: list[tuple[str, str]]
    return_type: str
    instructions: list[Instruction] = field(default_factory=list)


@dataclass
class IRProgram:
    globals: list[Instruction] = field(default_factory=list)
    functions: list[IRFunction] = field(default_factory=list)

    def format(self) -> str:
        out: list[str] = []
        if self.globals:
            out.append("# Globals")
            for inst in self.globals:
                out.append(format_instruction(inst))
            out.append("")

        for fn in self.functions:
            params = ", ".join(f"{name}:{ty}" for name, ty in fn.params)
            out.append(f"function {fn.name}({params}) -> {fn.return_type}")
            for inst in fn.instructions:
                out.append(f"  {format_instruction(inst)}")
            out.append("")
        return "\n".join(out).rstrip()


# ===================================================
# Pretty printing
# ===================================================


def format_instruction(inst: Instruction) -> str:
    op = inst[0]
    if len(inst) == 1:
        return op
    args = ", ".join(
        repr(x) if isinstance(x, str) and x.startswith("L") else str(x)
        for x in inst[1:]
    )
    return f"{op} {args}"


# ===================================================
# Generator
# ===================================================
class Visitor:
    def visit(self, node):
        method_name = f'visit_{type(node).__name__}'
        method = getattr(self, method_name, self.generic_visit)
        return method(node)
 
    def generic_visit(self, node):
        raise NotImplementedError(f"No visit_{type(node).__name__} method")
 


class IRCodeGen(Visitor):
    """
    Plantilla base para el proyecto de IRCode.

    Esta versión deja aproximadamente la mitad del trabajo resuelto:

    Ya implementado:
    - estructura del programa IR
    - manejo de temporales y labels
    - scopes y lookup de símbolos
    - declaración de variables y constantes
    - carga de literales enteros, booleanos y chars
    - lectura de variables (VarLoc)
    - impresión simple
    - retorno simple
    - parte de la selección de opcodes

    Pendiente para estudiantes:
    - completar BinOp
    - completar UnaryOp
    - completar Assignment compuesto
    - completar IfStmt / WhileStmt / ForStmt
    - completar FuncCall
    - arreglos y strings
    - conversiones adicionales y mejoras del IR

    Sugerencia pedagógica:
    1. Hacer primero expresiones aritméticas.
    2. Luego comparaciones.
    3. Después control de flujo.
    4. Finalmente llamadas, arreglos y extensiones.
    """

    def __init__(self):
        self.program = IRProgram()
        self.current_function: Optional[IRFunction] = None
        self.current_return_type: str = "void"
        self.temp_count = 0
        self.label_count = 0
        self.scopes: list[dict[str, Storage]] = []
        # stack de labels de break/continue para loops   
        self.loop_end_stack: list[str] = []
        self.loop_start_stack: list[str] = []

    @classmethod
    def generate(cls, node: Program) -> IRProgram:
        gen = cls()
        gen.visit(node)
        return gen.program

    # -------------------------------------------------
    # helpers básicos
    # -------------------------------------------------

    def new_temp(self) -> str:
        self.temp_count += 1
        return f"R{self.temp_count}"

    def new_label(self, prefix: str = "L") -> str:
        self.label_count += 1
        return f"{prefix}{self.label_count}"

    def emit(self, *inst) -> None:
        inst = tuple(inst)
        if self.current_function is None:
            self.program.globals.append(inst)
        else:
            self.current_function.instructions.append(inst)

    def push_scope(self) -> None:
        self.scopes.append({})

    def pop_scope(self) -> None:
        self.scopes.pop()

    def bind(self, storage: Storage) -> None:
        if not self.scopes:
            self.push_scope()
        self.scopes[-1][storage.name] = storage

    def lookup(self, name: str) -> Storage:
        for scope in reversed(self.scopes):
            if name in scope:
                return scope[name]
        raise NameError(f"Nombre no resuelto en IRCodeGen: {name}")

    def infer_type(self, node) -> str:
        if node is None:
            return "void"
        
        # Si el checker ya anotó el tipo, usarlo directamente
        ty = getattr(node, "type", None)
        if isinstance(ty, str):
            return ty
        
        if isinstance(node, IntLiteral):
            return "integer"
        if isinstance(node, BoolLiteral):
            return "boolean"
        if isinstance(node, CharLiteral):
            return "char"
        if isinstance(node, StringLiteral):
            return "string"

        return "integer"  # fallback

    def type_suffix(self, ty: str) -> str:
        
        name = ty.lower() if isinstance(ty, str) else "integer"
            
        if name in ("integer", "boolean"):
            return "I"
        if name == "float":
            return "F"
        if name == "char":
            return "B"
        if name == "void":
            return "V"
        
        # arreglos u otros → tratar como entero        
        return "I"

    def move_opcode(self, ty: str) -> str:
        return f"MOV{self.type_suffix(ty)}"

    def load_opcode(self, ty: str) -> str:
        return f"LOAD{self.type_suffix(ty)}"

    def store_opcode(self, ty: str) -> str:
        return f"STORE{self.type_suffix(ty)}"

    def alloc_opcode(self, ty: str ) -> str:
        return f"ALLOC{self.type_suffix(ty)}"

    def var_opcode(self, ty: str) -> str:
        return f"VAR{self.type_suffix(ty)}"

    def print_opcode(self, ty: str) -> str:
        return f"PRINT{self.type_suffix(ty)}"

    def cmp_opcode(self, ty: str) -> str:
        return f"CMP{self.type_suffix(ty)}"

    # -------------------------------------------------
    # opcodes auxiliares
    # -------------------------------------------------

    def binary_arith_opcode(self, oper: str, ty: str) -> str:
        suffix = self.type_suffix(ty)
        table = {
            "+": f"ADD{suffix}",
            "-": f"SUB{suffix}",
            "*": f"MUL{suffix}",
            "/": f"DIV{suffix}",
        }
        if oper not in table:
            raise NotImplementedError(f"Aritmética no soportada: {oper}")
        return table[oper]

    def binary_bit_opcode(self, oper: str, ty: str) -> str:
        table = {
            "&": "AND",
            "|": "OR",
            "^": "XOR",
        }
        if oper not in table:
            raise NotImplementedError(f"Bitwise no soportado: {oper}")
        return table[oper]

    # -------------------------------------------------
    # programa y declaraciones
    # -------------------------------------------------

    def visit_Program(self, node: Program):
        self.push_scope()

        # Primera pasada: registrar nombres globales.
        for decl in node.decls:
            if isinstance(decl, (VarDecl, VarDeclInit)):
                ty = self.infer_type(decl)
                self.bind(Storage(decl.name, ty, is_global=True))
            elif isinstance(decl, ConstDecl):
                ty = self.infer_type(decl)
                self.bind(Storage(decl.name, ty, is_global=True, is_const=True))
            elif isinstance(decl, (ArrayDecl, ArrayDeclInit)):
                ty = self.infer_type(decl)
                self.bind(Storage(decl.name, ty, is_global=True))
            elif isinstance(decl, (FuncDecl, FuncDeclInit)):
                ret = "void"
                if isinstance(decl.functype.ret_type, SimpleType):
                    ret = decl.functype.ret_type.name
                self.bind(Storage(decl.name, ret, is_global=True))

        # Segunda pasada: generar IR real.
        for decl in node.decls:
            self.visit(decl)

        self.pop_scope()
        return self.program
    

    def visit_VarDecl(self, node: VarDecl):
        ty = self.type_from_vartype(node.vartype)
        if self.current_function is None:
            self.emit(self.var_opcode(ty), node.name)
            return
        self.bind(Storage(node.name, ty))
        self.emit(self.alloc_opcode(ty), node.name)
 
    def visit_VarDeclInit(self, node: VarDeclInit):
        ty = self.type_from_vartype(node.vartype)
        if self.current_function is None:
            self.emit(self.var_opcode(ty), node.name)
            src = self.visit(node.value)
            self.emit(self.store_opcode(ty), src, node.name)
            return
        self.bind(Storage(node.name, ty))
        self.emit(self.alloc_opcode(ty), node.name)
        src = self.visit(node.value)
        self.emit(self.store_opcode(ty), src, node.name)
 
    def visit_ConstDecl(self, node: ConstDecl):
        ty = self.infer_type(node.value)
        if self.current_function is None:
            self.emit(self.var_opcode(ty), node.name)
            src = self.visit(node.value)
            self.emit(self.store_opcode(ty), src, node.name)
            return
        self.bind(Storage(node.name, ty, is_const=True))
        self.emit(self.alloc_opcode(ty), node.name)
        src = self.visit(node.value)
        self.emit(self.store_opcode(ty), src, node.name)
 
    def visit_ArrayDecl(self, node: ArrayDecl):
        ty = self.type_from_vartype(node.arrtype)
        size_reg = self.visit(node.arrtype.size)
        if self.current_function is None:
            self.emit("VARARR", node.name, size_reg)
            return
        self.bind(Storage(node.name, ty))
        self.emit("ALLOCARR", node.name, size_reg)
 
    def visit_ArrayDeclInit(self, node: ArrayDeclInit):
        ty = self.type_from_vartype(node.arrtype)
        size_reg = self.visit(node.arrtype.size)
        if self.current_function is None:
            self.emit("VARARR", node.name, size_reg)
        else:
            self.bind(Storage(node.name, ty))
            self.emit("ALLOCARR", node.name, size_reg)
        # inicializar cada elemento
        elem_ty = self.type_from_vartype(node.arrtype.elem_type)
        for i, elem in enumerate(node.elements):
            idx_reg = self.new_temp()
            self.emit("MOVI", i, idx_reg)
            val_reg = self.visit(elem)
            self.emit(f"STORE{self.type_suffix(elem_ty)}IDX", val_reg, node.name, idx_reg)
 
    def visit_FuncDecl(self, node: FuncDecl):
        # Solo prototipo, sin cuerpo — no generamos IR
        pass
 
    def visit_FuncDeclInit(self, node: FuncDeclInit):
        prev_fn = self.current_function
        prev_ret = self.current_return_type
 
        ret_ty = "void"
        if isinstance(node.functype.ret_type, SimpleType):
            ret_ty = node.functype.ret_type.name
 
        fn = IRFunction(
            name=node.name,
            params=[(p.name, self.type_from_vartype(p.paramtype))
                    for p in node.functype.params],
            return_type=ret_ty,
        )
        self.program.functions.append(fn)
        self.current_function = fn
        self.current_return_type = ret_ty
 
        self.push_scope()
        for p in node.functype.params:
            pty = self.type_from_vartype(p.paramtype)
            self.bind(Storage(p.name, pty, is_param=True))
            self.emit(self.alloc_opcode(pty), p.name)
 
        for stmt in node.body:
            self.visit(stmt)
 
        # RET implícito para funciones void
        if ret_ty == "void":
            if not fn.instructions or fn.instructions[-1][0] != "RET":
                self.emit("RET")
 
        self.pop_scope()
        self.current_function = prev_fn
        self.current_return_type = prev_ret
    # -------------------------------------------------
    # helper de tipos
    # -------------------------------------------------
 
    def type_from_vartype(self, vartype) -> str:
        """Convierte un nodo de tipo (SimpleType, ArrayType, etc.) a string."""
        if vartype is None:
            return "void"
        if isinstance(vartype, SimpleType):
            return vartype.name
        if isinstance(vartype, (ArrayType, ArrayTypeSized)):
            elem = self.type_from_vartype(vartype.elem_type)
            return f"array[]{elem}"
        if isinstance(vartype, str):
            return vartype
        return "integer"

    # -------------------------------------------------
    # statements
    # -------------------------------------------------

 
    def visit_Block(self, node: Block):
        self.push_scope()
        for stmt in node.stmts:
            self.visit(stmt)
        self.pop_scope()
 
    def visit_ExprStmt(self, node: ExprStmt):
        self.visit(node.expr)
 
    def visit_PrintStmt(self, node: PrintStmt):
        for expr in node.exprs:
            reg = self.visit(expr)
            ty = self.infer_type(expr)
            self.emit(self.print_opcode(ty), reg)
 
    def visit_ReturnStmt(self, node: ReturnStmt):
        if node.value is None:
            self.emit("RET")
            return
        reg = self.visit(node.value)
        self.emit("RET", reg)
 
    def visit_BreakStmt(self, node: BreakStmt):
        if self.loop_end_stack:
            self.emit("JUMP", self.loop_end_stack[-1])
 
    def visit_ContinueStmt(self, node: ContinueStmt):
        if self.loop_start_stack:
            self.emit("JUMP", self.loop_start_stack[-1])
 
    def visit_IfStmt(self, node: IfStmt):
        l_else = self.new_label("Lelse")
        l_end  = self.new_label("Lend")
 
        cond_reg = self.visit(node.cond)
        self.emit("BZ", cond_reg, l_else)       # si falso → else
 
        self.visit(node.then_branch)
        self.emit("JUMP", l_end)
 
        self.emit("LABEL", l_else)
        if node.else_branch is not None:
            self.visit(node.else_branch)
 
        self.emit("LABEL", l_end)
 
    def visit_WhileStmt(self, node: WhileStmt):
        l_start = self.new_label("Lstart")
        l_end   = self.new_label("Lend")
 
        self.loop_start_stack.append(l_start)
        self.loop_end_stack.append(l_end)
 
        self.emit("LABEL", l_start)
        cond_reg = self.visit(node.cond)
        self.emit("BZ", cond_reg, l_end)        # si falso → salir
 
        self.visit(node.body)
        self.emit("JUMP", l_start)
 
        self.emit("LABEL", l_end)
 
        self.loop_start_stack.pop()
        self.loop_end_stack.pop()
 
    def visit_ForStmt(self, node: ForStmt):
        l_start = self.new_label("Lstart")
        l_end   = self.new_label("Lend")
 
        self.loop_start_stack.append(l_start)
        self.loop_end_stack.append(l_end)
 
        self.push_scope()
 
        if node.init is not None:
            self.visit(node.init)
 
        self.emit("LABEL", l_start)
 
        if node.cond is not None:
            cond_reg = self.visit(node.cond)
            self.emit("BZ", cond_reg, l_end)
 
        self.visit(node.body)
 
        if node.update is not None:
            self.visit(node.update)
 
        self.emit("JUMP", l_start)
        self.emit("LABEL", l_end)
 
        self.pop_scope()
 
        self.loop_start_stack.pop()
        self.loop_end_stack.pop()
 
    # -------------------------------------------------
    # expressions
    # -------------------------------------------------
    def visit_Assign(self, node: Assign):
        """Asignación simple: target = value"""
        src = self.visit(node.value)
 
        if isinstance(node.target, Identifier):
            storage = self.lookup(node.target.name)
            self.emit(self.store_opcode(storage.ty), src, storage.name)
 
        elif isinstance(node.target, IndexExpr):
            idx_reg = self.visit(node.target.index)
            storage = self.lookup(node.target.name)
            elem_ty = storage.ty.replace("array[]", "") if "array[]" in storage.ty else storage.ty
            self.emit(f"STORE{self.type_suffix(elem_ty)}IDX", src, storage.name, idx_reg)
 
        return src
 
    def visit_BinOp(self, node: BinOp):
        left_ty  = self.infer_type(node.left)
        out      = self.new_temp()
 
        # ── Aritmética ────────────────────────────────────────
        if node.op in {"+", "-", "*", "/"}:
            left_reg  = self.visit(node.left)
            right_reg = self.visit(node.right)
            self.emit(self.binary_arith_opcode(node.op, left_ty), left_reg, right_reg, out)
            return out
 
        # ── Bitwise ───────────────────────────────────────────
        if node.op in {"&", "|", "^"}:
            left_reg  = self.visit(node.left)
            right_reg = self.visit(node.right)
            self.emit(self.binary_bit_opcode(node.op), left_reg, right_reg, out)
            return out
 
        # ── Comparaciones ─────────────────────────────────────
        cmp_table = {
            "==": "EQ", "!=": "NE",
            "<":  "LT", "<=": "LE",
            ">":  "GT", ">=": "GE",
        }
        if node.op in cmp_table:
            left_reg  = self.visit(node.left)
            right_reg = self.visit(node.right)
            self.emit(self.cmp_opcode(left_ty), left_reg, right_reg)
            self.emit(cmp_table[node.op], out)
            return out
 
        # ── Lógico AND con cortocircuito ──────────────────────
        if node.op == "&&":
            left_reg = self.visit(node.left)
            l_false  = self.new_label("Lfalse")
            l_end    = self.new_label("Lend")
            self.emit("MOVI", 0, out)               # asumir falso
            self.emit("BZ", left_reg, l_false)      # left falso → saltar
            right_reg = self.visit(node.right)      # evaluar right solo si left fue true
            self.emit("BZ", right_reg, l_false)
            self.emit("MOVI", 1, out)
            self.emit("JUMP", l_end)
            self.emit("LABEL", l_false)
            self.emit("LABEL", l_end)
            return out
 
        # ── Lógico OR con cortocircuito ───────────────────────
        if node.op == "||":
            left_reg = self.visit(node.left)
            l_true   = self.new_label("Ltrue")
            l_end    = self.new_label("Lend")
            self.emit("MOVI", 1, out)               # asumir verdadero
            self.emit("BNZ", left_reg, l_true)      # left verdadero → saltar
            right_reg = self.visit(node.right)      # evaluar right solo si left fue false
            self.emit("BNZ", right_reg, l_true)
            self.emit("MOVI", 0, out)
            self.emit("JUMP", l_end)
            self.emit("LABEL", l_true)
            self.emit("LABEL", l_end)
            return out
 
        raise NotImplementedError(f"BinOp no soportado: {node.op!r}")
 
    def visit_UnaryOp(self, node: UnaryOp):
        operand = self.visit(node.operand)
        ty      = self.infer_type(node.operand)
        out     = self.new_temp()
 
        if node.op == "+":
            self.emit(self.move_opcode(ty), operand, out)
            return out
 
        if node.op == "-":
            zero = self.new_temp()
            self.emit("MOVI", 0, zero)
            self.emit(self.binary_arith_opcode("-", ty), zero, operand, out)
            return out
 
        if node.op == "!":
            zero = self.new_temp()
            self.emit("MOVI", 0, zero)
            self.emit(self.cmp_opcode(ty), operand, zero)
            self.emit("EQ", out)    # out = 1 si operand == 0
            return out
 
        raise NotImplementedError(f"UnaryOp no soportado: {node.op!r}")
 
    def visit_CallExpr(self, node: CallExpr):
        # Evaluar cada argumento y emitir PARAM
        for arg in node.args:
            reg = self.visit(arg)
            self.emit("PARAM", reg)
 
        # Tipo de retorno
        try:
            storage = self.lookup(node.name)
            ret_ty  = storage.ty
        except NameError:
            ret_ty = "integer"
 
        out = self.new_temp()
        self.emit("CALL", node.name, len(node.args), out)
        return out
 
    def visit_Identifier(self, node: Identifier):
        storage = self.lookup(node.name)
        tmp = self.new_temp()
        self.emit(self.load_opcode(storage.ty), storage.name, tmp)
        return tmp
 
    def visit_IndexExpr(self, node: IndexExpr):
        storage = self.lookup(node.name)
        idx_reg = self.visit(node.index)
        elem_ty = storage.ty.replace("array[]", "") if "array[]" in storage.ty else storage.ty
        tmp = self.new_temp()
        self.emit(f"LOAD{self.type_suffix(elem_ty)}IDX", storage.name, idx_reg, tmp)
        return tmp
 
    def visit_DerefExpr(self, node: DerefExpr):
        return self.visit(node.expr)
 
    # -------------------------------------------------
    # literals
    # -------------------------------------------------
 
    def visit_IntLiteral(self, node: IntLiteral):
        tmp = self.new_temp()
        self.emit("MOVI", int(node.value), tmp)
        return tmp
 
    def visit_FloatLiteral(self, node: FloatLiteral):
        tmp = self.new_temp()
        self.emit("MOVF", float(node.value), tmp)
        return tmp
 
    def visit_BoolLiteral(self, node: BoolLiteral):
        tmp = self.new_temp()
        self.emit("MOVI", 1 if node.value else 0, tmp)
        return tmp
 
    def visit_CharLiteral(self, node: CharLiteral):
        tmp = self.new_temp()
        value = ord(node.value) if isinstance(node.value, str) and len(node.value) == 1 else int(node.value)
        self.emit("MOVB", value, tmp)
        return tmp
 
    def visit_StringLiteral(self, node: StringLiteral):
        tmp = self.new_temp()
        self.emit("MOVS", node.value, tmp)
        return tmp
 
 
# ===================================================
# demo
# ===================================================
 
if __name__ == "__main__":
    # Demo pequeña: función main con variable, aritmética y print
    ast = Program([
        FuncDeclInit(
            name="main",
            functype=FuncType(
                ret_type=SimpleType("void"),
                params=[],
            ),
            body=[
                VarDeclInit(
                    name="x",
                    vartype=SimpleType("integer"),
                    value=BinOp(
                        op="+",
                        left=IntLiteral(2),
                        right=BinOp(
                            op="*",
                            left=IntLiteral(3),
                            right=IntLiteral(4),
                        ),
                    ),
                ),
                PrintStmt(exprs=[Identifier(name="x")]),
            ],
        )
    ])
 
    ir = IRCodeGen.generate(ast)
    print(ir.format())