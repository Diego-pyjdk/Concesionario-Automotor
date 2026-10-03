# ==========================================
# VALIDACIONES REUTILIZABLES


# ==========================================
# Cada función devuelve una tupla:
#
#     (es_valido, mensaje_de_error)
#
# El mensaje va vacío cuando el valor es
# válido, para que los formularios puedan
# mostrarlo directamente con QMessageBox.
#
# Ninguna función lanza excepciones: validan
# y devuelven el resultado.


# ==========================================


import re


# ==========================================
# LIMITES


# ==========================================

ANIO_MINIMO = 1900

ANIO_MAXIMO = 2100

STOCK_MINIMO = 0

STOCK_MAXIMO = 999999

PRECIO_MINIMO = 0.0

PRECIO_MAXIMO = 999999999.0


# ==========================================
# TEXTO


# ==========================================

def texto_obligatorio(valor, campo):
    """
    Verifica que un campo de texto tenga contenido.
    """

    if valor is None:
        return False, f"El campo {campo} es obligatorio."

    if not str(valor).strip():
        return False, f"El campo {campo} es obligatorio."

    return True, ""


# ==========================================
# NUMEROS


# ==========================================

def es_numero(valor, campo="El valor"):
    """
    Verifica que el valor sea numérico.
    Acepta enteros y decimales.
    """

    if valor is None:
        return False, f"{campo} es obligatorio."

    try:
        float(str(valor).strip())
    except (TypeError, ValueError):
        return False, f"{campo} debe ser un número."

    return True, ""


def es_precio(valor, campo="El precio"):
    """
    Verifica que el valor sea un precio válido
    y dentro del rango de la columna DECIMAL.
    """

    valido, mensaje = es_numero(valor, campo)

    if not valido:
        return False, mensaje

    numero = float(str(valor).strip())

    if numero < PRECIO_MINIMO:
        return False, f"{campo} no puede ser negativo."

    if numero > PRECIO_MAXIMO:
        return False, f"{campo} es demasiado alto."

    return True, ""
def es_stock(valor, campo="El stock"):
    """
    Verifica que el valor sea una cantidad
    entera no negativa.
    """

    valido, mensaje = es_numero(valor, campo)

    if not valido:
        return False, mensaje

    numero = int(float(str(valor).strip()))

    if numero < STOCK_MINIMO or numero > STOCK_MAXIMO:
        return (
            False,
            f"{campo} debe estar entre {STOCK_MINIMO} y {STOCK_MAXIMO}."
        )

    return True, ""


# ==========================================
# PERSONAS Y USUARIOS


# ==========================================

# Se permiten tildes y ñ: los nombres en
# español los tienen.
PERSONA = r"[A-Za-zÁÉÍÓÚÜÑáéíóúüñ' \-]+"

# Marcas y modelos: letras, números y los
# signos habituales del catálogo.
TEXTO_SIMPLE = r"[A-Za-zÁÉÍÓÚÜÑáéíóúüñ0-9 .\-_/&()+]+"

NOMBRE_USUARIO = r"[A-Za-z0-9._\-]+"

LONGITUD_MINIMA_USUARIO = 4

LONGITUD_MAXIMA_USUARIO = 30

LONGITUD_MINIMA_CONTRASENA = 8

LONGITUD_MAXIMA_CONTRASENA = 72


def sin_caracteres_de_control(valor):
    """
    Rejecta saltos de línea y tabuladores: se
    colarían en los nombres y no se verían en
    la interfaz.
    """

    if valor is None:
        return True

    for caracter in str(valor):

        if ord(caracter) < 32:
            return False

    return True


def es_nombre_persona(valor, campo="El nombre"):
    """
    Nombre y apellido: letras, espacios, guion
    y apóstrofo.
    """

    texto = "" if valor is None else str(valor).strip()

    valido, mensaje = texto_obligatorio(texto, campo)

    if not valido:
        return valido, mensaje

    if not sin_caracteres_de_control(texto):
        return False, f"{campo} contiene caracteres no válidos."

    if not re.fullmatch(PERSONA, texto):
        return (
            False,
            f"{campo} solo admite letras, espacios, "
            "guion y apóstrofo."
        )

    return True, ""
def es_nombre_usuario(valor, campo="El nombre de usuario"):
    """
    Identificador de la cuenta.
    """

    texto = "" if valor is None else str(valor).strip()

    valido, mensaje = texto_obligatorio(texto, campo)

    if not valido:
        return valido, mensaje

    longitud = len(texto)

    if (
        longitud < LONGITUD_MINIMA_USUARIO
        or longitud > LONGITUD_MAXIMA_USUARIO
    ):

        return (
            False,
            f"{campo} debe tener entre "
            f"{LONGITUD_MINIMA_USUARIO} y "
            f"{LONGITUD_MAXIMA_USUARIO} caracteres."
        )

    if not re.fullmatch(NOMBRE_USUARIO, texto):

        return (
            False,
            f"{campo} solo admite letras, números, "
            "punto, guion y guion bajo."
        )

    return True, ""


def es_contrasena(valor, campo="La contraseña"):
    """
    Exige longitud mínima y mezcla de letras y
    números. El máximo de 72 es el límite de
    PBKDF2-HMAC con SHA-256.
    """

    texto = "" if valor is None else str(valor)

    if not texto:
        return False, f"{campo} es obligatoria."

    if len(texto) < LONGITUD_MINIMA_CONTRASENA:

        return (
            False,
            f"{campo} debe tener al menos "
            f"{LONGITUD_MINIMA_CONTRASENA} caracteres."
        )

    if len(texto) > LONGITUD_MAXIMA_CONTRASENA:

        return (
            False,
            f"{campo} no puede superar "
            f"{LONGITUD_MAXIMA_CONTRASENA} caracteres."
        )

    tiene_letras = any(
        caracter.isalpha() for caracter in texto
    )

    tiene_numeros = any(
        caracter.isdigit() for caracter in texto
    )

    if not tiene_letras or not tiene_numeros:

        return (
            False,
            f"{campo} debe combinar letras y números."
        )

    return True, ""


def contrasenas_coinciden(primera, segunda, campo="Las contraseñas"):
    """
    Compara la contraseña con su confirmación.
    """

    if primera != segunda:

        return False, f"{campo} no coinciden."

    return True, ""


# ==========================================
# CONTACTO


# ==========================================

def es_email(valor, campo="El email", obligatorio=False):
    """
    Verifica el formato de un correo electrónico.
    """

    texto = "" if valor is None else str(valor).strip()

    if not texto:
        if obligatorio:
            return False, f"{campo} es obligatorio."

        return True, ""

    patron = r"[^@\s]+@[^@\s]+\.[A-Za-z]{2,}"

    if not re.fullmatch(patron, texto):
        return False, f"{campo} no tiene un formato válido."

    return True, ""


def es_telefono(valor, campo="El teléfono", obligatorio=False):
    """
    Verifica un teléfono. Admite dígitos,
    espacios y los signos + - ( ).
    """

    texto = "" if valor is None else str(valor).strip()

    if not texto:
        if obligatorio:
            return False, f"{campo} es obligatorio."

        return True, ""

    patron = r"[0-9\s\+\-\(\)]{6,20}"

    if not re.fullmatch(patron, texto):
        return (
            False,
            f"{campo} solo puede contener números y los signos + - ( )."
        )

    return True, ""


# ==========================================
# COMBINADOR


# ==========================================

def primer_error(resultados):
    """
    Recibe la lista de tuplas devueltas por las
    validaciones y devuelve el primer mensaje
    de error, o None si todas son válidas.

    Evita repetir el bloque de validaciones en
    cada formulario.
    """

    for es_valido, mensaje in resultados:
        if not es_valido:
            return mensaje

    return None
