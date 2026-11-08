import glob
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True, cwd=ROOT)
    return r.returncode, r.stdout, r.stderr


def main():
    entries = sorted(glob.glob(os.path.join(ROOT, "examples", "*", "app.py")))
    print(f"=== Multi-file examples: PySubset vs CPython ({len(entries)} programs) ===")
    passed = 0
    for entry in entries:
        name = os.path.relpath(entry, ROOT).replace(os.sep, "/")
        code, expected, err = run([sys.executable, "-B", entry])
        if code != 0:
            print(f"FAIL  {name}  (CPython exited with {code}: {err.strip()[:120]})")
            continue
        _, actual, _ = run([sys.executable, os.path.join(ROOT, "main.py"), entry])
        if expected == actual:
            passed += 1
            print(f"PASS  {name}")
        else:
            print(f"FAIL  {name}")
            print(f"      CPython : {expected!r}")
            print(f"      PySubset: {actual!r}")
    print(f"\n{passed}/{len(entries)} examples match CPython")
    if not entries or passed != len(entries):
        sys.exit(1)


if __name__ == "__main__":
    main()
