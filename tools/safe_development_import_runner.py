from __future__ import annotations

import importlib
import os
import sys
import traceback


def main() -> int:
    if len(sys.argv) != 2:
        print("SAFE_IMPORT_ERROR=module_required", file=sys.stderr)
        return 2
    module = str(sys.argv[1]).strip()
    importlib.import_module(module)
    print(f"SAFE_IMPORT_OK={module}", flush=True)
    return 0


if __name__ == "__main__":
    code = 1
    try:
        code = main()
    except BaseException:
        traceback.print_exc()
        code = 1
    finally:
        try:
            sys.stdout.flush()
            sys.stderr.flush()
        finally:
            os._exit(code)
