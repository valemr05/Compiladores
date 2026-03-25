# topdown.py
# Analizador Descendente Recursivo para B-Minor
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Iterator, Optional, List, Union
import re

# ===================================================
# AST (dataclasses)
# ===================================================

class Type: ...

@dataclass(frozen=True)
class SimpleType(Type):
    name: str

@dataclass(frozen=True)
class ArrayType(Type):
    elem: Type

@dataclass(frozen=True)
class ArraySizedType(Type):
    size_expr: "Expr"
    elem: Type

@dataclass(frozen=True)
class FuncType(Type):
    ret: Type
    params: List["Param"]

@dataclass(frozen=True)
class Param:
    name: str
    typ: Type

# ---------- Program / Decl ----------
class Decl: ...

@dataclass
class Program:
    decls: List[Decl]

@dataclass
class DeclTyped(Decl):
    name: str
    typ: Type

@dataclass
class DeclInit(Decl):
    name: str
    typ: Type
    init: Any

# ---------- Stmt ----------
class Stmt: ...

@dataclass
class Print(Stmt):
    values: List["Expr"]

@dataclass
class Return(Stmt):
    value: Optional["Expr"]

@dataclass
class Block(Stmt):
    stmts: List[Union[Stmt, Decl]]

@dataclass
class ExprStmt(Stmt):
    expr: "Expr"

@dataclass
class If(Stmt):
    cond: Optional["Expr"]
    then: Stmt
    otherwise: Optional[Stmt] = None

@dataclass
class For(Stmt):
    init: Optional["Expr"]
    cond: Optional["Expr"]
    step: Optional["Expr"]
    body: Stmt

@dataclass
class While(Stmt):
    cond: Optional["Expr"]
    body: Stmt

# ---------- Expr ----------
class Expr: ...

@dataclass
class Name(Expr):
    id: str

@dataclass
class Literal(Expr):
    kind: str
    value: Any

@dataclass
class Index(Expr):
    base: Expr
    indices: List[Expr]

@dataclass
class Call(Expr):
    func: str
    args: List[Expr]

@dataclass
class Assign(Expr):
    target: Expr
    value: Expr

@dataclass
class BinOp(Expr):
    op: str
    left: Expr
    right: Expr

@dataclass
class UnaryOp(Expr):
    op: str
    expr: Expr

@dataclass
class PostfixOp(Expr):
    op: str
    expr: Expr


# ===================================================
# Tokenizer
# ===================================================

@dataclass
class Token:
    type: str
    value: Any
    line: int
    col: int

KEYWORDS = {
    "if", "else", "for", "while", "print", "return", "true",
    "false", "integer", "float", "boolean", "char",
    "string", "void", "array", "function", "break", "continue",
    "constant",
}

MULTI = {
    "||": "LOR",
    "&&": "LAND",
    "==": "EQ",
    "!=": "NE",
    "<=": "LE",
    ">=": "GE",
    "++": "INC",
    "--": "DEC",
}

SINGLE = {
    "+": "+", "-": "-", "*": "*", "/": "/",
    "%": "%", "^": "^", "<": "LT", ">": "GT",
    "=": "=", ":": ":", ",": ",", ";": ";",
    "(": "(", ")": ")", "{": "{", "}": "}",
    "[": "[", "]": "]",
    "!": "NOT",
}

class Tokenizer:
    def __init__(self, text: str):
        self.s = text
        self.i = 0
        self.line = 1
        self.col = 1

    def _peek(self, k=0) -> str:
        j = self.i + k
        return self.s[j] if j < len(self.s) else ""

    def _adv(self, n=1) -> None:
        for _ in range(n):
            ch = self._peek()
            self.i += 1
            if ch == "\n":
                self.line += 1
                self.col = 1
            else:
                self.col += 1

    def tokens(self) -> Iterator[Token]:
        while self.i < len(self.s):
            ch = self._peek()

            if ch.isspace():
                self._adv()
                continue

            if ch == "/" and self._peek(1) == "/":
                while self._peek() not in ("", "\n"):
                    self._adv()
                continue

            if ch == "/" and self._peek(1) == "*":
                self._adv(2)
                while not (self._peek() == "*" and self._peek(1) == "/"):
                    if self._peek() == "":
                        raise SyntaxError(f"Comentario sin cerrar (línea {self.line})")
                    self._adv()
                self._adv(2)
                continue

            two = ch + self._peek(1)
            if two in MULTI:
                t = Token(MULTI[two], two, self.line, self.col)
                self._adv(2)
                yield t
                continue

            if ch == '"':
                L, C = self.line, self.col
                self._adv()
                buf = []
                while True:
                    c = self._peek()
                    if c == "":
                        raise SyntaxError(f"STRING sin cerrar (línea {L})")
                    if c == '"':
                        self._adv()
                        break
                    if c == "\\":
                        self._adv()
                        esc = self._peek()
                        mapping = {"n": "\n", "t": "\t", '"': '"', "\\": "\\"}
                        buf.append(mapping.get(esc, esc))
                        self._adv()
                    else:
                        buf.append(c)
                        self._adv()
                yield Token("STRING_LITERAL", "".join(buf), L, C)
                continue

            if ch == "'":
                L, C = self.line, self.col
                self._adv()
                c = self._peek()
                if c == "\\":
                    self._adv()
                    esc = self._peek()
                    mapping = {"n": "\n", "t": "\t", "'": "'", "\\": "\\"}
                    val = mapping.get(esc, esc)
                    self._adv()
                else:
                    val = c
                    self._adv()
                if self._peek() != "'":
                    raise SyntaxError(f"CHAR inválido (línea {L})")
                self._adv()
                yield Token("CHAR_LITERAL", val, L, C)
                continue

            if ch.isdigit():
                L, C = self.line, self.col
                m = re.match(r"\d+(\.\d+)?", self.s[self.i:])
                lex = m.group(0)
                self._adv(len(lex))
                if "." in lex:
                    yield Token("FLOAT_LITERAL", float(lex), L, C)
                else:
                    yield Token("INTEGER_LITERAL", int(lex), L, C)
                continue

            if ch.isalpha() or ch == "_":
                L, C = self.line, self.col
                m = re.match(r"[A-Za-z_]\w*", self.s[self.i:])
                lex = m.group(0)
                self._adv(len(lex))
                if lex in KEYWORDS:
                    yield Token(lex, lex, L, C)
                else:
                    yield Token("ID", lex, L, C)
                continue

            if ch in SINGLE:
                t = Token(SINGLE[ch], ch, self.line, self.col)
                self._adv()
                yield t
                continue

            raise SyntaxError(f"Caracter ilegal '{ch}' (línea {self.line}, col {self.col})")

        yield Token("EOF", None, self.line, self.col)


# ===================================================
# Parser (Recursive Descent)
# ===================================================

class Parser:
    def __init__(self):
        self.tok: Optional[Token] = None
        self.la: Optional[Token] = None
        self.it: Optional[Iterator[Token]] = None

    def parse(self, tokens: Iterator[Token]) -> Program:
        self.it = iter(tokens)
        self.tok = None
        self.la = next(self.it)
        return self.prog()

    def _advance(self) -> None:
        self.tok = self.la
        try:
            self.la = next(self.it)
        except StopIteration:
            self.la = Token("EOF", None, -1, -1)

    def _accept(self, t: str) -> bool:
        if self.la and self.la.type == t:
            self._advance()
            return True
        return False

    def _expect(self, t: str) -> Token:
        if not self._accept(t):
            got = self.la.type if self.la else None
            line = self.la.line if self.la else -1
            col = self.la.col if self.la else -1
            raise SyntaxError(f"Esperaba '{t}', obtuve '{got}' (línea {line}, col {col})")
        return self.tok

    def _unadvance(self, previous_la: Token) -> None:
        assert self.it is not None
        old_la = self.la
        old_it = self.it

        def chain():
            yield previous_la
            yield old_la
            yield from old_it

        self.it = iter(chain())
        self.tok = None
        self.la = next(self.it)

    # =================================================
    # prog ::= decl_list EOF
    # =================================================
    def prog(self) -> Program:
        decls = self.decl_list()
        self._expect("EOF")
        return Program(decls)

    def decl_list(self) -> List[Decl]:
        decls: List[Decl] = []
        while self.la.type != "EOF":
            decls.append(self.decl())
        return decls

    def decl(self) -> Decl:
        name = self._expect("ID").value
        self._expect(":")
        typ = self.type_any_decl_head()

        if self._accept("="):
            if isinstance(typ, FuncType):
                self._expect("{")
                body = self.opt_stmt_list()
                self._expect("}")
                return DeclInit(name, typ, body)
            if isinstance(typ, ArraySizedType):
                self._expect("{")
                xs = self.opt_expr_list()
                self._expect("}")
                self._expect(";")
                return DeclInit(name, typ, xs)
            e = self.expr()
            self._expect(";")
            return DeclInit(name, typ, e)

        self._expect(";")
        return DeclTyped(name, typ)

    def type_any_decl_head(self) -> Type:
        if self.la.type == "function":
            return self.type_func()
        if self.la.type == "array":
            return self.type_array_sized()
        return self.type_simple()

    # =================================================
    # Statements
    # =================================================
    def opt_stmt_list(self) -> List[Union[Stmt, Decl]]:
        if self._starts_stmt():
            return self.stmt_list()
        return []

    def stmt_list(self) -> List[Union[Stmt, Decl]]:
        items: List[Union[Stmt, Decl]] = []
        while self._starts_stmt():
            items.append(self.stmt())
        return items

    def _starts_stmt(self) -> bool:
        return self.la.type in {
            "if", "for", "while", "print", "return",
            "break", "continue", "{", "ID"
        }

    def stmt(self) -> Union[Stmt, Decl]:
        if self.la.type == "if":
            return self.if_stmt()
        if self.la.type == "for":
            return self.for_stmt()
        if self.la.type == "while":
            return self.while_stmt()
        if self.la.type == "print":
            return self.print_stmt()
        if self.la.type == "return":
            return self.return_stmt()
        if self.la.type == "break":
            self._advance()
            self._expect(";")
            return ExprStmt(Name("break"))
        if self.la.type == "continue":
            self._advance()
            self._expect(";")
            return ExprStmt(Name("continue"))
        if self.la.type == "{":
            return self.block_stmt()

        if self.la.type == "ID":
            save = self.la
            self._advance()
            is_decl = (self.la.type == ":")
            self._unadvance(save)
            if is_decl:
                return self.decl()

        e = self.expr()
        self._expect(";")
        return ExprStmt(e)

    def if_stmt(self) -> Stmt:
        self._expect("if")
        self._expect("(")
        cond = self.opt_expr()
        self._expect(")")
        then = self.stmt()
        if self._accept("else"):
            otherwise = self.stmt()
            return If(cond, then, otherwise)
        return If(cond, then, None)

    def for_stmt(self) -> Stmt:
        self._expect("for")
        self._expect("(")
        init = self.opt_expr()
        self._expect(";")
        cond = self.opt_expr()
        self._expect(";")
        step = self.opt_expr()
        self._expect(")")
        body = self.stmt()
        return For(init, cond, step, body)

    def while_stmt(self) -> Stmt:
        self._expect("while")
        self._expect("(")
        cond = self.opt_expr()
        self._expect(")")
        body = self.stmt()
        return While(cond, body)

    def print_stmt(self) -> Print:
        self._expect("print")
        xs = self.opt_expr_list()
        self._expect(";")
        return Print(xs)

    def return_stmt(self) -> Return:
        self._expect("return")
        v = self.opt_expr()
        self._expect(";")
        return Return(v)

    def block_stmt(self) -> Block:
        self._expect("{")
        stmts = self.opt_stmt_list()
        self._expect("}")
        return Block(stmts)

    # =================================================
    # Expressions
    # =================================================
    def opt_expr(self) -> Optional[Expr]:
        if self._starts_expr():
            return self.expr()
        return None

    def opt_expr_list(self) -> List[Expr]:
        if self._starts_expr():
            return self.expr_list()
        return []

    def _starts_expr(self) -> bool:
        return self.la.type in {
            "ID", "INTEGER_LITERAL", "FLOAT_LITERAL", "CHAR_LITERAL",
            "STRING_LITERAL", "true", "false", "(", "-", "NOT", "INC", "DEC"
        }

    def expr_list(self) -> List[Expr]:
        xs = [self.expr()]
        while self._accept(","):
            xs.append(self.expr())
        return xs

    def expr(self) -> Expr:
        return self.expr1()

    def expr1(self) -> Expr:
        left = self.expr2()
        if self._accept("="):
            if not isinstance(left, (Name, Index)):
                raise SyntaxError("Asignación: lado izquierdo no es lval")
            right = self.expr1()
            return Assign(left, right)
        return left

    def expr2(self) -> Expr:
        e = self.expr3()
        while self._accept("LOR"):
            e = BinOp("||", e, self.expr3())
        return e

    def expr3(self) -> Expr:
        e = self.expr4()
        while self._accept("LAND"):
            e = BinOp("&&", e, self.expr4())
        return e

    def expr4(self) -> Expr:
        e = self.expr5()
        while True:
            if self._accept("EQ"):   e = BinOp("==", e, self.expr5()); continue
            if self._accept("NE"):   e = BinOp("!=", e, self.expr5()); continue
            if self._accept("LT"):   e = BinOp("<",  e, self.expr5()); continue
            if self._accept("LE"):   e = BinOp("<=", e, self.expr5()); continue
            if self._accept("GT"):   e = BinOp(">",  e, self.expr5()); continue
            if self._accept("GE"):   e = BinOp(">=", e, self.expr5()); continue
            break
        return e

    def expr5(self) -> Expr:
        e = self.expr6()
        while True:
            if self._accept("+"): e = BinOp("+", e, self.expr6()); continue
            if self._accept("-"): e = BinOp("-", e, self.expr6()); continue
            break
        return e

    def expr6(self) -> Expr:
        e = self.expr7()
        while True:
            if self._accept("*"): e = BinOp("*", e, self.expr7()); continue
            if self._accept("/"): e = BinOp("/", e, self.expr7()); continue
            if self._accept("%"): e = BinOp("%", e, self.expr7()); continue
            break
        return e

    def expr7(self) -> Expr:
        e = self.expr8()
        while self._accept("^"):
            e = BinOp("^", e, self.expr8())
        return e

    def expr8(self) -> Expr:
        if self._accept("-"):
            return UnaryOp("-", self.expr8())
        if self._accept("NOT"):
            return UnaryOp("NOT", self.expr8())
        if self._accept("INC"):
            return UnaryOp("pre++", self.expr9())
        if self._accept("DEC"):
            return UnaryOp("pre--", self.expr9())
        return self.expr9()

    def expr9(self) -> Expr:
        e = self.group()
        while True:
            if self._accept("INC"): e = PostfixOp("++", e); continue
            if self._accept("DEC"): e = PostfixOp("--", e); continue
            break
        return e

    def group(self) -> Expr:
        if self._accept("("):
            e = self.expr()
            self._expect(")")
            return e

        if self.la.type == "ID":
            self._advance()
            name = self.tok.value
            if self._accept("("):
                args = self.opt_expr_list()
                self._expect(")")
                return Call(name, args)
            if self.la.type == "[":
                indices = self.index_list()
                return Index(Name(name), indices)
            return Name(name)

        return self.factor()

    def index_list(self) -> List[Expr]:
        idxs = [self.index()]
        while self.la.type == "[":
            idxs.append(self.index())
        return idxs

    def index(self) -> Expr:
        self._expect("[")
        e = self.expr()
        self._expect("]")
        return e

    def factor(self) -> Expr:
        if self._accept("ID"):             return Name(self.tok.value)
        if self._accept("INTEGER_LITERAL"): return Literal("int", self.tok.value)
        if self._accept("FLOAT_LITERAL"):   return Literal("float", self.tok.value)
        if self._accept("CHAR_LITERAL"):    return Literal("char", self.tok.value)
        if self._accept("STRING_LITERAL"):  return Literal("string", self.tok.value)
        if self._accept("true"):            return Literal("bool", True)
        if self._accept("false"):           return Literal("bool", False)
        raise SyntaxError(f"Factor inválido: '{self.la.type}' (línea {self.la.line})")

    # =================================================
    # Types
    # =================================================
    def type_simple(self) -> SimpleType:
        for t in ("integer", "float", "boolean", "char", "string", "void"):
            if self._accept(t):
                return SimpleType(t)
        raise SyntaxError(f"Se esperaba tipo simple, obtuve '{self.la.type}' (línea {self.la.line})")

    def type_array(self) -> ArrayType:
        self._expect("array")
        self._expect("[")
        self._expect("]")
        if self.la.type == "array":
            return ArrayType(self.type_array())
        return ArrayType(self.type_simple())

    def type_array_sized(self) -> ArraySizedType:
        self._expect("array")
        size = self.index()
        if self.la.type == "array":
            return ArraySizedType(size, self.type_array_sized())
        return ArraySizedType(size, self.type_simple())

    def type_func(self) -> FuncType:
        self._expect("function")
        if self.la.type == "array":
            ret = self.type_array_sized()
        else:
            ret = self.type_simple()
        self._expect("(")
        params = self.opt_param_list()
        self._expect(")")
        return FuncType(ret, params)

    def opt_param_list(self) -> List[Param]:
        if self.la.type == "ID":
            return self.param_list()
        return []

    def param_list(self) -> List[Param]:
        params = [self.param()]
        while self._accept(","):
            params.append(self.param())
        return params

    def param(self) -> Param:
        name = self._expect("ID").value
        self._expect(":")
        if self.la.type == "array":
            self._expect("array")
            self._expect("[")
            if self._accept("]"):
                if self.la.type == "array":
                    elem = self.type_array()
                else:
                    elem = self.type_simple()
                return Param(name, ArrayType(elem))
            else:
                e = self.expr()
                self._expect("]")
                if self.la.type == "array":
                    return Param(name, ArraySizedType(e, self.type_array_sized()))
                return Param(name, ArraySizedType(e, self.type_simple()))
        return Param(name, self.type_simple())


# ===================================================
# Utilidad: imprimir AST
# ===================================================
def print_ast(node, indent=0):
    prefix = "  " * indent
    if node is None:
        print(f"{prefix}None")
        return
    if isinstance(node, list):
        for item in node:
            print_ast(item, indent)
        return
    if hasattr(node, "__dataclass_fields__"):
        print(f"{prefix}{node.__class__.__name__}")
        for key in node.__dataclass_fields__:
            val = getattr(node, key)
            print(f"{prefix}  .{key}:")
            if isinstance(val, list):
                print_ast(val, indent + 2)
            elif hasattr(val, "__dataclass_fields__"):
                print_ast(val, indent + 2)
            else:
                print(f"{prefix}    {val!r}")
    else:
        print(f"{prefix}{node!r}")


# ===================================================
# Punto de entrada
# ===================================================
def parse(src: str) -> Program:
    return Parser().parse(Tokenizer(src).tokens())


if __name__ == "__main__":
    import sys

    if len(sys.argv) == 2:
        filename = sys.argv[1]
        print(f"\n{'='*60}")
        print(f"  Analizando (topdown): {filename}")
        print(f"{'='*60}\n")
        src = open(filename, encoding="utf-8").read()
    else:
        src = r'''
x: integer = 3;
a: array [10] integer = { 1, 2, 3 };

f: function integer (x: integer, y: integer) = {
    if (x > 0) {
        print x;
    } else {
        print 0;
    }
    return x;
}
'''

    try:
        ast = parse(src)
        print("✔  Análisis sintáctico exitoso — sin errores.\n")
        print("── AST ──────────────────────────────────────────────────")
        print_ast(ast)
    except SyntaxError as e:
        print(f"\n✘  SyntaxError: {e}")
        sys.exit(1)