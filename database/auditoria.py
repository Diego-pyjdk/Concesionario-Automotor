# ==========================================
# AUDITORÍA
# ==========================================
# Rastro de las acciones importantes del
# sistema: quién entró, qué creó, qué borró y
# qué cambió.
#
# REGLA CRÍTICA
# --------------
# Registrar una acción NUNCA puede romper la
# operación que la origina. Si el INSERT falla
# (MySQL caído, tabla ausente, sin
# permisos), el error se guarda en
# registro_errores.log y la venta o el guardado
# continúa igual.
#
# Por eso registrar_accion() no propaga
# excepciones: es un "mejor esfuerzo".
#
# En la práctica eso significa que puede faltar
# una entrada si MySQL se cayó justo en ese
# momento. Es un compromiso consciente: perder
# una venta sería mucho peor que perder una
# línea del rastro.
# ==========================================


import mysql.connector

from database.conexion import obtener_conexion

import sesion as modulo_sesion

from permisos import (
    requiere_permiso,
    VER_AUDITORIA
)

from utils.registro import registrar_error


# ==========================================
# CATÁLOGOS
# ==========================================
# El código es estable y corto; el texto
# legible se resuelve al mostrar. Cambiar un
# texto no rompe los registros antiguos.
# ==========================================

ACCIONES = {
    "LOGIN": "Inicio de sesión",
    "LOGIN_FALLIDO": "Intento fallido",
    "LOGIN_BLOQUEADO": "Acceso bloqueado",
    "LOGOUT": "Cierre de sesión",
    "CREAR": "Creación",
    "MODIFICAR": "Modificación",
    "ELIMINAR": "Eliminación",
    "VENTA": "Venta registrada",
    "VENTA_ANULADA": "Venta anulada",
    "DESBLOQUEO": "Desbloqueo de cuenta",
    "CONFIGURACION": "Cambio de configuración",
    "ACCESO_DENEGADO": "Acceso denegado"
}


MODULOS = {
    "acceso": "Acceso",
    "vehiculos": "Vehículos",
    "marcas": "Marcas",
    "clientes": "Clientes",
    "ventas": "Ventas",
    "usuarios": "Usuarios",
    "configuracion": "Configuración"
}


LIMITE_POR_DEFECTO = 500


# ==========================================
# CENTINELA
# ==========================================
# None es un valor válido para usuario_id:
# significa "sin usuario". Hace falta un
# marcador aparte para diferenciar "el
# llamador no dijo nada" (y entonces se usa la
# sesión) de "el llamador dijo que no hay
# usuario".
# ==========================================

SIN_INFORMAR = object()


# ==========================================
# ESCRITURA
# ==========================================

def registrar_accion(
    modulo,
    accion,
    descripcion=None,
    usuario_id=SIN_INFORMAR,
    usuario_nombre=SIN_INFORMAR
):
    """
    Guarda una acción en el rastro.

    Devuelve True si se registró, False si no.
    Nunca lanza excepciones.
    """

    # Con el centinela se distingue "no informado"
    # de "informado como NULL": un login fallido
    # contra un usuario inexistente debe
    # guardarse con usuario_id NULL a propósito,
    # no con el id de quien esté sentado delante.
    if usuario_id is SIN_INFORMAR:

        usuario_id = modulo_sesion.obtener_sesion().id_usuario

    if usuario_nombre is SIN_INFORMAR:

        usuario_nombre = (
            modulo_sesion.obtener_sesion().nombre_usuario
        )

    if descripcion is not None:

        descripcion = str(descripcion)[:255]

    conexion = None
    cursor = None

    try:

        conexion = obtener_conexion()

        cursor = conexion.cursor()

        consulta = """
            INSERT INTO auditoria
            (
                usuario_id,
                usuario_nombre,
                accion,
                modulo,
                descripcion
            )
            VALUES (%s, %s, %s, %s, %s)
        """

        valores = (
            usuario_id,
            usuario_nombre,
            accion,
            modulo,
            descripcion
        )

        cursor.execute(consulta, valores)

        conexion.commit()

        return True

    except mysql.connector.Error as error:

        registrar_error(error)

        return False

    except Exception as error:

        registrar_error(error)

        return False

    finally:

        if cursor is not None:

            try:
                cursor.close()
            except Exception:
                pass

        if conexion is not None:

            try:
                conexion.close()
            except Exception:
                pass


def registrar_logout():
    """
    Cierre de sesión.

    Se llama ANTES de destruir la sesión: si se
    registrara después, ya no habría usuario
    al que atribuirle la acción.
    """

    sesion = modulo_sesion.obtener_sesion()

    if not sesion.activa:

        return False

    return registrar_accion(
        "acceso",
        "LOGOUT",
        f"Cierre de sesión de {sesion.nombre_usuario}"
    )


def registrar_login(
    nombre_usuario,
    correcto,
    id_usuario=SIN_INFORMAR,
    motivo=None
):
    """
    Intento de acceso.

    Un fallo contra un usuario que no existe se
    registra con id NULL y el nombre tal como
    se escribió, que es justo lo que un
    atacante estaría probando.
    """

    if correcto:

        return registrar_accion(
            "acceso",
            "LOGIN",
            f"Acceso de {nombre_usuario}",
            usuario_id=id_usuario,
            usuario_nombre=nombre_usuario
        )

    accion = "LOGIN_FALLIDO"

    if motivo == "bloqueado":
        accion = "LOGIN_BLOQUEADO"

    return registrar_accion(
        "acceso",
        accion,
        f"Intento fallido de {nombre_usuario}",
        usuario_id=id_usuario,
        usuario_nombre=nombre_usuario
    )


# ==========================================
# CONSULTA
# ==========================================
# Estas lecturas exigen VER_AUDITORIA, igual
# que la sección de la barra lateral. Ocultar
# el menú no basta: el rastro también se
# protege en la capa de datos.
# ==========================================


def _condiciones(
    usuario,
    modulo,
    accion,
    desde,
    hasta
):
    """
    Construye el WHERE una sola vez.

    obtener_auditoria() y contar_registros() la
    comparten: si cada una construyera el filtro
    por su cuenta, un cambio en uno dejaría al
    otro contando cosas distintas.
    """

    condiciones = []
    valores = []

    if usuario:

        condiciones.append("usuario_nombre LIKE %s")
        valores.append(f"%{usuario}%")

    if modulo:

        condiciones.append("modulo = %s")
        valores.append(modulo)

    if accion:

        condiciones.append("accion = %s")
        valores.append(accion)

    if desde:

        condiciones.append("fecha_hora >= %s")
        valores.append(desde)

    if hasta:

        # El usuario elige "hasta el día X" y
        # espera todo ese día. Sumarle un día
        # hace que el filtro sea inclusivo.

        condiciones.append(
            "fecha_hora < DATE_ADD(%s, INTERVAL 1 DAY)"
        )

        valores.append(hasta)

    return condiciones, valores


def _where(condiciones):
    return (
        " WHERE " + " AND ".join(condiciones)
        if condiciones else ""
    )


@requiere_permiso(VER_AUDITORIA)
def obtener_auditoria(
    usuario=None,
    modulo=None,
    accion=None,
    desde=None,
    hasta=None,
    limite=LIMITE_POR_DEFECTO
):
    """
    Devuelve (id, fecha_hora, usuario_nombre,
    accion, modulo, descripcion) del más
    reciente al más antiguo.

    Los filtros son opcionales y se acumulan.
    Solo un administrador puede leer el rastro.
    """

    condiciones, valores = _condiciones(
        usuario, modulo, accion, desde, hasta
    )

    conexion = obtener_conexion()
    cursor = conexion.cursor()

    consulta = """
        SELECT
            id,
            fecha_hora,
            usuario_nombre,
            accion,
            modulo,
            descripcion
        FROM auditoria
    """ + _where(condiciones) + " ORDER BY id DESC LIMIT %s"

    valores.append(limite)

    cursor.execute(consulta, tuple(valores))

    registros = cursor.fetchall()

    cursor.close()
    conexion.close()

    return registros


@requiere_permiso(VER_AUDITORIA)
def contar_registros(
    usuario=None,
    modulo=None,
    accion=None,
    desde=None,
    hasta=None
):
    """
    Total de entradas que cumplen los filtros.

    Comparte _condiciones() con obtener_auditoria():
    el número que sale aquí es el mismo que el
    número de filas de la vista.
    """

    condiciones, valores = _condiciones(
        usuario, modulo, accion, desde, hasta
    )

    conexion = obtener_conexion()
    cursor = conexion.cursor()

    consulta = "SELECT COUNT(*) FROM auditoria" + _where(
        condiciones
    )

    cursor.execute(consulta, tuple(valores))

    total = cursor.fetchone()[0]

    cursor.close()
    conexion.close()

    return total


@requiere_permiso(VER_AUDITORIA)
def obtener_usuarios_auditados():
    """
    Nombres distintos que aparecen en el
    rastro, para el filtro de la vista.
    """

    conexion = obtener_conexion()
    cursor = conexion.cursor()

    consulta = """
        SELECT DISTINCT usuario_nombre
        FROM auditoria
        WHERE usuario_nombre IS NOT NULL
        ORDER BY usuario_nombre
    """

    cursor.execute(consulta)

    nombres = [
        fila[0] for fila in cursor.fetchall()
    ]

    cursor.close()
    conexion.close()

    return nombres


@requiere_permiso(VER_AUDITORIA)
def obtener_resumen():
    """
    Contadores para las tarjetas de la vista.
    """

    conexion = obtener_conexion()
    cursor = conexion.cursor(dictionary=True)

    consulta = """
        SELECT
            COUNT(*) AS total,
            SUM(accion = 'LOGIN') AS accesos,
            SUM(accion = 'LOGIN_FALLIDO') AS fallidos,
            SUM(accion = 'ACCESO_DENEGADO') AS denegados
        FROM auditoria
    """

    cursor.execute(consulta)

    resumen = cursor.fetchone()

    cursor.close()
    conexion.close()

    return resumen


@requiere_permiso(VER_AUDITORIA)
def vaciar_auditoria():
    """
    Borra todo el rastro.

    Pensado para mantenimiento, no para la
    operación diaria. Devuelve cuántas filas
    eliminó.
    """

    conexion = obtener_conexion()
    cursor = conexion.cursor()

    cursor.execute("DELETE FROM auditoria")

    conexion.commit()

    total = cursor.rowcount

    cursor.close()
    conexion.close()

    return total
