# ==========================================
# HASH DE CONTRASEÑAS
# ==========================================
# PBKDF2-HMAC-SHA256 de la biblioteca estándar.
# No hace falta instalar nada.
#
# Nunca se guarda la contraseña: se guarda
#
#     <sal hexadecimal>:<hash hexadecimal>
#
# Cada usuario tiene su propia sal, así que dos
# contraseñas iguales producen hashes distintos.
#
# No se puede recuperar la contraseña desde el
# hash: solo se puede comprobar.
# ==========================================


import hashlib
import hmac
import os


# ==========================================
# PARÁMETROS
# ==========================================

ALGORITMO = "sha256"

# Coste del hashmarcado. Medido en esta máquina:
# ~0,17 s por verificación, que es lo que tarda
# un login y desincentiva la fuerza bruta.
ITERACIONES = 260000

LONGITUD_SAL = 16

LONGITUD_HASH = 32

SEPARADOR = ":"


# ==========================================
# HASHD
# ==========================================

def hashear_contrasena(contrasena, sal=None):
    """
    Devuelve (sal, hash) en bytes.

    Si no se pasa sal, genera una nueva: es lo
    que hay que hacer al crear un usuario.
    """

    if sal is None:
        sal = os.urandom(LONGITUD_SAL)

    hash_calculado = hashlib.pbkdf2_hmac(
        ALGORITMO,
        contrasena.encode("utf-8"),
        sal,
        ITERACIONES
    )

    return sal, hash_calculado


def construir_hash(contrasena):
    """
    Devuelve el texto a guardar en la columna
    password_hash.
    """

    sal, hash_calculado = hashear_contrasena(contrasena)

    return sal.hex() + SEPARADOR + hash_calculado.hex()


def separar_hash(password_hash):
    """
    Descompone 'sal:hash' en dos bytes.

    Devuelve (None, None) si el formato no es
    válido, para no reventar con datos viejos.
    """

    if not password_hash:
        return None, None

    partes = password_hash.split(SEPARADOR)

    if len(partes) != 2:
        return None, None

    try:
        sal = bytes.fromhex(partes[0])

        esperado = bytes.fromhex(partes[1])

    except ValueError:
        return None, None

    return sal, esperado


def verificar_contrasena(contrasena, password_hash):
    """
    Comprueba una contraseña contra el hash
    guardado.

    Devuelve False si el hash guardado no tiene
    un formato válido, en lugar de fallar.
    """

    sal, esperado = separar_hash(password_hash)

    if sal is None or esperado is None:
        return False

    _, calculado = hashear_contrasena(
        contrasena,
        sal
    )

    # compare_digest evita los ataques de
    # temporización.
    return hmac.compare_digest(
        calculado,
        esperado
    )


def hash_para_placeholder():
    """
    Genera un hash con una contraseña inventada.

    Sirve para igualar el coste cuando el usuario
    no existe: si el login respondiera de
    inmediato, un atacante podría enumerar
    nombres de usuario midiendo tiempos.
    """

    return construir_hash("contrasena-inexistente")
