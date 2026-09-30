# AGENTS.md

## Commands

- Run from the **repo root**: `venv\Scripts\python.exe main.py`
  - Root is mandatory. Imports are absolute from the project root (`from gui.ventana_principal import ...`) and `main.py` opens `gui/estilo.css` by relative path — any other working directory breaks both.
- There is **no `requirements.txt` / `pyproject.toml` / lockfile**. Dependencies exist only in the local (gitignored) `venv/`: Python 3.13.15, PySide6 6.11.2, mysql-connector-python 26.7.0.
- **No tests, no linter, no formatter, no type checker.** Verify changes by launching the app and exercising the screen you touched.
- MySQL must be running locally first — the window queries the DB during construction.

## What actually exists

- Only the **Vehículos** (`autos`) module is implemented end to end: `database/autos.py`, `database/marcas.py`, `gui/autos_view.py`, `gui/formularios/auto_form.py`.
- These are **deliberate 0-byte placeholders, not yet built**: `database/clientes.py`, `database/ventas.py`, `gui/clientes_view.py`, `gui/ventas_view.py`, `gui/ventana.py`, `gui/formularios/cliente_form.py`, `gui/formularios/venta_form.py`, `utils/helpers.py`, `utils/validaciones.py`. Don't assume a feature exists because its file is there.
- `VentanaPrincipal` has 6 sidebar buttons; only **Inicio** and **Vehículos** are connected. The rest are inert.
- Everything is in **Spanish** — identifiers, UI strings, comments. Keep new code Spanish to match.

## Database

- Credentials are hardcoded in `database/conexion.py` (`localhost`, `root`, db `concesionario`). Nothing reads env vars, even though `.env` is gitignored.
- Schema: load `database/esquema.sql` into MySQL once to create the `concesionario` database plus the `autos` and `marcas` tables. No migrations exist — treat schema edits as edits to that file.
- `autos` depends on `marcas` (`autos.marca_id -> marcas.id`) and the SELECTs `INNER JOIN` it, so `marcas` rows are required.
- Every function in `database/*.py` opens a fresh connection via `obtener_conexion()`, runs one query, closes cursor + connection. Writes `commit()`; reads don't. No pooling, error handling, or rollback — follow the existing shape rather than introducing a new abstraction mid-task.
- Search builds its LIKE wildcard in Python (`f"%{texto}%"`) and still passes it as a `%s` param. Keep new queries parameterized; never interpolate input.

## Column order is a cross-layer contract

`database/autos.py` selects exactly `autos.id, marcas.nombre, autos.modelo, autos.anio, autos.precio, autos.color, autos.stock`.

That order is hardcoded in three more places:
- `AutosView.mostrar_autos` writes each row positionally and puts the Editar/Eliminar buttons in column **7** via `setCellWidget`.
- `AutosView.editar_auto` re-reads columns 0–6 and rebuilds a typed 7-tuple.
- `AutoForm.cargar_datos` unpacks the same 7-tuple with the brand **name** at index 1, matching it against combo text.

Reordering or adding a SELECT column breaks the GUI with no error at the DB layer. Change all four together.

All DB calls run synchronously on the Qt main thread — `cargar_datos()` is invoked at the end of `crear_interfaz`, so startup blocks on MySQL.

## Styling

- One app-wide stylesheet, `gui/estilo.css`, loaded once in `main.py`. Widgets are themed via `setObjectName` + a matching QSS selector; there is no inline styling anywhere.
- Existing object names: `titulo`, `subtitulo`, `icono`, `nombre_tarjeta`, `cantidad`, `sidebar`, `titulo_sidebar`, `tarjeta`, `boton_principal`, `boton_editar`, `boton_eliminar`, `auto_form`.
- **Trap:** the bare `QPushButton` rule is styled as a *sidebar* button (transparent bg, light-grey left-aligned text). Any new button without an `objectName` renders as a nav item — that's why "Cancelar" in `auto_form.py` looks wrong. Add an objectName and a QSS rule, never inline styles.
- `QComboBox QAbstractItemView` is currently black background / white text; looks like a leftover. Check before reusing or "fixing".

## House style

- Calls are exploded **one argument per line** with blank lines between statements; sections use ASCII banners (`# =====`, `# -----`). Deliberate — match it when editing, or a normal reformat buries the real change in noise.
- Import order: project packages first, then PySide6.
- GUI methods colliding with DB function names are aliased on import (`from database.autos import eliminar_auto as eliminar_auto_db`, `gui/autos_view.py:6`). Follow that instead of renaming.
- `main.py` creates the `QApplication` and shows the window at module top level with no `if __name__ == "__main__"` guard — importing it has side effects.
- Only `database/` has an `__init__.py`; `gui/`, `gui/formularios/`, and `utils/` rely on implicit namespace packages. Don't add `__init__.py` for tidiness.
- Feature layout convention: `database/<entidad>.py` + `gui/<entidad>_view.py` + `gui/formularios/<entidad>_form.py`. Lookup tables (e.g. `marcas`) get a `database/` module only. Views own `cargar_datos()` / `mostrar_<entidad>()`; forms are `QDialog` that `accept()` on save, and the view reloads when `exec()` returns truthy.
