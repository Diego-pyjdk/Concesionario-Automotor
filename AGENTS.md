# AGENTS.md

## Comandos

- Arrancar desde la **raíz del proyecto**: `venv\Scripts\python.exe main.py`
- Comprobar la instalación: `venv\Scripts\python.exe verificar_instalacion.py`
  - Recorre los pasos de instalación y dice en cuáles falla y cómo arreglarlo.
- Administrador inicial (solo si no hay ninguno activo):
  `venv\Scripts\python.exe crear_admin.py`
- Instalación completa en `README.md`, paso a paso.

Dependencias en `requirements.txt` (PySide6 6.11.2, mysql-connector-python 26.7.0). Todo lo demás es biblioteca estándar: **no añadas dependencias** sin motivo.

## Configuración

- Las credenciales van en **`.env`** (gitignored). `.env.example` es la plantilla. `database/conexion.py` lee `DB_HOST`, `DB_PORT`, `DB_USER`, `DB_PASSWORD`, `DB_NAME`; las variables reales del entorno mandan sobre el archivo.
- **`cargar_env()` abre el `.env` con `encoding="utf-8-sig"`, no con `utf-8`.** Si el archivo lleva BOM —lo pone de más el Bloc de notas de Windows al guardarlo— la primera clave se llamaría `\ufeffDB_HOST`, no se leería, y el fallo sería **silencioso**: se usaría el valor por defecto y todo parecería correcto. Quita el BOM con `utf-8-sig`; nunca con `strip()`, que no lo quita.
- Nunca muestres ni devuelvas contraseñas: existe `sin_password()` para eso. La pantalla de diagnóstico lo usa a propósito.

## Flujo de arranque

`main.py` → `LoginView` → `VentanaPrincipal`. La ventana principal solo se construye con sesión activa; sin ella lanza `PermissionError` a propósito.

- `main.py` tiene `if __name__ == "__main__":`.
- Logout emite `VentanaPrincipal.solicitar_cierre_sesion` (un `Signal`; `pyqtSignal` no existe en PySide6). `main.mostrar_login` oculta y destruye la ventana vieja y vuelve al login. La X cierra la app.

## Arquitectura

`main.py` → `gui/*_view.py` (+ `gui/formularios/*_form.py`) → `database/<entidad>.py` → `database/conexion.py` → MySQL.

Módulos en la raíz:
- `errores.py` — `ErrorSistema`, `ErrorBaseDatos`, `ErrorValidacion`, `PermisoDenegado`, `traducir_error()` (errno de MySQL → mensaje en español). Los módulos de datos lanzan estos; nunca dejes escapar `mysql.connector.Error`.
- `sesion.py` — `iniciar_sesion(datos)`, `cerrar_sesion()`, `hay_sesion()`, `usuario_actual()`, `rol_actual()`, `obtener_sesion()`.
- `permisos.py` — `PERMISOS_POR_ROL`, constantes, `tiene_permiso()`, `requiere_permiso()`.

`database/`:
- Un módulo por entidad: toda la escritura va con `@requiere_permiso`.
- **`reportes.py`** — toda la capa de agregados y estadísticas, para el panel y para la pantalla de reportes. **No existe `dashboard.py`**: se absorbió aquí para que una misma cifra no se calculara de dos maneras.
- `auditoria.py`, `configuracion.py` — servicios transversales.
- `esquema.sql` — 7 tablas. Empieza con `DROP DATABASE`: es un script desde cero, nunca sobre datos reales.

`gui/`:
- **`vista_base.py`** — `VistaBase`. Envuelve la base de datos en `self.proteger(operacion, *args)`, que devuelve `None` si falla y muestra un mensaje legible. `mostrar_mensaje_error(texto)` es para errores sin excepción (un borrado bloqueado por FK, que vuelve como `False`).
- **`vista_listado.py`** — `VistaListado(VistaBase)`: el esqueleto de los cinco listados (vehículos, marcas, clientes, ventas, usuarios). Antes cada uno repetía ~60 líneas; ahí se colaban las diferencias. Una vista concreta declara `titulo`, `columnas`, `columna_acciones`, `placeholder_busqueda`, `muesaje`/`detalle_vacio`, y define `pintar_fila`, `cargar_datos` y `buscar`. **Al añadir un listado, hereda de aquí, no copies otro.**
  - Ofrece: `mostrar_de(operacion, *args)` (consulta protegida y vuelca), `mostrar_filas(filas)` (alterna tabla/estado vacío), `marcar_columnas(fila, valores, centrar={...})`, `poner_acciones(fila, widget)`, `leer_valores(fila, n)`, `confirmar_borrado(nombre, extra)`, y `self.acciones_encabezado` para botones extra.
  - El botón de alta aparece si `puede_gestionar` **y** existe `nuevo_registro()`. `VentasView` sobrescribe `muestra_boton_nuevo()` porque el vendedor registra ventas aunque no pueda gestionarlas.
- `diagnostico.py` — comprobaciones de solo lectura para el administrador. Nunca escribe.
- `formularios/` — un `QDialog` por entidad.

`utils/`: `validaciones.py` (todo devuelve `(es_valido, mensaje)`; `primer_error(lista)`), `helpers.py` (componentes), `seguridad.py` (PBKDF2; no importes `hashlib` en otro sitio), `registro.py` (trazas a `registro_errores.log`).

## Permisos

Dos capas. Ocultar un botón no es la protección.

1. `VentanaPrincipal.SECCIONES` es `(texto, vista, permiso)`. Una vista **no se construye** si al rol le falta el permiso de lectura. Son 9 secciones para el administrador, 5 para el vendedor.
2. `@requiere_permiso(PERMISO)` sobre las funciones que escriben. Sin sesión, todo permiso es `False`.

| | administrador | vendedor |
|---|---|---|
| Consultar autos / marcas / clientes / ventas | sí | sí |
| Registrar ventas | sí | sí |
| Crear, editar y **borrar** autos / marcas / clientes | sí | **no** |
| **Borrar** ventas | sí | **no** |
| Reportes / Usuarios / Auditoría / Configuración | sí | **no** |

- Un intento denegado escribe `ACCESO_DENEGADO` en la auditoría antes de lanzar la excepción.
- `crear_primer_usuario` va **sin** decorar (aún no hay sesión) y se niega a funcionar si ya hay un administrador activo.
- Las **lecturas** de auditoría exigen `VER_AUDITORIA`; la **escritura** del rastro no lleva permiso, porque tiene que funcionar durante el login, antes de que exista sesión.
- Las consultas de `reportes.py` usan dos permisos distintos a propósito: `obtener_resumen`, `obtener_ventas_del_dia/mes`, `obtener_top_vehiculos` y `obtener_ventas_por_cliente` piden `VER_TABLERO` (el vendedor las ve en el panel); las de detalle y métricas piden `VER_REPORTES` (solo admin). **No las unifiques**: se rompería el vendedor.
- Las lecturas de entidades no llevan decorador: ambos roles pueden leer.

## Contraseñas

- `usuarios.password_hash` guarda `sal_hex:hash_hex`. El texto plano no se guarda, no se registra y no se recupera.
- `autenticar()` devuelve `(True, "", datos)` o `(False, mensaje, None)`; `datos` es `(id, nombre_usuario, nombre_completo, rol)`.
- Usuario inexistente y contraseña incorrecta dan el **mismo** mensaje, y el caso inexistente verifica un hash señuelo para que el tiempo no revele qué cuentas existen.
- Bloqueo tras `MAX_INTENTOS = 5` durante `MINUTOS_BLOQUEO = 15` minutos, en `intentos_fallidos` / `bloqueado_hasta`. La contraseña correcta **no** lo salta.
- Las cuentas nuevas 默认 son `vendedor` (menor privilegio).
- `eliminar_usuario` devuelve `(True, "")` o `(False, motivo)`; no deja borrar tu propia cuenta ni el último administrador activo. `actualizar_usuario` no deja degradar ni desactivar al último administrador activo.
- Coste ~0,17 s por verificación (`ITERACIONES = 260000`). Subirlo vale; bajarlo no.

## Auditoría

`registrar_accion()` **nunca rompe la operación que la origina**: se traga sus propios errores y devuelve un booleano. Perder una línea del rastro es aceptable; perder una venta no.

- Las ventas se auditan **después** del `commit()`, para no afirmar ventas revertidas.
- `usuario_id` es `ON DELETE SET NULL` y `usuario_nombre` es una **copia**: borrar una cuenta no borra su historial.
- El centinela `SIN_INFORMAR` distingue "el llamador no dijo nada" (usa la sesión) de "el llamador dijo que no hay usuario" (guarda NULL). Un login fallido contra un usuario inexistente va con `usuario_id` NULL, no con el id de quien está sentado delante.
- `ACCIONES` y `MODULOS` en `database/auditoria.py` son el único sitio donde el código se traduce a texto. Añade códigos ahí, no en línea.
- `obtener_auditoria()` y `contar_registros()` comparten `_condiciones()`. Si construyesen el filtro por separado, uno contaría cosas distintas del otro.
- "Vaciar auditoría" pide confirmación doble y escribir `VACIAR`.

## Base de datos

- Relaciones: `marcas 1:N autos`, `clientes 1:N ventas`, `autos 1:N ventas`. `ventas.precio` congela el precio del momento.
- Cada función abre conexión, hace una consulta y la cierra. Salvo dos excepciones deliberadas en `database/ventas.py`: `registrar_venta` y `eliminar_venta` usan transacción.
- `registrar_venta` bloquea el vehículo con `SELECT ... FOR UPDATE`, comprueba stock, inserta y descuenta.
- `eliminar_venta` **devuelve la unidad al stock** en la misma transacción.
- `eliminar_marca`, `eliminar_cliente` y `eliminar_auto` devuelven `False` en vez de lanzar excepción cuando una FK lo bloquea. Comprueba el retorno.
- `cliente_duplicado(...)` compara por correo, o por nombre + apellido + teléfono a la vez.
- `_condiciones_ventas()` en `reportes.py` es la **única** forma de construir el filtro de ventas. Todas las consultas de reportes la usan, para que "por cliente" signifique lo mismo en el conteo, en el importe y en el detalle.
- `obtener_tablas()` en `gui/diagnostico.py` cruza en Python un `UNION` de conteos con `information_schema`: el nombre de tabla nunca se interpola en el SQL.
- **`FIRST_DAY()` es de MariaDB y no existe en MySQL.** Para el día 1 del mes usa `DATE_SUB(CURDATE(), INTERVAL (DAYOFMONTH(CURDATE()) - 1) DAY)`.
- La búsqueda arma el comodín en Python (`f"%{texto}%"`) y lo pasa como `%s`. Nada de interpolar entrada del usuario.

## Orden de columnas: contrato entre capas

`database/autos.py` selecciona exactamente `autos.id, marcas.nombre, autos.modelo, autos.anio, autos.precio, autos.color, autos.stock`.

Está codificado en tres sitios más:
- `AutosView.pintar_fila` escribe por posición y pone los botones en la columna **7** con `setCellWidget`.
- `AutosView.leer_auto` relee las columnas 0–6 y reconstruye la tupla con tipos.
- `AutoForm.cargar_datos` desempaqueta la misma tupla con la **nombre** de la marca en el índice 1, comparándolo contra el texto del combo.

Reordenar o añadir una columna rompe la interfaz sin error en la capa de datos. Cambia las cuatro a la vez.

**La columna 4 (precio) se muestra con separador de miles y hay que deshacerlo antes de convertir:** `float(datos[4].replace(",", ""))`. Olvidar el `replace` rompe la edición de cualquier vehículo de más de 999.

Las consultas de stock de `database/autos.py` reutilizan esas mismas 7 columnas para que `ReportesView` comparta el pintado (es de solo lectura, no deshace nada).

Otros contratos: `obtener_ventas` → `id, fecha, cliente, vehiculo, precio` (los dos últimos son `CONCAT`, no ids). `obtener_usuarios` → `id, nombre_usuario, nombre_completo, rol, activo, ultimo_acceso, intentos_fallidos, bloqueado_hasta`.

`leer_valores()` devuelve `None` si falta una celda, en vez de inventar un vacío que reventaría la conversión.

## Las ventas no se editan

Una venta es histórico. El botón `Ver` muestra el detalle en solo lectura. Corregir una venta es anularla (lo que devuelve la unidad al stock) y volver a registrarla.

## Teclado

- `Escape` ya lo resuelve `QDialog`: cierra con `reject()` sin escribir código.
- `Return` **no**: `QLineEdit`, `QSpinBox` y `QComboBox` se lo quedan. Por eso cada formulario llama a `conectar_enter_guardar(campos, guardar)`.
- No lo conectes a un `QComboBox`: `Return` ahí abre y cierra la lista desplegable.

## Búsqueda

`crear_busqueda()` devuelve un contenedor con `.campo` y `.boton` (o el `QLineEdit` suelto con `con_boton=False`). Filtra con `Enter` al momento y solo al dejar de escribir, con 350 ms de retardo (`ESPERA_BUSQUEDA_MS`): sin esa espera cada tecla dispara una consulta. El temporizador cuelga del campo (`.temporizador`) y `_disparar()` lo cancela para no filtrar dos veces.

Vaciar el campo filtra al instante: sin texto no hay nada que filtrar.

## Estilos

- Una sola hoja: `gui/estilo.css`, aplicada con `setObjectName` + selector QSS. Nada de estilos en línea.
- Paleta documentada al principio del archivo: grises pizarra, azul **solo** para lo principal, rojo **solo** para lo destructivo.
- Object names: `titulo`, `subtitulo`, `pie`, `etiqueta_filtro`, `icono`, `nombre_tarjeta`, `cantidad`, `tarjeta`, `tile`, `tile_nombre`, `tile_valor`, `metrica`, `metrica_nombre`, `metrica_valor`, `estado_vacio_icono`, `estado_vacio_titulo`, `estado_vacio_detalle`, `filtros`, `sidebar`, `titulo_sidebar`, `boton_menu`, `boton_menu_activo`, `boton_salir`, `bloque_usuario`, `usuario_nombre`, `usuario_rol`, `boton_principal`, `boton_secundario`, `boton_peligro`, `boton_filtro`, `boton_editar`, `boton_eliminar`, `aviso`, `aviso_error`, `estado_conexion`, `estado_ok`, `estado_error`, `login_*`, `campo_login`, `casilla_ver`.
- **La regla base de `QPushButton` es para la barra lateral.** Un botón sin `objectName` se ve como un elemento de menú. Usa los helpers.
- Cambiar el `objectName` después no reestila: `style().unpolish(w)` y luego `polish(w)`.
- **`QLabel { background-color: transparent }` sostiene todo el diseño.** Sin eso, cada etiqueta pinta su propia banda gris sobre las tarjetas.
- **La altura de fila hay que fijarla.** Qt la calcula desde el texto e ignora `setCellWidget`, así que los botones de 30 px salían cortados. `crear_tabla` pone `setDefaultSectionSize(44)` y `crear_botones_accion` fija el contenedor en 34 px.
- **Las tablas cortas necesitan `ajustar_alto_tabla(tabla)`.** Con un `setMaximumHeight()` fijo se quedan con barra de desplazamiento y solo enseñan la primera fila.
- Las etiquetas de error empiezan ocultas (`setVisible(False)`) y se ocultan al limpiarlas, o queda un recuadro rojo vacío.
- **No dibujes flechas en QSS con bordes:** salen como bloques sólidos. Deja `::down-arrow` al estilo de Qt.
- No pongas anchos fijos en tablas dentro de paneles estrechos: las columnas centrales se colapsan a unos píxeles. Da más ancho al panel, no a la columna.

## Estilo del código

- Español en todo: identificadores, textos, comentarios.
- Las llamadas van **un argumento por línea**, con línea en blanco entre sentencias; las secciones llevan marcos ASCII (`# =====`, `# -----`). Respétalo: un reformateo normal esconde el cambio real.
- Orden de imports: primero los del proyecto, luego PySide6. **No importes dentro de funciones.**
- Los métodos de GUI que chocan con funciones de datos se(aliasan: `from database.autos import eliminar_auto as eliminar_auto_db`.
- Los botones de fila capturan su índice por valor por defecto: `lambda _, f=fila: self.editar(f)`. `clicked` emite un booleano y el primer parámetro lo absorbe.
- Archivos UTF-8 **sin BOM** y con salto de línea final.
- Compilar no detecta nombres mal escritos dentro de un método: solo fallan al construir el widget. Antes de dar algo por bueno, **constrúyelo**.

## Verificación

No hay suite de tests en el repositorio. Hasta que la haya, comprueba con estas piezas:

- `venv\Scripts\python.exe verificar_instalacion.py` — entorno y conexión.
- Compilar todos los `.py` y revisar imports sin usar con AST.
- **Construir cada vista y cada formulario** en `QT_QPA_PLATFORM=offscreen` y navegar por las 9 secciones. Es lo único que detecta un `NameError` de runtime, un import que sobra o un parámetro mal pasado.
- Parchear `QMessageBox.warning/information/question/critical` antes de construir nada: si no, un error inesperado **cuelga** la comprobación en vez de fallarla. Si una comprobación se queda colgada, busca el `QMessageBox` que nadie parcheó.
- Para esperar a un `QTimer` hay que procesar eventos (`app.processEvents()` en bucle); `time.sleep` no los deja correr.
- Capturas sin pantalla: `widget.grab().save(ruta)` tras registrar fuentes del sistema con `QFontDatabase.addApplicationFont()` (`segoeui.ttf`, `segoeuib.ttf`, `arial.ttf`, `seguiemj.ttf`). Sin eso salen cajas en vez de acentos y emojis: es un artefacto del renderizado, no un fallo de la aplicación.
