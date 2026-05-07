# errors.py
'''
Gestión de errores del compilador.
'''
from rich import print

_errors_detected = 0
_source_lines = [] 

def load_source(text: str):
    """
    NUEVO: Carga el código fuente en la memoria de errores.
    Así podemos imprimir la línea exacta que causó el problema.
    """
    global _source_lines
    _source_lines = text.splitlines()

def error(message, lineno=None):
    global _errors_detected
    
    if lineno:
        # 1. Imprimimos el mensaje de error destacado
        print(f'[bold red] Error Semántico en línea {lineno}:[/bold red] {message}')
        
        # 2. Si tenemos el código fuente, imprimimos la línea exacta
        if _source_lines and 1 <= lineno <= len(_source_lines):
            # Restamos 1 porque las listas en Python empiezan en 0, pero las líneas en 1
            codigo_malo = _source_lines[lineno - 1]
            print(f'   [bold cyan]{lineno} |[/bold cyan] [white]{codigo_malo}[/white]')
            print() # Un salto de línea para que no se amontonen los errores
    else:
        print(f"[bold red] Error Semántico:[/bold red] {message}")
        
    _errors_detected += 1
    
def errors_detected():
    return _errors_detected
    
def clear_errors():
    global _errors_detected
    _errors_detected = 0