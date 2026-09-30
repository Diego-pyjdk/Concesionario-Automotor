# AGENTS.md

## Commands

- Run from the **repo root**: `venv\Scripts\python.exe main.py`
  - Root is mandatory. Imports are absolute from the project root (`from gui.ventana_principal import ...`) and `main.py` opens `gui/estilo.css` by relative path — any other working directory breaks both.
- There is **no `requirements.txt` / `pyproject.toml` / lockfile**. Dependencies exist only in the local (gitignored) `venv/`: Python 3.13.15, PySide6 6.11.2, mysql-connector-python 26.7.0.
- **No tests, no linter, no formatter, no type checker are committed.** Verification is manual: launch the app and exercise the screen you touched.
- MySQL must be running locally first — every view queries the DB while building itself, so a down database means a crash at startup, before any error UI is reachable.
- Headless check of the GUI without a desktop: `QT_QPA_PLATFORM=offscreen` plus a `QApplication`, with `QMessageBox.warning/information/question` monkeypatched (they block on `exec()`).

## Architecture

`main.py` → `gui/*_view.py` (views + `gui/formularios/*_form.py`) → `database/<entidad>.py` → `database/conexion.py` → MySQL.

- **All SQL lives in `database/*.py`.** Views and forms never build SQL.
- Per entity: `database/<entidad>.py` + `gui/<entidad>_view.py` + `gui/formularios/<entidad>_form.py`. Lookup tables (e.g. `marcas`) get a `database/` module only.
- Views own `cargar_datos()` (reload from DB) and `mostrar_<entidad>()` (fill the table). Forms are `QDialog` that `accept()` on save; the view reloads when `exec()` returns truthy.
- `utils/helpers.py` holds shared Qt pieces: `crear_tabla`, `celda`, `crear_botones_accion`, `crear_boton_principal`, `crear_boton_secundario`, `crear_titulo`. Use them instead of rebuilding tables and action buttons per view.
- `utils/validaciones.py` returns `(es_valido, mensaje)`; `primer_error(lista_de_tuplas)` returns the first message or `None`. Never raise from a validator.
- `database/dashboard.py` and `database/configuracion.py` are not entities: they serve the panel and the settings screen. There is no `reportes.py` on purpose — `ReportesView` composes queries owned by the entity modules.
- Only `database/` has an `__init__.py`; `gui/`, `gui/formularios/`, and `utils/` rely on implicit namespace packages. Don't add `__init__.py` for tidiness.
- `gui/ventana.py` is empty leftover scaffolding; nothing imports it.

## Database

- Credentials are hardcoded in `database/conexion.py` (`localhost`, `root`, db `concesionario`). Nothing reads env vars, even though `.env` is gitignored.
- Schema: `database/esquema.sql` creates the database, the 4 tables (`marcas`, `autos`, `clientes`, `ventas`), and 10 seed marcas. It starts with `DROP DATABASE` — it is a from-scratch script, so do not run it over real data. No migrations exist.
- Relations: `marcas 1:N autos`, `clientes 1:N ventas`, `autos 1:N ventas`. `ventas.precio` freezes the price at sale time so later edits to `autos.precio` don't rewrite history.
- `database/conexion.py` hardcodes the schema too — if you add a column or table, update both files.
- Normally each function opens a fresh connection via `obtener_conexion()`, runs one query, closes cursor + connection. Writes `commit()`; reads don't. No pooling, no error handling, no rollback.
  - **Two deliberate exceptions in `database/ventas.py`:** `registrar_venta` and `eliminar_venta` use `start_transaction()` / `commit()` / `rollback()`, because stock and the sale row must move together or not at all.
  - `registrar_venta` locks the vehicle with `SELECT ... FOR UPDATE` before checking stock, then inserts the sale, then decrements. It returns `(True, "")` or `(False, mensaje)`.
  - `eliminar_venta` also **returns the unit to stock** in the same transaction. Never delete a sale row without that, or inventory silently drifts.
- `eliminar_marca`, `eliminar_cliente` and `eliminar_auto` return `False` instead of raising when a foreign key blocks the delete; the view shows the reason. Check the return value.
- Search builds its LIKE wildcard in Python (`f"%{texto}%"`) and still passes it as a `%s` param. Keep new queries parameterized; never interpolate input.

## Column order is a cross-layer contract

`database/autos.py` selects exactly `autos.id, marcas.nombre, autos.modelo, autos.anio, autos.precio, autos.color, autos.stock`.

That order is hardcoded in three more places:
- `AutosView.mostrar_autos` writes each row positionally and puts the Editar/Eliminar buttons in column **7** via `setCellWidget`.
- `AutosView.editar_auto` re-reads columns 0–6 and rebuilds a typed 7-tuple.
- `AutoForm.cargar_datos` unpacks the same 7-tuple with the brand **name** at index 1, matching it against combo text.

Reordering or adding a SELECT column breaks the GUI with no error at the DB layer. Change all four together. The stock queries in `database/autos.py` deliberately return these same 7 columns in this order so `ReportesView` can reuse one display routine.

`obtener_ventas` has its own contract: `id, fecha, cliente, vehiculo, precio`, where `cliente` and `vehiculo` are `CONCAT` expressions, not ids.

Views read table cells positionally to rebuild a form's tuple (same pattern in `AutosView`, `ClientesView`, `MarcasView`). A row missing an item returns early rather than crashing.

## Sales are create-only

A sale is not editable — the row is history. The `Ver` button shows the detail read-only. Correcting a sale means deleting it (which returns the unit to stock) and registering it again. Don't add an edit path without handling stock movement for both the old and new vehicle.

## Styling

- One app-wide stylesheet, `gui/estilo.css`, loaded once in `main.py`. Widgets are themed via `setObjectName` + a matching QSS selector; there is no inline styling anywhere.
- Object names: `titulo`, `subtitulo`, `pie`, `icono`, `nombre_tarjeta`, `cantidad`, `tarjeta`, `sidebar`, `titulo_sidebar`, `boton_menu`, `boton_menu_activo`, `boton_principal`, `boton_secundario`, `boton_filtro`, `boton_editar`, `boton_eliminar`, `aviso`, `filtros`, `estado_conexion`, `estado_ok`, `estado_error`.
- **Trap:** the bare `QPushButton` rule is styled as a *sidebar* button (transparent bg, light-grey left-aligned text). Any new button without an `objectName` renders as a nav item. Use `crear_boton_principal` / `crear_boton_secundario`.
- Changing an `objectName` after the widget exists does not restyle it. Call `style().unpolish(w)` then `style().polish(w)`, as `ventana_principal.marcar_activo` does.

## House style

- Spanish everywhere: identifiers, UI strings, comments.
- Calls are exploded **one argument per line** with blank lines between statements; sections use ASCII banners (`# =====`, `# -----`). Deliberate — match it when editing, or a normal reformat buries the real change in noise.
- Import order: project packages first, then PySide6.
- GUI methods colliding with DB function names are aliased on import (`from database.autos import eliminar_auto as eliminar_auto_db`, `gui/autos_view.py:5`). Follow that instead of renaming.
- Row-action buttons capture their index with a default argument: `lambda _, f=fila: self.editar(f)`. `clicked` emits a bool, so the first parameter absorbs it.
- `main.py` creates the `QApplication` and shows the window at module top level with no `if __name__ == "__main__"` guard — importing it has side effects.
