# Concesionario Automotor

Sistema de gestión para un concesionario de
automóviles, de escritorio, en Python.

- **Interfaz:** PySide6 (Qt)
- **Base de datos:** MySQL
- **Acceso:** usuarios con roles y contraseña
  cifrada
- **Rastro:** auditoría de las acciones
  importantes

---

## Índice

1. [Requisitos](#1-requisitos)
2. [Instalación](#2-instalación-paso-a-paso)
3. [Uso](#3-uso)
   - [Contratos de compraventa](#contratos-de-compraventa)
   - [Pagos y saldo](#pagos-y-saldo)
   - [La moneda](#la-moneda)
4. [Estructura del proyecto](#4-estructura-del-proyecto)
5. [Roles y permisos](#5-roles-y-permisos)
6. [Problemas frecuentes](#6-problemas-frecuentes)
7. [Para desarrolladores](#7-para-desarrolladores)

---

## 1. Requisitos

| | |
|---|---|
| **Sistema** | Windows 10/11, macOS o Linux |
| **Python** | 3.10 o superior (probado en 3.13) |
| **MySQL** | 8.0 o superior, o MariaDB 10.5+ |
| **Espacio** | ~500 MB (la mitad es PySide6) |
| **RAM** | 2 GB libre |

MySQL debe estar **encendido** antes de abrir la
aplicación.

---

## 2. Instalación (paso a paso)

Los pasos van del 1 al 8. Si algo falla,
`verificar_instalacion.py` (paso 8) dice en cuál.

### 1. Instalar Python

Descárgalo de <https://www.python.org/downloads/>

**Importante en Windows:** marca la casilla
*Add Python to PATH* durante la instalación.

Comprueba que funciona:

```bash
python --version
```

### 2. Crear el entorno virtual

Sitúate en la carpeta del proyecto y ejecuta:

```bash
python -m venv venv
```

El entorno virtual guarda las dependencias del
proyecto aparte de las del sistema, para que no
se mezclen con otros programas de Python.

### 3. Instalar las dependencias

**Windows:**

```bat
venv\Scripts\activate
pip install -r requirements.txt
```

**macOS o Linux:**

```bash
source venv/bin/activate
pip install -r requirements.txt
```

Instala tres paquetes:

| Paquete | Para qué |
|---|---|
| `PySide6` | La interfaz |
| `mysql-connector-python` | La conexión a MySQL |
| `reportlab` | El PDF de los contratos |

`reportlab` se trae consigo `pillow`, que se
instala solo.

### 4. Configurar el `.env`

Las credenciales **no van en el código**. Crea
tu copia del archivo de ejemplo:

**Windows:**

```bat
copy .env.example .env
```

**macOS o Linux:**

```bash
cp .env.example .env
```

Abre `.env` con un editor de texto y rellénalo:

```ini
DB_HOST=localhost
DB_PORT=3306
DB_USER=root
DB_PASSWORD=aquí_tu_contraseña
DB_NAME=concesionario
```

> `.env` está en `.gitignore`: no se sube al
> repositorio nunca. Cada equipo tiene el suyo.

### 5. Crear la base de datos

Abre **MySQL Workbench** (o una consola de MySQL)
y crea la base vacía:

```sql
CREATE DATABASE concesionario
    CHARACTER SET utf8mb4
    COLLATE utf8mb4_0900_ai_ci;
```

Si la tienes en un servidor remoto, no hace
falta este paso: ejecuta el siguiente directamente.

### 6. Cargar el esquema

Desde Workbench: **File → Open SQL Script →
`database/esquema.sql`** y pulsa la flecha verde.

Desde la consola:

```bash
mysql -u root -p < database/esquema.sql
```

Crea las 7 tablas (`marcas`, `autos`, `clientes`,
`ventas`, `usuarios`, `configuracion`, `auditoria`)
y carga 10 marcas de ejemplo.

> **Cuidado:** el script empieza con
> `DROP DATABASE concessionario`. Está pensado
> para empezar de cero. **No lo ejecutes sobre
> una base con datos reales**, o los perderás.

### 7. Crear el administrador inicial

```bash
venv\Scripts\python.exe crear_admin.py
```

Te pedirá nombre de usuario, nombre completo y
contraseña (no se escribe en pantalla).

Solo funciona si no hay ningún administrador
activo. Las cuentas siguientes se crean desde
dentro de la aplicación, en **Usuarios**.

### 8. Comprobar y arrancar

Comprueba la instalación:

```bash
venv\Scripts\python.exe verificar_instalacion.py
```

Recorre los 8 pasos y dice en cuáles hay
problemas y cómo arreglarlos.

Si todo sale correcto:

```bash
venv\Scripts\python.exe main.py
```

Aparece la pantalla de acceso. Entra con las
credenciales del paso 7.

---

## 3. Uso

### Pantalla de acceso

Es el primer sitio que aparece. Sin credenciales
válidas no se abre el sistema.

Tras 5 intentos fallidos la cuenta se bloquea
15 minutos.

### Secciones

| Sección | Para qué |
|---|---|
| **Inicio** | Panel con cifras del negocio |
| **Vehículos** | Alta, edición, búsqueda y stock |
| **Marcas** | Catálogo de marcas |
| **Clientes** | Ficha de clientes |
| **Ventas** | Registrar y consultar ventas |
| **Contratos** | Contratos de compraventa y su PDF |
| **Reportes** | Informes con filtros y CSV |
| **Usuarios** | Cuentas y roles (solo admin) |
| **Auditoría** | Historial de acciones (solo admin) |
| **Configuración** | Ajustes y diagnóstico |

### Contratos de compraventa

El contrato documenta una venta ya registrada. No
se crea desde cero: nace siempre de una venta,
porque hereda de ella el cliente, el vehículo, el
precio y la fecha.

Hay tres formas de llegar al mismo sitio:

1. Al registrar una venta, el sistema pregunta si
   quieres crear el contrato ahora.
2. En **Ventas**, cada fila tiene un botón
   **Contrato**.
3. En **Contratos**, el botón **+ Nuevo contrato**
   lista las ventas que todavía no lo tienen.

El número es único y se forma con el año y el id
del propio contrato: `CTR-2026-00001`.

**Una venta solo admite un contrato.** Para
rehacerlo se cancela el anterior (un contrato
cancelado no surte efecto pero queda registrado) y
se crea uno nuevo desde la misma venta.

Estados y transiciones:

| Desde | Puede pasar a |
|---|---|
| Borrador | Activo, Cancelado |
| Activo | Finalizado, Cancelado |
| Finalizado | Cancelado |
| Cancelado | Activo |

Al confirmar, el PDF se genera solo y se guarda en
`documentos/contratos/`. Desde el listado se puede
volver a abrir con el botón **PDF**.

### Pagos y saldo

Cada venta tiene un saldo. Se llega desde **Ventas**,
con el botón **Ver** de la fila: ahí se ve el precio,
lo cobrado, lo pendiente y la lista de pagos, con su
botón **Registrar pago**.

Un pago es un hecho económico, así que **no se
edita**: si está mal, el administrador lo borra desde
el mismo diálogo y se vuelve a registrar. Queda
constancia en la auditoría.

La diferencia entre contrato y pago:

- El **contrato** dice *qué* se debe pagar (precio,
  anticipo, número de cuotas).
- El **pago** dice *qué* se ha cobrado, uno a uno.

Por eso el anticipo del contrato **no** descuenta
saldo hasta que se registra como pago: si lo hiciera
por su cuenta, el saldo cuadraría con una entrada
que nadie vería en la lista de cobros ni podría
explicar en un extracto bancario.

Cuando la venta queda saldada, el botón de registrar
pago se desactiva solo.

Una venta con dinero cobrado **no se puede anular**.
Primero hay que deshacer el pago.

El importe tiene que ser **exacto a céntimos**. La
columna guarda dos decimales, así que un pago de
0.004 se redondearía a 0.00 y el dinero se perdería
sin avisar; en vez de tragarse el redondeo, la
aplicación lo rechaza y avisa. El formulario ya
solo deja escribir dos decimales.

### La moneda

La moneda se cambia en **Configuración → Ajustes**,
sin tocar el código y sin reiniciar. Se guarda en la
base, así que es la misma para todo el que use el
programa.

Hay cinco ajustes:

| Ajuste | Por defecto | Para qué |
|---|---|---|
| Código | `USD` | código ISO de la moneda |
| Símbolo | `$` | lo que se ve junto al importe |
| Formato | `simbolo_espacio` | cómo se juntan símbolo e importe |
| Separador de miles | `,` | `1,500.00` o `1.500,00` |
| Separador de decimales | `.` | `1,500.00` o `1.500,00` |

Los formatos admitidos, con `1234.50` como ejemplo:

| Formato | Resultado |
|---|---|
| `simbolo_espacio` | `$ 1,234.50` |
| `simbolo_pegado` | `$1,234.50` |
| `simbolo_despues` | `1,234.50 $` |
| `codigo_espacio` | `USD 1,234.50` |
| `codigo_pegado` | `USD1,234.50` |
| `codigo_despues` | `1,234.50 USD` |

**Para facturar en euros**: código `EUR`, símbolo
`€`, formato `simbolo_despues` (lo normal en
Europa), separador de miles `.` y de decimales `,`.
Sale `1.234,50 €`.

Mientras escribes, el panel enseña cómo quedaría,
sin guardar. El separador de miles y el de decimales
**no pueden ser el mismo**: `1.234.56` y `1.234,56`
se leerían igual.

El cambio afecta a todas partes a la vez: los
listados, el detalle de una venta, los contratos, el
PDF y los reportes. Las tablas de los listados no
llevan símbolo (no lo han llevado nunca), pero sí
siguen los separadores.

> Si tienes una base que ya estaba funcionando, la
> moneda se pone por su cuenta al leer los ajustes:
> aunque no existan esas cinco claves, la aplicación
> usa los valores por defecto, que son exactamente
> los de siempre. Si quieres verlas y poder
> cambiarlas, aplica `database/migracion_moneda.sql`.

### Atajos de teclado

| Tecla | Dónde | Qué hace |
|---|---|---|
| `Enter` | Formularios | Guardar |
| `Escape` | Formularios | Cerrar sin guardar |
| `Enter` | Buscadores | Buscar al momento |
| — | Buscadores | Filtra solo al dejar de escribir |

---

## 4. Estructura del proyecto

```
concesionario/
├── main.py                     Arranque: login -> aplicación
├── crear_admin.py              Administrador inicial
├── verificar_instalacion.py    Diagnóstico de la instalación
├── requirements.txt            Dependencias
├── pytest.ini                  Configuración de las pruebas
├── .env.example                Plantilla de configuración
│
├── sesion.py                   Usuario en sesión
├── permisos.py                 Permisos por rol
├── errores.py                  Errores controlados
│
├── tests/                      Pruebas automáticas (pytest)
│   ├── conftest.py             Base de prueba y fixtures
│   ├── test_marcas.py          test_clientes.py
│   ├── test_autos.py           test_ventas.py
│   ├── test_contratos.py       test_usuarios.py
│   ├── test_pagos.py           test_reportes.py
│
├── database/                   Acceso a datos (todo el SQL aquí)
│   ├── conexion.py             Lee el .env y abre conexiones
│   ├── esquema.sql             Estructura completa
│   ├── marcas.py               autos.py
│   ├── clientes.py             ventas.py
│   ├── usuarios.py             auditoria.py
│   ├── contratos.py            Contratos de compraventa
│   ├── pagos.py                Cobros y saldo de cada venta
│   ├── configuracion.py        Ajustes
│   ├── migracion_contratos.sql Para bases ya existentes
│   ├── migracion_indices.sql   Índices y marcas únicas
│   ├── migracion_ventas_usuario.sql  Quién registró cada venta
│   ├── migracion_pagos.sql     Tabla de pagos
│   ├── migracion_moneda.sql    Claves de moneda configurable
│   └── reportes.py             Estadísticas y agregados
│
├── gui/                        Interfaz
│   ├── ventana_principal.py    Ventana y navegación
│   ├── login_view.py           Acceso
│   ├── vista_base.py           Base: manejo de errores
│   ├── vista_listado.py        Base: listados con búsqueda
│   ├── diagnostico.py          Comprobaciones
│   ├── dashboard_view.py       Panel
│   ├── autos_view.py           marcas_view.py
│   ├── clientes_view.py        ventas_view.py
│   ├── usuarios_view.py        auditoria_view.py
│   ├── contratos_view.py       contratos_view.py
│   ├── reportes_view.py        configuracion_view.py
│   ├── estilo.css              Apariencia
│   └── formularios/            Formularios de alta y edición
│
├── documentos/contratos/       PDF generados (se crea sola)
│
└── utils/                      Utilidades
    ├── validaciones.py         Reglas de validación
    ├── helpers.py              Componentes reutilizables
    ├── seguridad.py            Cifrado de contraseñas
    ├── contrato_pdf.py         Maquetación del contrato (Platypus)
    └── registro.py             Registro de errores
```

Las dependencias van siempre hacia abajo:

```
GUI  ->  database/  ->  conexion.py  ->  MySQL
```

**El SQL solo existe en `database/`.** Las
vistas nunca escriben consultas.

---

## 5. Roles y permisos

| | Administrador | Vendedor |
|---|:---:|:---:|
| Consultar vehículos, marcas, clientes, ventas | Sí | Sí |
| Registrar ventas | Sí | Sí |
| Crear y editar vehículos, marcas, clientes | Sí | **No** |
| Eliminar cualquier registro | Sí | **No** |
| Anular ventas | Sí | **No** |
| Consultar y **crear** contratos | Sí | Sí |
| Cancelar o eliminar contratos | Sí | **No** |
| Reportes | Sí | **No** |
| Usuarios | Sí | **No** |
| Auditoría | Sí | **No** |
| Configuración | Sí | **No** |

El vendedor crea contratos porque son parte de
la venta, pero no los cancela ni los borra: eso es
de la administración.

Ocultar un botón no es la protección: cada
operación de escritura comprueba el permiso en
la capa de datos y **registra el intento** en la
auditoría.

### Sobre las contraseñas

Se guardan cifradas con **PBKDF2-HMAC-SHA256**,
260 000 iteraciones y una sal distinta por
usuario. La contraseña en claro:

- no se guarda
- no se escribe en el registro
- no se puede recuperar

Si se olvida, un administrador la restablece
desde **Usuarios → Editar**.

---

## 6. Problemas frecuentes

### "No se pudo conectar con MySQL"

1. ¿Está MySQL encendido?
2. ¿`.env` existe? (`verificar_instalacion.py` lo comprueba)
3. ¿La contraseña es correcta?

### "Access denied for user"

Usuario o contraseña incorrectos en `.env`.

### "La base de datos no existe" o "falta la tabla"

Se ejecutó `esquema.sql` a medias. Vuelve a
ejecutarlo **sobre una base vacía**.

### Ya tenía datos y quiero añadir los contratos

`esquema.sql` empieza con `DROP DATABASE`: **no lo
ejecutes sobre una base con datos**, se los
borra. Usa la migración, que solo añade:

```bash
mysql -u root -p concesionario < database/migracion_contratos.sql
```

O en MySQL Workbench: *File → Open SQL Script* →
el archivo → clic en la flecha.

Qué hace, exactamente:

- añade la tabla `contratos`
- añade la columna opcional `documento` a
  `clientes` (los clientes que ya existían se
  quedan con `NULL` y el PDF pone "No
  registrado")

No borra ni modifica ninguna fila.

### Ya tenía datos y quiero los índices

La aplicación nueva lleva tres cosas que una
base creada antes no tiene:

- un índice en `ventas.fecha` (los reportes
  filtran por rango de fechas)
- un índice en `contratos.fecha`
- `marcas.nombre` no puede repetirse

```bash
mysql -u root -p concesionario < database/migracion_indices.sql
```

**Antes de aplicarlo, comprueba que no tengas
marcas repetidas**, porque el UNIQUE las
rechazaría. El archivo lleva la consulta:

```sql
SELECT nombre, COUNT(*) c
FROM marcas
GROUP BY LOWER(TRIM(nombre))
HAVING c > 1;
```

Si no devuelve nada, puedes seguir. Si devuelve
algo, renombra o fusiona esas marcas desde la
aplicación primero.

También aquí: ni una fila se toca.

### El PDF del contrato no sale

Mira `documentos/contratos/` dentro del proyecto.
Si el contrato existe pero el archivo no,
vuelve a pulsarlo con **PDF** en el listado: se
vuelve a generar.

Si el directorio no se puede escribir, el
contrato se guarda igual y el aviso explica por
qué no se pudo escribir el archivo.

### "No hay ningún usuario creado"

Falta el paso 7:

```bash
venv\Scripts\python.exe crear_admin.py
```

### La ventana se abre sin estilos

Falta `gui/estilo.css`. Se lee con ruta
relativa: hay que arrancar **desde la raíz del
proyecto**.

```bash
cd ruta\al\proyecto
venv\Scripts\python.exe main.py
```

### La cuenta quedó bloqueada

Tras 5 intentos fallidos se bloquea 15 minutos.
Un administrador la desbloquea desde
**Usuarios → Editar**.

### Los acentos o los emojis se ven como cajas

Falta una fuente en el sistema. En Windows con
Segoe UI debería verse bien.

### Empezar de cero

```sql
DROP DATABASE concesionario;
```

Luego repite los pasos 6 y 7.

---

## 7. Para desarrolladores

`AGENTS.md` recoge las convenciones del
proyecto: dónde vive cada cosa, qué contratos no
se pueden romper y qué errores se han cometido
ya. **Léelo antes de tocar nada.**

Y ejecuta `verificar_instalacion.py` antes de
suponer que el entorno está bien: avisa de
problemas que a simple vista no se ven.

### Pruebas

Hay una batería con [pytest](https://docs.pytest.org/)
en `tests/`:

```
venv\Scripts\python.exe -m pytest
```

Son 255 pruebas. **No tocan tus datos**: cada
sesión levanta una base temporal llamada
`pruebas_concesionario` a partir de
`database/esquema.sql` —es decir, una
instalación limpia hecha de cero—, fija
`DB_NAME` en el entorno para que toda la
aplicación hable con ella y la borra al
terminar. Puedes trabajar con la base real
mientras corren.

Si algo se queda esperando, añade
`-o faulthandler_timeout=10` para ver dónde:
sin eso, un cuelgue no dice absolutamente nada.

Para añadir una dependencia solo de las
pruebas, instálala sin tocar `requirements.txt`:

```
venv\Scripts\python.exe -m pip install pytest
```

`pytest` no hace falta para usar la aplicación,
solo para tocarla.

### Lo que las pruebas no detectan

Compilar no encuentra un nombre mal escrito
dentro de un método: solo falla al construir el
widget. Si añades una vista o un formulario,
**constrúyelo** antes de darlo por bueno. La
comprobación completa está en `AGENTS.md`, en
"Verificación".
