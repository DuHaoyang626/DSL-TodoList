# DSL TodoList

This repository is split into clear modules so the GUI and the core services evolve independently:

- `dsl_todolist/db.py` – database helpers (connections, schema bootstrap, reset utilities).
- `dsl_todolist/api.py` – JSON-based CRUD interface consumed by both the GUI and the fixture runner.
- `dsl_todolist/gui.py` – Tkinter user interface that talks to the JSON API only.
- `todolist_gui.py` – thin compatibility shim for launching the GUI (`python todolist_gui.py`). Prefer running `python -m dsl_todolist.gui` going forward.
- `tests/test_json_api.py` – interactive runner that sends JSON fixtures to the API.

All imports have been updated so modules only rely on the package names above, keeping naming consistent across the project.
