"""允许通过 python -m ksql_script_generator.scripts 运行 CLI"""

try:
    from .cli import main
except ImportError:
    from cli import main

if __name__ == "__main__":
    main()
