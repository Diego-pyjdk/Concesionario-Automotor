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


def es_anio(valor, campo="El año"):
    """
    Verifica que el valor sea un año razonable
    para un vehículo.
    """

    valido, mensaje = es_numero(valor, campo)

    if not valido:
        return False, mensaje

    numero = int(float(str(valor).strip()))

    if numero < ANIO_MINIMO or numero > ANIO_MAXIMO:
        return (
            False,
            f"{campo} debe estar entre {ANIO_MINIMO} y {ANIO_MAXIMO}."
        )

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
