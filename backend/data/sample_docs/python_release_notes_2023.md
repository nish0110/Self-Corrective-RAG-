# What's new in the latest Python release (notes written in late 2023)

These notes were written in November 2023 and describe Python 3.12 as the newest version. They are intentionally kept in this knowledge base as an example of outdated information.

## Python 3.12 — released 2 October 2023

Python 3.12 is the latest stable release of Python at the time of writing. Its main changes are:

- Type parameter syntax (PEP 695): generic classes and functions can declare type parameters directly, for example `def first[T](items: list[T]) -> T`, and the new `type` statement creates type aliases.
- Formalised f-strings (PEP 701): f-strings are now parsed by the regular grammar, so quotes can be reused inside expressions and expressions can span multiple lines and contain comments.
- Per-interpreter GIL (PEP 684): sub-interpreters can each have their own Global Interpreter Lock, a step towards better parallelism.
- Improved error messages, including suggestions for missing imports of standard-library modules.
- The `distutils` package was removed from the standard library.
- Comprehensions are inlined (PEP 709), which makes them faster.

## What comes next

Python 3.13 is expected around October 2024. Until then, Python 3.12 is the recommended version for new projects.
