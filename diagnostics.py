def _get_line(sources, filename, line):
    lines = sources.get(filename)
    if not lines or line < 1 or line > len(lines):
        return None
    return lines[line - 1]


def _caret_line(src_line, col):
    if col < 1:
        return None
    pad = "".join("\t" if ch == "\t" else " " for ch in src_line[:col - 1])
    return pad + "^"


def format_traceback(kind, message, filename, line, col, sources, call_stack=None):
    parts = []
    if call_stack:
        parts.append("Traceback (most recent call last):")
        for entry in call_stack:
            if len(entry) == 4:
                ef, fn, el, ec = entry
            else:
                fn, el = entry
                ef, ec = filename, 0
            loc = f'  File "{ef}", line {el}' + (f", col {ec}" if ec else "") + f", in {fn}"
            parts.append(loc)
            src = _get_line(sources, ef, el)
            if src is not None:
                parts.append("    " + src)
                caret = _caret_line(src, ec)
                if caret is not None:
                    parts.append("    " + caret)
    elif line:
        loc = f'  File "{filename}", line {line}' + (f", col {col}" if col else "")
        parts.append(loc)
        src = _get_line(sources, filename, line)
        if src is not None:
            parts.append("    " + src)
            caret = _caret_line(src, col)
            if caret is not None:
                parts.append("    " + caret)

    if line and call_stack:
        # Also show the exact failing line if it differs from the top frame
        top = call_stack[-1]
        top_line = top[2] if len(top) == 4 else top[1]
        top_file = top[0] if len(top) == 4 else filename
        if (top_file, top_line) != (filename, line):
            loc = f'  File "{filename}", line {line}' + (f", col {col}" if col else "")
            parts.append(loc)
            src = _get_line(sources, filename, line)
            if src is not None:
                parts.append("    " + src)
                caret = _caret_line(src, col)
                if caret is not None:
                    parts.append("    " + caret)

    parts.append(f"{kind}: {message}")
    return "\n".join(parts)