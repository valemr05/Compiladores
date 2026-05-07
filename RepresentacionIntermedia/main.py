#!/usr/bin/env python3
# main.py
import sys
import os

# DEBE IR AQUÍ ANTES DE CUALQUIER OTRO IMPORT
# Fuerza a Python a buscar primero en la carpeta del proyecto
# antes de buscar en los módulos built-in (como el 'parser' de Python 3.9)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from rich import print
from errors  import clear_errors, errors_detected, load_source
from lexer   import Lexer
from parser  import Parser
from checker import Checker
from ircode_starter  import IRCodeGen


def parse_and_check(filename: str):
    if not os.path.isfile(filename):
        print(f"error: no se encontró el archivo '{filename}'")
        return None

    clear_errors()

    src = open(filename, encoding="utf-8").read()
    load_source(src)
    lexer  = Lexer()
    parser = Parser()

    ast = parser.parse(lexer.tokenize(src))

    if errors_detected():
        print("semantic check: failed (errores léxicos/sintácticos)")
        return None

    if ast is None:
        print("error: el parser no produjo un AST.")
        return None

    Checker.check(ast)

    if errors_detected():
        print("\n[bold red]semantic check: failed[/bold red]")
        return None

    return ast


def run_checker(filename: str) -> int:
    ast = parse_and_check(filename)
    if ast is None:
        return 1
    print("\n[bold green]semantic check: success[/bold green]")
    return 0


def run_ir(filename: str) -> int:
    ast = parse_and_check(filename)
    if ast is None:
        return 1

    print("\n[bold green]semantic check: success[/bold green]")
    print("\n[bold cyan]# IR generado:[/bold cyan]\n")

    ir = IRCodeGen.generate(ast)
    print(ir.format())
    return 0


def main():
    args = sys.argv[1:]

    if len(args) == 2 and args[0] == "checker":
        sys.exit(run_checker(args[1]))

    elif len(args) == 2 and args[0] == "ir":
        sys.exit(run_ir(args[1]))

    elif len(args) == 1 and args[0] not in ("--help", "-h"):
        sys.exit(run_checker(args[0]))

    else:
        print("Uso:")
        print("  python3 main.py checker <archivo.bminor>")
        print("  python3 main.py ir <archivo.bminor>")
        print("  python3 main.py <archivo.bminor>")
        sys.exit(0)


if __name__ == "__main__":
    main()