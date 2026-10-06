import mysql.connector

from database.conexion import (
    conexiones_libres,
    obtener_conexion
)

from database.auditoria import registrar_accion

from utils.moneda import (
    FORMATOS as FORMATOS_MONEDA,
    MONEDAS,
    config_de,
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

VERSION_SISTEMA = "1.2.1"

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

# ------------------------------
# CUÁNTOS DECIMALES SE MUESTRAN
# ------------------------------
# Es la sexta clave, y la que hace posible el guaraní:
# sin ella el sistema es estructuralmente de dos
# decimales, y "Gs. 1.500,00" es un formato que no
# existe. Se guarda como texto porque la tabla
# configuracion es de clave/valor y no distingue.

CLAVE_MONEDA_CIFRAS = "moneda_cifras"

# ------------------------------
# LAS MONEDAS, Y POR QUÉ NO SE
# ESCRIBEN A MANO
# ------------------------------
# Solo dos: guaraní y dólar. Vienen del catálogo de
# utils/moneda.py, que es donde viven el símbolo, los
# separadores y los decimales de cada una.
#
# Elegir una moneda elige LAS CINCO COSAS a la vez. Es
# lo que hace imposible lo que antes se podía teclear
# sin darse cuenta: guaraníes con dos decimales, o
# dólares con el punto de miles. Cada una de esas
# combinaciones produce importes que no se pueden leer,
# y se descubren en un contrato, no en la pantalla.

MONEDA_POR_DEFECTO = {
    "codigo": "USD",
    "simbolo": "$",
    "formato": "simbolo_espacio",
    "separador_miles": ",",
    "separador_decimales": ".",
    "decimales": 2
}

DESCRIPCIONES_MONEDA = {
    CLAVE_MONEDA_CODIGO: (
        "Moneda de la aplicación: PYG o USD. El "
        "símbolo, los separadores y los decimales "
        "salen del catálogo, no se escriben a mano."
    ),
    CLAVE_MONEDA_SIMBOLO: (
        "Símbolo de la moneda."
    ),
    CLAVE_MONEDA_FORMATO: (
        "Cómo se juntan el símbolo y el importe."
    ),
    CLAVE_MONEDA_MILES: (
        "Separador de millares."
    ),
    CLAVE_MONEDA_DECIMALES: (
        "Separador de decimales. Vacío si la moneda "
        "no usa decimales."
    ),
    CLAVE_MONEDA_CIFRAS: (
        "Cuántos decimales se muestran. El "
        "guaraní no tiene subunitario: 0."
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

        # El separador de decimales puede venir vacío
        # a propósito: es lo que dice que la moneda no
        # usa decimales. Antes un vacío se tomaba por
        # "no guardado" y se caía al valor por defecto,
        # así que una moneda sin decimales no se podía
        # guardar.

        if valor is None:

            continue

        if valor == "" and nombre == "separador_decimales":

            ajustes[nombre] = ""

        elif len(valor) == 1:

            ajustes[nombre] = valor

    # ------------------------------
    # LOS DECIMALES
    # ------------------------------
    # Se leen de la clave nueva. Si no está (una base
    # instalada antes de esta versión) se deducen del
    # separador de decimales: si está vacío, cero.

    try:

        ajustes["decimales"] = int(
            guardado.get(CLAVE_MONEDA_CIFRAS)
        )

    except (TypeError, ValueError):

        if ajustes["separador_decimales"] == "":

            ajustes["decimales"] = 0

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
def actualizar_moneda(codigo):
    """
    Cambia la moneda de la aplicación.

    Recibe SOLO el código ("PYG" o "USD") y saca el
    símbolo, el formato, los dos separadores y los
    decimales del catálogo de `utils/moneda.py`.

    ------------------------------
    # POR QUÉ UN ARGUMENTO Y NO CINCO
    # ------------------------------

    Porque las cinco cosas van juntas y no se pueden
    elegir por separado sin producir importes que no se
    pueden leer: guaraníes con dos decimales, o dólares
    con el punto de miles. Antes quien configuraba
    tecleaba el símbolo y elegía los separadores de dos
    desplegables, y el resultado era una mezcla que
    parecía válida y no lo era. Se descubría leyendo
    un contrato.

    Un desplegable con dos opciones no se equivoca.

    ------------------------------
    # NO CONVIERTE NADA
    # ------------------------------

    Esto cambia cómo se MUESTRAN e INTERPRETAN los
    importes. No toca ni un valor de `ventas`,
    `contratos`, `cuotas` ni `pagos`, y no calcula
    ningún tipo de cambio.

    Es lo correcto y no es un recorte: convertir un
    contrato firmado exige una fecha, una fuente y una
    tasa que aquí no hay. Un "Gs. 25.000" que en
    realidad son 25.000 dólares es peor que un importe
    sin moneda.

    Los contratos que ya tienen `moneda` guardada
    siguen enseñándose con la suya, así que este ajuste
    no reescribe documentos firmados.

    Devuelve (True, "") o (False, motivo).
    """

    from utils import moneda

    clave = str(codigo or "").strip().upper()

    if clave not in MONEDAS:

        return (
            False,
            f"'{clave}' no es una moneda disponible. "
            "Las que hay: "
            + ", ".join(MONEDAS.keys())
            + "."
        )

    nuevo = config_de(clave)

    valido, mensaje = moneda.validar_config(nuevo)

    if not valido:

        return (False, mensaje)

    anterior = leer_moneda()

    conexion = obtener_conexion()
    cursor = conexion.cursor()

    for nombre, clave_ajuste in (
        ("codigo", CLAVE_MONEDA_CODIGO),
        ("simbolo", CLAVE_MONEDA_SIMBOLO),
        ("formato", CLAVE_MONEDA_FORMATO),
        ("separador_miles", CLAVE_MONEDA_MILES),
        ("separador_decimales", CLAVE_MONEDA_DECIMALES),
        ("decimales", CLAVE_MONEDA_CIFRAS)
    ):

        valor = str(nuevo[nombre])

        cursor.execute(
            """
            INSERT INTO configuracion
            (clave, valor, descripcion)
            VALUES (%s, %s, %s)
            ON DUPLICATE KEY UPDATE valor = %s
            """,
            (
                clave_ajuste,
                valor,
                DESCRIPCIONES_MONEDA[clave_ajuste],
                valor
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
                   "separador_decimales", "decimales"):

        if anterior.get(nombre) != nuevo[nombre]:

            cambios.append(
                f"{nombre}: "
                f"{anterior.get(nombre)} -> "
                f"{nuevo[nombre]}"
            )

    if not cambios:

        # Se guardó lo mismo que ya había. Se dice igual,
        # porque quien apretó el botón quiere una
        # confirmación, no un silencio que parece un fallo.

        cambios = ["sin cambios"]

    registrar_accion(
        "configuracion",
        "CONFIGURACION",
        "Moneda actualizada a "
        f"{clave} ({moneda.nombre_de(clave)}): "
        + "; ".join(cambios)
        + ". No se convierte ningún importe."
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
