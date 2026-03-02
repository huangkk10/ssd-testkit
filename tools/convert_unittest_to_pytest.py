"""
Convert unittest.TestCase style tests to pure pytest style.

Handles:
- Remove bare `import unittest`
- class Foo(unittest.TestCase): -> class Foo:
- def setUp(self): -> def setup_method(self):
- def tearDown(self): -> def teardown_method(self):
- self.assertEqual(a, b) -> assert a == b
- self.assertNotEqual(a, b) -> assert a != b
- self.assertTrue(x) -> assert x
- self.assertFalse(x) -> assert not x
- self.assertIsNone(x) -> assert x is None
- self.assertIsNotNone(x) -> assert x is not None
- self.assertIsInstance(x, T) -> assert isinstance(x, T)
- self.assertIn(a, b) -> assert a in b
- self.assertNotIn(a, b) -> assert a not in b
- with self.assertRaises(E): -> with pytest.raises(E):
- with self.assertRaisesRegex(E, pat): -> with pytest.raises(E, match=pat):
- Remove `if __name__ == '__main__': unittest.main()`
- Add `import pytest` when needed
"""
import re
import sys
from pathlib import Path


# ---------------------------------------------------------------------------
# Balanced-paren argument extractor
# ---------------------------------------------------------------------------

def _extract_call_args(text: str, start: int) -> tuple[list[str], int]:
    """
    Given text[start] == '(', return (list_of_args, index_after_closing_paren).
    Handles nested parens/brackets/braces and strings.
    The opening paren at `start` is consumed; iteration starts at start+1.
    """
    assert text[start] == '('
    depth = 1          # opening paren already consumed
    in_str = None
    current: list[str] = []
    args: list[str] = []
    i = start + 1      # start AFTER the opening paren

    while i < len(text):
        ch = text[i]

        if in_str:
            current.append(ch)
            if ch == '\\':
                i += 1
                if i < len(text):
                    current.append(text[i])
            elif ch == in_str:
                in_str = None
        elif ch in ('"', "'"):
            in_str = ch
            current.append(ch)
        elif ch in ('(', '[', '{'):
            depth += 1
            current.append(ch)
        elif ch in (')', ']', '}'):
            depth -= 1
            if depth == 0:
                args.append(''.join(current).strip())
                return args, i + 1
            current.append(ch)
        elif ch == ',' and depth == 1:
            args.append(''.join(current).strip())
            current = []
        else:
            current.append(ch)

        i += 1

    return args, i


# ---------------------------------------------------------------------------
# Line-level conversions
# ---------------------------------------------------------------------------

def _convert_line(line: str) -> tuple[str, bool]:
    """
    Convert one line. Returns (new_line, needs_pytest).
    new_line may be '' to signal 'delete this line'.
    """
    needs_pytest = False

    raw_stripped = line.lstrip()
    indent = line[:len(line) - len(raw_stripped)]
    stripped = raw_stripped.rstrip('\n').rstrip()
    nl = '\n' if line.endswith('\n') else ''

    # -----------------------------------------------------------------------
    # 1. Remove bare   import unittest
    # -----------------------------------------------------------------------
    if re.match(r'^import unittest\s*$', stripped):
        return '', False

    # -----------------------------------------------------------------------
    # 2. Remove unittest.main() block
    # -----------------------------------------------------------------------
    if re.match(r"^if __name__ == ['\"]__main__['\"]:", stripped):
        return '__SKIP_NEXT__', False

    # -----------------------------------------------------------------------
    # 3. class Foo(unittest.TestCase): -> class Foo:
    # -----------------------------------------------------------------------
    line = re.sub(r'\(unittest\.TestCase\)', '', line)
    stripped = line.lstrip().rstrip('\n').rstrip()

    # -----------------------------------------------------------------------
    # 4. setUp / tearDown
    # -----------------------------------------------------------------------
    line = re.sub(r'\bdef setUp\(self\)', 'def setup_method(self)', line)
    line = re.sub(r'\bdef tearDown\(self\)', 'def teardown_method(self)', line)
    stripped = line.lstrip().rstrip('\n').rstrip()

    # -----------------------------------------------------------------------
    # 5. with self.assertRaises(E):
    # -----------------------------------------------------------------------
    m = re.match(r'^with self\.assertRaises\(', stripped)
    if m:
        idx = stripped.index('(')
        args, end = _extract_call_args(stripped, idx)
        exc = args[0] if args else '...'
        needs_pytest = True
        return f'{indent}with pytest.raises({exc}):{nl}', True

    # -----------------------------------------------------------------------
    # 6. with self.assertRaisesRegex(E, pat):
    # -----------------------------------------------------------------------
    m = re.match(r'^with self\.assertRaisesRegex\(', stripped)
    if m:
        idx = stripped.index('(')
        args, end = _extract_call_args(stripped, idx)
        exc = args[0] if len(args) > 0 else '...'
        pat = args[1] if len(args) > 1 else '...'
        needs_pytest = True
        return f'{indent}with pytest.raises({exc}, match={pat}):{nl}', True

    # -----------------------------------------------------------------------
    # Helper: extract the full self.assertXxx(...) from stripped
    # -----------------------------------------------------------------------
    def _get_assert_args(method: str):
        pat = rf'^self\.{method}\('
        if not re.match(pat, stripped):
            return None
        idx = stripped.index('(')
        args, _ = _extract_call_args(stripped, idx)
        return args

    # -----------------------------------------------------------------------
    # 7. self.assertEqual(a, b)
    # -----------------------------------------------------------------------
    args = _get_assert_args('assertEqual')
    if args and len(args) >= 2:
        return f'{indent}assert {args[0]} == {args[1]}{nl}', False

    # -----------------------------------------------------------------------
    # 8. self.assertNotEqual(a, b)
    # -----------------------------------------------------------------------
    args = _get_assert_args('assertNotEqual')
    if args and len(args) >= 2:
        return f'{indent}assert {args[0]} != {args[1]}{nl}', False

    # -----------------------------------------------------------------------
    # 9. self.assertTrue(x)
    # -----------------------------------------------------------------------
    args = _get_assert_args('assertTrue')
    if args and len(args) >= 1:
        return f'{indent}assert {args[0]}{nl}', False

    # -----------------------------------------------------------------------
    # 10. self.assertFalse(x)
    # -----------------------------------------------------------------------
    args = _get_assert_args('assertFalse')
    if args and len(args) >= 1:
        return f'{indent}assert not {args[0]}{nl}', False

    # -----------------------------------------------------------------------
    # 11. self.assertIsNone(x)
    # -----------------------------------------------------------------------
    args = _get_assert_args('assertIsNone')
    if args and len(args) >= 1:
        return f'{indent}assert {args[0]} is None{nl}', False

    # -----------------------------------------------------------------------
    # 12. self.assertIsNotNone(x)
    # -----------------------------------------------------------------------
    args = _get_assert_args('assertIsNotNone')
    if args and len(args) >= 1:
        return f'{indent}assert {args[0]} is not None{nl}', False

    # -----------------------------------------------------------------------
    # 13. self.assertIsInstance(x, T)
    # -----------------------------------------------------------------------
    args = _get_assert_args('assertIsInstance')
    if args and len(args) >= 2:
        return f'{indent}assert isinstance({args[0]}, {args[1]}){nl}', False

    # -----------------------------------------------------------------------
    # 14. self.assertIn(a, b)
    # -----------------------------------------------------------------------
    args = _get_assert_args('assertIn')
    if args and len(args) >= 2:
        return f'{indent}assert {args[0]} in {args[1]}{nl}', False

    # -----------------------------------------------------------------------
    # 15. self.assertNotIn(a, b)
    # -----------------------------------------------------------------------
    args = _get_assert_args('assertNotIn')
    if args and len(args) >= 2:
        return f'{indent}assert {args[0]} not in {args[1]}{nl}', False

    return line, False


def _insert_pytest_import(lines: list[str]) -> list[str]:
    """Insert 'import pytest' after the last top-level import block.

    Handles multi-line imports like:
        from foo import (
            A,
            B,
        )
    by tracking open parentheses and only marking end after the closing ')'.
    """
    last_import_end = -1
    in_multiline = False
    paren_depth = 0

    for i, ln in enumerate(lines):
        stripped = ln.rstrip()
        if in_multiline:
            paren_depth += stripped.count('(') - stripped.count(')')
            if paren_depth <= 0:
                in_multiline = False
                last_import_end = i
        elif re.match(r'^(import |from )', ln):
            if stripped.endswith('(') or stripped.count('(') > stripped.count(')'):
                in_multiline = True
                paren_depth = stripped.count('(') - stripped.count(')')
            else:
                last_import_end = i

    insert_at = last_import_end + 1 if last_import_end >= 0 else 0
    lines.insert(insert_at, 'import pytest\n')
    return lines


def convert_file(filepath: Path, dry_run: bool = False) -> bool:
    content = filepath.read_text(encoding='utf-8')
    raw_lines = content.splitlines(keepends=True)

    output: list[str] = []
    needs_pytest = False
    skip_next_indent = False

    for i, line in enumerate(raw_lines):
        if skip_next_indent:
            # Skip the `    unittest.main()` line following the if-block
            stripped_content = line.lstrip()
            if stripped_content.startswith('unittest.main()'):
                skip_next_indent = False
                continue
            # Not the expected line; stop skipping
            skip_next_indent = False

        new_line, np = _convert_line(line)
        if np:
            needs_pytest = True

        if new_line == '':
            continue  # deleted line
        elif new_line == '__SKIP_NEXT__':
            skip_next_indent = True
            continue
        else:
            output.append(new_line)

    if needs_pytest:
        output = _insert_pytest_import(output)

    new_content = ''.join(output)
    if new_content == content:
        print(f'  [no change] {filepath}')
        return False

    if not dry_run:
        filepath.write_text(new_content, encoding='utf-8')
        print(f'  [converted] {filepath}')
    else:
        print(f'  [dry-run]   {filepath}')
    return True


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

TARGET_FILES = [
    'tests/unit/lib/testtool/test_phm/test_ui_monitor.py',
    'tests/unit/lib/testtool/test_phm/test_controller.py',
    'tests/unit/lib/testtool/test_phm/test_process_manager.py',
    'tests/unit/lib/testtool/test_burnin/test_controller.py',
    'tests/unit/lib/testtool/test_python_installer/test_controller.py',
    'tests/unit/lib/testtool/test_python_installer/test_process_manager.py',
    'tests/unit/lib/testtool/test_cdi/test_controller.py',
    'tests/unit/lib/testtool/test_cdi/test_ui_monitor.py',
]

if __name__ == '__main__':
    dry_run = '--dry-run' in sys.argv
    root = Path(__file__).parent.parent  # project root (ssd-testkit)

    changed = 0
    for rel in TARGET_FILES:
        fp = root / rel
        if not fp.exists():
            print(f'  [missing]   {fp}')
            continue
        if convert_file(fp, dry_run=dry_run):
            changed += 1

    print(f'\nDone. {changed}/{len(TARGET_FILES)} files converted.')
