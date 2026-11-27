"""Safe parser and evaluator for price formulas (no eval).

Grammar::

    expr    = term { ("+" | "-") term }
    term    = unary { ("*" | "/") unary }
    unary   = ("-" | "+") unary | primary
    primary = number | "P" | ("min" | "max") "(" expr sep expr { sep expr } ")" | "(" expr ")"

``P`` is the bare market price. ``×`` equals ``*`` and ``−`` (U+2212) equals ``-``.
Numbers use a decimal point or comma. A comma directly between two digits is a decimal
comma (``0,02``); function arguments are separated by ``;`` or by a comma followed by a
space (``min(P, 0.3)``). Hence ``min(1,5)`` is the single number 1.5 and fails.

A formula must not decrease when ``P`` increases (this keeps P10 <= value <= P90); parse()
rejects every formula that it cannot prove to be non-decreasing.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from .errors import FormulaError

_CONST, _INC, _DEC, _NONE = "const", "inc", "dec", "none"
_FUNCTIONS: dict[str, Callable[..., float]] = {"min": min, "max": max}
_OPERATORS = {"+": "+", "-": "-", "−": "-", "*": "*", "×": "*", "/": "/"}


@dataclass(frozen=True)
class _Token:
    kind: str  # num, name, op, lpar, rpar, sep, end
    text: str
    pos: int
    value: float = 0.0


def _tokenize(text: str) -> list[_Token]:
    tokens: list[_Token] = []
    i, n = 0, len(text)
    while i < n:
        c = text[i]
        if c.isspace():
            i += 1
        elif c.isdigit() and c.isascii():
            j = i
            while j < n and text[j].isascii() and text[j].isdigit():
                j += 1
            if j + 1 < n and text[j] in ".," and text[j + 1].isascii() and text[j + 1].isdigit():
                j += 1
                while j < n and text[j].isascii() and text[j].isdigit():
                    j += 1
            tokens.append(_Token("num", text[i:j], i, float(text[i:j].replace(",", "."))))
            i = j
        elif c.isalpha():
            j = i
            while j < n and (text[j].isalnum() or text[j] == "_"):
                j += 1
            tokens.append(_Token("name", text[i:j], i))
            i = j
        elif c in _OPERATORS:
            tokens.append(_Token("op", _OPERATORS[c], i))
            i += 1
        elif c == "(":
            tokens.append(_Token("lpar", c, i))
            i += 1
        elif c == ")":
            tokens.append(_Token("rpar", c, i))
            i += 1
        elif c == ";":
            tokens.append(_Token("sep", c, i))
            i += 1
        elif c == ",":
            if i + 1 >= n or not text[i + 1].isspace():
                raise FormulaError("use ';' or ', ' between arguments", i)
            tokens.append(_Token("sep", c, i))
            i += 1
        else:
            raise FormulaError(f"unexpected character {c!r}", i)
    tokens.append(_Token("end", "", n))
    return tokens


@dataclass(frozen=True)
class _Num:
    value: float


@dataclass(frozen=True)
class _Var:
    pass


@dataclass(frozen=True)
class _Neg:
    operand: _Node


@dataclass(frozen=True)
class _Bin:
    op: str
    left: _Node
    right: _Node
    pos: int


@dataclass(frozen=True)
class _Call:
    name: str
    args: tuple[_Node, ...]


_Node = _Num | _Var | _Neg | _Bin | _Call


def _evaluate(node: _Node, p: float) -> float:
    match node:
        case _Num(value):
            return value
        case _Var():
            return p
        case _Neg(operand):
            return -_evaluate(operand, p)
        case _Bin(op, left, right, _):
            a, b = _evaluate(left, p), _evaluate(right, p)
            if op == "+":
                return a + b
            if op == "-":
                return a - b
            if op == "*":
                return a * b
            return a / b
        case _Call(name, args):
            return _FUNCTIONS[name](*(_evaluate(arg, p) for arg in args))
    raise AssertionError(node)


def _flip(kind: str) -> str:
    return {_INC: _DEC, _DEC: _INC}.get(kind, kind)


def _combine(kinds: list[str]) -> str:
    """Direction of a sum, min or max of terms with the given directions."""
    varying = {k for k in kinds if k != _CONST}
    if _NONE in varying or len(varying) > 1:
        return _NONE
    return varying.pop() if varying else _CONST


def _direction(node: _Node) -> str:
    """Return const, inc, dec or none (not provable) for the node as function of P."""
    match node:
        case _Num():
            return _CONST
        case _Var():
            return _INC
        case _Neg(operand):
            return _flip(_direction(operand))
        case _Call(_, args):
            return _combine([_direction(arg) for arg in args])
        case _Bin(op, left, right, pos):
            a, b = _direction(left), _direction(right)
            if op == "+":
                return _combine([a, b])
            if op == "-":
                return _combine([a, _flip(b)])
            if op == "/":
                if b != _CONST:
                    raise FormulaError("divisor must not depend on P", pos)
                divisor = _evaluate(right, 0.0)
                if divisor == 0:
                    raise FormulaError("division by zero", pos)
                return a if divisor > 0 else _flip(a)
            if a != _CONST and b != _CONST:
                raise FormulaError("product of two P-dependent terms", pos)
            if a == _CONST and b == _CONST:
                return _CONST
            factor = _evaluate(left if a == _CONST else right, 0.0)
            kind = b if a == _CONST else a
            if factor == 0:
                return _CONST
            return kind if factor > 0 else _flip(kind)
    raise AssertionError(node)


class _Parser:
    def __init__(self, tokens: list[_Token]) -> None:
        self._tokens = tokens
        self._i = 0

    def _peek(self) -> _Token:
        return self._tokens[self._i]

    def _next(self) -> _Token:
        token = self._tokens[self._i]
        self._i += 1
        return token

    def parse(self) -> _Node:
        node = self._expr()
        token = self._peek()
        if token.kind != "end":
            raise FormulaError(f"unexpected {token.text!r}", token.pos)
        return node

    def _expr(self) -> _Node:
        node = self._term()
        while (t := self._peek()).kind == "op" and t.text in "+-":
            self._next()
            node = _Bin(t.text, node, self._term(), t.pos)
        return node

    def _term(self) -> _Node:
        node = self._unary()
        while (t := self._peek()).kind == "op" and t.text in "*/":
            self._next()
            node = _Bin(t.text, node, self._unary(), t.pos)
        return node

    def _unary(self) -> _Node:
        t = self._peek()
        if t.kind == "op" and t.text in "+-":
            self._next()
            operand = self._unary()
            return _Neg(operand) if t.text == "-" else operand
        return self._primary()

    def _primary(self) -> _Node:
        t = self._next()
        if t.kind == "num":
            return _Num(t.value)
        if t.kind == "lpar":
            node = self._expr()
            self._expect("rpar", "')'")
            return node
        if t.kind == "name":
            if t.text == "P":
                return _Var()
            if t.text in _FUNCTIONS:
                return self._call(t)
            raise FormulaError(f"unknown name {t.text!r}", t.pos)
        raise FormulaError(f"unexpected {t.text!r}" if t.text else "unexpected end", t.pos)

    def _call(self, name: _Token) -> _Node:
        self._expect("lpar", "'('")
        args = [self._expr()]
        while self._peek().kind == "sep":
            self._next()
            args.append(self._expr())
        if len(args) < 2:
            raise FormulaError(f"{name.text}() needs at least 2 arguments", name.pos)
        self._expect("rpar", "')'")
        return _Call(name.text, tuple(args))

    def _expect(self, kind: str, label: str) -> None:
        t = self._next()
        if t.kind != kind:
            raise FormulaError(f"expected {label}", t.pos)


@dataclass(frozen=True)
class Formula:
    """A parsed, validated, non-decreasing price formula."""

    text: str
    _root: _Node

    def evaluate(self, p: float) -> float:
        return _evaluate(self._root, p)

    def is_monotonic(self) -> bool:
        return _direction(self._root) in (_CONST, _INC)


def parse(text: str) -> Formula:
    """Parse text; raise FormulaError when invalid or not provably non-decreasing in P."""
    root = _Parser(_tokenize(text)).parse()
    formula = Formula(text, root)
    if not formula.is_monotonic():
        raise FormulaError("formula must not decrease when P increases", 0)
    return formula
