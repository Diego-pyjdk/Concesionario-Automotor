# ==========================================
# CONFIGURACIÓN DE LAS PRUEBAS
# ==========================================
# Fixtures compartidas.
#
# La regla importante: las pruebas NUNCA tocan
# la base de datos real. Cada sesión levanta
# una base temporal llamada 'pruebas_concesionario'
# a partir de database/esquema.sql, y apunta
# ahí la aplicación entera.
#
# Cómo se hace sin tocar el código de la
# aplicación: se fija DB_NAME en el entorno.
# database/conexion.py lee las variables en cada
# llamada, y cargar_env() usa os.environ.setdefault
# para que lo que ya está en el entorno mande
# sobre el .env. Así que con la variable puesta
# antes de la primera conexión, todo el
# aplicativo habla con la base de prueba.
#
# La alternativa era sustituir obtener_conexion
# módulo por módulo, y se descartó: al
# sustituirla se salta la instrumentación que
# registra las conexiones abiertas, y las
# pruebas no detectaban las fugas. Además
# obligaba a mantener una lista de módulos que
# se iba olvidando.
#
# El .env se sigue leyendo para las
# credenciales: el usuario y la contraseña son
# los mismos que usa la aplicación.
# ==========================================


import os
import sys

import pytest

import mysql.connector

RAIZ = os.path.dirname(
    os.path.dirname(os.path.abspath(__file__))
)

BASE_PRUEBA = "pruebas_concesionario"

sys.path.insert(0, RAIZ)

# Las credenciales salen del mismo .env que usa
# la aplicacion. Sin esto el proceso arranca con
# las variables de entorno vacias y MySQL
# contesta "Access denied ... (using password:
# NO)".

from database.conexion import cargar_env

cargar_env()

# Y a partir de aquí, la base de datos es la de
# prueba. Se pone DESPUÉS de cargar_env() para
# que el .env no la pise.

os.environ["DB_NAME"] = BASE_PRUEBA

import sesion as modulo_sesion


# ==========================================
# CONEXIÓN A LA BASE DE PRUEBA
# ==========================================

def _conectar(base=None):
    """
    Conexion cruda.

    Sin "base" se conecta al servidor sin elegir
    base de datos: es lo unico que funciona
    para CREAR la base de prueba, que todavia no
    existe cuando se llama por primera vez.
    """

    argumentos = {
        "host": "localhost",
        "user": os.environ.get("DB_USER", "root"),
        "password": os.environ.get("DB_PASSWORD", "")
    }

    if base is not None:

        argumentos["database"] = base

    return mysql.connector.connect(**argumentos)


@pytest.fixture(scope="session")
def base_de_prueba():
    """
    Crea la base temporal una vez por sesión y
    la destruye al terminar.

    Sale del propio esquema.sql, así que si un
    día cambia el esquema, las pruebas se
    adaptan solas.
    """

    raiz = _conectar()

    cursor = raiz.cursor()

    cursor.execute(
        f"DROP DATABASE IF EXISTS {BASE_PRUEBA}"
    )

    cursor.execute(
        f"CREATE DATABASE {BASE_PRUEBA} "
        "CHARACTER SET utf8mb4"
    )

    cursor.close()
    raiz.close()

    # Ahora si, contra la base recien creada: si
    # se conecta sin elegir base, el USE del
    # esquema (que se salta mas abajo) deja a
    # las tablas sin destino y MySQL contesta
    # "No database selected".

    raiz = _conectar(BASE_PRUEBA)

    cursor = raiz.cursor()

    esquema = os.path.join(
        RAIZ, "database", "esquema.sql"
    )

    with open(esquema, encoding="utf-8") as archivo:

        sql = archivo.read()

    # El esquema trae DROP/CREATE de la base
    # con su nombre: se quitan para no borrar la
    # de prueba recien creada.

    sql = "\n".join(
        linea for linea in sql.splitlines()
        if not linea.strip().startswith("--")
    )

    for sentencia in sql.split(";"):

        limpia = sentencia.strip()

        # Se salta el DROP/CREATE/USE del
        # principio del archivo.

        if not limpia:
            continue

        if limpia.upper().startswith("DROP DATABASE"):
            continue

        if limpia.upper().startswith("CREATE DATABASE"):
            continue

        if limpia.upper().startswith("USE "):
            continue

        cursor.execute(limpia)

    raiz.commit()
    cursor.close()
    raiz.close()

    yield BASE_PRUEBA

    # El DROP espera un bloqueo de metadatos si
    # alguna sesión sigue abierta sobre la base.
    # Por defecto eso son 24 horas: una fuga de
    # conexión en el código Convertía la batería
    # de pruebas en un cuelgue sin pistas. Con
    # cinco segundos, el DROP falla rápido y se
    # ve en el mensaje cuál es la sesión que no
    # se cierra.
    #
    # Si alguna vez salta este error, el problema
    # está en database/, no en las pruebas.

    raiz = _conectar()

    cursor = raiz.cursor()

    cursor.execute(
        "SET SESSION lock_wait_timeout = 5"
    )

    cursor.execute(
        f"DROP DATABASE IF EXISTS {BASE_PRUEBA}"
    )

    raiz.commit()
    cursor.close()
    raiz.close()


@pytest.fixture
def limpiar_tablas(base_de_prueba):
    """
    Deja las tablas vacias antes de cada prueba.

    Es por prueba, no por modulo: una prueba que
    crea un cliente no puede dejar rastro en la
    siguiente.

    Depende de base_de_prueba de forma explicita
    (y no solo del autouse de sesion) porque si
    no, pytest puede intentar vaciar las tablas
    antes de que la base exista.
    """

    conexion = _conectar(base_de_prueba)

    cursor = conexion.cursor()

    # El orden importa por las claves foráneas:
    # primero los hijos, después los padres.
    #
    # "pagos" va antes que "ventas" y que
    # "contratos" porque sus dos claves son ON
    # DELETE RESTRICT: si se borrara la venta
    # primero, MySQL rechazaría el DELETE y la
    # prueba siguiente fallaría sin motivo
    # aparente.

    for tabla in (
        "auditoria",
        "pagos",
        "contratos",
        "ventas",
        "autos",
        "clientes",
        "marcas",
        "usuarios"
    ):

        cursor.execute(f"DELETE FROM {tabla}")

    conexion.commit()

    cursor.close()
    conexion.close()

    yield


@pytest.fixture
def como_administrador(base_de_prueba, limpiar_tablas):
    """
    Abre sesion como administrador.

    Depende de limpiar_tablas a proposito: si
    la cuenta se creara antes de vaciar las
    tablas, el borrado se llevaria por delante al
    propio administrador y la sesion apuntaria a
    un id inexistente (la FK de auditoria lo
    detectaria).

    Se crea una cuenta real en la base de
    prueba en vez de inventarse un id: asi las
    claves foraneas de auditoria y contratos se
    comportan igual que en produccion.
    """

    from database.usuarios import crear_primer_usuario

    # Devuelve (id_usuario, ""), no el id suelto:
    # si se pasa la tupla entera como
    # id_usuario, la sesion apunta a una tupla y
    # la FK de auditoria falla al escribir.
    id_usuario, motivo = crear_primer_usuario(
        "admin",
        "Administrador de pruebas",
        "Concesionario2026"
    )

    if id_usuario is None:

        pytest.skip(
            f"no se pudo crear el administrador: "
            f"{motivo}"
        )

    modulo_sesion.iniciar_sesion((
        id_usuario,
        "admin",
        "Administrador de pruebas",
        "administrador"
    ))

    yield id_usuario

    modulo_sesion.cerrar_sesion()


@pytest.fixture
def como_vendedor(como_administrador):
    """
    Cambia la sesion a un vendedor.

    Depende de como_administrador porque hace
    falta un administrador para crearlo.
    """

    from database.usuarios import insertar_usuario

    id_vendedor = insertar_usuario(
        "vendedor_test",
        "Vendedor de pruebas",
        "VendedorDePruebas2026",
        "vendedor",
        True
    )

    modulo_sesion.iniciar_sesion((
        id_vendedor,
        "vendedor_test",
        "Vendedor de pruebas",
        "vendedor"
    ))

    yield id_vendedor


# ==========================================
# SESIÓN
# ==========================================

def _datos_de_sesion():
    """
    Copia los valores de la sesión, no la sesión.

    sesion.obtener_sesion() devuelve SIEMPRE el
    mismo objeto y iniciar_sesion() lo modifica
    dentro. Si una fixture guarda la referencia
    para restaurarla después, estará guardando
    un espejo: al cambiar el rol, la "copia"
    cambia con él y al restaurar se queda con el
    rol nuevo. Por eso se copian los valores.
    """

    actual = modulo_sesion.obtener_sesion()

    if not actual.activa:

        return None

    return (
        actual.id_usuario,
        actual.nombre_usuario,
        actual.nombre_completo,
        actual.rol
    )


@pytest.fixture
def datos_base(como_administrador):
    """
    Un conjunto minimo para poder operar.

    Devuelve (id_marca, id_auto, id_cliente) y
    deja un vehiculo con stock 3.

    Inserta como administrador y luego devuelve
    la sesion a quien la tuviera. Hace falta
    porque el orden de las fixtures es el del
    orden en que se piden: si la prueba pide
    (como_vendedor, datos_base), la sesion ya es
    de vendedor cuando esta fixture inserta, y el
    alta se deniega con PermisoDenegado.
    """

    from database.marcas import insertar_marca
    from database.autos import insertar_auto
    from database.clientes import insertar_cliente

    # Se reaprovecha el administrador que ya creó
    # como_administrador. No se puede llamar a
    # crear_primer_usuario otra vez: se niega a
    # hacerlo si ya hay un administrador activo.

    id_admin = como_administrador

    previa = _datos_de_sesion()

    modulo_sesion.iniciar_sesion((
        id_admin,
        "admin",
        "Administrador de pruebas",
        "administrador"
    ))

    id_marca = insertar_marca("Toyota")

    id_auto = insertar_auto(
        id_marca, "Corolla", 2024, 25000.0, "Blanco", 3
    )

    id_cliente = insertar_cliente(
        "Ana", "García", "0981234567", "ana@correo.com"
    )

    if previa is not None:

        modulo_sesion.iniciar_sesion(previa)

    return id_marca, id_auto, id_cliente


# ==========================================
# UTILIDADES PARA LAS PRUEBAS
# ==========================================

@pytest.fixture
def conexion_directa():
    """
    Conexion cruda a la base de prueba, para
    cuando una prueba necesita comprobar algo
    que las funciones de la aplicacion no
    exponen (indices, constraints, filas
    crudas).
    """

    conexion = _conectar(base_de_prueba)

    yield conexion

    conexion.close()


@pytest.fixture
def sin_fugas_de_conexion(base_de_prueba):
    """
    Comprueba que la prueba no ha dejado
    conexiones abiertas en MySQL.

    Sin esto, una fuga no se ve hasta que el
    DROP del final se queda esperando horas, o
    hasta que la aplicación, ya en producción,
    deja de poder conectar sin explicación. Aquí
    se nota en la prueba que la dejó.
    """

    def abiertas():

        raiz = _conectar()

        cursor = raiz.cursor()

        # Se cuentan las sesiones sobre la base
        # de prueba. Esta pregunta va sin base
        # elegida, así que no cuenta a sí misma.

        cursor.execute(
            """
            SELECT COUNT(*)
            FROM information_schema.processlist
            WHERE db = %s
            """,
            (base_de_prueba,)
        )

        total = cursor.fetchone()[0]

        cursor.close()
        raiz.close()

        return total

    antes = abiertas()

    yield antes

    despues = abiertas()

    assert despues <= antes, (
        f"la prueba dejó {despues - antes} "
        "conexiones abiertas en MySQL"
    )


@pytest.fixture
def ruta_pdf_temporal(tmp_path):
    """
    Carpeta temporal para los PDF que generan
    las pruebas.

    Sin esto cada prueba deja un archivo en
    documentos/contratos/ y la carpeta se llena
    de restos.
    """

    return str(tmp_path)


@pytest.fixture(autouse=True)
def entorno_offline():
    """
    Nada de pantallas ni de estilos.

    QT_QPA_PLATFORM=offscreen hace que Qt no
    necesite un monitor en una máquina sin
    escritorio (un servidor, un contenedor).
    Las pruebas no dibujan nada, asi que la
    plataforma da igual.
    """

    os.environ["QT_QPA_PLATFORM"] = "offscreen"

    yield
