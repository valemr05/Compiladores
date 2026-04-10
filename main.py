#!/usr/bin/env python3
# main.py
# Punto de entrada del compilador B-Minor.
#
# Uso:
#   python3 main.py checker <archivo.bminor>
#   python3 main.py <archivo.bminor>          (modo checker por defecto)

import sys
import os

from errors import clear_errors, errors_detected
from lexer   import Lexer
from parser  import Parser
from checker import Checker


def run_checker(filename: str) -> int:
    """
    Ejecuta el análisis semántico sobre el archivo dado.
    Retorna 0 si no hay errores, 1 si los hay.
    """
    if not os.path.isfile(filename):
        print(f"error: no se encontró el archivo '{filename}'")
        return 1

    clear_errors()

    src = open(filename, encoding="utf-8").read()
    lexer  = Lexer()
    parser = Parser()

    ast = parser.parse(lexer.tokenize(src))

    # Si el lexer / parser generaron errores, no tiene sentido continuar
    if errors_detected():
        print("semantic check: failed (errores léxicos/sintácticos)")
        return 1

    if ast is None:
        print("error: el parser no produjo un AST.")
        print("semantic check: failed")
        return 1

    checker = Checker.check(ast)

    if checker.ok():
        print("semantic check: success")
        return 0
    else:
        for msg in checker.errors:
            print(msg)
        print("semantic check: failed")
        return 1


def main():
    args = sys.argv[1:]

    # Modo: python3 main.py checker <archivo>
    if len(args) == 2 and args[0] == "checker":
        sys.exit(run_checker(args[1]))

    # Modo: python3 main.py <archivo>  (checker por defecto)
    elif len(args) == 1 and args[0] not in ("--help", "-h"):
        sys.exit(run_checker(args[0]))

    else:
        print("Uso:")
        print("  python3 main.py checker <archivo.bminor>")
        print("  python3 main.py <archivo.bminor>")
        sys.exit(0)


if __name__ == "__main__":
    main()
