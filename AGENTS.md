# AGENTS.md

## Comandos

- Arrancar desde la **raíz del proyecto**: `venv\Scripts\python.exe main.py`
- Comprobar la instalación: `venv\Scripts\python.exe verificar_instalacion.py`
  - Recorre los pasos de instalación y dice en cuáles falla y cómo arreglarlo.
- Administrador inicial (solo si no hay ninguno activo):
  `venv\Scripts\python.exe crear_admin.py`
- Instalación completa en `README.md`, paso a paso.

Dependencias en `requirements.txt` (PySide6 6.11.2, mysql-connector-python 26.7.0, reportlab 5.0.1). Todo lo demás es biblioteca estándar. **No añadas dependencias** sin motivo: el PDF se compone con Platypus, que ya trae reportlab.

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
- **`contratos.py`** — contratos de compraventa. El número (`CTR-2026-00001`) se arma con el año y el **id del propio contrato**, dentro de la misma transacción: se hace `INSERT` con `numero` a NULL, se toma `lastrowid` y se hace `UPDATE`. Así es único por construcción y no depende de contar filas ni de que dos usuarios creen contratos a la vez. `_validar_financiacion()` y `_a_importe()` son suyos: las guardas duras del documento firmado y la normalización del dinero.
- **`financiera.py`** — el núcleo de la venta financiada: `calcular_cronograma()` (puro, sin base), generación, cuotas, pagos, estados, detección de vencidas y rastro con valor anterior/nuevo.
- **`cobranza.py`** — cuentas por cobrar, vencidas, por vencer, resúmenes, antigüedad y concentración. Todas sus lecturas llevan `@requiere_permiso(VER_FINANCIERA)`. `SALDO_PENDIENTE_POR_CONTRATO` es el filtro de "todavía debe dinero" y `SALDO_PENDIENTE_ACTIVO` el de "debe y además está vivo".
- **`garantias.py`** — garantías y gravámenes, con `AVISO_GRAVAMEN`, `TIPOS`, `ESTADOS` y `TRANSICIONES`. **No calcula importes de garantía ni hace de escribano**, y su cabecera lo dice.
- **`pagos.py`** — entradas de dinero de una venta. Devuelve `(precio, pagado, saldo)` desde `saldo_venta()` y el saldo se calcula con `SUM()` en SQL, no trayendo pagos a Python. La comprobación de "el importe no puede pasar del saldo" va **dentro** de la transacción con la venta bloqueada (`FOR UPDATE`): sin bloqueo, dos cobros a la vez pasarían los dos la comprobación.
- `auditoria.py`, `configuracion.py` — servicios transversales.
- `esquema.sql` — **12 tablas**. Empieza con `DROP DATABASE`: es un script desde cero, nunca sobre datos reales. **Las tablas van en orden de dependencias y no hay ningún `ALTER TABLE`**: `marcas → autos → clientes → usuarios → ventas → configuracion → auditoria → contratos → cuotas → garantias → convenios → pagos`. `usuarios` va antes que `ventas` a propósito, para que `ventas.usuario_id` declare su clave foránea en línea, dentro del propio `CREATE TABLE`.
- **`Al añadir una tabla, tres cosas más.** La fila del `UNION` de `gui/diagnostico.py::obtener_tablas()`, la lista `TABLAS` de `tests/test_instalacion.py`, y `DEPENDENCIAS` en ese mismo archivo. **Si se olvida el `UNION`, la tabla sigue apareciendo en el diagnóstico pero con siempre 0 filas**: un fallo silencioso.
- `migracion_contratos.sql` — para bases que **ya** tienen datos: añade `contratos` y `clientes.documento` sin tocar ninguna fila.
- `migracion_indices.sql` — añade `ix_ventas_fecha`, `ix_contratos_fecha` y el UNIQUE `marcas.nombre`. **Avisa antes de aplicarlo** de que si ya hay marcas repetidas el UNIQUE las rechazará: el archivo lleva la consulta de comprobación.
- `migracion_ventas_usuario.sql` — añade `ventas.usuario_id`, `ventas.usuario_nombre` e `ix_ventas_usuario`.
- `migracion_pagos.sql` — crea la tabla `pagos`.
- `migracion_moneda.sql` — siembra las cinco claves de moneda. **`INSERT IGNORE`, no `INSERT`**: si el administrador ya cambió la moneda desde Configuración, migrar no debe pisarla.
- **`migracion_financiera.sql`** — añade `cuotas`, `garantias` y `convenios`, las columnas de financiación de `contratos`, `pagos.cuota_id` / `recibo` / las de anulación, y siembra los siete ajustes `financiera_*`. **No toca ninguna fila**: los contratos que ya dicen "12 cuotas" se quedan sin cronograma, y eso es lo correcto.
- **`migracion_auditoria_cambios.sql`** — añade `valor_anterior`, `valor_nuevo` y `referencia` a `auditoria`, con sus índices.

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

1. `VentanaPrincipal.SECCIONES` es `(texto, vista, permiso)`. Una vista **no se construye** si al rol le falta el permiso de lectura. Son **11 secciones para el administrador, 6 para el vendedor**: el administrador tiene además **Cartera**.
2. `@requiere_permiso(PERMISO)` sobre las funciones que escriben. Sin sesión, todo permiso es `False`.

| | administrador | vendedor |
|---|---|---|
| Consultar autos / marcas / clientes / ventas | sí | sí |
| Registrar ventas | sí | sí |
| Crear, editar y **borrar** autos / marcas / clientes | sí | **no** |
| **Borrar** ventas | sí | **no** |
| Consultar y **crear** contratos | sí | sí |
| Generar el cronograma de un contrato | sí | sí |
| **Cobrar** cuotas | sí | **no** |
| Consultar la **cartera** y la cobranza | sí | **no** |
| Anular cuotas y pagos, garantías | sí | **no** |
| Cancelar o eliminar contratos | sí | **no** |
| Reportes / Usuarios / Auditoría / Configuración | sí | **no** |

- El vendedor **genera** el cronograma porque es parte de la venta que está firmando, pero **no cobra**: cobrar un crédito no es lo mismo que registrar una venta. Y **no ve la cartera**, porque la cartera dice a cuánto debe cada cliente del concesionario con su teléfono para llamarle, no solo los suyos. Si algún día hace falta que alguien externo cobre, la respuesta es un **rol nuevo** (`cobrador`) con `VER_FINANCIERA` y `GESTIONAR_FINANCIERA`, no abrirle la cartera al vendedor.
- Un intento denegado escribe `ACCESO_DENEGADO` en la auditoría antes de lanzar la excepción.
- `crear_primer_usuario` va **sin** decorar (aún no hay sesión) y se niega a funcionar si ya hay un administrador activo.
- Las **lecturas** de auditoría exigen `VER_AUDITORIA`; la **escritura** del rastro no lleva permiso, porque tiene que funcionar durante el login, antes de que exista sesión.
- Las consultas de `reportes.py` usan dos permisos distintos a propósito: `obtener_resumen`, `obtener_ventas_del_dia/mes`, `obtener_top_vehiculos` y `obtener_ventas_por_cliente` piden `VER_TABLERO` (el vendedor las ve en el panel); las de detalle y métricas piden `VER_REPORTES` (solo admin). **No las unifiques**: se rompería el vendedor.
- Las lecturas de **entidades** no llevan decorador: ambos roles pueden leer. Las lecturas de la **cartera** (`database/cobranza.py`) sí, con `VER_FINANCIERA`: no es lo mismo leer un cliente que leer cuánto debe cada cliente con su teléfono.

## Contraseñas

- `usuarios.password_hash` guarda `sal_hex:hash_hex`. El texto plano no se guarda, no se registra y no se recupera.
- `autenticar()` devuelve `(True, "", datos)` o `(False, mensaje, None)`; `datos` es `(id, nombre_usuario, nombre_completo, rol)`.
- Usuario inexistente y contraseña incorrecta dan el **mismo** mensaje, y el caso inexistente verifica un hash señuelo para que el tiempo no revele qué cuentas existen.
- **El mensaje no lleva el contador de intentos, nunca.** Se quitó a propósito: como el contador solo subía si la cuenta existía, un solo intento fallido bastaba para averiguar qué cuentas hay. El aviso de cuenta bloqueada sí menciona la cuenta, porque para entonces ya se han gastado cinco intentos y no se averigua nada nuevo. Si lo vuelves a añadir, rompes esto.
- Bloqueo tras `MAX_INTENTOS = 5` durante `MINUTOS_BLOQUEO = 15` minutos, en `intentos_fallidos` / `bloqueado_hasta`. La contraseña correcta **no** lo salta.
- Las cuentas nuevas son `vendedor` por defecto en UsuarioForm (menor privilegio). En la capa de datos `insertar_usuario` **exige** el rol: si no viene, es un fallo de quien llama, no algo que se deba adivinar.
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

Otros contratos: **`obtener_ventas` → `id, fecha, cliente, vehiculo, precio, usuario_nombre`** (6 columnas; los dos de texto son `CONCAT`, no ids, y el último puede ser `None` en ventas anteriores a `migracion_ventas_usuario.sql`, así que quien lo pinte tiene que poner algo legible).

**Y las filas de una venta NO son intercambiables.** `obtener_ventas()` trae el vendedor (6) y `ventas_sin_contrato()` / `venta_para_contrato()` no (5). `ContratoForm` recibe el **id**, no una fila, y busca los datos él. Antes recibía la fila y la desempaquetaba en cinco, así que desde **Ventas** —crear el contrato al confirmar una venta, que es el flujo principal— moría con `ValueError: too many values to unpack`, y la aplicación se caía de espaldas. Ninguna prueba lo veía: las de los formularios le construían a mano una tupla de cinco, justo la forma que le daba gusto al constructor. Las dos consultas comparten el `DATOS_VENTA` de `database/contratos.py` para que no se vuelvan a separar. Está escrito en `VentasView.pintar_fila`, `VentasView.ver_venta` y `VentasView.columnas`/`columna_acciones`: si añades la columna del vendedor, la de acciones pasa a ser la 7. `obtener_usuarios` → `id, nombre_usuario, nombre_completo, rol, activo, ultimo_acceso, intentos_fallidos, bloqueado_hasta`. **`obtener_clientes` → `id, nombre, apellido, telefono, email, documento`** (6 columnas): `documento` se añadió para el contrato y `ClientesView`, `ClienteForm` y las búsquedas se actualizaron a la vez.

`obtener_tablas()` en `gui/diagnostico.py` cruza en Python un `UNION` de conteos con `information_schema`: el nombre de tabla nunca se interpola en el SQL. **El `UNION` lleva una línea por cada tabla de `esquema.sql`.** Si al añadir una tabla se olvida esa línea, la tabla sigue apareciendo en el diagnóstico pero con **siempre 0 filas**, porque el `get()` no la encuentra: un fallo silencioso.

`leer_valores()` devuelve `None` si falta una celda, en vez de inventar un vacío que reventaría la conversión.

## Los pagos no se editan

Un pago es un hecho económico. Si está mal, `pagos.eliminar_pago()` lo borra (solo el administrador, con confirmación doble) y se vuelve a registrar. Queda el rastro. **Un pago nunca se "anula con signo contrario"**: `importe` es siempre positivo y la aplicación rechaza los menores o iguales a cero, porque un importe negativo no es un pago, es un reembolso, y haría que el saldo pareciera un error de cálculo.

**Un contrato dice QUÉ se debe pagar; la tabla `pagos` dice QUÉ se ha pagado.** No se mezclan: el contrato se firma una vez, los pagos se registran uno a uno. El anticipo del contrato **no** cuenta como pago hasta que se registre uno: si lo contara automáticamente, el saldo cuadraría con un movimiento que nadie puede ver en la lista de pagos ni explicar en un extracto.

- `eliminar_venta()` **no anula una venta con pagos**. `pagos.venta_id` es `ON DELETE RESTRICT` y la función lo comprueba antes para devolver `False` con motivo, en vez de saltar por la excepción. A diferencia del contrato cancelado, aquí no hay nada que borrar antes: deshacer un cobro es una operación aparte, que decide `pagos.eliminar_pago()`, con permiso de administrador y con rastro.
- **`registrar_pago()` rechaza un importe con más de dos decimales.** `pagos.importe` es `DECIMAL(10,2)`: un pago de 0.004 se guardaría redondeado como 0.00, el dinero desaparecería sin avisar y el saldo no se movería. Se rechaza en vez de redondear, porque un "no puede tener más de dos decimales" es preferible a un cobro que se pierde. El formulario usa `QDoubleSpinBox` con dos decimales, así que desde la interfaz es imposible llegar ahí.
- **La comparación del saldo es exacta, sin margen de tolerancia**, y va en `Decimal`. Con `precio` y `pagado` en `DECIMAL(10,2)` el saldo siempre es múltiplo de un céntimo y se compara sin aproximado. El residuo que deja dividir 20.000 en 7 cuotas (2 céntimos) **sí** se puede cobrar, porque es un importe representable.
- **Por qué se quitó la tolerancia:** con medio céntimo de margen, un pago de 0.004 pasaba la comprobación, se guardaba como 0.00 por el redondeo del DECIMAL, el saldo no cambiaba y el siguiente volvía a pasar. Se acumulaban filas de 0.00 que no movían nada. El margen parecía acotado y no lo era.
- `saldo_venta()` devuelve `(precio, pagado, saldo)` con `SUM()` en SQL, no sumando en Python: si se sumara en Python, un pago de otra venta podría colarse.
- `venta_bloqueada_por_pagos()` devuelve `(True, n)` o `(False, 0)`, igual que `venta_bloqueada_por_contrato()` devuelve el número: lo que hay que enseñar, no un booleano pelado.
- `obtener_pagos()` → `id, fecha, importe, forma, referencia, concepto, usuario_nombre`.
- El `rollback` de `registrar_pago()` va en `except BaseException`, no solo en `except mysql.connector.Error`: con la versión anterior, un fallo que no fuese de MySQL salía sin deshacer la transacción. El decorador `@conexiones_libres` cerraba la conexión y al cerrarla MySQL haría rollback igualmente, así que no se perdía dinero, pero la garantía dependedía de que el cierre funcionara.

## La moneda

**`utils/moneda.py` es el único sitio donde vive el símbolo de la moneda.** Antes el `"$ "` estaba escrito dentro de cuatro funciones distintas: `utils/contrato_pdf.py`, dos métodos `dinero()` en la interfaz y otra copia local en `contrato_form.py`. Cuatro copias significa que cambiar la moneda obligaba a tocar cuatro archivos y era fácil olvidar uno.

Cinco claves en `configuracion`:

| Clave | Por defecto | Para qué |
|---|---|---|
| `moneda_codigo` | `USD` | código ISO |
| `moneda_simbolo` | `$` | símbolo |
| `moneda_formato` | `simbolo_espacio` | cómo se juntan símbolo e importe |
| `moneda_separador_miles` | `,` | `1,500.00` o `1.500,00` |
| `moneda_separador_decimales` | `.` | `1,500.00` o `1.500,00` |

Formatos: `simbolo_espacio`, `simbolo_pegado`, `simbolo_despues`, `codigo_espacio`, `codigo_pegado`, `codigo_despues`.

- Los valores por defecto reproducen **exactamente** el `f"$ {valor:,.2f}"` de antes, byte a byte, incluidos los empates del redondeo en coma flotante. No es casualidad: con los separadores de siempre, `formatear_numero()` devuelve directamente `format(valor, ",.2f")` en vez de armar entero y céntimos a mano. **Armarlos a mano daba dos importes mal escritos** (`0.99` salía `1.99`, `-1500.75` salía `-1501.75`) y resolvía los empates distinto que Python (`0.995`). Solo hace falta cuando los separadores cambian.
- **El signo va antes de la moneda**: `-$ 1,500.75`, no `$ -1,500.75`. Es una corrección sobre el comportamiento antiguo, no una regresión.
- **No hay negativo cero**: `-0.004` se redondea a cero y sale `$ 0.00`, no `-$ 0.00`. El signo sale solo si queda alguna cifra detrás.
- `prefijo_moneda()` es para los campos numéricos (`QDoubleSpinBox.setPrefix`). Con el formato que pone la moneda detrás devuelve cadena vacía: si no, el símbolo saldría dos veces.
- **Las tablas no llevan símbolo** (nunca lo llevaron y añadirlo ensancha las columnas), pero usan `formatear_numero()` para que los separadores sí sigan la configuración. Si no, el listado diría `36,500.00` mientras el detalle diría `EUR 36.500,00`.
- La configuración se lee una vez y se cachea en `utils/moneda.py`. `main.py` la calienta al arrancar y `ConfiguracionView` la reaplica al guardar, para que un cambio se vea **sin reiniciar**.
- `utils/moneda.py` hace un import de `database.configuracion` **dentro** de la función, y solo en el primer fallo de caché. Es la única excepción a "no importes dentro de funciones" de todo el proyecto, y está ahí para no invertir la capa: `gui/` y `database/` usan `utils/`, no al revés. Si la lectura falla se cae a los valores por defecto: **formatear un importe nunca debe ser el motivo de que una pantalla no se abra.**
- Un ajuste guardado con basura no rompe nada: `_normalizar()` descarta lo que no sirva y `actualizar_moneda()` valida antes de escribir. En particular, **el separador de miles y el de decimales no pueden ser el mismo**: `1.234.56` y `1.234,56` se leerían igual.

## El orden de las tablas en esquema.sql

El esquema se declara **en orden de dependencias**: `marcas → autos → clientes → usuarios → ventas → configuracion → auditoria → contratos → cuotas → garantias → convenios → pagos`.

`usuarios` va antes que `ventas` **a propósito**: así `ventas.usuario_id` declara su clave foránea en línea, dentro del propio `CREATE TABLE`, y **no hay ningún `ALTER TABLE` en todo el archivo**. Antes estaba al revés y hacía falta un `ALTER TABLE` suelto después de crear `usuarios`, lo que ataba la instalación al orden en que se ejecutaran las sentencias.

`tests/test_instalacion.py` comprueba las tres cosas: que no hay `ALTER TABLE`, que cada tabla va después de las que referencia, y que `ventas_usuario_fk` existe con `ON DELETE SET NULL` tras ejecutar el esquema entero.

`SET NULL` y no `CASCADE` es lo que separa "un empleado se va" de "se borran las ventas que hizo": con `CASCADE`, borrar la cuenta se llevaría sus ventas. `usuario_nombre` es una **copia**, así que aunque `usuario_id` quede a NULL el histórico sigue diciendo quién vendió. `tests/test_integridad_ventas.py` lo comprueba borrando la cuenta de verdad y verificando que la venta sobrevive con el nombre.

## Los contratos no se editan

Como las ventas, un contrato es histórico. Se cancela y se rehace desde la venta. `TRANSICIONES` en `database/contratos.py` es el único sitio donde se decide qué cambio de estado es legal: `finalizado` no vuelve a `activo` (sí se puede anular), `cancelado` sí se puede reactivar porque no surte efecto.

`venta_id` es UNIQUE: impide dos contratos vivos para la misma venta. La ruta para rehacer uno es cancelar el anterior y crear el nuevo, y `crear_contrato()` borra el cancelado dentro de la misma transacción.

Una venta con contrato vivo **no se puede anular**. La clave foránea ya lo impide (`ON DELETE RESTRICT`), pero `eliminar_venta()` lo comprueba antes para poder devolver `False` en vez de saltar por la excepción, y la vista usa `venta_bloqueada_por_contrato()` para explicarlo en vez de decir "no se pudo anular".

`registrar_venta()` devuelve el **id** de la venta, no `True`. Quien llama solo mira si es cierto y no cambia, pero con el id el formulario puede ofrecer el contrato sin volver a buscarla.

## Las ventas no se editan

Una venta es histórico. El botón `Ver` muestra el detalle en solo lectura. Corregir una venta es anularla (lo que devuelve la unidad al stock) y volver a registrarla.

## La venta financiada

La sección **Cartera** y el detalle del contrato son la otra mitad del sistema de ventas. Lo que hay que saber antes de tocar nada:

### El dinero entra en `pagos`, con `cuota_id` nullable

**No hay tabla de pagos de cuotas.** `pagos.cuota_id` apunta a `cuotas` y vale NULL en un pago suelto (la entrega inicial). Una tabla aparte obligaría a sumar las dos en cada consulta que calcula un saldo, y esa suma es justo el sitio donde un pago anulado o de otra cuota se cuela sin que nada lo note.

`pagos.obtener_pagos(venta_id)` devuelve **7 columnas y como tuplas**: `id, fecha, importe, forma, referencia, concepto, usuario_nombre`. Es la del listado. Para las pantallas que necesitan saber más (si está anulado, a qué cuota se imputó, su recibo) está `obtener_pagos_detalle(venta_id)`, que devuelve diccionarios. La vista de auditoría del rastro lee la primera; la de pagos, la segunda.

### `cuotas.saldo` es una columna, no un `SUM()`

El estado y el saldo tienen que cambiar **juntos**, y por eso `registrar_pago_cuota()` es la única que escribe en las dos tablas, dentro de la misma transacción que inserta el pago. `recalcular_saldo_cuota()` existe para **demostrar que no hay deriva**: si alguna vez el saldo y la suma de pagos no coinciden, algo ha escrito por otro lado.

### Vencida se deriva de la fecha

`procesar_vencidas()` marca **y desmarca**. Pagar una cuota vencida la saca de `vencida`. Una cuota vencida no cambia de estado sola: cambia porque alguien mira, y quien mira es quien abre la cartera. Por eso no hay proceso de fondo: añadiría una cosa que puede romperse sin que nadie lo note.

### El número de recibo lo arma el `INSERT`

`siguiente_numero_recibo()` (`MAX(id) + 1`) es una **vista previa**, no un número que se pueda guardar: dos cobros a la vez saldrían con el mismo. Para guardar se deja en `None` y lo arma el propio `INSERT`, con el id que le toque. Si añades un camino de pago nuevo, que siga esa regla.

### El cobro adelantado: una suma, N imputaciones, un recibo

Un cliente paga dos meses seguidos de una vez. `registrar_pago_adelantado(id_contrato, importe, fecha, forma, ...)` lo resuelve con **N filas de `pagos`, un mismo `recibo` y una sola entrada de rastro**.

Lo que **no** se hace, y por qué:

- **Guardarlo como pago suelto sin imputar.** El dinero entra y el saldo del contrato baja, pero las cuotas siguen con su saldo entero: la cartera vuelve a pedirle al cliente los meses que ya pagó, cada mes.
- **Imputarlo todo a una cuota y que su saldo quede NEGATIVO.** Un saldo negativo rompe todas las cuentas de la cartera, que comparan contra cero, y un «-3.208.333,33» no significa nada.

Compartir un número de recibo **no es editar los pagos**: es decir «esto entró junto». Los pagos no se agrupan ni se tocan; hay N porque hay N imputaciones, y eso es lo que pasó.

**Todo en una transacción.** Encadenar N llamadas a `registrar_pago_cuota()` por fuera dejaría las primeras cobradas si la tercera fallara: el cliente entregó 30.000, hay 20.000 aplicados y 10.000 en un pago suelto que nadie sabe a qué corresponde. Aquí o entra todo o no entra nada.

**`repartir_adelanto(cuotas, importe)` es PURA** (no toca la base) y es la **misma** que usa la vista previa de `PagoAdelantadoForm` y que luego guarda el cobro. Si el formulario calculara el reparto por su cuenta, el cliente vería un reparto y le aplicarían otro.

Su regla es **cuota entera o nada**, de la más antigua a la más reciente:

> Repartir de a poco —10.000 en la 3, que quedan 20.000, y seguir a la 4— deja un resto pequeño en la cuota 3 **para siempre**, porque siempre hay una cuota más antigua detrás. El cliente acaba debiendo la 3 mientras paga la 4, y el residuo se acumula sin que nadie lo vea. Con «entera o nada» o la cuota queda saldada o el dinero no cabe y se avisa. Nunca queda un residuo escondido.

**El sobrante se rechaza, no se improvisa.** Si el importe no cabe en las cuotas pendientes, se devuelve el sobrante con su motivo y el botón se apaga: es preferible un «no puede» a un cobro repartido de una manera que el cajero no ha elegido.

Se comprueba el **total** contra el saldo de la venta, no cada parte: un cobro de 30.000 repartido en tres de 10.000 pasaría parte a parte y fallaría en la tercera, dejando dos cobradas de un total que no cabía.

### El cronograma avanza por meses de calendario con día ancla

No por 30 días: un crédito firmado el día 31 se movería al 28 para siempre. `_sumar_meses(fecha, meses, dia_referencia)` mantiene el día. `contratos.dia_vencimiento` guarda ese día para poder recomponerlo sin recalcular nada.

La **última cuota se lleva el residuo** del redondeo, para que la suma sea el saldo financiado hasta el céntimo. Es lo que hace `_repartir()`, y la vista previa del formulario usa **la misma `calcular_cronograma()`** que va a generar las cuotas: si calculara de otra manera, la última cuota del papel sería distinta de la que ve el cliente.

### Las condiciones se congelan al firmar

`crear_contrato()` escribe `saldo_financiado`, `tasa_interes`, `gastos_administrativos`, `periodicidad`, `primer_vencimiento`, `dia_vencimiento`, `moneda`, `retencion`, `clausulas` **y la fotografía del vehículo** (`marca`, `modelo`, `anio`, `color`, `precio_lista`). Corregir el vehículo después ya no cambia el contrato firmado.

`saldo_financiado` sale de `precio - anticipo - gastos` **salvo que se pase**: hay financieras que financian el precio de lista y el cliente pone la diferencia. Y en `Contado` es cero por definición.

**`crear_contrato()` exige periodicidad y primer vencimiento si hay cuotas.** Un contrato con "12 cuotas" y sin fecha se guarda, pero no genera cronograma; la cartera lo avisa y el detalle lo ofrece. Un contrato con la mitad de las cuotas, no se arregla.

### Cobrar es de la administración

`registrar_pago_cuota()` lleva `GESTIONAR_FINANCIERA`, **no** `VER_CONTRATOS` ni `REGISTRAR_VENTAS`. Registrar una venta lo puede hacer el vendedor porque es su trabajo; quedarse con el cobro de las cuotas de un crédito es de quien responde de que ese dinero llegó. Antes llevaba `VER_CONTRATOS`, que el vendedor tiene, y bastaba llamar a la función desde un script.

Y `database/cobranza.py` **también** lleva permiso en todas sus lecturas, con `VER_FINANCIERA`. La cartera dice a cuánto debe cada cliente del concesionario con su teléfono, no solo los del vendedor: eso es información de la dirección, no de la venta.

### `crear_contrato()` normaliza el dinero

`_a_importe()` convierte a `Decimal` por la **cadena**, no con `float()`. El precio sale de la base como `Decimal` y el anticipo suele llegar como `float` desde un formulario: `Decimal - float` es un `TypeError` que no dice nada del contrato. Y `float()` de un número con más de 15 dígitos ya ha perdido precisión al entrar.

### El historial de un contrato está repartido

Las garantías usan el **número del contrato** como `referencia` y cada pago usa **su recibo**. Por eso buscar por el número da las garantías y ni un pago. `historial_contrato(id_contrato)` junta las dos cosas en una consulta: pregunta por el número y por todos los recibos de su venta, y esa regla vive en la **capa de datos**, no en la pantalla.

Devuelve **tuplas** de 9 columnas como `obtener_auditoria()`, no diccionarios: quien lo pinta los recorre por índice.

### Lo que este módulo NO hace, a propósito

Nada de interés de mora, nada de homologación, nada de envío a ningún registro. Un gravamen es una **inscripción registral**: lo que se registra aquí es lo que el concesionario **afirma**, no un documento ante el Registro Público. Por eso `garantias.AVISO_GRAVAMEN` sale en pantalla **siempre**, con garantías o sin ellas, y `registrar_garantia()` escribe una entrada de rastro que lo dice.

Lo mismo con la retención y la mora: son datos que se **guardan**, no obligaciones que la aplicación calcule. **Revisar con un asesor fiscal, un abogado y un escribano.**

Liberar una garantía exige saldo pendiente cero, y autorización del administrador: liberar es devolverle al cliente su respaldo.

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
- **`crear_tabla()` NO añade la columna de acciones.** Solo le pone el ancho fijo. Si `columna_acciones` queda fuera de la lista de cabeceros, la columna no se crea, `setCellWidget()` no pone nada y **los botones no se ven**: sin error, sin aviso y sin que ninguna prueba lo note, porque construcción no es pintura. `"Acciones"` tiene que ir **en la lista**. Las tres tablas de `CarteraView` estuvieron así una temporada: la cartera entera era de solo lectura y no había forma de cobrar desde ella.
- **El ancho de la columna de acciones se CALCULA, nunca se pone a mano.** Los botones van con `setFixedSize`, así que el layout no los encoge: si la columna se queda corta se salen de su celda y se pintan encima de la vecina. Usa `ancho_acciones_para([...])` con los anchos de tus botones. Suma el hueco de la barra de desplazamiento vertical: Qt se la resta al área visible y no aparece en el ancho de la columna. Un ancho de 148 a mano para dos botones se quedaba 18 px corto.
- **El ancho de cada botón se MIDE con la hoja de estilos puesta.** `QPushButton.sizeHint()` con la hoja: `"Editar"` pide 68, `"Eliminar"` 90, `"Adelantado"` 112. Sin ella Qt mide con la fuente por defecto y con su relleno, y `"Eliminar"` pide **110**: 20 px de más. Arreglar anchos con esa medición los deja más anchos de lo necesario, que es inofensivo; el error peligroso es al revés, y por eso las pruebas que miden tienen que **aplicar `gui/estilo.css`**. Los 15 botones de la aplicación estaban entre 6 y 22 px cortos, con el texto cortado. `test_los_botones_no_se_recortan` los recorre todos.
- **Un botón sin `objectName` se ve como elemento de menú.** La regla base de `QPushButton` en la hoja es la de la barra lateral: 13 px, relleno 10x14, texto a la izquierda. Los botones de `acciones_extra` también necesitan el suyo: en `CarteraView` iban con `objeto=None` y medían 112 px en vez de 68. Usa `"boton_editar"` para los de acción y `"boton_eliminar"` para los destructivos, como hacen `VentasView` y `ContratosView`.
- **Los botones de acción se capturan por valor:** `lambda _, f=fila: self.algo(f)`. Para meter un tercer botón, pásalo en `acciones_extra=[(texto, callback, objeto, ancho)]` en vez de tocar el helper.
- El ancho de una columna debe cubrir el **texto + los 20 px de padding** de `QTableWidget::item { padding: 9px 10px }`. Sin ese padding el cálculo da falsos negativos y en pantalla el texto sale con puntos suspensivos.
- **No abras un diálogo modal desde dentro de otro.** `VentaForm.guardar()` deja `venta_para_contrato` y es `VentasView` quien lanza el contrato al cerrar. Encadenarlos apila dos modales y cuelga cualquier prueba que conteste "Sí" a un `QMessageBox`.

## Estilo del código

- Español en todo: identificadores, textos, comentarios.
- Las llamadas van **un argumento por línea**, con línea en blanco entre sentencias; las secciones llevan marcos ASCII (`# =====`, `# -----`). Respétalo: un reformateo normal esconde el cambio real.
- Orden de imports: primero los del proyecto, luego PySide6. **No importes dentro de funciones.**
- Los métodos de GUI que chocan con funciones de datos se aliasan: `from database.autos import eliminar_auto as eliminar_auto_db`.
- Los botones de fila capturan su índice por valor por defecto: `lambda _, f=fila: self.editar(f)`. `clicked` emite un booleano y el primer parámetro lo absorbe.
- Archivos UTF-8 **sin BOM** y con salto de línea final.
- Compilar no detecta nombres mal escritos dentro de un método: solo fallan al construir el widget. Antes de dar algo por bueno, **constrúyelo**.

## Verificación

Hay suite de pruebas en `tests/`, con pytest:

- `venv\Scripts\python.exe -m pytest` — **471 pruebas**.
- `venv\Scripts\python.exe verificar_instalacion.py` — entorno y conexión, y **los 52 módulos** que usan PySide6, MySQL o reportlab. Cada uno importa o no: un módulo que falla al importar no da error al arrancar, da error cuando alguien abre esa pantalla. **Al añadir un módulo a `gui/` o `database/`, añádelo también a la lista de `verificar_instalacion.py`**: si no, se importa sin comprobarse.

### Cómo aísla las pruebas

Cada sesión levanta una base temporal llamada `pruebas_concesionario` a partir de `database/esquema.sql` y **fija `DB_NAME` en el entorno** para que toda la aplicación hable con ella. No se sustituye `obtener_conexion` módulo por módulo: al sustituirlo se salta la instrumentación de `conexion.py` y las pruebas dejan de detectar fugas de conexión. Además `cargar_env()` usa `os.environ.setdefault`, así que lo que está en el entorno manda sobre el `.env`.

- **`base_de_prueba` va con `lock_wait_timeout = 5` antes del `DROP`.** Por defecto ese DROP espera **24 horas** si hay una sesión sin cerrar: una fuga de conexión convierte la batería de pruebas en un cuelgue sin pistas.
- `limpiar_tablas` va antes de `como_administrador`, no al revés: si la cuenta se creara antes de vaciar, el borrado se llevaría por delante al propio administrador.
- `datos_base` crea los datos como administrador y **restaura la sesión copiando los valores**, no la referencia. `obtener_sesion()` devuelve SIEMPRE el mismo objeto y `iniciar_sesion()` lo muta dentro: guardar la referencia para restaurarla guarda un espejo, y "restaurar" copia los valores nuevos.
- `sin_fugas_de_conexion` cuenta las sesiones abiertas sobre la base de prueba antes y después.

### Lo que las pruebas atrapan y la compilación no

- **Construir cada vista y cada formulario** en `QT_QPA_PLATFORM=offscreen` y navegar por las 11 secciones (11 admin, 6 vendedor). Es lo único que detecta un `NameError` de runtime, un import que sobra o un parámetro mal pasado. El `QWidget` sin importar en `contrato_form.py` solo apareció así.
- Parchear `QMessageBox.warning/information/question/critical` **y `QInputDialog.getItem/getText`** antes de construir nada: si no, un error inesperado **cuelga** la comprobación en vez de fallarla.
- `pytest -o faulthandler_timeout=10` vuelca el rastro cuando algo se queda esperando. Sin eso, un cuelgue no dice nada.
- **Una prueba no puede depender del orden.** `test_no_hay_usuarios_sembrados` se apoyaba en que *otra* prueba hubiera dejado una cuenta, y con la suite reordenada fallaba sin que hubiera pasado nada: se apoyaba en una casualidad, no en el código. Si una prueba necesita que exista algo, que lo pida como `fixture`.
- **Pide la fixture que necesitas, aunque hoy no la uses.** El mismo caso: `como_admin_un_rato` (gestor de contexto) es lo que permite comprobar que el vendedor *no* puede cobrar, pagando antes el cobro con la administración.
- **Construir una vista no es usarla.** Un método que llama a otro que ya no existe revienta al **pulsar**, no al abrir: `ver_venta()` estuvo roto porque le faltaba `buscar_venta()` y no se notó con 428 pruebas porque ninguna pulsaba nada. Hay pruebas que **llaman a los métodos de acción** con el índice de fila.
- **Los parches de diálogo tienen que ser fixtures, no `try/finally` dentro del método.** Si se restauran al terminar de construir la vista, la llamada siguiente vuelve a tener el `exec` de verdad y la prueba se queda colgada en un modal sin decir dónde. Se perdía una hora así, con `faulthandler_timeout` para encontrarlo.
- **`QMessageBox.question` tiene que devolver `Yes` para probar un `confirmar()`.** Parchearlo a ciegas a `Ok` es lo natural y hace que el formulario se calle: el cobro no se hace y parece que el botón está roto cuando lo que está roto es el parche. Y `_prepara_qt()` lo repone en cada llamada, así que el parche va **después**.
- **`leer_pdf(ruta)` (en `conftest.py`) devuelve el TEXTO de un PDF.** Comprobar que existe y pesa más de 500 bytes no dice nada de lo que lleva escrito: un recibo en blanco pasa esa comprobación. Deshace ASCII85 → Flate → escapes octalos, y por eso encuentra la `€` (`\200`) y no solo el `$`.
- **Las pruebas que miden tienen que aplicar `gui/estilo.css`.** Sin la hoja, `sizeHint()` mide con la fuente por defecto y con su relleno: `"Eliminar"` pide 110 en vez de 90. Y la hoja se pone **siempre**, no solo si no hay `QApplication`: si otro archivo la creó antes, el `if` la saltaba y las medidas dependían del **orden** de los archivos.

### Más comprobaciones puntuales

- **Medir la maqueta, no fiarse de la captura.** `grab()` sin pantalla duplica los widgets de celda y usa una fuente genérica más ancha que Segoe UI: aparenta que todo el texto se corta y no es cierto. Registra las fuentes del sistema y comprueba con `QFontMetrics`. Para que la captura salga limpia, espera un ciclo de eventos (`QEventLoop` + `QTimer.singleShot`).
- Para esperar a un `QTimer` hay que procesar eventos (`app.processEvents()` en bucle); `time.sleep` no los deja correr.
- Capturas sin pantalla: `widget.grab().save(ruta)` tras registrar fuentes con `QFontDatabase.addApplicationFont()`.

### Cuidado con las pruebas destructivas

`test_auditoria.py` llama a `vaciar_auditoria()` al empezar y en un `finally`. Las pruebas de contratos borran lo que crean capturando el id devuelto, **nunca "el último" ni "por posición"**. Una suite antigua que vivía fuera del repositorio incumplía esto y borró dos veces los contratos de demostración de la base real: por eso las pruebas están ahora dentro, con base propia.

## Conexiones: se cierran siempre

**Toda función de `database/` que abra conexión y escriba lleva `@conexiones_libres`** (de `database/conexion.py`), por encima de `@requiere_permiso`.

Sin eso, un INSERT que falla a mitad (una clave foránea, un UNIQUE, MySQL que se cae) saca la excepción **con la conexión abierta**. MySQL no la suelta: sigue sosteniendo la sesión en el servidor, ocupa una de las `max_connections` y, si la función había abierto una transacción, se lleva por delante los bloqueos de las filas que hubiera tocado. Con unos pocos fallos seguidos la aplicación deja de poder conectar y no hay forma de saber por qué mirando el mensaje de error.

El decorador no traga excepciones ni altera el valor devuelto: solo añade el cierre. Va por encima de `@requiere_permiso` para que también cubra el caso de que el permiso falle.

Las llamadas a `conexion.close()` que ya había dentro de la función se pueden dejar: cerrar dos veces no hace nada.

**Al añadir una función de escritura en `database/`, decorarlo no es opcional.**

## Los errores de MySQL se traducen, siempre

Un `INSERT` contra una columna UNIQUE revienta con `mysql.connector.IntegrityError`. Si eso sale de `database/`, el formulario (que solo recoge `ErrorSistema`) no lo entiende y **la aplicación revienta en vez de enseñar un mensaje**. La regla: dentro de la capa de datos se traduce con `traducir_error(error)` y se lanza con `raise ... from error`.

Ya está en `marcas.insertar_marca`, `marcas.actualizar_marca`, `usuarios.insertar_usuario` y `usuarios.actualizar_usuario`. Las columnas UNIQUE son `marcas.nombre`, `usuarios.nombre_usuario`, `contratos.numero` y `contratos.venta_id`.

## Huecos conocidos

Dejarlos escritos es mejor que olvidarlos:

- **La clave foránea de `ventas.cliente_id` y `ventas.auto_id` se llama `ventas_ibfk_1` y `ventas_ibfk_2` en las bases ya migradas**, no `ventas_cliente_fk` / `ventas_auto_fk` como en `esquema.sql`. No rompe nada (el nombre de una restricción es decorativo) pero desconcierta al comparar el esquema con una base en marcha. Renombrarla es un `ALTER TABLE ... RENAME CONSTRAINT` por cada una.
- **`crear_contrato` no registra el anticipo como pago.** Queda pendiente decidir quién lo hace: el formulario al firmar, o que el usuario lo registre a mano desde el detalle de la venta. Ahora mismo el saldo de una venta con anticipo aparece entero hasta que se mete el pago.

- **`crear_contrato` congela precio, cliente y vehículo, pero no la marca, el modelo, el año, el color ni el precio de lista.** Se leen en vivo con un JOIN, así que corregir el vehículo cambia el contrato ya firmado. **Resuelto**: `crear_contrato()` escribe la fotografía del vehículo al firmar. Los contratos ya existentes (CTR-2026-00088 y 00090) tienen esas columnas a NULL y muestran el dato actual con un aviso en el pie del detalle.
- **Los contratos anteriores a la financiación no tienen cronograma.** Los dos contratos de la base real (`CTR-2026-00088` y `CTR-2026-00090`) dicen "12 cuotas" con `saldo_financiado` en 0.00 y no tienen ni una fila en `cuotas`: se crearon antes de que existiera el módulo. `generar_cronograma()` los rechaza ("No hay saldo financiado"), que es lo correcto. Si hay que financiarlos de verdad, hay que rehacerlos desde la venta con `migracion_financiera.sql` ya aplicada.
- **La validación del anticipo y las cuotas vive en `contrato_form`, no en `crear_contrato`.** En la capa de datos solo están las tres guardas duras (forma de pago válida, anticipo no negativo, anticipo no mayor que el precio, y "Contado" sin anticipo ni cuotas), porque un contrato es un documento legal y no puede quedar guardado uno que imprimiría una cuota en negativo. El resto sigue dependiendo de que quien llame pase por el formulario. **Parcialmente resuelto**: `_validar_financiacion()` comprueba ahora también la periodicidad, la tasa negativa, la retención por encima del 100 % y el máximo de cuotas.
- **`insertar_usuario` exige `rol`.** Que las cuentas nuevas sean de vendedor es cosa del formulario, no un valor por defecto de la capa de datos.
- **`registrar_venta` devuelve el id de la venta en la primera posición de la tupla**, no `True`. Quien llama solo mira la veracidad.
- **`obtener_auditoria` devuelve 9 columnas: `id, fecha_hora, usuario_nombre, accion, modulo, descripcion, valor_anterior, valor_nuevo, referencia`.** El usuario va en el índice 2, no en el 4, y la descripción en el 5. `usuario_id` no se expone a propósito. **Léelas por índice, no desempaquetando**: `a, b, c, d, e, f = registro` revienta en cuanto cae una columna más, y revienta **al pintar la pantalla**, no en los datos. Pasó con `gui/auditoria_view.py`, que dejaba la aplicación sin arrancar.
- **`obtener_usuarios` no devuelve `password_hash`** (8 columnas: id, nombre_usuario, nombre_completo, rol, activo, ultimo_acceso, intentos_fallidos, bloqueado_hasta). Para comprobar el formato del hash hay que leer la fila cruda.
- **`hashear_contrasena` devuelve `(sal, hash)` en bytes**, no una cadena. Lo que se guarda es `sal.hex():hash.hex()`.
- **`registrar_pago_adelantado()` comprueba el saldo de la venta antes de abrir la transacción, no dentro.** `registrar_pago()` lo hace con la venta bloqueada (`FOR UPDATE`), que es mejor; aquí hace falta **una sola** transacción para las N imputaciones, y anidar transacciones en la misma conexión no es transaccional en MySQL: un `START TRANSACTION` anula el anterior de forma silenciosa. Se acepta la ventana porque las cuotas van con `FOR UPDATE` en el mismo `SELECT`: si otro cobra a la vez, su `UPDATE` espera al lock. Aun así, la comprobación del saldo de la venta es la única que no está dentro de su propio bloqueo.
- **`PagoAdelantadoForm` no tiene atajo de teclado para cobrar.** `conectar_enter_guardar()` está puesto en el concepto y el recibo, que son de texto. El importe va en `QDoubleSpinBox`, donde `Return` se lo queda el propio control, y es lo correcto: escribir "30000" y dar `Enter` sin querer pondría el importe de otro cobro.
- **La tabla de antigüedad no lleva botones** y se construye sin `columna_acciones`. Antes pasaba `-1`, que `crear_tabla()` ignoraba en silencio.

## El PDF

Hay dos: `utils/contrato_pdf.py` y `utils/recibo_pdf.py`. Los dos con **Platypus** (reportlab), en flujo, y **comparten los helpers de texto**: `escapar()` y `sustituir_no_mapeables()` se importan del del contrato. Una copia sería una copia que algún día se queda vieja sin que nadie lo note.

- El **recibo va en A5**, no en A4: un recibo grande no cabe en un cajero y se doblega de una manera que acaba con la cantidad dentro. Va el **importe en letras** (hasta el millón, con los céntimos como "/100", que se lee igual con cualquier separador de miles configurado), qué **cuota cubre**, y el saldo de ESA cuota.
- **El recibo NO lleva el saldo total del contrato.** Un recibo de 500.000 con un "saldo pendiente: 4.200.000" al lado se lee como una afirmación sobre la deuda entera, y el saldo es una foto de hoy. Este documento resuelve **las cuotas que lista**.
- `generar_recibo(pagos, contrato, cuotas=None)` recibe **una LISTA** de pagos y la lista de cuotas **en el mismo orden**. Un cobro adelantado son N pagos con el MISMO número de recibo y el cliente se lleva UN papel: con un solo `pago` por parámetro habría que imprimir N recibos de un solo acto, o peor, elegir uno y dejar los demás sin papel («su recibo es de 10.000» de un total de 30.000). Un cobro de una cuota es una lista de uno. Se acepta también un `dict` suelto por comodidad, y se normaliza dentro.
- `generar_recibo()` **no acepta `ruta`**: el nombre del archivo lo decide el número de recibo, que es único. Pedirle a quien llama que invente una ruta solo abriría la puerta a sobrescribir el recibo de otro cobro.
- `ContratoDetalleDialog.agrupar_por_recibo()` es la que agrupa: **por recibo, no por pago**. Si se eligiera por pago aparecerían N líneas con el mismo número y habría que elegir «cuál de estos cinco», cuando el cliente compró uno.
- **`generar_contrato()` va DESPUÉS de `generar_cronograma()`** en el flujo de alta: el PDF imprime el cronograma y necesita leer las cuotas. Al revés sale un contrato con las condiciones y sin la tabla de vencimientos, que es media información para el cliente.

`utils/contrato_pdf.py` maqueta el contrato. Se compone en flujo: cada bloque mide su alto, el texto se ajusta solo al ancho de su columna y salta de página sin partir nada a la mitad. Con esto ya no se calculan posiciones ni anchos de glifo a mano.

- **La banda de la cabecera y el pie se dibujan en `onPage`, no en el flujo.** Son decoración: si fueran flowables ocuparían hueco en el marco y se podrían partir. `_pintar_hoja` se llama una vez por hoja. Para leer los datos del contrato, `construir_documento` los cuelga en `documento.contrato`: reportlab no se los pasa a la función de página.
- **Un `Table` necesita un ancho por celda, no por par.** Si se dan menos de los que hay celdas, reportlab calcula el último por su cuenta, la fila se pasa de ancha y la tabla se centra saliendose por la izquierda. Pasa en `bloque_total`, que tiene 2 celdas sin cuotas y 3 con ellas.
- **Escapa SIEMPRE el texto que va en un `Paragraph`.** `Paragraph` lee `<b>`, `<i>` y `&` como marcado: un precio con `<` o un "&" en una observación rompe el párrafo. `escapar()` los neutraliza siempre, no solo cuando "parece" que haga falta.
- **reportlab sustituye en silencio lo que la fuente no sabe dibujar**, por el glifo `.notdef` de Helvetica, que es una "n": un emoji pegado en unas observaciones salía como "nn", que parece una palabra y no un signo ilegible. `sustituir_no_mapeables()` cambia por "?" lo que no se puede convertir a `cp1252`, que es lo que hay detrás de `WinAnsiEncoding`. Con eso la "€" (0x80 en WinAnsi) se conserva y sale bien; los emoji y el chino salen como "?".
- Los estilos se construyen en `construir_estilos()`, no como constantes de módulo: `getSampleStyleSheet()` toca el registro global de reportlab y llamarlo al importar modificaría el proceso aunque nadie genere un PDF.
- Las fuentes base-14 (Helvetica) no hay que incrustarlas. reportlab les pone `/WinAnsiEncoding`, que ya cubre tildes, ñ, «», · y €.
- **Para comprobar un PDF no vale un volcado a pelo:** reportlab codifica las páginas con ASCII85 y luego Flate, y además coloca cada bloque con `cm`. Hay que descomprimir (en ese orden) y sumar las traslaciones para saber dónde cae cada texto. Tres trampas más, todas las pisadas alguna vez:
  - Al descomprimir hay que **quitar el `~>`** del final del bloque ASCII85 antes de `a85decode`, o falla con `Non-Ascii85 digit found: ~`.
  - **El símbolo de la moneda no se busca como carácter en el flujo de texto.** Con las fuentes base-14, reportlab codifica en WinAnsi: el `$` es ASCII y sale tal cual, pero la `€` sale como el escape octal `\200`. Buscar `chr(0x20AC)` en un texto latin-1 no la encuentra nunca, y buscar el byte `0x80` en el **archivo** tampoco, porque el contenido va comprimido. Hay que buscar `b"\200"` en el flujo ya descomprimido. Y el tamaño del PDF no dice nada: `$ 52,000.00` y `52.000,00 €` ocupan los mismos once caracteres.
- `KeepTogether` en el bloque de condiciones y en el de firmas: si no caben enteros pasan a la página siguiente en vez de quedar partidos.
