import mysql.connector

from database.conexion import (
    conexiones_libres,
    obtener_conexion
)

from database.auditoria import registrar_accion

from utils.moneda import (
    FORMATOS as FORMATOS_MONEDA,
    validar_config
)

from permisos import (
    requiere_permiso,
    GESTIONAR_CONFIGURACION
)


# =============================
# DATOS DEL SISTEMA
# =============================

NOMBRE_SISTEMA = "Concesionario Automotor"

VERSION_SISTEMA = "1.1.0"

CLAVE_STOCK_MINIMO = "stock_minimo"

STOCK_MINIMO_POR_DEFECTO = 3


# =============================
# MONEDA
# =============================

CLAVE_MONEDA_CODIGO = "moneda_codigo"

CLAVE_MONEDA_SIMBOLO = "moneda_simbolo"

CLAVE_MONEDA_FORMATO = "moneda_formato"

CLAVE_MONEDA_MILES = "moneda_separador_miles"

CLAVE_MONEDA_DECIMALES = "moneda_separador_decimales"

# Lo que se escribe si no hay nada guardado. Son
# los MISMOS valores que producía el "$ " escrito
# a mano, para que cambiar a moneda configurable
# no altere ni un pixel de la aplicación.

MONEDA_POR_DEFECTO = {
    "codigo": "USD",
    "simbolo": "$",
    "formato": "simbolo_espacio",
    "separador_miles": ",",
    "separador_decimales": "."
}

DESCRIPCIONES_MONEDA = {
    CLAVE_MONEDA_CODIGO: (
        "Código de la moneda (USD, EUR, MXN...). "
        "Se muestra en los formatos que usan "
        "código en vez de símbolo."
    ),
    CLAVE_MONEDA_SIMBOLO: (
        "Símbolo de la moneda, como $ o €."
    ),
    CLAVE_MONEDA_FORMATO: (
        "Cómo se juntan el símbolo y el importe: "
        "simbolo_espacio, simbolo_pegado, "
        "simbolo_despues, codigo_espacio, "
        "codigo_pegado o codigo_despues."
    ),
    CLAVE_MONEDA_MILES: (
        "Separador de millares. Con ',' son "
        "1,500.00; con '.' son 1.500,00."
    ),
    CLAVE_MONEDA_DECIMALES: (
        "Separador de decimales. Con '.' son "
        "1,500.00; con ',' son 1.500,00."
    )
}


# =============================
# AJUSTES
# =============================

def obtener_configuracion():
    """
    Devuelve la tabla clave/valor como
    diccionario de cadenas.
    """

    conexion = obtener_conexion()
    cursor = conexion.cursor()

    consulta = """
        SELECT clave, valor
        FROM configuracion
    """

    cursor.execute(consulta)

    ajustes = {
        fila[0]: fila[1]
        for fila in cursor.fetchall()
    }

    cursor.close()
    conexion.close()

    return ajustes


def obtener_stock_minimo():
    """
    Umbral de stock bajo.

    Si el valor guardado no es un número
    utilizable, cae al valor por defecto en
    lugar de romper el panel principal.
    """

    ajustes = obtener_configuracion()

    valor = ajustes.get(CLAVE_STOCK_MINIMO)

    if valor is None:

        return STOCK_MINIMO_POR_DEFECTO

    try:

        numero = int(valor)

    except (TypeError, ValueError):

        return STOCK_MINIMO_POR_DEFECTO

    if numero < 0:

        return STOCK_MINIMO_POR_DEFECTO

    return numero


@conexiones_libres
@requiere_permiso(GESTIONAR_CONFIGURACION)
def actualizar_stock_minimo(valor):
    """
    Cambia el umbral de stock bajo y deja la
    entrada en la auditoría.

    Devuelve el valor guardado.
    """

    anterior = obtener_stock_minimo()

    conexion = obtener_conexion()
    cursor = conexion.cursor()

    consulta = """
        INSERT INTO configuracion
        (clave, valor, descripcion)
        VALUES (%s, %s, %s)
        ON DUPLICATE KEY UPDATE valor = %s
    """

    descripcion = (
        "Un vehículo con stock menor o igual a "
        "este valor aparece como stock bajo."
    )

    valores = (
        CLAVE_STOCK_MINIMO,
        str(valor),
        descripcion,
        str(valor)
    )

    cursor.execute(consulta, valores)

    conexion.commit()

    cursor.close()
    conexion.close()

    registrar_accion(
        "configuracion",
        "CONFIGURACION",
        f"Umbral de stock bajo: {anterior} -> {valor}"
    )

    return valor


# =============================
# MONEDA: LECTURA
# =============================

def leer_moneda():
    """
    Los ajustes de moneda tal como están en la
    base, sin aplicar en memoria.

    Devuelve un diccionario con las cinco claves,
    rellenando con los valores por defecto lo que
    falte o no sirva. Nunca lanza: si la tabla no
    está o está corrupta, sale lo de siempre.
    """

    ajustes = dict(MONEDA_POR_DEFECTO)

    try:

        guardado = obtener_configuracion()

    except mysql.connector.Error:

        return ajustes

    codigo = (
        guardado.get(CLAVE_MONEDA_CODIGO)
    )

    if codigo and len(codigo.strip()) <= 10:

        ajustes["codigo"] = codigo.strip()

    simbolo = guardado.get(CLAVE_MONEDA_SIMBOLO)

    if simbolo is not None and len(
            simbolo.strip()
    ) <= 5:

        ajustes["simbolo"] = simbolo.strip()

    formato = guardado.get(CLAVE_MONEDA_FORMATO)

    if formato in FORMATOS_MONEDA:

        ajustes["formato"] = formato

    for clave, nombre in (
        (CLAVE_MONEDA_MILES, "separador_miles"),
        (CLAVE_MONEDA_DECIMALES,
         "separador_decimales")
    ):

        valor = guardado.get(clave)

        if valor and len(valor) == 1:

            ajustes[nombre] = valor

    return ajustes


def obtener_moneda():
    """
    Lee la moneda de la base y la deja aplicada en
    memoria, para que todo lo que se pinte a partir
    de ahora use ese formato.

    La aplicación la llama al arrancar (main.py) y
    ConfiguracionView después de guardar, para no
    depender de que alguien se acuerde.
    """

    from utils import moneda

    ajustes = leer_moneda()

    moneda.aplicar_config(ajustes)

    return ajustes


# =============================
# MONEDA: ESCRITURA
# =============================

@conexiones_libres
@requiere_permiso(GESTIONAR_CONFIGURACION)
def actualizar_moneda(codigo, simbolo, formato,
                      separador_miles,
                      separador_decimales):
    """
    Guarda la configuración de la moneda y la
    aplica en memoria, para que se vea sin
    reiniciar.

    Devuelve (True, "") o (False, motivo).

    Valida antes de escribir: un separador de dos
    caracteres haría que todos los importes de la
    aplicación fueran ambiguos, y eso no se
    descubre leyendo un contrato.
    """

    from utils import moneda

    nuevo = {
        "codigo": (codigo or "").strip(),
        "simbolo": simbolo,
        "formato": formato,
        "separador_miles": separador_miles,
        "separador_decimales": separador_decimales
    }

    valido, mensaje = moneda.validar_config(nuevo)

    if not valido:

        return (False, mensaje)

    if (
        nuevo["separador_miles"]
        == nuevo["separador_decimales"]
    ):

        return (
            False,
            "El separador de miles y el de "
            "decimales no pueden ser el mismo: "
            "el importe no se podría leer."
        )

    anterior = leer_moneda()

    conexion = obtener_conexion()
    cursor = conexion.cursor()

    for clave, valor in (
        (CLAVE_MONEDA_CODIGO, nuevo["codigo"]),
        (CLAVE_MONEDA_SIMBOLO, nuevo["simbolo"]),
        (CLAVE_MONEDA_FORMATO, nuevo["formato"]),
        (CLAVE_MONEDA_MILES,
         nuevo["separador_miles"]),
        (CLAVE_MONEDA_DECIMALES,
         nuevo["separador_decimales"])
    ):

        cursor.execute(
            """
            INSERT INTO configuracion
            (clave, valor, descripcion)
            VALUES (%s, %s, %s)
            ON DUPLICATE KEY UPDATE valor = %s
            """,
            (
                clave,
                str(valor),
                DESCRIPCIONES_MONEDA[clave],
                str(valor)
            )
        )

    conexion.commit()

    cursor.close()
    conexion.close()

    # Se aplica ya, sin esperar al reinicio.

    moneda.aplicar_config(nuevo)

    cambios = []

    for nombre in ("codigo", "simbolo", "formato",
                   "separador_miles",
                   "separador_decimales"):

        if anterior[nombre] != nuevo[nombre]:

            cambios.append(
                f"{nombre}: "
                f"{anterior[nombre]} -> "
                f"{nuevo[nombre]}"
            )

    registrar_accion(
        "configuracion",
        "CONFIGURACION",
        "Moneda actualizada: " + "; ".join(cambios)
    )

    return (True, "")


# =============================
# ESTADO DE LA CONEXIÓN
# =============================

def estado_conexion():
    """
    Comprueba que MySQL responda.

    Devuelve (conectado, detalle).
    """

    try:
        conexion = obtener_conexion()

        cursor = conexion.cursor()

        cursor.execute("SELECT VERSION()")

        version = cursor.fetchone()[0]

        cursor.close()
        conexion.close()

        return True, version

    except mysql.connector.Error as error:

        return False, str(error)
