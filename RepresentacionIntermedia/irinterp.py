from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional


class IRRuntimeError(RuntimeError):
	"""Generic IR interpreter error."""
	
	
class IRReturn(Exception):
	def __init__(self, value: Any):
		self.value = value
		
		
@dataclass
class IRFunction:
	"""
	Runtime function container.
	
	Compatible with several possible codegen layouts:
	- name, params, return_type, instructions
	- name, args, rettype, code
	"""
	name: str
	params: list[str] = field(default_factory=list)
	return_type: Any = None
	instructions: list[tuple] = field(default_factory=list)
	
	
@dataclass
class IRModule:
	globals: list[tuple] = field(default_factory=list)
	functions: list[Any] = field(default_factory=list)
	
	
@dataclass
class Frame:
	name: str
	instructions: list[tuple]
	params: list[str] = field(default_factory=list)
	locals: dict[str, Any] = field(default_factory=dict)
	pc: int = 0
	stack: list[Any] = field(default_factory=list)
	labels: dict[str, int] = field(default_factory=dict)
	regs: dict[str, Any] = field(default_factory=dict)  # registros virtuales R1, R2, ...
	
	def __post_init__(self):
		self.labels = self._index_labels(self.instructions)
		
	@staticmethod
	def _index_labels(code: list[tuple]) -> dict[str, int]:
		labels: dict[str, int] = {}
		for i, inst in enumerate(code):
			if inst and inst[0] == "LABEL":
				if len(inst) != 2:
					raise IRRuntimeError(f"LABEL inválido: {inst}")
				labels[inst[1]] = i
		return labels
		
		
class IRInterpreter:
	"""
	Intérprete para un IR estilo máquina de pila inspirado en el material de Dabeaz.
	
	Soporta:
	- enteros, flotantes y bytes
	- variables globales y locales
	- operaciones sobre pila
	- IF/ELSE/ENDIF
	- LOOP/CBREAK/CONTINUE/ENDLOOP
	- LABEL/BRANCH/CBRANCH
	- CALL/RET
	- memoria lineal con PEEK/POKE/GROW
	
	Convenciones:
	- bool se representa con enteros 0/1
	- byte se trunca con & 0xFF
	- las funciones reciben argumentos ya evaluados
	- LOAD/STORE buscan primero en locales y luego en globals
	"""
	
	def __init__(self, module_or_functions: Any = None, memory_size: int = 65536, trace: bool = False):
		self.trace = trace
		self.memory = bytearray(memory_size)
		self.globals: dict[str, Any] = {}
		self.functions: dict[str, Frame | Any] = {}
		self.call_depth = 0
		
		if module_or_functions is not None:
			self.load(module_or_functions)
			
	# -------------------------------------------------
	# Public API
	# -------------------------------------------------
	
	def load(self, module_or_functions: Any) -> None:
		self.functions.clear()
		
		if hasattr(module_or_functions, "functions"):
			module = module_or_functions
			if hasattr(module, "globals"):
				self._execute_global_inits(getattr(module, "globals"))
			for fn in getattr(module, "functions"):
				self._register_function(fn)
			return
			
		if isinstance(module_or_functions, dict):
			for name, fn in module_or_functions.items():
				self.functions[name] = fn
			return
			
		if isinstance(module_or_functions, list):
			for fn in module_or_functions:
				self._register_function(fn)
			return
			
		raise IRRuntimeError(f"No puedo cargar funciones desde {type(module_or_functions).__name__}")
		
	def run(self, name: str = "main", *args):
		return self.call(name, list(args))
		
	def call(self, name: str, args: list[Any]):
		if name not in self.functions:
			raise IRRuntimeError(f"Función no encontrada: {name}")
			
		fn = self.functions[name]
		
		# Permitir builtins Python
		if callable(fn) and not hasattr(fn, "instructions") and not hasattr(fn, "code"):
			return fn(*args)
			
		frame = self._make_frame(fn, args)
		return self._execute_frame(frame)
		
	# -------------------------------------------------
	# Frame and function helpers
	# -------------------------------------------------
	
	def _register_function(self, fn: Any) -> None:
		name = getattr(fn, "name", None)
		if not name:
			raise IRRuntimeError(f"Función sin nombre: {fn}")
		self.functions[name] = fn
		
	def _make_frame(self, fn: Any, args: list[Any]) -> Frame:
		instructions = self._extract_code(fn)
		param_names = self._extract_param_names(fn)
		
		if len(args) != len(param_names):
			raise IRRuntimeError(
				f"La función {getattr(fn, 'name', '<anon>')} esperaba {len(param_names)} args y recibió {len(args)}"
			)
			
		locals_: dict[str, Any] = {}
		for name, value in zip(param_names, args):
			locals_[name] = value
			
		return Frame(
			name=getattr(fn, "name", "<anon>"),
			instructions=instructions,
			params=param_names,
			locals=locals_,
		)
		
	def _extract_code(self, fn: Any) -> list[tuple]:
		if hasattr(fn, "instructions"):
			return list(getattr(fn, "instructions"))
		if hasattr(fn, "code"):
			return list(getattr(fn, "code"))
		raise IRRuntimeError(f"No encuentro instrucciones en {fn}")
		
	def _extract_param_names(self, fn: Any) -> list[str]:
		if hasattr(fn, "params"):
			params = getattr(fn, "params")
			out = []
			for p in params:
				if isinstance(p, tuple):
					out.append(p[0])
				else:
					out.append(str(p))
			return out
		if hasattr(fn, "args"):
			return [str(x) for x in getattr(fn, "args")]
		return []
		
	# -------------------------------------------------
	# Global initialization
	# -------------------------------------------------
	
	def _execute_global_inits(self, code: list[tuple]) -> None:
		"""
		Ejecuta una secuencia simple de inicialización global.
		Usa un frame sintético llamado _globals.
		"""
		if not code:
			return
		frame = Frame(name="_globals", instructions=list(code))
		self._execute_frame(frame)
		
	# -------------------------------------------------
	# Core execution
	# -------------------------------------------------
	
	def _execute_frame(self, frame: Frame):
		self.call_depth += 1
		try:
			while frame.pc < len(frame.instructions):
				inst = frame.instructions[frame.pc]
				self._trace(frame, inst)
				jumped = self._dispatch(frame, inst)
				if not jumped:
					frame.pc += 1
		except IRReturn as ret:
			return ret.value
		finally:
			self.call_depth -= 1
		return None
		
	def _dispatch(self, frame: Frame, inst: tuple) -> bool:
		op = inst[0]
		args = inst[1:]
		
		# -----------------------------------------------
		# No-op structure / labels
		# -----------------------------------------------
		if op == "LABEL":
			return False
			
		# -----------------------------------------------
		# Integer / float / byte constants
		# -----------------------------------------------
		if op == "CONSTI":
			self._push(frame, int(args[0]))
			return False
		if op == "CONSTF":
			self._push(frame, float(args[0]))
			return False
		if op == "CONSTB":
			self._push(frame, int(args[0]) & 0xFF)
			return False
			
    # -----------------------------------------------
		# Variable declarations
		# -----------------------------------------------

		if op in {"GLOBALI", "GLOBALF", "GLOBALB"}:
			name = args[0]
			self.globals.setdefault(name, 0)
			return False

		if op in {"VARI", "VARF", "VARB"}:
			name = args[0]
			self.globals[name] = 0
			return False

		if op in {"LOCALI", "LOCALF", "LOCALB"}:
			name = args[0]
			frame.locals.setdefault(name, 0)
			return False
		
			
		# -----------------------------------------------
		# Variable load / store
		# -----------------------------------------------
		if op == "LOAD":
			name = args[0]
			self._push(frame, self._load_var(frame, name))
			return False
			
		if op == "STORE":
			name = args[0]
			value = self._pop(frame)
			self._store_var(frame, name, value)
			return False
			
		# Compatibility aliases if some codegen emits typed store/load
		# Soporte para arquitectura de registros:
		#   LOADI  varname, Rdest    -> Rdest = var
		#   LOADI  varname           -> push var (modo pila)
		if op in {"LOADI", "LOADF", "LOADB"}:
			name = args[0]
			value = self._load_var(frame, name)
			if len(args) == 2 and self._is_reg(args[1]):
				frame.regs[args[1]] = value
			else:
				self._push(frame, value)
			return False
		
		# Soporte para arquitectura de registros:
		#   STOREI Rsrc, varname     -> var = Rsrc
		#   STOREI varname           -> pop -> var (modo pila)
		if op in {"STOREI", "STOREF", "STOREB"}:
			if len(args) == 2 and self._is_reg(args[0]):
				value = self._reg_read(frame, args[0])
				name = args[1]
			else:
				name = args[0]
				value = self._pop(frame)
			if op == "STOREB":
				value = int(value) & 0xFF
			self._store_var(frame, name, value)
			return False


		# -----------------------------------------------
		# Opcodes de arquitectura de registros
		# -----------------------------------------------

		# MOVI / MOVF / MOVB: mueve inmediato a registro
		#   MOVI  value, Rdest
		if op in {"MOVI", "MOVF", "MOVB"}:
			if len(args) == 2 and self._is_reg(args[1]):
				val = args[0]
				if op == "MOVF":
					val = float(val)
				elif op == "MOVB":
					val = int(val) & 0xFF
				else:
					val = int(val)
				frame.regs[args[1]] = val
				return False
			# fallthrough: si no hay registro destino, tratar como CONSTI
			self._push(frame, int(args[0]))
			return False

		# ALLOCI / ALLOCF / ALLOCB: declara variable local (modo registro)
		#   ALLOCI varname
		if op in {"ALLOCI", "ALLOCF", "ALLOCB"}:
			name = args[0]
			if name not in frame.locals and name not in self.globals:
				frame.locals[name] = 0
			return False

		# VARАРР: declara array global con tamaño en registro
		#   VARАРР name, Rsize
		if op == "VARARR":
			name = args[0]
			size_arg = args[1]
			if self._is_reg(size_arg):
				size = int(self._reg_read(frame, size_arg))
			else:
				size = int(size_arg)
			if size < 0:
				raise IRRuntimeError(f"Tamaño inválido para array '{name}': {size}")
			arr = [0] * size
			self.globals[name] = arr
			return False

		# -----------------------------------------------
		# Arrays
		# -----------------------------------------------
		if op == "ALLOCARR":
			name = args[0]

			# tamaño puede venir directo o desde stack
			if len(args) > 1:
				size = int(args[1])
			else:
				size = int(self._pop(frame))

			if size < 0:
				raise IRRuntimeError(
					f"Tamaño inválido para array '{name}': {size}"
				)

			arr = [0] * size

			# global o local
			if name in self.globals:
				self.globals[name] = arr
			else:
				frame.locals[name] = arr

			return False


		if op == "STOREIIDX":
			# Modo registro: STOREIIDX Rvalue, name, Rindex
			# Modo stack:   STOREIIDX name  (pop index, pop value)
			# Modo mixto:   STOREIIDX value, name, index  (sin registros)

			if len(args) == 3:
				value_arg = args[0]
				name = args[1]
				index_arg = args[2]

				if self._is_reg(value_arg):
					value = self._reg_read(frame, value_arg)
				elif isinstance(value_arg, str):
					value = self._load_var(frame, value_arg)
				else:
					value = value_arg

				if self._is_reg(index_arg):
					index = self._reg_read(frame, index_arg)
				elif isinstance(index_arg, str):
					index = self._load_var(frame, index_arg)
				else:
					index = index_arg

			else:
				index = self._pop(frame)
				value = self._pop(frame)
				name = args[0]

			index = int(index)

			# buscar array
			if name in frame.locals:
				arr = frame.locals[name]
			elif name in self.globals:
				arr = self.globals[name]
			else:
				raise IRRuntimeError(
					f"Array no definido: {name}"
				)

			# validar índice
			if index < 0 or index >= len(arr):
				raise IRRuntimeError(
					f"Índice fuera de rango: {name}[{index}]"
				)

			arr[index] = value

			return False


		if op == "LOADIIDX":
			# Modo registro: LOADIIDX name, Rindex, Rdest
			# Modo stack:   LOADIIDX name  (pop index, push value)
			# Modo mixto:   LOADIIDX name, index, target (sin registros)

			if len(args) == 3:
				name = args[0]
				index_arg = args[1]
				target = args[2]

				if self._is_reg(index_arg):
					index = self._reg_read(frame, index_arg)
				elif isinstance(index_arg, str):
					index = self._load_var(frame, index_arg)
				else:
					index = index_arg

			else:
				index = self._pop(frame)
				name = args[0]
				target = None

			index = int(index)

			# buscar array
			if name in frame.locals:
				arr = frame.locals[name]
			elif name in self.globals:
				arr = self.globals[name]
			else:
				raise IRRuntimeError(
					f"Array no definido: {name}"
				)

			# validar índice
			if index < 0 or index >= len(arr):
				raise IRRuntimeError(
					f"Índice fuera de rango: {name}[{index}]"
				)

			value = arr[index]

			# modo registro o stack
			if target is not None:
				if self._is_reg(target):
					frame.regs[target] = value
				else:
					frame.locals[target] = value
			else:
				self._push(frame, value)

			return False

		# -----------------------------------------------
		# Arithmetic / logical
		# -----------------------------------------------

		if op in {"ADDI", "SUBI", "MULI", "DIVI", "ANDI", "ORI", "XORI"}:

			# -----------------------------------
			# FORMATO SSA
			# OP R1, R2, Rdest
			# -----------------------------------

			if len(args) == 3:

				left = args[0]
				right = args[1]
				target = args[2]

				if self._is_reg(left):
					a = int(self._reg_read(frame, left))
				else:
					a = int(self._load_var(frame, left))

				if self._is_reg(right):
					b = int(self._reg_read(frame, right))
				else:
					b = int(self._load_var(frame, right))

				if op == "ADDI":
					result = a + b

				elif op == "SUBI":
					result = a - b

				elif op == "MULI":
					result = a * b

				elif op == "DIVI":

					if b == 0:
						raise IRRuntimeError(
							"División por cero en DIVI"
						)

					result = int(a / b)

				elif op == "ANDI":
					result = a & b

				elif op == "ORI":
					result = a | b

				else:
					result = a ^ b

				frame.regs[target] = result

				return False

			# -----------------------------------
			# FORMATO STACK ORIGINAL
			# -----------------------------------

			b = int(self._pop(frame))
			a = int(self._pop(frame))

			if op == "ADDI":
				self._push(frame, a + b)

			elif op == "SUBI":
				self._push(frame, a - b)

			elif op == "MULI":
				self._push(frame, a * b)

			elif op == "DIVI":

				if b == 0:
					raise IRRuntimeError(
						"División por cero en DIVI"
					)

				self._push(frame, int(a / b))

			elif op == "ANDI":
				self._push(frame, a & b)

			elif op == "ORI":
				self._push(frame, a | b)

			else:
				self._push(frame, a ^ b)

			return False


		if op in {"ADDF", "SUBF", "MULF", "DIVF"}:
			b = float(self._pop(frame))
			a = float(self._pop(frame))

			if op == "ADDF":
				self._push(frame, a + b)

			elif op == "SUBF":
				self._push(frame, a - b)

			elif op == "MULF":
				self._push(frame, a * b)

			else:

				if b == 0.0:
					raise IRRuntimeError(
						"División por cero en DIVF"
					)

				self._push(frame, a / b)

			return False

		
		# -----------------------------------------------
		# Comparisons
		# -----------------------------------------------
		if op in {"LTI", "LEI", "GTI", "GEI", "EQI", "NEI"}:
			b = int(self._pop(frame))
			a = int(self._pop(frame))
			self._push(frame, int(self._compare(op, a, b)))
			return False
			
		if op in {"LTF", "LEF", "GTF", "GEF", "EQF", "NEF"}:
			b = float(self._pop(frame))
			a = float(self._pop(frame))
			self._push(frame, int(self._compare(op, a, b)))
			return False
			
		if op == "CMPF":
			cmpop = args[0]
			b = float(self._pop(frame))
			a = float(self._pop(frame))
			self._push(frame, int(self._compare_symbol(cmpop, a, b)))
			return False
			
		if op == "CMPI":

			# FORMATO REGISTRO:
			# CMPI <, R1, R2, R3
			if len(args) == 4:

				cmpop = args[0]
				left = args[1]
				right = args[2]
				target = args[3]

				if self._is_reg(left):
					a = self._reg_read(frame, left)
				else:
					a = self._load_var(frame, left)

				if self._is_reg(right):
					b = self._reg_read(frame, right)
				else:
					b = self._load_var(frame, right)

				result = int(
					self._compare_symbol(cmpop, a, b)
				)

				if self._is_reg(target):
					frame.regs[target] = result
				else:
					frame.locals[target] = result

				return False

			# FORMATO STACK
			cmpop = args[0]
			b = int(self._pop(frame))
			a = int(self._pop(frame))

			self._push(
				frame,
				int(self._compare_symbol(cmpop, a, b))
			)

			return False
			
		if op == "CMPB":
			cmpop = args[0]
			b = int(self._pop(frame)) & 0xFF
			a = int(self._pop(frame)) & 0xFF
			self._push(frame, int(self._compare_symbol(cmpop, a, b)))
			return False

		# EQ Rdest
		if op == "EQ":

			value = self._pop(frame)

			result = int(value == 0)

			target = args[0]

			if self._is_reg(target):
				frame.regs[target] = result
			else:
				frame.locals[target] = result

			return False
			
		# -----------------------------------------------
		# Printing / debugging
		# -----------------------------------------------
		# PRINTI / PRINTF / PRINTB: soporta modo registro y modo pila
		#   PRINTI Rn   -> imprime el valor del registro Rn
		#   PRINTI      -> imprime el tope del stack
		if op == "PRINTI":
			if args and self._is_reg(args[0]):
				print(int(self._reg_read(frame, args[0])))
			else:
				print(int(self._pop(frame)))
			return False
		if op == "PRINTF":
			if args and self._is_reg(args[0]):
				print(float(self._reg_read(frame, args[0])))
			else:
				print(float(self._pop(frame)))
			return False
		if op == "PRINTB":
			if args and self._is_reg(args[0]):
				print(chr(int(self._reg_read(frame, args[0])) & 0xFF), end="")
			else:
				print(chr(int(self._pop(frame)) & 0xFF), end="")
			return False
			
		# -----------------------------------------------
		# Type conversions
		# -----------------------------------------------
		if op == "ITOF":
			self._push(frame, float(int(self._pop(frame))))
			return False
		if op == "FTOI":
			self._push(frame, int(float(self._pop(frame))))
			return False
		if op == "ITOB":
			self._push(frame, int(self._pop(frame)) & 0xFF)
			return False
		if op == "BTOI":
			self._push(frame, int(self._pop(frame)) & 0xFF)
			return False
			
		# -----------------------------------------------
		# Memory
		# -----------------------------------------------
		if op == "GROW":
			nbytes = int(self._pop(frame))
			if nbytes < 0:
				raise IRRuntimeError("GROW con tamaño negativo")
			self.memory.extend(b"\x00" * nbytes)
			self._push(frame, len(self.memory))
			return False
			
		if op == "PEEKI":
			addr = int(self._pop(frame))
			self._push(frame, self._mem_read_int(addr))
			return False
			
		if op == "POKEI":
			value = int(self._pop(frame))
			addr = int(self._pop(frame))
			self._mem_write_int(addr, value)
			return False
			
		if op == "PEEKF":
			import struct
			addr = int(self._pop(frame))
			self._ensure_mem(addr, 8)
			self._push(frame, struct.unpack("<d", self.memory[addr:addr + 8])[0])
			return False
			
		if op == "POKEF":
			import struct
			value = float(self._pop(frame))
			addr = int(self._pop(frame))
			self._ensure_mem(addr, 8)
			self.memory[addr:addr + 8] = struct.pack("<d", value)
			return False
			
		if op == "PEEKB":
			addr = int(self._pop(frame))
			self._ensure_mem(addr, 1)
			self._push(frame, self.memory[addr])
			return False
			
		if op == "POKEB":
			value = int(self._pop(frame)) & 0xFF
			addr = int(self._pop(frame))
			self._ensure_mem(addr, 1)
			self.memory[addr] = value
			return False
			
		# -----------------------------------------------
		# Structured IF / LOOP
		# -----------------------------------------------
		if op == "IF":
			test = self._pop(frame)
			if test:
				return False
			frame.pc = self._find_else_or_endif(frame.instructions, frame.pc)
			return True
			
		if op == "ELSE":
			frame.pc = self._find_matching_endif(frame.instructions, frame.pc)
			return True
			
		if op == "ENDIF":
			return False
			
		if op == "LOOP":
			return False
			
		if op == "CBREAK":
			test = self._pop(frame)
			if test:
				frame.pc = self._find_matching_endloop(frame.instructions, frame.pc)
				return True
			return False
			
		if op == "CONTINUE":
			frame.pc = self._find_loop_start(frame.instructions, frame.pc)
			return True
			
		if op == "ENDLOOP":
			frame.pc = self._find_loop_start(frame.instructions, frame.pc)
			return True
			
		# -----------------------------------------------
		# Label-based control flow
		# -----------------------------------------------
		if op == "JUMP":
			label = args[0]
			frame.pc = self._jump_to_label(frame, label)
			return True

		if op == "BRANCH":
			label = args[0]
			frame.pc = self._jump_to_label(frame, label)
			return True
			
		if op == "CBRANCH":

			# FORMATO REGISTRO:
			# CBRANCH Rcond, Ltrue, Lfalse
			if len(args) == 3:

				cond = args[0]
				label_true = args[1]
				label_false = args[2]

				if self._is_reg(cond):
					test = self._reg_read(frame, cond)
				else:
					test = self._load_var(frame, cond)

				frame.pc = self._jump_to_label(
					frame,
					label_true if test else label_false
				)

				return True

			# FORMATO STACK
			test = self._pop(frame)

			label_true, label_false = args

			frame.pc = self._jump_to_label(
				frame,
				label_true if test else label_false
			)

			return True
			
		# -----------------------------------------------
		# Calls / returns
		# -----------------------------------------------
		if op == "CALL":

			name = args[0]

			# -----------------------------------
			# FORMATO REGISTRO
			# CALL fn, arg1, arg2, ..., Rdest
			# -----------------------------------

			if len(args) >= 2 and self._is_reg(args[-1]):

				dest = args[-1]

				call_args = []

				for arg in args[1:-1]:

					if self._is_reg(arg):
						call_args.append(
							self._reg_read(frame, arg)
						)

					elif isinstance(arg, str):

						call_args.append(
							self._load_var(frame, arg)
						)

					else:
						call_args.append(arg)

				result = self.call(name, call_args)

				frame.regs[dest] = result

				return False

			# -----------------------------------
			# FORMATO STACK ORIGINAL
			# -----------------------------------

			argc = int(args[1]) if len(args) > 1 else 0

			call_args = [
				self._pop(frame)
				for _ in range(argc)
			]

			call_args.reverse()

			result = self.call(name, call_args)

			if result is not None:
				self._push(frame, result)

			return False

		if op == "RET":

			# RET Rn
			if args:

				src = args[0]

				if self._is_reg(src):
					value = self._reg_read(frame, src)
				else:
					value = self._load_var(frame, src)

				raise IRReturn(value)

			# RET stack
			value = self._pop(frame) if frame.stack else None

			raise IRReturn(value)
		
		# -----------------------------------------------
		# Registro: instrucción genérica de copia entre registros
		# -----------------------------------------------
		# MOV Rsrc, Rdest
		if op == "MOV":
			if len(args) == 2:
				src, dst = args
				if self._is_reg(src):
					frame.regs[dst] = self._reg_read(frame, src)
				else:
					frame.regs[dst] = self._load_var(frame, src)
			return False
			
		raise IRRuntimeError(f"Opcode no soportado: {op}")
		
	# -------------------------------------------------
	# Utility methods
	# -------------------------------------------------
	
	def _trace(self, frame: Frame, inst: tuple) -> None:
		if not self.trace:
			return
		indent = "  " * max(0, self.call_depth - 1)
		print(f"{indent}[{frame.name} pc={frame.pc}] {inst} stack={frame.stack} locals={frame.locals}")
		
	def _push(self, frame: Frame, value: Any) -> None:
		frame.stack.append(value)
		
	def _pop(self, frame: Frame) -> Any:
		if not frame.stack:
			raise IRRuntimeError("Stack underflow")
		return frame.stack.pop()

	@staticmethod
	def _is_reg(name: Any) -> bool:
		"""Devuelve True si 'name' tiene forma de registro virtual (R seguido de dígitos)."""
		if not isinstance(name, str):
			return False
		return len(name) >= 2 and name[0] == "R" and name[1:].isdigit()

	def _reg_read(self, frame: Frame, reg: str) -> Any:
		"""Lee el valor de un registro virtual del frame actual."""
		if reg not in frame.regs:
			raise IRRuntimeError(f"Registro no inicializado: {reg}")
		return frame.regs[reg]
		
	def _load_var(self, frame: Frame, name: str) -> Any:
		if name in frame.locals:
			return frame.locals[name]
		if name in self.globals:
			return self.globals[name]
		raise IRRuntimeError(f"Variable no definida: {name}")
		
	def _store_var(self, frame: Frame, name: str, value: Any) -> None:
		if name in frame.locals:
			frame.locals[name] = value
			return
		if name in self.globals:
			self.globals[name] = value
			return
		# Si no existe, asumimos local implícita
		frame.locals[name] = value
		
	def _jump_to_label(self, frame: Frame, label: str) -> int:
		if label not in frame.labels:
			raise IRRuntimeError(f"Label no encontrado: {label}")
		return frame.labels[label]
		
	def _ensure_mem(self, addr: int, size: int) -> None:
		if addr < 0:
			raise IRRuntimeError("Dirección de memoria negativa")
		if addr + size > len(self.memory):
			raise IRRuntimeError("Acceso de memoria fuera de rango")
			
	def _mem_read_int(self, addr: int) -> int:
		import struct
		self._ensure_mem(addr, 8)
		return struct.unpack("<q", self.memory[addr:addr + 8])[0]
		
	def _mem_write_int(self, addr: int, value: int) -> None:
		import struct
		self._ensure_mem(addr, 8)
		self.memory[addr:addr + 8] = struct.pack("<q", int(value))
		
	@staticmethod
	def _compare(op: str, a: Any, b: Any) -> bool:
		if op in {"LTI", "LTF"}:
			return a < b
		if op in {"LEI", "LEF"}:
			return a <= b
		if op in {"GTI", "GTF"}:
			return a > b
		if op in {"GEI", "GEF"}:
			return a >= b
		if op in {"EQI", "EQF"}:
			return a == b
		if op in {"NEI", "NEF"}:
			return a != b
		raise IRRuntimeError(f"Comparación desconocida: {op}")
		
	@staticmethod
	def _compare_symbol(op: str, a: Any, b: Any) -> bool:
		if op == "<":
			return a < b
		if op == "<=":
			return a <= b
		if op == ">":
			return a > b
		if op == ">=":
			return a >= b
		if op == "==":
			return a == b
		if op == "!=":
			return a != b
		raise IRRuntimeError(f"Operador de comparación desconocido: {op}")
		
	# -------------------------------------------------
	# Structured control flow search helpers
	# -------------------------------------------------
	
	@staticmethod
	def _find_else_or_endif(code: list[tuple], start: int) -> int:
		depth = 0
		for i in range(start + 1, len(code)):
			op = code[i][0]
			if op == "IF":
				depth += 1
			elif op == "ENDIF":
				if depth == 0:
					return i
				depth -= 1
			elif op == "ELSE" and depth == 0:
				return i
		raise IRRuntimeError("No se encontró ELSE/ENDIF correspondiente")
		
	@staticmethod
	def _find_matching_endif(code: list[tuple], start: int) -> int:
		depth = 0
		for i in range(start + 1, len(code)):
			op = code[i][0]
			if op == "IF":
				depth += 1
			elif op == "ENDIF":
				if depth == 0:
					return i
				depth -= 1
		raise IRRuntimeError("No se encontró ENDIF correspondiente")
		
	@staticmethod
	def _find_matching_endloop(code: list[tuple], start: int) -> int:
		depth = 0
		for i in range(start + 1, len(code)):
			op = code[i][0]
			if op == "LOOP":
				depth += 1
			elif op == "ENDLOOP":
				if depth == 0:
					return i
				depth -= 1
		raise IRRuntimeError("No se encontró ENDLOOP correspondiente")
		
	@staticmethod
	def _find_loop_start(code: list[tuple], start: int) -> int:
		depth = 0
		for i in range(start - 1, -1, -1):
			op = code[i][0]
			if op == "ENDLOOP":
				depth += 1
			elif op == "LOOP":
				if depth == 0:
					return i
				depth -= 1
		raise IRRuntimeError("No se encontró LOOP correspondiente")
		
		
# ---------------------------------------------------
# Small demo
# ---------------------------------------------------

def _demo_module() -> IRModule:
	"""
	Programa demo:
	x: integer = 1;
	while x <= 5 {
		print x;
		x = x + 1;
	}
	return x;
	"""
	main = IRFunction(
		name="main",
		params=[],
		return_type="I",
		instructions=[
			("LOCALI", "x"),
			("CONSTI", 1),
			("STORE", "x"),
			
			("LOOP",),
				("LOAD", "x"),
				("CONSTI", 5),
				("LEI",),
				("CONSTI", 0),
				("EQI",),       # test de break: !(x <= 5)
				("CBREAK",),
			
				("LOAD", "x"),
				("PRINTI",),
			
				("LOAD", "x"),
				("CONSTI", 1),
				("ADDI",),
				("STORE", "x"),
			("ENDLOOP",),
			
			("LOAD", "x"),
			("RET",),
		],
	)
	return IRModule(functions=[main])
	
	
if __name__ == "__main__":
	interp = IRInterpreter(_demo_module(), trace=False)
	result = interp.run("main")
	print("\nreturn =", result)
