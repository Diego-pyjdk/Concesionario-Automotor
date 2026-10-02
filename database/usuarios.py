# ==========================================
# USUARIOS
# ==========================================
# Acceso al sistema, verificación de
# contraseñas y bloqueo por intentos fallidos.
#
# La contraseña nunca se guarda ni se compara
# directamente: solo se hashea con PBKDF2 y se
# compara con compare_digest.
#
# autenticar() NO lleva permiso: es justamente
# la puerta de entrada. Todas las demás sí.
# ==========================================


import mysql.connector

from database.conexion import obtener_conexion

from database.auditoria import (
    registrar_accion,
    registrar_login
)

from utils.seguridad import (
    construir_hash,
    verificar_contrasena,
    hash_para_placeholder
)

import sesion as modulo_sesion

from permisos import (
    requiere_permiso,
    GESTIONAR_USUARIOS
)

from errores import traducir_error


# ==========================================
# BLOQUEO
# ==========================================

MAX_INTENTOS = 5

MINUTOS_BLOQUEO = 15


# ==========================================
# LOGIN
# ==========================================

def autenticar(nombre_usuario, contrasena):
    """
    Comprueba las credenciales.

    Devuelve (True, "", datos) o
    (False, mensaje, None), donde datos es
    (id, nombre_usuario, nombre_completo, rol).

    El mensaje es el mismo para usuario
    inexistente y contraseña incorrecta: no se
    revela qué cuentas existen.
    """

    conexion = obtener_conexion()

    cursor = conexion.cursor(dictionary=True)

    try:

        cursor.execute("""
            SELECT
                id,
                nombre_usuario,
                nombre_completo,
                password_hash,
                rol,
                activo,
                intentos_fallidos,
                bloqueado_hasta
            FROM usuarios
            WHERE nombre_usuario = %s
        """, (nombre_usuario,))

        usuario = cursor.fetchone()

        # ------------------------------
        # USUARIO INEXISTENTE
        # ------------------------------
        # Se verifica una contraseña falsa
        # para que el tiempo de respuesta sea
        # parecido al de un usuario real y no
        # permita adivinar nombres.

        if usuario is None:

            verificar_contrasena(
                contrasena,
                hash_para_placeholder()
            )

            registrar_login(
                nombre_usuario,
                False
            )

            return (
                False,
                "Usuario o contraseña incorrectos.",
                None
            )

        # ------------------------------
        # BLOQUEO
        # ------------------------------

        bloqueado_hasta = usuario["bloqueado_hasta"]

        if bloqueado_hasta is not None:

            minutos = minutos_restantes(
                bloqueado_hasta
            )

            if minutos > 0:

                registrar_login(
                    nombre_usuario,
                    False,
                    id_usuario=usuario["id"],
                    motivo="bloqueado"
                )

                return (
                    False,
                    "La cuenta está bloqueada por "
                    "intentos fallidos. Intenta de "
                    f"nuevo en {minutos} minuto(s).",
                    None
                )

        # ------------------------------
        # CUENTA DESACTIVADA
        # ------------------------------

        if not usuario["activo"]:

            registrar_login(
                nombre_usuario,
                False,
                id_usuario=usuario["id"]
            )

            return (
                False,
                "El usuario está desactivado. "
                "Contacta al administrador.",
                None
            )

        # ------------------------------
        # CONTRASEÑA
        # ------------------------------

        if not verificar_contrasena(
            contrasena,
            usuario["password_hash"]
        ):

            registrar_intento_fallido(
                usuario["id"],
                usuario["intentos_fallidos"]
            )

            restantes = (
                MAX_INTENTOS
                - usuario["intentos_fallidos"]
                - 1
            )

            if restantes > 0:

                return (
                    False,
                    "Usuario o contraseña incorrectos. "
                    f"Te quedan {restantes} "
                    "intento(s).",
                    None
                )

            return (
                False,
                "Cuenta bloqueada por seguridad. "
                f"Intenta de nuevo en "
                f"{MINUTOS_BLOQUEO} minutos.",
                None
            )

        # ------------------------------
        # ACCESO CONCEDIDO
        # ------------------------------

        cursor.execute("""
            UPDATE usuarios
            SET
                ultimo_acceso = NOW(),
                intentos_fallidos = 0,
                bloqueado_hasta = NULL
            WHERE id = %s
        """, (usuario["id"],))

        conexion.commit()

        datos = (
            usuario["id"],
            usuario["nombre_usuario"],
            usuario["nombre_completo"],
            usuario["rol"]
        )

        registrar_login(
            usuario["nombre_usuario"],
            True,
            id_usuario=usuario["id"]
        )

        return True, "", datos

    except mysql.connector.Error as error:

        raise traducir_error(error) from error

    finally:

        cursor.close()
        conexion.close()


def minutos_restantes(bloqueado_hasta):
    """
    Minutos que faltan para desbloquear.

    Devuelve 0 si la bloqueo ya venció.
    """

    import datetime

    ahora = datetime.datetime.now()

    if bloqueado_hasta is None:
        return 0

    diferencia = (bloqueado_hasta - ahora).total_seconds()

    if diferencia <= 0:
        return 0

    return max(1, round(diferencia / 60))


def registrar_intento_fallido(id_usuario, intentos_actuales):
    """
    Suma un intento y bloquea la cuenta al
    superar el máximo.
    """

    conexion = obtener_conexion()
    cursor = conexion.cursor()

    intentos = intentos_actuales + 1

    if intentos >= MAX_INTENTOS:

        consulta = """
            UPDATE usuarios
            SET
                intentos_fallidos = %s,
                bloqueado_hasta =
                    DATE_ADD(NOW(), INTERVAL %s MINUTE)
            WHERE id = %s
        """

        valores = (
            intentos,
            MINUTOS_BLOQUEO,
            id_usuario
        )

    else:

        consulta = """
            UPDATE usuarios
            SET intentos_fallidos = %s
            WHERE id = %s
        """

        valores = (
            intentos,
            id_usuario
        )

    cursor.execute(consulta, valores)

    conexion.commit()

    cursor.close()
    conexion.close()


@requiere_permiso(GESTIONAR_USUARIOS)
def reiniciar_bloqueo(id_usuario):
    """
    Desbloquea una cuenta y pone el contador a
    cero. Lo usa el administrador.
    """

    conexion = obtener_conexion()
    cursor = conexion.cursor()

    consulta = """
        UPDATE usuarios
        SET
            intentos_fallidos = 0,
            bloqueado_hasta = NULL
        WHERE id = %s
    """

    cursor.execute(consulta, (id_usuario,))

    conexion.commit()

    cursor.close()
    conexion.close()

    registrar_accion(
        "usuarios",
        "DESBLOQUEO",
        f"Cuenta {id_usuario} desbloqueada"
    )


# ==========================================
# LISTAR Y BUSCAR
# ==========================================

@requiere_permiso(GESTIONAR_USUARIOS)
def obtener_usuarios():
    """
    Contrato de columnas para UsuariosView:
    id, nombre_usuario, nombre_completo, rol,
    activo, ultimo_acceso, intentos_fallidos,
    bloqueado_hasta.
    """

    conexion = obtener_conexion()
    cursor = conexion.cursor()

    consulta = """
        SELECT
            id,
            nombre_usuario,
            nombre_completo,
            rol,
            activo,
            ultimo_acceso,
            intentos_fallidos,
            bloqueado_hasta
        FROM usuarios
        ORDER BY nombre_usuario
    """

    cursor.execute(consulta)

    usuarios = cursor.fetchall()

    cursor.close()
    conexion.close()

    return usuarios


@requiere_permiso(GESTIONAR_USUARIOS)
def buscar_usuarios(texto):

    conexion = obtener_conexion()
    cursor = conexion.cursor()

    consulta = """
        SELECT
            id,
            nombre_usuario,
            nombre_completo,
            rol,
            activo,
            ultimo_acceso,
            intentos_fallidos,
            bloqueado_hasta
        FROM usuarios
        WHERE
            nombre_usuario LIKE %s
            OR nombre_completo LIKE %s
            OR rol LIKE %s
        ORDER BY nombre_usuario
    """

    parametro = f"%{texto}%"

    cursor.execute(
        consulta,
        (parametro, parametro, parametro)
    )

    usuarios = cursor.fetchall()

    cursor.close()
    conexion.close()

    return usuarios


# ==========================================
# EXISTENCIA
# ==========================================

@requiere_permiso(GESTIONAR_USUARIOS)
def usuario_existe(nombre_usuario, id_usuario=None):
    """
    La comparación ignora mayúsculas.
    id_usuario excluye al propio usuario al
    editar.
    """

    conexion = obtener_conexion()
    cursor = conexion.cursor()

    consulta = """
        SELECT COUNT(*)
        FROM usuarios
        WHERE LOWER(nombre_usuario) = LOWER(%s)
    """

    valores = (nombre_usuario,)

    if id_usuario:
        consulta += " AND id <> %s"
        valores = valores + (id_usuario,)

    cursor.execute(consulta, valores)

    total = cursor.fetchone()[0]

    cursor.close()
    conexion.close()

    return total > 0


def contar_administradores_activos(id_excluir=None):
    """
    Sirve para no dejar el sistema sin ningún
    administrador con acceso.
    """

    conexion = obtener_conexion()
    cursor = conexion.cursor()

    consulta = """
        SELECT COUNT(*)
        FROM usuarios
        WHERE rol = 'administrador'
            AND activo = 1
    """

    valores = ()

    if id_excluir:
        consulta += " AND id <> %s"
        valores = (id_excluir,)

    cursor.execute(consulta, valores)

    total = cursor.fetchone()[0]

    cursor.close()
    conexion.close()

    return total


def es_administrador(id_usuario):

    conexion = obtener_conexion()
    cursor = conexion.cursor()

    consulta = """
        SELECT rol
        FROM usuarios
        WHERE id = %s
            AND activo = 1
    """

    cursor.execute(consulta, (id_usuario,))

    fila = cursor.fetchone()

    cursor.close()
    conexion.close()

    if not fila:
        return False

    return fila[0] == "administrador"


def hay_usuarios():
    """
    Indica si el sistema tiene alguna cuenta
    creada.
    """

    conexion = obtener_conexion()
    cursor = conexion.cursor()

    consulta = """
        SELECT COUNT(*)
        FROM usuarios
    """

    cursor.execute(consulta)

    total = cursor.fetchone()[0]

    cursor.close()
    conexion.close()

    return total > 0


# ==========================================
# ARRANQUE
# ==========================================

def crear_primer_usuario(
    nombre_usuario,
    nombre_completo,
    contrasena
):
    """
    Crea el administrador inicial.

    No lleva permiso a propósito: es el punto de
    entrada antes de que exista ninguna sesión.

    Solo funciona si NO hay ningún administrador
    activo, así que no sirve para añadir cuentas
    por la puerta de atrás.

    Devuelve (id_usuario, "") o (None, motivo).
    """

    if contar_administradores_activos() > 0:

        return (
            None,
            "Ya existe un administrador activo. "
            "Usa la pantalla Usuarios para crear "
            "cuentas nuevas."
        )

    conexion = obtener_conexion()
    cursor = conexion.cursor()

    consulta = """
        INSERT INTO usuarios
        (
            nombre_usuario,
            nombre_completo,
            password_hash,
            rol,
            activo
        )
        VALUES (%s, %s, %s, 'administrador', 1)
    """

    valores = (
        nombre_usuario,
        nombre_completo,
        construir_hash(contrasena)
    )

    cursor.execute(consulta, valores)

    conexion.commit()

    id_usuario = cursor.lastrowid

    cursor.close()
    conexion.close()

    return id_usuario, ""


# ==========================================
# INSERTAR
# ==========================================

@requiere_permiso(GESTIONAR_USUARIOS)
def insertar_usuario(
    nombre_usuario,
    nombre_completo,
    contrasena,
    rol,
    activo=True
):
    """
    Devuelve el id del usuario nuevo.
    """

    conexion = obtener_conexion()
    cursor = conexion.cursor()

    consulta = """
        INSERT INTO usuarios
        (
            nombre_usuario,
            nombre_completo,
            password_hash,
            rol,
            activo
        )
        VALUES (%s, %s, %s, %s, %s)
    """

    valores = (
        nombre_usuario,
        nombre_completo,
        construir_hash(contrasena),
        rol,
        1 if activo else 0
    )

    cursor.execute(consulta, valores)

    conexion.commit()

    id_usuario = cursor.lastrowid

    cursor.close()
    conexion.close()

    registrar_accion(
        "usuarios",
        "CREAR",
        f"Usuario '{nombre_usuario}' creado "
        f"con rol {rol}"
    )

    return id_usuario


# ==========================================
# ACTUALIZAR
# ==========================================

@requiere_permiso(GESTIONAR_USUARIOS)
def actualizar_usuario(
    id_usuario,
    nombre_usuario,
    nombre_completo,
    rol,
    activo,
    contrasena=None
):
    """
    Actualiza los datos del usuario.

    contrasena=None deja la contraseña igual.
    Si viene informed se guarda su hash, nunca
    el texto.
    """

    # ------------------------------
    # SALVAGUARDAS
    # ------------------------------
    # El sistema no puede quedarse sin ningún
    # administrador con acceso.

    if not activo or rol != "administrador":

        if contar_administradores_activos(
            id_usuario
        ) == 0:

            return False

    conexion = obtener_conexion()
    cursor = conexion.cursor()

    if contrasena:

        consulta = """
            UPDATE usuarios
            SET
                nombre_usuario = %s,
                nombre_completo = %s,
                rol = %s,
                activo = %s,
                password_hash = %s,
                intentos_fallidos = 0,
                bloqueado_hasta = NULL
            WHERE id = %s
        """

        valores = (
            nombre_usuario,
            nombre_completo,
            rol,
            1 if activo else 0,
            construir_hash(contrasena),
            id_usuario
        )

    else:

        consulta = """
            UPDATE usuarios
            SET
                nombre_usuario = %s,
                nombre_completo = %s,
                rol = %s,
                activo = %s
            WHERE id = %s
        """

        valores = (
            nombre_usuario,
            nombre_completo,
            rol,
            1 if activo else 0,
            id_usuario
        )

    cursor.execute(consulta, valores)

    conexion.commit()

    cursor.close()
    conexion.close()

    detalles = [f"rol {rol}"]

    if not activo:
        detalles.append("desactivado")

    if contrasena:
        detalles.append("contraseña restablecida")

    registrar_accion(
        "usuarios",
        "MODIFICAR",
        f"Usuario '{nombre_usuario}' actualizado: "
        + ", ".join(detalles)
    )

    return True


@requiere_permiso(GESTIONAR_USUARIOS)
def cambiar_contrasena(id_usuario, contrasena):
    """
    Restablece la contraseña y limpia el bloqueo.
    """

    conexion = obtener_conexion()
    cursor = conexion.cursor()

    consulta = """
        UPDATE usuarios
        SET
            password_hash = %s,
            intentos_fallidos = 0,
            bloqueado_hasta = NULL
        WHERE id = %s
    """

    valores = (
        construir_hash(contrasena),
        id_usuario
    )

    cursor.execute(consulta, valores)

    conexion.commit()

    cursor.close()
    conexion.close()

    registrar_accion(
        "usuarios",
        "MODIFICAR",
        f"Contraseña del usuario {id_usuario} "
        "restablecida y bloqueo limpiado"
    )


# ==========================================
# ELIMINAR
# ==========================================

@requiere_permiso(GESTIONAR_USUARIOS)
def eliminar_usuario(id_usuario):
    """
    Elimina una cuenta.

    Devuelve (True, "") o (False, motivo).

    No deja que un administrador se borre a sí
    mismo ni que el sistema se quede sin
    administradores activos.
    """

    actual = modulo_sesion.obtener_sesion()

    if actual.id_usuario == id_usuario:

        return (
            False,
            "No puedes eliminar tu propia cuenta."
        )

    if es_administrador(id_usuario):

        if contar_administradores_activos(
            id_usuario
        ) == 0:

            return (
                False,
                "Debe quedar al menos un "
                "administrador activo."
            )

    conexion = obtener_conexion()
    cursor = conexion.cursor()

    consulta = """
        DELETE FROM usuarios
        WHERE id = %s
    """

    cursor.execute(consulta, (id_usuario,))

    conexion.commit()

    cursor.close()
    conexion.close()

    registrar_accion(
        "usuarios",
        "ELIMINAR",
        f"Usuario {id_usuario} eliminado"
    )

    return True, ""
