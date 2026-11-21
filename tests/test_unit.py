import contextlib
import io
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ast_nodes import BinOp, Block, FromImportStmt, Number, UnaryOp
from diagnostics import format_traceback
from environment import Environment
from interpreter import Interpreter
from lexer import Lexer
from main import run_source
from parser import Parser
from tokens import TokenType


def parse(src, filename="<test>"):
    return Parser(Lexer(src, filename=filename).tokenize(), filename=filename).parse()


def capture_run(src, filename="<test>"):
    buf = io.StringIO()
    interp = Interpreter()
    with contextlib.redirect_stdout(buf):
        run_source(src, interp, filename=filename)
    return buf.getvalue(), interp


class TestLexer(unittest.TestCase):
    def test_indent_dedent_and_comments(self):
        src = "if True:\n    # comment\n\n    x = 1\ny = 2\n"
        toks = Lexer(src).tokenize()
        types = [t.type for t in toks]
        self.assertIn(TokenType.INDENT, types)
        self.assertIn(TokenType.DEDENT, types)
        self.assertEqual(types[-1], TokenType.EOF)

    def test_newlines_ignored_inside_parens(self):
        src = "x = (\n    1 +\n    2\n)\n"
        toks = Lexer(src).tokenize()
        types = [t.type for t in toks]
        self.assertNotIn(TokenType.INDENT, types)

    def test_unterminated_string_error_position(self):
        with self.assertRaises(SyntaxError) as ctx:
            Lexer('x = "hello\n', filename="s.py").tokenize()
        self.assertEqual(ctx.exception.filename, "s.py")
        self.assertEqual(ctx.exception.lineno, 1)
        self.assertEqual(ctx.exception.offset, 5)

    def test_unterminated_fstring_error_position(self):
        with self.assertRaises(SyntaxError) as ctx:
            Lexer('x = f"hi {1}\n', filename="f.py").tokenize()
        self.assertEqual(ctx.exception.lineno, 1)
        self.assertEqual(ctx.exception.offset, 6)

    def test_unexpected_character(self):
        with self.assertRaises(SyntaxError) as ctx:
            Lexer("x = 1 $ 2\n", filename="c.py").tokenize()
        self.assertEqual(ctx.exception.lineno, 1)
        self.assertEqual(ctx.exception.offset, 7)


class TestParser(unittest.TestCase):
    def test_operator_precedence(self):
        tree = parse("2 + 3 * 4\n")
        stmt = tree.statements[0].expr
        self.assertIsInstance(stmt, BinOp)
        self.assertEqual(stmt.op, "+")
        self.assertEqual(stmt.left.value, 2)
        self.assertEqual(stmt.right.op, "*")

    def test_right_associative_power_and_unary(self):
        tree = parse("-2 ** 2\n")
        expr = tree.statements[0].expr
        self.assertIsInstance(expr, UnaryOp)
        self.assertEqual(expr.op, "-")
        self.assertEqual(expr.operand.op, "**")

    def test_relative_import_ast(self):
        tree = parse("from ..pkg.mod import a, b as c\n")
        stmt = tree.statements[0]
        self.assertIsInstance(stmt, FromImportStmt)
        self.assertEqual(stmt.level, 2)
        self.assertEqual(stmt.module, "pkg.mod")
        self.assertEqual(stmt.names, [("a", None), ("b", "c")])

    def test_try_without_except_or_finally_raises(self):
        with self.assertRaises(SyntaxError):
            parse("try:\n    pass\n")

    def test_positional_after_keyword_raises(self):
        with self.assertRaises(SyntaxError):
            parse("f(a=1, 2)\n")


class TestEnvironment(unittest.TestCase):
    def test_global_and_nonlocal_delete(self):
        root = Environment()
        root.set("g", 10)
        child = Environment(root)
        child.global_names = frozenset({"g"})
        child.delete("g")
        with self.assertRaises(NameError):
            root.get("g")

        outer = Environment()
        outer.set("x", 99)
        inner = Environment(outer)
        inner.nonlocal_names = frozenset({"x"})
        inner.delete("x")
        with self.assertRaises(NameError):
            outer.get("x")


class TestDiagnosticsAndErrors(unittest.TestCase):
    def test_format_traceback_caret_alignment(self):
        sources = {"app.py": ["def f():", "    return nope", "f()"]}
        out = format_traceback(
            "NameError",
            "Name 'nope' is not defined",
            "app.py",
            2,
            12,
            sources,
            call_stack=[("app.py", "f", 1, 5)],
        )
        self.assertIn('File "app.py", line 1, col 5, in f', out)
        self.assertIn('File "app.py", line 2, col 12', out)
        self.assertIn("        return nope", out)
        self.assertIn("               ^", out)
        self.assertIn("NameError: Name 'nope' is not defined", out)

    def test_runtime_traceback_includes_file_and_caret(self):
        out, _ = capture_run("def boom():\n    return missing_var\n\nboom()\n", filename="demo_err.py")
        self.assertIn('File "demo_err.py", line 1, col 5, in boom', out)
        self.assertIn('File "demo_err.py", line 2, col 12', out)
        self.assertIn("NameError: Name 'missing_var' is not defined", out)

    def test_imported_module_error_includes_module_file(self):
        interp = Interpreter()
        interp.register_module("broken_mod", "x = 1\ny = nope + 1\n")
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            run_source("import broken_mod\n", interp, filename="main_app.py")
        out = buf.getvalue()
        self.assertIn('File "<broken_mod>", line 2', out)
        self.assertIn("NameError: Name 'nope' is not defined", out)

    def test_top_level_break_reports_syntax_error(self):
        out, _ = capture_run("break\n", filename="brk.py")
        self.assertIn("SyntaxError", out)


class TestModulesAndGenerators(unittest.TestCase):
    def test_virtual_package_relative_import(self):
        interp = Interpreter()
        interp.register_module("pkg", "VAL = 7\nfrom . import helper\nprint(helper.double(VAL))\n")
        interp.register_module("pkg.helper", "from . import VAL\ndef double(x):\n    return x * 2\nprint(VAL)\n")
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            run_source("import pkg\n", interp, filename="app.py")
        self.assertEqual(buf.getvalue().splitlines(), ["7", "14"])


if __name__ == "__main__":
    unittest.main()