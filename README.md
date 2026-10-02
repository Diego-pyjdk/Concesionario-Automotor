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

Installa PySide6 (interfaz) y mysql-connector
(conexión a la base de datos). Nada más.

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
| **Reportes** | Informes con filtros y CSV |
| **Usuarios** | Cuentas y roles (solo admin) |
| **Auditoría** | Historial de acciones (solo admin) |
| **Configuración** | Ajustes y diagnóstico |

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
├── .env.example                Plantilla de configuración
│
├── sesion.py                   Usuario en sesión
├── permisos.py                 Permisos por rol
├── errores.py                  Errores controlados
│
├── database/                   Acceso a datos (todo el SQL aquí)
│   ├── conexion.py             Lee el .env y abre conexiones
│   ├── esquema.sql             Estructura completa
│   ├── marcas.py               autos.py
│   ├── clientes.py             ventas.py
│   ├── usuarios.py             auditoria.py
│   ├── configuracion.py        Ajustes
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
│   ├── reportes_view.py        configuracion_view.py
│   ├── estilo.css              Apariencia
│   └── formularios/            Formularios de alta y edición
│
└── utils/                      Utilidades sin dependencias
    ├── validaciones.py         Reglas de validación
    ├── helpers.py              Componentes reutilizables
    ├── seguridad.py            Cifrado de contraseñas
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
| Reportes | Sí | **No** |
| Usuarios | Sí | **No** |
| Auditoría | Sí | **No** |
| Configuración | Sí | **No** |

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
