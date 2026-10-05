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

from database.conexion import (
    conexiones_libres,
    obtener_conexion
)

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
    "PAGO": "Pago registrado",
    "PAGO_ANULADO": "Pago anulado",
    "VENTA_PAGADA": "Venta totalmente cobrada",
    "DESBLOQUEO": "Desbloqueo de cuenta",
    "CONFIGURACION": "Cambio de configuración",
    "FINANCIERA": "Movimiento de financiación",
    "CRONOGRAMA": "Cronograma generado",
    "PAGO_CUOTA": "Pago a cuota",
    "CUOTA_ANULADA": "Cuota anulada",
    "CUOTA_REACTIVADA": "Cuota reactivada",
    "VENCIDAS": "Detección de vencidas",
    "GARANTIA": "Garantía modificada",
    "CONVENIO": "Convenio de pago",
    "ACCESO_DENEGADO": "Acceso denegado"
}


MODULOS = {
    "acceso": "Acceso",
    "vehiculos": "Vehículos",
    "marcas": "Marcas",
    "clientes": "Clientes",
    "ventas": "Ventas",
    "contratos": "Contratos",
    "financiera": "Financiera",
    "pagos": "Pagos",
    "garantias": "Garantías",
    "convenios": "Convenios",
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

    Los dos parámetros del usuario se reenvían a
    registrar_cambio() TAL CUAL, centinela incluido.
    Reenviarlos como None los convertiría en "sin
    usuario", y como valor concreto los convertiría en
    "usa la sesión": las dos cosas están mal.

    El día que se partió esta función en dos se
    olvidó reenviarlos, y un login fallido contra una
    cuenta que no existe pasó a quedar anotado a
    nombre de quien estuviera sentado delante, que es
    justo lo que el centinela existe para evitar: un
    intento fallido tiene que quedarse sin atribuir,
    no atribuirse a otra persona.
    """

    return registrar_cambio(
        modulo,
        accion,
        descripcion,
        usuario_id=usuario_id,
        usuario_nombre=usuario_nombre
    )


def registrar_cambio(
    modulo,
    accion,
    descripcion=None,
    usuario_id=SIN_INFORMAR,
    usuario_nombre=SIN_INFORMAR,
    valor_anterior=None,
    valor_nuevo=None,
    referencia=None
):
    """
    Guarda una acción Y, si los hay, los valores
    anterior y nuevo.

    Es registrar_accion() con una columna más a
    cada lado. Existe separado, y no como parámetro
    opcional, porque una modificación que se puede
    registrar SIN decir qué cambió no cumple su
    trabajo: quien la lea no sabe si el saldo era
    200.000 o 2.000.000 antes de que alguien lo
    tocara.

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

    # Los valores van a 255 también, por el mismo
    # motivo que la descripción. Si alguien pasa un
    # texto más largo, se corta: es preferible un
    # valor anterior truncado a un INSERT que falla
    # y deja la modificación sin rastro.

    if valor_anterior is not None:

        valor_anterior = str(valor_anterior)[:255]

    if valor_nuevo is not None:

        valor_nuevo = str(valor_nuevo)[:255]

    if referencia is not None:

        referencia = str(referencia)[:255]

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
                descripcion,
                valor_anterior,
                valor_nuevo,
                referencia
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """

        valores = (
            usuario_id,
            usuario_nombre,
            accion,
            modulo,
            descripcion,
            valor_anterior,
            valor_nuevo,
            referencia
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
    accion, modulo, descripcion, valor_anterior,
    valor_nuevo, referencia) del más reciente al
    más antiguo.

    Las tres últimas pueden ser None: las entradas
    anteriores a la migración que añadió esas columnas
    no las tienen, y no se van a rellenar con nada
    inventado. Quien las pinte tiene que distinguir
    "no se registró" de "se registró vacío", así que
    una celda vacía no vale: hay que poner algo.

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
            descripcion,
            valor_anterior,
            valor_nuevo,
            referencia
        FROM auditoria
    """ + _where(condiciones) + " ORDER BY id DESC LIMIT %s"

    valores.append(limite)

    cursor.execute(consulta, tuple(valores))

    registros = cursor.fetchall()

    cursor.close()
    conexion.close()

    return registros


@requiere_permiso(VER_AUDITORIA)
def obtener_historial(referencia, limite=LIMITE_POR_DEFECTO):
    """
    Todo lo que le pasó a una cosa concreta: un
    contrato, un recibo, un número de cuota.

    Es el historial que pide el cliente cuando
    pregunta por su contrato, y el que necesita el
    vendedor cuando una cuota no cuadra.

    Se busca por la columna referencia, no por la
    descripción: buscando texto dentro de una
    descripción el resultado depende de cómo se
    escribió esa vez, y el mismo pago podría
    aparecer en un sitio y no en otro.

    Devuelve filas con el mismo formato que
    obtener_auditoria().
    """

    conexion = obtener_conexion()
    cursor = conexion.cursor()

    consulta = """
        SELECT
            id,
            fecha_hora,
            usuario_nombre,
            accion,
            modulo,
            descripcion,
            valor_anterior,
            valor_nuevo,
            referencia
        FROM auditoria
        WHERE referencia = %s
        ORDER BY id DESC
        LIMIT %s
    """

    cursor.execute(consulta, (referencia, limite))

    registros = cursor.fetchall()

    cursor.close()
    conexion.close()

    return registros


@requiere_permiso(VER_AUDITORIA)
def historial_contrato(id_contrato, limite=300):
    """
    Todo lo registrado sobre un contrato, junto y en
    orden.

    Y "junto" es el motivo de que exista. El rastro se
    reparte por la columna referencia, y cada módulo
    escribe lo que le viene bien: las garantías usan
    el NÚMERO del contrato, y cada pago usa SU
    recibo.

    De ahí que buscar por el número del contrato dé
    las garantías y ni uno de los pagos, y que
    buscar por el recibo dé cada pago una vez y haya
    que preguntar recibo a recibo. Un historial al
    que le faltan los cobros no sirve: es justo el
    movimiento que el cliente viene a preguntar.

    Por eso la regla de "qué es la referencia de qué"
    vive aquí y no en la pantalla: la pantalla solo
    pinta lo que le devuelven.

    Dos consultas, no una por recibo: el número del
    contrato y los recibios de su venta se piden
    juntos y luego se busca con un IN.

    El contrato entra por id y no por número porque
    quien llama tiene el id, y el número depende del
    año: el contrato 7 puede ser CTR-2025-00007 y no
    CTR-2027-00007.

    Devuelve filas con el mismo formato que
    obtener_auditoria(), de la más reciente a la más
    antigua.
    """

    conexion = obtener_conexion()
    cursor = conexion.cursor(dictionary=True)

    cursor.execute(
        """
        SELECT
            contratos.numero,
            contratos.venta_id
        FROM contratos
        WHERE contratos.id = %s
        """,
        (id_contrato,)
    )

    contrato = cursor.fetchone()

    if not contrato:

        cursor.close()
        conexion.close()

        return []

    cursor.execute(
        """
        SELECT pagos.recibo
        FROM pagos
        WHERE pagos.venta_id = %s
          AND pagos.recibo IS NOT NULL
          AND pagos.recibo <> ''
        """,
        (contrato["venta_id"],)
    )

    recibos = [
        fila["recibo"] for fila in cursor.fetchall()
    ]

    valores = [contrato["numero"]]
    criterios = "referencia = %s"

    if recibos:

        criterios += (
            " OR referencia IN ("
            + ", ".join(["%s"] * len(recibos))
            + ")"
        )

        valores.extend(recibos)

    consulta = """
        SELECT
            id,
            fecha_hora,
            usuario_nombre,
            accion,
            modulo,
            descripcion,
            valor_anterior,
            valor_nuevo,
            referencia
        FROM auditoria
        WHERE {criterios}
        ORDER BY fecha_hora DESC, id DESC
        LIMIT %s
    """.format(criterios=criterios)

    valores.append(int(limite))

    # ------------------------------
    # CURSOR NUEVO, SIN DICCIONARIO
    # ------------------------------
    # Estas dos consultas necesitan nombres de
    # columna: "contrato["numero"]" es mucho más
    # legible que "tupla[0]" y no depende del orden
    # de la lista. La del rastro, en cambio, tiene que
    # devolver TUPLAS, porque su formato es el mismo
    # que el de obtener_auditoria() y quien la pinta
    # los recorre con índices: si salieran
    # diccionarios, en el historial del contrato cada
    # fila daría KeyError con el número de columna.

    cursor.close()

    cursor = conexion.cursor()

    cursor.execute(consulta, tuple(valores))

    registros = cursor.fetchall()

    cursor.close()
    conexion.close()

    return registros


@requiere_permiso(VER_AUDITORIA)
def obtener_cambios(dejar_registros_financiera=False):
    """
    Las entradas que llevan valor anterior y valor
    nuevo, de la más reciente a la más antigua.

    Es la respuesta a "¿qué se ha tocado en esta
    instalación?", que obtener_auditoria() no
    contesta: ahí hay también los inicios de sesión.

    deja_registros_financiera trae además las
    operaciones de la caja (pagos, ventas,
    anulaciones), que ya están en la tabla con sus
    valores pero no son "cambios" de un dato: son
    movimientos de dinero. Filtro así para que el
    informe se pueda pedir de dos formas.
    """

    conexiones = obtener_conexion()
    cursor = conexiones.cursor()

    if dejar_registros_financiera:

        condicion = (
            "(valor_anterior IS NOT NULL "
            " OR valor_nuevo IS NOT NULL "
            " OR modulo IN ('financiera', 'pagos', "
            "               'ventas', 'garantias'))"
        )

    else:

        condicion = (
            "(valor_anterior IS NOT NULL "
            " OR valor_nuevo IS NOT NULL)"
        )

    consulta = f"""
        SELECT
            id,
            fecha_hora,
            usuario_nombre,
            accion,
            modulo,
            descripcion,
            valor_anterior,
            valor_nuevo,
            referencia
        FROM auditoria
        WHERE {condicion}
        ORDER BY id DESC
        LIMIT %s
    """

    cursor.execute(consulta, (LIMITE_POR_DEFECTO,))

    registros = cursor.fetchall()

    cursor.close()
    conexiones.close()

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


@conexiones_libres
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
