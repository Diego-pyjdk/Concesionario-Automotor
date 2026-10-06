# Actualización incluida

Consulta `INSTRUCCIONES_ACTUALIZACION.md` antes de ejecutar SQL.

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
   - [Ventas financiadas](#ventas-financiadas)
   - [Cobrar varios meses de una vez](#cobrar-varios-meses-de-una-vez)
   - [Cartera y cobranza](#cartera-y-cobranza)
   - [Garantías](#garantías)
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
| **Cartera** | Quién debe, cuánto y desde cuándo (solo admin) |
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

### Ventas financiadas

El contrato puede financiarse. En la pestaña
**Financiación y cronograma** del formulario se
indica el saldo a financiar, cada cuánto vence,
cuándo vence la primera, el interés anual, los gastos
de administración y la retención.

**El cronograma se ve antes de firmar**, con las
fechas y los importes de verdad. No es un adorno: las
condiciones quedan congeladas en el contrato y un
cronograma ya firmado no se puede cambiar, así que
firmar a ciegas 72 vencimientos es pedir un problema
en el mes seis. La **última cuota** lleva un céntimo
distinto para que la suma cuadre exactamente con el
saldo financiado.

Al confirmar, las cuotas se generan y el PDF sale con
la tabla de vencimientos.

Para **cobrar** se entra en el detalle del contrato
(**Ver** desde el botón *Contrato* de la venta, o el
botón de la fila en **Contratos**), o directamente
desde **Cartera**. El detalle tiene cuatro pestañas:
cronograma, pagos, garantías e historial, con los
datos del contrato fijos arriba.

- El formulario de cobro propone **el saldo entero**,
  que es lo que se cobra casi siempre, y no deja
  escribir más que ese saldo.
- Cada cobro genera su **recibo en PDF**, en
  `documentos/recibos/`, con el número arriba, el
  importe en letras y a qué cuota se imputa.
- Un cobro **no se borra: se anula**, con su motivo y
  su rastro, y el importe vuelve a la cuota.

#### Cobrar varios meses de una vez

Un cliente que paga dos meses seguidos es lo normal. El
botón **Adelantado** (en **Cartera** y en el detalle
del contrato) abre un formulario que **enseña el reparto
antes de cobrar**:

```
Importe recibido:  20.000,00        [+ Una cuota] [Todo lo pendiente]

Así se va a repartir:
  Nº   Vencimiento   Importe        Saldo
   1   05/11/2026    $ 10.000,00    $ 0,00
   2   05/12/2026    $ 10.000,00    $ 0,00

2 cuota(s) quedan saldadas
```

Las cuotas se cubren **enteras**, de la más antigua a la
más reciente, y el importe que no quepa se avisa en vez
de repartirse. El dinero nunca se guarda "suelto": sale
un pago por cuota, **con el mismo número de recibo**, y
el recibo en PDF sale con una tabla del reparto. Todo
ocurre en una sola transacción: o entra entero o no
entra nada.

Si el cliente entrega de más, ese excedente **no se
imputa** a ninguna cuota: se registra aparte como otro
cobro.

**Las cuotas vencidas se detectan solas.** No hay
ningún proceso de fondo: una cuota vencida es un estado
derivado de la fecha, y se revisa al abrir la cartera.
Pagar una cuota vencida la saca de esa lista.

Los pagos y las cuotas **no se editan**, ni siquiera
por la administración. Un pago mal registrado se anula
y se vuelve a registrar; una cuota con pagos tampoco se
anula, porque el saldo del contrato dejaría de cuadrar.

### Cartera y cobranza

La sección **Cartera** es solo del administrador. Es
la lista de a quién se le llama, por cuánto y desde
cuándo, con el teléfono al lado. Un vendedor **no la
ve**: ver sus propios contratos sí puede, desde
**Contratos**.

Cuatro pestañas:

| Pestaña | Qué es |
|---|---|
| **Por cobrar** | Todos los contratos con saldo, **ordenados por retraso** y no por importe |
| **Vencidas** | Las cuotas que ya pasaron su fecha y siguen con saldo |
| **Por vencer** | Las que vencen en los próximos días (el aviso se ajusta aquí) |
| **Antigüedad** | La cartera por tramos de retraso, y qué deudores la concentran |

Se ordena por retraso y no por importe a propósito: un
cliente que debe 80.000 y va 40 días atrasado no puede
quedar detrás de uno que debe 3.000 y no ha pagado
nunca. La urgencia la marca el retraso.

Desde la cartera se cobra. Cada fila tiene tres botones:
**Adelantado** (varios meses de una vez), **Cobrar** (la
cuota más antigua) y **Ver** (el detalle del contrato).

### Garantías

Un contrato financiado puede llevar garantías: prenda,
fijación, aval, un garante tercero, un seguro. Se
registran desde la pestaña **Garantías** del detalle.

**Un gravamen es una inscripción registral, y el
programa no tramita inscripciones.** Lo que se guarda
aquí es lo que el concesionario **afirma**; la forma de
la inscripción, sus datos y su eficacia hay que
verificarlos con un abogado y con el escribano. Por eso
el aviso sale siempre, tenga garantías o no.

Lo mismo con la **retención** y la **mora**: se guardan
como datos pactados y la aplicación **no calcula
ninguna obligación fiscal**. Antes de firmar un
contrato financiado, revisa el porcentaje con un asesor
fiscal.

Liberar una garantía solo se permite con **saldo
pendiente cero** y es del administrador: liberar es
devolverle al cliente su respaldo.

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

Hay dos, y se elige una en **Configuración →
Ajustes**: un desplegable, sin escribir nada.

| Moneda | Cómo se ven los importes |
|---|---|
| **Guaraní paraguayo** (PYG) | `Gs. 1.500` — sin decimales, punto de miles |
| **Dólar estadounidense** (USD) | `$ 1,500.00` — dos decimales, coma de miles |

Ejemplos de cada una:

| Importe | Guaraní | Dólar |
|---|---|---|
| 1.500 | `Gs. 1.500` | `$ 1,500.00` |
| 150.000 | `Gs. 150.000` | `$ 150,000.00` |
| 1.500.000 | `Gs. 1.500.000` | `$ 1,500,000.00` |
| 150.000.000 | `Gs. 150.000.000` | `$ 150,000,000.00` |
| 2.500.000.000 | `Gs. 2.500.000.000` | `$ 2,500,000,000.00` |

#### El guaraní no lleva decimales

Porque **no tiene subunitario**: no hay moneda
fraccionaria que circule y los precios se escriben en
números enteros. `Gs. 1.500,00` inventaría una
precisión que no existe, y un cajero quecompare
`Gs. 1.500,00` con `Gs. 1.500` tendría dos cifras
distintas para lo mismo.

El importe se guarda igual en la base con dos
decimales; lo que no lleva decimales es **la forma de
enseñarlo**. Si alguien escribe 1.500,50 en
guaraníes, se guarda y se muestra como `Gs. 1.501`.

#### El símbolo es `Gs.` y no `₲`

El símbolo oficial del guaraní es `₲` (U+20B2), y no
se usa aquí por dos razones:

- Las fuentes de los PDF (Helvetica) **no lo
  tienen**. Los contratos saldrían con un `?` donde
  debería estar el símbolo, y un contrato con
  interrogaciones en el importe no es un documento que
  se pueda defender.
- `₲` no está en `cp1252`, que es lo que hay detrás de
  la codificación que usa reportlab. Habría que
  incrustar una fuente entera para un signo.

`Gs.` es como se escribe de todas formas en un
documento de este país.

#### Elegir UNA moneda, no cinco caracteres

El desplegable elige la moneda entera: símbolo,
formato, separadores y decimales salen de una tabla
del programa (`utils/moneda.py`) y no se escriben a
mano.

Antes había cinco campos —un código, un símbolo y
tres desplegables— y se podían combinar en cosas que
**no son monedas**: guaraníes con dos decimales, o
dólares con el punto de miles. Nada de eso daba un
error al guardarlo: salía un importe que no se puede
leer, y se descubría leyendo un contrato. Con el
desplegable no se puede.

Mientras eliges, el panel enseña cómo quedarían
varios importes de verdad (un vehículo, un cobro, una
venta grande), sin guardar nada.

#### Cambiar la moneda NO convierte importes

> **No hay tipo de cambio en ninguna parte del
> programa, y no se calcula ninguno.**

Cambiar el ajuste cambia **cómo se muestran** los
importes. No toca ni un valor de ventas, contratos,
cuotas ni pagos. Un `Gs. 25.000` que en realidad son
25.000 dólares sería peor que un importe sin moneda:
parece un dato y es mentira.

Por eso **cada venta y cada contrato guardan la
moneda con la que se hicieron** (`ventas.moneda` y
`contratos.moneda`). Un contrato firmado en dólares se
sigue enseñando y **se sigue imprimiendo en dólares**
aunque el concesionario pase a guaraníes dentro de seis
meses. Un documento firmado que al reimprimirse dice
otra moneda no sirve para nada.

Cuando el administrador cambia el ajuste, la
aplicación avisa de esto en la misma pantalla.

#### Los importes grandes

Las columnas de dinero son `DECIMAL(15, 2)`: **13
cifras enteras**, hasta 9.999.999.999.999,99. Antes
eran `DECIMAL(10, 2)`, cuyo techo son 99.999.999,99, y
en guaraníes eso no daba ni para un vehículo normal.

Los campos de escritura llegan hasta ese mismo tope, y
no lo recortan: se puede escribir 250.000.000 y se
guarda 250.000.000. Con el tope anterior, el campo
**recortaba el precio en silencio** y el usuario veía
una cifra que no era la que había escrito.

El paso de la flechita del campo también cambia: en
guaraníes salta de 100.000 en 100.000, porque con un
salto de 100 hay que pulsarla cientos de veces para
llegar de un millón al siguiente.

> Si tienes una base que ya estaba funcionando, aplica
> `database/migracion_monedas.sql`. Amplía las columnas
> de dinero (sin tocar ni un valor), añade
> `ventas.moneda` y siembra la clave de los decimales.
> Se puede aplicar dos veces sin miedo.

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
│   ├── test_financiera.py      Cronogramas, cuotas, cobros
│   ├── test_cobranza.py        Cartera, vencidas, garantías
│   └── test_cartera.py         Pantallas de la financiera
│
├── database/                   Acceso a datos (todo el SQL aquí)
│   ├── conexion.py             Lee el .env y abre conexiones
│   ├── esquema.sql             Estructura completa (12 tablas)
│   ├── marcas.py               autos.py
│   ├── clientes.py             ventas.py
│   ├── usuarios.py             auditoria.py
│   ├── contratos.py            Contratos de compraventa
│   ├── pagos.py                Cobros y saldo de cada venta
│   ├── financiera.py           Cronogramas, cuotas y su estado
│   ├── cobranza.py             Cuentas por cobrar y vencidas
│   ├── garantias.py            Garantías y gravámenes
│   ├── configuracion.py        Ajustes
│   ├── migracion_contratos.sql Para bases ya existentes
│   ├── migracion_indices.sql   Índices y marcas únicas
│   ├── migracion_ventas_usuario.sql  Quién registró cada venta
│   ├── migracion_pagos.sql     Tabla de pagos
│   ├── migracion_moneda.sql    Moneda por venta, importes grandes
│   ├── migracion_financiera.sql    Cuotas, garantías y ajustes
│   ├── migracion_auditoria_cambios.sql  Valor anterior y nuevo
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
│   ├── contratos_view.py       detalle_venta_dialog.py
│   ├── cartera_view.py         Cartera y cobranza
│   ├── contrato_detalle_dialog.py  Cronograma, pagos, garantías
│   ├── reportes_view.py        configuracion_view.py
│   ├── estilo.css              Apariencia
│   └── formularios/            Formularios de alta y edición
│       ├── pago_cuota_form.py    Cobro de una cuota
│       ├── pago_adelantado_form.py  Cobro de varias cuotas
│       └── garantia_form.py      Garantías y su inscripción
│
├── documentos/contratos/       PDF generados (se crea sola)
│
└── utils/                      Utilidades
    ├── validaciones.py         Reglas de validación
    ├── helpers.py              Componentes reutilizables
    ├── seguridad.py            Cifrado de contraseñas
    ├── contrato_pdf.py         Maquetación del contrato (Platypus)
    ├── recibo_pdf.py           Recibo de cobro (Platypus)
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
| Generar el cronograma de un contrato | Sí | Sí |
| **Cobrar** cuotas (de una o de varias) | Sí | **No** |
| Consultar la **cartera** y la cobranza | Sí | **No** |
| Anular cuotas, pagos y garantías | Sí | **No** |
| Cancelar o eliminar contratos | Sí | **No** |
| Reportes | Sí | **No** |
| Usuarios | Sí | **No** |
| Auditoría | Sí | **No** |
| Configuración | Sí | **No** |

El vendedor crea contratos y les genera el
cronograma porque son parte de la venta, pero **no
cobra**: quedarse con el dinero de un crédito no es
lo mismo que registrar una venta. Y **no ve la
cartera**, que dice a cuánto debe cada cliente del
concesionario con su teléfono, no solo los suyos. Si
algún día hace falta que alguien externo cobre, la
respuesta es un **rol nuevo** (`cobrador`), no abrirle
la cartera al vendedor.

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

### Ya tenía datos y quiero las ventas financiadas

Si tu base se creó con una versión anterior a la
financiación, faltan las cuotas, las garantías y las
condiciones del contrato. Aplica las dos
migraciones, **en este orden**:

```bash
mysql -u root -p concesionario < database/migracion_financiera.sql
mysql -u root -p concesionario < database/migracion_auditoria_cambios.sql
```

Qué hace:

- crea las tablas `cuotas`, `garantias` y
  `convenios`
- añade a `contratos` las columnas de
  financiación (saldo financiado, tasa, gastos,
  periodicidad, primer vencimiento, moneda,
  retención, cláusulas) **y la fotografía del
  vehículo** (marca, modelo, año, color, precio de
  lista)
- añade a `pagos` la columna `cuota_id`, el
  `recibo` y las columnas de anulación
- añade a `auditoria` el valor anterior, el nuevo y
  la referencia
- siembra los siete ajustes `financiera_*`

**Ni una fila se toca.** Los contratos que ya
existían se quedan sin fotografía del vehículo (el
detalle lo avisa y muestra el dato actual) y **sin
cronograma**. Los que dicen "12 cuotas" pero no
tienen ni una cuota en la tabla no se pueden
generar, porque su saldo financiado está en cero: para
financiarlos de verdad hay que **rehacerlos desde la
venta**.

La aplicación te avisa en **Cartera** si hay
contratos con saldo y sin cronograma.

### El PDF del contrato no sale

Mira `documentos/contratos/` dentro del proyecto.
Si el contrato existe pero el archivo no,
vuelve a pulsarlo con **PDF** en el listado: se
vuelve a generar.

Si el directorio no se puede escribir, el
contrato se guarda igual y el aviso explica por
qué no se pudo escribir el archivo.

### El PDF sale sin la tabla de cuotas

El PDF del contrato imprime el cronograma, así que
**las cuotas tienen que existir antes de generarlo**.
En el flujo normal no hay problema: el formulario las
crea antes de llamar al PDF.

Si ves un contrato con las condiciones pero sin las
fechas de vencimiento, abre su detalle y pulsa
**Generar cronograma**.

### Un contrato dice "12 cuotas" y no tiene ninguna

Es un contrato creado **antes** de que existiera la
financiación, o rehacido sin las condiciones de
financiación. La aplicación no inventa el cronograma
porque no sabe de cuánto es cada cuota ni cuándo vence.

Para financiarlo de verdad hay que rehacerlo: en
**Ventas**, la fila del contrato → **Cancelar**, y
luego **+ Nuevo contrato** desde la misma venta,
rellenando la pestaña **Financiación y cronograma**.

### "No tienes permisos para realizar esta acción" al cobrar

Correcto. **Cobrar una cuota es de la
administración.** El vendedor registra ventas y crea
contratos con su cronograma, pero no se queda con el
dinero de un crédito.

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

Son 505 pruebas. **No tocan tus datos**: cada
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

Dos cosas que han pasado de verdad y que conviene
tener presentes:

- **Un `return` con una tupla de más o de menos**
  rompe al construir la pantalla, no al ejecutar
  el método. Y si la función devuelve datos que
  cambió de forma, quien la pinte reventa al abrir
  la ventana, no con un mensaje: sin ventana.
- **Una condición que solo se cumple en un camino.**
  Un formulario que desactiva un campo cuando el
  pago es de contado, pero que al abrirse ya está en
  "Contado" sin pasar por esa comprobación, deja el
  campo activo. Poner el mismo valor que ya tiene no
  dispara la señal de "cambió": hay que llamar al
  método al abrir.

Y dos cosas más que son fallos silenciosos, por eso
merecen nombre propio:

- **Construir una vista no es usarla.** Un método que
  llama a otro que ya no existe revienta al **pulsar**
  el botón, no al abrir la pantalla. El botón *Ver* de
  una venta estuvo roto un tiempo porque le faltaba
  una función, y ninguna prueba lo notó porque todas
  construían la vista sin pulsar nada.
- **Un botón que no se ve no da error.** Si la columna
  de acciones no está en la lista de cabeceros, la
  columna no se crea, el botón no se pinta, y la tabla
  se ve perfectamente normal: solo faltan los botones.
  `crear_tabla()` **no** añade esa columna. Y el ancho
  de cada botón hay que medirlo **con la hoja de estilos
  puesta**, porque sin ella Qt mide con otra fuente y
  sale otro número.
