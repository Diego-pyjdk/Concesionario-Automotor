# AGENTS.md

## Commands

- Run from the **repo root**: `venv\Scripts\python.exe main.py`
  - Root is mandatory. Imports are absolute from the project root and `main.py` opens `gui/estilo.css` by relative path.
- **First time only**, create the initial administrator (interactive, hidden password):
  - `venv\Scripts\python.exe crear_admin.py`
  - Only works while no active administrator exists. After that, accounts are made from the Usuarios screen.
- Credentials live in **`.env`** at the repo root (gitignored). `.env.example` is the template. `database/conexion.py` reads `DB_HOST`, `DB_PORT`, `DB_USER`, `DB_PASSWORD`, `DB_NAME`, with real environment variables taking precedence over the file.
- There is **no `requirements.txt` / `pyproject.toml` / lockfile**. Dependencies exist only in the local (gitignored) `venv/`: Python 3.13.15, PySide6 6.11.2, mysql-connector-python 26.7.0. Phase 2 added nothing — everything uses the standard library.
- **No tests, linter, formatter or type checker are committed.** Verification is manual.
- Headless check of the GUI: `QT_QPA_PLATFORM=offscreen` plus a `QApplication`, with `QMessageBox.warning/information/question/critical` monkeypatched (they block on `exec()`).

## Startup flow

`main.py` → `LoginView` → `VentanaPrincipal`. The main window is only constructed after a successful login.

- `main.py` now has an `if __name__ == "__main__":` guard (it did not in phase 1).
- Logout emits `VentanaPrincipal.solicitar_cierre_sesion` (a `Signal`, not `pyqtSignal` — that name does not exist in PySide6). `main.mostrar_login` hides + `deleteLater()`s the old window and shows the login again, so the process survives a logout. Closing the main window with the X quits the app.
- **Never build `VentanaPrincipal` without an active session**: it raises `PermissionError` on purpose.

## Architecture

`main.py` → `gui/*_view.py` (views + `gui/formularios/*_form.py`) → `database/<entidad>.py` → `database/conexion.py` → MySQL.

Root modules (not in a package):
- `errores.py` — `ErrorSistema`, `ErrorBaseDatos`, `ErrorValidacion`, `PermisoDenegado`, `traducir_error()` (MySQL errno → Spanish message). Raise these from `database/*.py`; never let `mysql.connector.Error` escape.
- `sesion.py` — session singleton: `iniciar_sesion(datos)`, `cerrar_sesion()`, `hay_sesion()`, `usuario_actual()`, `rol_actual()`, `obtener_sesion()`.
- `permisos.py` — `PERMISOS_POR_ROL`, permission constants, `tiene_permiso()`, and the `requiere_permiso()` decorator.

Rules that hold:
- **All SQL lives in `database/*.py`.** Views and forms never build SQL.
- `utils/helpers.py` — shared Qt pieces (`crear_tabla`, `celda`, `crear_botones_accion`, `crear_boton_principal`, `crear_boton_secundario`, `crear_titulo`, `crear_campo_contrasena`).
- `utils/validaciones.py` — every validator returns `(es_valido, mensaje)`; `primer_error(lista)` returns the first message or `None`. Never raise from a validator.
- `utils/seguridad.py` — PBKDF2-HMAC-SHA256 hashing (`construir_hash`, `verificar_contrasena`). Never import `hashlib` directly elsewhere.
- `utils/registro.py` — appends tracebacks to `registro_errores.log`. The user never sees a traceback.
- `gui/vista_base.py` — `VistaBase` is the base of every view. It wraps DB work in `proteger(operacion, *args)` which returns `None` on any failure and shows a readable message. Use `self.proteger(...)` around anything that touches the database; `self.confirmar(titulo, mensaje)` for confirmations.
- Views take a `puede_gestionar` / `puede_registrar` flag so the sidebar and the action buttons match the role.
- Only `database/` has an `__init__.py`; `gui/`, `gui/formularios/`, `utils/` rely on implicit namespace packages.
- `gui/ventana.py` is empty leftover scaffolding; nothing imports it.
- There is no `reportes.py` on purpose — `ReportesView` composes queries owned by the entity modules.

## Permissions

Enforced in **two** layers. Hiding a button is not the protection — the decorator in `database/*.py` is.

1. `VentanaPrincipal.SECCIONES` maps `(texto, vista, permiso)`. A view is **not instantiated** if the role lacks the read permission, so the widget does not exist.
2. `@requiere_permiso(PERMISO)` decorates the mutating functions in `database/*.py` and raises `PermisoDenegado`. Without an active session every permission resolves to `False`.

| | administrador | vendedor |
|---|---|---|
| Consultar autos / marcas / clientes / ventas | sí | sí |
| Registrar ventas | sí | sí |
| Crear, editar y **borrar** autos / marcas / clientes | sí | **no** |
| **Borrar** ventas | sí | **no** |
| Reportes | sí | **no** |
| Usuarios | sí | **no** |
| Configuración | sí | **no** |

Read functions are intentionally undecorated: both roles may read. To lock a read down, add the decorator — `obtener_usuarios` and `buscar_usuarios` are decorated precisely so a vendedor cannot enumerate accounts.

- `crear_primer_usuario` is deliberately **not** decorated (no session exists yet). It refuses if any active administrator already exists, so it cannot be used to add accounts later.
- `contar_administradores_activos`, `es_administrador` and `hay_usuarios` are left undecorated: they return a count or a bool, no data.
- Deleting sales is admin-only because it returns the unit to stock and rewrites history.

## Passwords and login

- `usuarios.password_hash` stores `sal_hex:hash_hex`. The plaintext is never stored, never logged and cannot be recovered.
- `autenticar()` returns `(True, "", datos)` or `(False, mensaje, None)`, where `datos` is `(id, nombre_usuario, nombre_completo, rol)`.
- Unknown user and wrong password give the **same** message, and the unknown-user path verifies a dummy hash so timing does not reveal which accounts exist.
- Lockout after `MAX_INTENTOS = 5`, for `MINUTOS_BLOQUEO = 15` minutes, tracked in `intentos_fallidos` / `bloqueado_hasta`. A correct password does **not** bypass it. `UsuariosView.editar_usuario` offers to unlock a blocked account, and setting a new password in the form clears the lock.
- New accounts default to **`vendedor`** (least privilege). Making someone an administrator is a deliberate choice.
- `eliminar_usuario` returns `(True, "")` or `(False, motivo)`; it refuses to delete your own account or the last active administrator. `actualizar_usuario` refuses to demote or deactivate the last active administrator.
- Hash cost is ~0.17 s per verification (`ITERACIONES = 260000`). Raising it is fine; lowering it is not.

## Database

- Schema: `database/esquema.sql` creates the database, 5 tables (`marcas`, `autos`, `clientes`, `ventas`, `usuarios`) and 10 seed marcas. It starts with `DROP DATABASE` — a from-scratch script, never run over real data. No migrations exist.
- Relations: `marcas 1:N autos`, `clientes 1:N ventas`, `autos 1:N ventas`. `ventas.precio` freezes the price at sale time.
- Normally each function opens a fresh connection, runs one query, closes cursor + connection. Writes `commit()`; reads don't.
  - **Two deliberate exceptions in `database/ventas.py`:** `registrar_venta` and `eliminar_venta` use `start_transaction()` / `commit()` / `rollback()`.
  - `registrar_venta` locks the vehicle with `SELECT ... FOR UPDATE`, checks stock, inserts the sale, then decrements.
  - `eliminar_venta` also returns the unit to stock in the same transaction.
- `eliminar_marca`, `eliminar_cliente`, `eliminar_auto` return `False` instead of raising when a foreign key blocks the delete. Check the return value.
- `cliente_duplicado(nombre, apellido, telefono, email, id_usuario=None)` matches on email, or on name + surname + phone together.
- Search builds its LIKE wildcard in Python (`f"%{texto}%"`) and still passes it as a `%s` param. Keep new queries parameterized; never interpolate input.

## Column order is a cross-layer contract

`database/autos.py` selects exactly `autos.id, marcas.nombre, autos.modelo, autos.anio, autos.precio, autos.color, autos.stock`.

That order is hardcoded in three more places:
- `AutosView.mostrar_autos` writes each row positionally and puts the action buttons in column **7** via `setCellWidget`.
- `AutosView.editar_auto` re-reads columns 0–6 and rebuilds a typed 7-tuple.
- `AutoForm.cargar_datos` unpacks the same 7-tuple with the brand **name** at index 1, matching it against combo text.

Reordering or adding a SELECT column breaks the GUI with no error at the DB layer. The stock queries in `database/autos.py` deliberately reuse these same 7 columns so `ReportesView` can share one display routine.

Other contracts: `obtener_ventas` → `id, fecha, cliente, vehiculo, precio` (last two are `CONCAT` expressions, not ids). `obtener_usuarios` → `id, nombre_usuario, nombre_completo, rol, activo, ultimo_acceso, intentos_fallidos, bloqueado_hasta`.

Views read table cells positionally to rebuild a form's tuple. A row missing an item returns early rather than crashing.

## Sales are create-only

A sale is not editable — the row is history. The `Ver` button shows the detail read-only. Correcting a sale means deleting it (which returns the unit to stock) and registering it again.

## Styling

- One app-wide stylesheet, `gui/estilo.css`, loaded once in `main.py`. Widgets are themed via `setObjectName` + a matching QSS selector; there is no inline styling anywhere.
- Object names: `titulo`, `subtitulo`, `pie`, `icono`, `nombre_tarjeta`, `cantidad`, `tarjeta`, `sidebar`, `titulo_sidebar`, `boton_menu`, `boton_menu_activo`, `boton_salir`, `bloque_usuario`, `usuario_nombre`, `usuario_rol`, `boton_principal`, `boton_secundario`, `boton_filtro`, `boton_editar`, `boton_eliminar`, `aviso`, `aviso_error`, `filtros`, `campo_login`, `casilla_ver`, `login_icono`, `login_titulo`, `login_subtitulo`, `login_error`, `login_pie`, `estado_conexion`, `estado_ok`, `estado_error`.
- **Trap:** the bare `QPushButton` rule is styled as a *sidebar* button. Any new button without an `objectName` renders as a nav item. Use `crear_boton_principal` / `crear_boton_secundario`.
- Changing an `objectName` after the widget exists does not restyle it. Call `style().unpolish(w)` then `style().polish(w)`, as `ventana_principal.marcar_activo` does.

## House style

- Spanish everywhere: identifiers, UI strings, comments.
- Calls are exploded **one argument per line** with blank lines between statements; sections use ASCII banners (`# =====`, `# -----`). Match it — a normal reformat buries the real change in noise.
- Import order: project packages first, then PySide6. Do not import inside functions.
- GUI methods colliding with DB function names are aliased on import (`from database.autos import eliminar_auto as eliminar_auto_db`). Follow that instead of renaming.
- Row-action buttons capture their index with a default argument: `lambda _, f=fila: self.editar(f)`. `clicked` emits a bool, so the first parameter absorbs it.
