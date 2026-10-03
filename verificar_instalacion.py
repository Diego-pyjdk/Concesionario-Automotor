"""
COMPROBACIÓN DE LA INSTALACIÓN
================================

Recorre los pasos de instalación y dice en cuáles
va bien y en cuáles no. Pensado para cuando algo
falla en un equipo nuevo y hay que saber POR
QUÉ, no solo qué.

    venv\\Scripts\\python.exe verificar_instalacion.py

No modifica nada: solo lee y consulta.
Salida 0 si todo está correcto, 1 si hay
problemas.
"""


import os
import platform
import sys


RAIZ = os.path.dirname(os.path.abspath(__file__))

VERSION_MINIMA = (3, 10)

ARCHIVO_ENV = os.path.join(RAIZ, ".env")

PLANTILLA_ENV = os.path.join(RAIZ, ".env.example")

ESQUEMA = os.path.join(
    RAIZ, "database", "esquema.sql"
)


fallos = []
avisos = []


def ok(mensaje):
    print(f"  [ OK ]    {mensaje}")


def fallo(mensaje, solucion=""):
    print(f"  [FALLO]  {mensaje}")

    if solucion:
        print(f"           -> {solucion}")

    fallos.append(mensaje)


def aviso(mensaje):
    print(f"  [AVISO]  {mensaje}")

    avisos.append(mensaje)


def titulo(texto):
    print()
    print(f"{texto}")
    print("-" * len(texto))


# ==========================================
# 1. PYTHON
# ==========================================

def comprobar_python():

    titulo("1. Python")

    actual = sys.version_info[:2]

    version = platform.python_version()

    if actual >= VERSION_MINIMA:

        ok(f"Python {version}")

    else:

        fallo(
            f"Python {version} es demasiado antiguo.",
            f"Se necesita {VERSION_MINIMA[0]}."
            f"{VERSION_MINIMA[1]} o superior."
        )

    dentro_venv = sys.prefix != sys.base_prefix

    if dentro_venv:

        ok("Ejecutando dentro de un entorno virtual")

    else:

        fallo(
            "No está dentro de un entorno virtual.",
            "Cree uno: python -m venv venv"
        )


# ==========================================
# 2. ENTORNO VIRTUAL
# ==========================================

def comprobar_venv():

    titulo("2. Entorno virtual")

    carpeta = os.path.join(RAIZ, "venv")

    if os.path.isdir(carpeta):

        ok("La carpeta venv/ existe")

    else:

        fallo(
            "No existe la carpeta venv/.",
            "python -m venv venv"
        )


# ==========================================
# 3. DEPENDENCIAS
# ==========================================

def comprobar_dependencias():

    titulo("3. Dependencias")

    requeridos = [
        ("PySide6", "PySide6"),
        ("mysql-connector-python", "mysql.connector"),
        ("reportlab", "reportlab")
    ]

    for nombre, modulo in requeridos:

        try:

            import importlib

            cargado = importlib.import_module(modulo)

            version = getattr(
                cargado, "__version__", "instalado"
            )

            ok(f"{nombre} {version}")

        except ImportError:

            fallo(
                f"Falta {nombre}.",
                "pip install -r requirements.txt"
            )

    archivo = os.path.join(RAIZ, "requirements.txt")

    if os.path.exists(archivo):

        ok("requirements.txt presente")

    else:

        aviso(
            "No hay requirements.txt; se/"
            "recommendaría documentar las "
            "versiones."
        )


# ==========================================
# 4. ARCHIVO .env
# ==========================================

def comprobar_env():

    titulo("4. Configuración .env")

    if os.path.exists(PLANTILLA_ENV):

        ok(".env.example presente")

    else:

        aviso("No existe .env.example")

    if not os.path.exists(ARCHIVO_ENV):

        fallo(
            "No existe el archivo .env.",
            "Copie .env.example a .env y "
            "complete la contraseña."
        )

        return

    ok(".env presente")

    lectura = {}

    try:

        # utf-8-sig quita el BOM si lo hay. Con
        # utf-8 a secas, la primera clave
        # aparecería como "\ufeffDB_HOST" y el
        # diagnóstico daría un fallo falso... o
        # peor, dejaría pasar un .env que en
        # realidad no se está leyendo.

        with open(
            ARCHIVO_ENV, "r", encoding="utf-8-sig"
        ) as archivo:

            for linea in archivo:

                linea = linea.strip()

                if not linea or linea.startswith("#"):
                    continue

                if "=" in linea:

                    clave, _, valor = (
                        linea.partition("=")
                    )

                    lectura[clave.strip()] = (
                        valor.strip().strip('"').strip("'")
                    )

    except OSError as error:

        fallo(f"No se puede leer .env: {error}")

        return

    for clave in (
        "DB_HOST",
        "DB_USER",
        "DB_PASSWORD",
        "DB_NAME"
    ):

        if clave not in lectura:

            fallo(
                f"Falta {clave} en .env.",
                "Copie .env.example a .env."
            )

        elif not lectura[clave]:

            fallo(
                f"{clave} está vacío en .env."
            )

        else:

            ok(f"{clave} definido")

    # En Windows MySQL suele ir sin puerto.
    # No se avisa de eso.


# ==========================================
# 5-6. BASE DE DATOS
# ==========================================

def comprobar_esquema():

    titulo("5. Esquema SQL")

    if os.path.exists(ESQUEMA):

        ok("database/esquema.sql presente")

    else:

        fallo(
            "Falta database/esquema.sql.",
            "Restaure el archivo del proyecto."
        )

        return

    sys.path.insert(0, RAIZ)

    try:

        from database.conexion import obtener_conexion

    except Exception as error:

        fallo(
            f"No se puede cargar la conexión: {error}"
        )

        return

    titulo("6. Conexión con MySQL")

    try:

        conexion = obtener_conexion()

    except Exception as error:

        fallo(
            f"No se pudo conectar: {error}",
            "Compruebe que MySQL esté encendido "
            "y que .env sea correcto."
        )

        return

    ok("Conexión establecida")

    cursor = conexion.cursor()

    requeridas = [
        "marcas", "autos", "clientes",
        "ventas", "usuarios",
        "configuracion", "auditoria",
        "contratos", "pagos"
    ]

    # Cada tabla que falte dice qué migración
    # aplicar, en vez de mandar siempre a la de
    # contratos: si a alguien le falta pagos, la
    # de contratos no le va a servir de nada.

    AYUDA_MIGRACION = {
        "contratos": "database/migracion_contratos.sql",
        "pagos": "database/migracion_pagos.sql"
    }

    cursor.execute("SHOW TABLES")

    existentes = {
        fila[0] for fila in cursor.fetchall()
    }

    for tabla in requeridas:

        if tabla in existentes:

            ok(f"Tabla {tabla}")

            continue

        migracion = AYUDA_MIGRACION.get(tabla)

        if migracion:

            pista = (
                f"Ejecute {migracion}: no borra "
                "ninguna fila."
            )

        else:

            pista = (
                "En una base nueva, ejecute "
                "database/esquema.sql.\nEn una base "
                "que ya tenía datos, aplique la "
                "migración correspondiente."
            )

        fallo(
            f"Falta la tabla {tabla}.",
            pista
        )

    # La tabla contratos no sirve de nada sin
    # la columna documento de clientes: el PDF
    # la lee y sin ella sale siempre "No
    # registrado".

    cursor.execute(
        "SHOW COLUMNS FROM clientes LIKE 'documento'"
    )

    if cursor.fetchone():

        ok("Columna clientes.documento")

    else:

        fallo(
            "Falta la columna documento en "
            "clientes.",
            "Ejecute database/migracion_contratos.sql"
        )

    cursor.close()
    conexion.close()


# ==========================================
# 7. ADMINISTRADOR
# ==========================================

def comprobar_admin():

    titulo("7. Administrador inicial")

    sys.path.insert(0, RAIZ)

    try:

        from database.usuarios import (
            hay_usuarios,
            contar_administradores_activos
        )

    except Exception as error:

        fallo(f"No se pudo consultar usuarios: {error}")

        return

    if not hay_usuarios():

        fallo(
            "No hay ningún usuario creado.",
            "Ejecute: venv\\Scripts\\python.exe "
            "crear_admin.py"
        )

        return

    ok("Hay usuarios registrados")

    if contar_administradores_activos() > 0:

        ok("Existe al menos un administrador activo")

    else:

        fallo(
            "No hay ningún administrador activo.",
            "Sin él no se puede entrar al sistema."
        )


# ==========================================
# 8. APLICACIÓN
# ==========================================

def comprobar_aplicacion():

    titulo("8. Módulos de la aplicación")

    sys.path.insert(0, RAIZ)

    modulos = [
        "main",
        "sesion",
        "permisos",
        "errores",
        "gui.ventana_principal",
        "gui.login_view",
        "gui.vista_listado",
        "gui.vista_base",
        "gui.auditoria_view",
        "gui.diagnostico",
        "gui.contratos_view",
        "gui.formularios.contrato_form",
        "database.reportes",
        "database.auditoria",
        "database.usuarios",
        "database.contratos",
        "utils.helpers",
        "utils.validaciones",
        "utils.seguridad",
        "utils.contrato_pdf"
    ]

    for nombre in modulos:

        try:

            import importlib

            importlib.import_module(nombre)

            ok(nombre)

        except Exception as error:

            fallo(
                f"{nombre} no se puede importar: "
                f"{error}"
            )

    ruta_css = os.path.join(
        RAIZ, "gui", "estilo.css"
    )

    if os.path.exists(ruta_css):

        ok("gui/estilo.css presente")

    else:

        fallo(
            "Falta gui/estilo.css.",
            "La aplicación abriría sin estilos."
        )


# ==========================================
# RESUMEN
# ==========================================

def resumen():

    print()

    print("=" * 52)

    if not fallos and not avisos:

        print("  Todo correcto. La aplicación está lista.")
        print("=" * 52)

        return 0

    if fallos:

        print(
            f"  {len(fallos)} problema(s) que "
            "impiden arrancar:"
        )

        for problema in fallos:

            print(f"    - {problema}")

    if avisos:

        print(f"\n  {len(avisos)} aviso(s):")

        for nota in avisos:

            print(f"    - {nota}")

    print("=" * 52)

    return 1


def main():

    print()
    print("  VERIFICACIÓN DE LA INSTALACIÓN")
    print("  Concesionario Automotor")

    comprobar_python()
    comprobar_venv()
    comprobar_dependencias()
    comprobar_env()
    comprobar_esquema()
    comprobar_admin()
    comprobar_aplicacion()

    return resumen()


sys.exit(main())
