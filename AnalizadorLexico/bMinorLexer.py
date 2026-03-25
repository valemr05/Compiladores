import sly
import unittest
import io
import sys


class BMinorLexer(sly.Lexer):
    # Tokens
    tokens = {
        # Palabras Reservadas
        CONSTANT, PRINT, RETURN, BREAK, CONTINUE,
        IF, ELSE, WHILE, FUNCTION, TRUE, FALSE,

        # Identificador
        ID,

        # Literales 
        ENTERO, FLOTANTE, CHAR,

        # Operadores
        PLUS, MINUS, TIMES, DIVIDE,
        LE, GE, EQ, NE, LAND, LOR, 
        LT, GT, LNOT, GROW,        

        # Símbolos varios
        ASSIGN, SEMI, LPAREN, RPAREN, LBRACE, RBRACE, RBRACKET, LBRACKET, COMA, DEREF
    }

    # Caracteres a ignorar por defecto 
    ignore = ' \t\r'
    
    # Comentario de una línea (//)
    @_(r'//.*')
    def ignore_line_comment(self, t):
        pass 

    # Comentario de bloque  (/* ... */)
    @_(r'/\*(.|\n)*?\*/') #r'/\*[\s\S]*?\*/'
    def ignore_block_comment(self, t):
        self.lineno += t.value.count('\n')

    # ERROR: Comentario sin terminación 
    @_(r'/\*(.|\n)*') #r'/\*[\s\S]*'
    def ignore_unterminated_comment(self, t):
        print(f"linea {self.lineno}: Comentario sin terminación")
        self.lineno += t.value.count('\n') 

    
    LE    = r'<='
    GE    = r'>='
    EQ    = r'=='
    NE    = r'!='
    LAND  = r'&&'
    LOR   = r'\|\|'  

    PLUS   = r'\+'  
    MINUS  = r'-'
    TIMES  = r'\*'   
    DIVIDE = r'/'   
    LT     = r'<'
    GT     = r'>'
    LNOT   = r'!'
    GROW   = r'\^'   
    
    ASSIGN = r'='
    SEMI   = r';'
    LPAREN = r'\('   
    RPAREN = r'\)'   
    LBRACE = r'\{'  
    RBRACE = r'\}'   
    LBRACKET = r'\['
    RBRACKET = r'\]'
    COMA   = r','
    DEREF  = r'`'

    
    FLOTANTE = r'[+-]?(\d+\.\d*|\.\d+|\d+\.|\d+)([eE][+-]?\d+)?'
    ENTERO = r'\d+'
    
    # Carácter CORRECTO
    @_(r"'([^\\']|\\x[0-9a-fA-F]{2}|\\n|\\')'")
    def CHAR(self, t):
        return t

    # ERROR: Constante de carácter sin terminación
    @_(r"'[^\n]*")
    def ignore_unterminated_char(self, t):
        print(f"linea {self.lineno}: Constante de carácter sin terminación")


    # Identificadores y Palabras Reservadas
    ID = r'[a-zA-Z_][a-zA-Z0-9_]*'

    # Diccionario interno
    ID['constant'] = CONSTANT
    ID['print']    = PRINT
    ID['return']   = RETURN
    ID['break']    = BREAK
    ID['continue'] = CONTINUE
    ID['if']       = IF
    ID['else']     = ELSE
    ID['while']    = WHILE
    ID['function'] = FUNCTION
    ID['true']     = TRUE
    ID['false']    = FALSE

    # Manejo de nuevas líneas 
    @_(r'\n+')
    def ignore_newline(self, t):
        self.lineno += t.value.count('\n')

    # Manejo de Errores Básico 
    def error(self, t):
        print(f"linea {self.lineno}: Carácter '{t.value[0]}' ilegal")
        self.index += 1


# =============================================================================
# PRUEBAS UNITARIAS
# =============================================================================

class TestBMinorLexer(unittest.TestCase):

    def setUp(self):
        self.lexer = BMinorLexer()

    def get_tokens(self, text):
        return [(tok.type, tok.value) for tok in self.lexer.tokenize(text)]

    def get_types(self, text):
        return [tok.type for tok in self.lexer.tokenize(text)]

    
    # LITERALES NUMÉRICOS

    # 1 Entero
    def test_integer(self):
        tokens = self.get_tokens("123")
        self.assertEqual(tokens[0], ("ENTERO", "123"))

    # 2 Flotante con parte decimal
    def test_float_full(self):
        tokens = self.get_tokens("1.234")
        self.assertEqual(tokens[0], ("FLOTANTE", "1.234"))

    # 3 Flotante sin parte entera (.5)
    def test_float_no_integer_part(self):
        tokens = self.get_tokens(".14")
        self.assertEqual(tokens[0], ("FLOTANTE", ".14"))

    # 4 Flotante sin parte decimal (3.)
    def test_float_no_decimal_part(self):
        tokens = self.get_tokens("3.")
        self.assertEqual(tokens[0], ("FLOTANTE", "3."))


    # IDENTIFICADORES Y KEYWORDS

    # 5 Identificador simple
    def test_identifier(self):
        tokens = self.get_tokens("mivariable1")
        self.assertEqual(tokens[0], ("ID", "mivariable1"))

    # 6 Identificador con guion bajo
    def test_identifier_underscore(self):
        tokens = self.get_tokens("_mi_var123")
        self.assertEqual(tokens[0], ("ID", "_mi_var123"))

    # 7 Todas las keywords generan su token correcto
    def test_todas_las_keywords(self):
        casos = [
            ('constant', 'CONSTANT'),
            ('print',    'PRINT'),
            ('return',   'RETURN'),
            ('break',    'BREAK'),
            ('continue', 'CONTINUE'),
            ('if',       'IF'),
            ('else',     'ELSE'),
            ('while',    'WHILE'),
            ('function', 'FUNCTION'),
            ('true',     'TRUE'),
            ('false',    'FALSE'),
        ]
        for texto, esperado in casos:
            with self.subTest(texto=texto):
                # Lexer fresco por cada subTest para evitar estado compartido
                lexer = BMinorLexer()
                tipos = [tok.type for tok in lexer.tokenize(texto)]
                self.assertEqual(tipos, [esperado],
                    f"'{texto}' debería generar [{esperado}], obtuvo {tipos}")

    # 8 Keyword como prefijo de otro texto → debe ser ID, no keyword
    def test_keyword_como_prefijo_es_ID(self):
        tipos = self.get_types("ifelse")
        self.assertEqual(tipos, ["ID"])

 
    # LITERALES CHAR

    # 9 Char válido con letra
    def test_char_valid(self):
        tokens = self.get_tokens("'a'")
        self.assertEqual(tokens[0][0], "CHAR")

    # 10 Char con escape \n
    def test_char_escape_newline(self):
        tokens = self.get_tokens(r"'\n'")
        self.assertEqual(tokens[0][0], "CHAR")

    # 11 Char sin terminar → error, no genera token CHAR
    def test_char_sin_terminar(self):
        salida = io.StringIO()
        sys.stdout = salida
        tipos = self.get_types("'a")
        sys.stdout = sys.__stdout__
        self.assertNotIn("CHAR", tipos)
        self.assertIn("Constante de carácter sin terminación", salida.getvalue())


    # OPERADORES Y SÍMBOLOS

    # 12 Operadores de dos caracteres no se parten en dos tokens
    def test_operadores_dos_caracteres(self):
        casos = [
            ("<=", "LE"), (">=", "GE"), ("==", "EQ"),
            ("!=", "NE"), ("&&", "LAND"), ("||", "LOR"),
        ]
        for texto, esperado in casos:
            with self.subTest(op=texto):
                lexer = BMinorLexer()
                tipos = [tok.type for tok in lexer.tokenize(texto)]
                self.assertEqual(tipos, [esperado],
                    f"'{texto}' debería ser [{esperado}], obtuvo {tipos}")

    # 13 Operador suma
    def test_plus_operator(self):
        tokens = self.get_tokens("+")
        self.assertEqual(tokens[0], ("PLUS", "+"))

    # 14 Token DEREF (comilla invertida)
    def test_deref(self):
        tipos = self.get_types("`")
        self.assertEqual(tipos, ["DEREF"])

    # COMENTARIOS

    # 15 Comentario de línea es ignorado
    def test_line_comment_ignored(self):
        tipos = self.get_types("// esto es un comentario\nx = 1;")
        self.assertEqual(tipos, ["ID", "ASSIGN", "ENTERO", "SEMI"])

    # 16 Comentario sin cerrar → reporta error
    def test_comentario_sin_cerrar(self):
        salida = io.StringIO()
        sys.stdout = salida
        self.get_types("/* sin cerrar")
        sys.stdout = sys.__stdout__
        self.assertIn("Comentario sin terminación", salida.getvalue())


    # ERRORES Y RECUPERACIÓN

    # 17 Carácter ilegal reporta error
    def test_caracter_ilegal(self):
        salida = io.StringIO()
        sys.stdout = salida
        self.get_types("@")
        sys.stdout = sys.__stdout__
        self.assertIn("ilegal", salida.getvalue())

    # 18 Tras un carácter ilegal el lexer se recupera y sigue tokenizando
    def test_recuperacion_tras_error(self):
        tipos = self.get_types("x @ y")
        self.assertEqual(tipos.count("ID"), 2)


if __name__ == '__main__':
    import sys

    # Si se pasa el argumento "test", correr pruebas unitarias
    # python bMinorLexer.py test
    if len(sys.argv) > 1 and sys.argv[1] == 'test':
        sys.argv.pop(1)  # quitar 'test' para que unittest no lo confunda
        unittest.main(verbosity=2)
    else:
        # Demo del lexer
        lex = BMinorLexer()
        test_code = """
        // Esto es un comentario valido
        3.14
        .14
        .014
        0.14
        1e10
        1.1e-1
        10e+1
        +12e-12
        -31e-3
        .000000100001
        +31.42e-34
        """
        print("Probando Lexer:")
        for tok in lex.tokenize(test_code):
            print(tok)