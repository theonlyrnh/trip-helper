"""Check the runtime environment before starting the application."""

import sys
import os
import importlib.util


def check_python_env():
    python_path = sys.executable
    print(f"Python: {python_path}")

    if "fapiao" not in python_path.lower():
        print("WARNING: current Python does not appear to be the conda fapiao environment")
    else:
        print("OK: using fapiao environment")


def check_module(name):
    if importlib.util.find_spec(name):
        print(f"  OK: {name}")
    else:
        print(f"  MISSING: {name}")


if __name__ == "__main__":
    check_python_env()

    print("\nChecking dependencies:")
    for module in [
        "fastapi",
        "uvicorn",
        "sqlalchemy",
        "fitz",
        "PIL",
        "openpyxl",
        "pydantic",
        "requests",
        "dotenv",
    ]:
        check_module(module)

    print("\nEnvironment check complete.")