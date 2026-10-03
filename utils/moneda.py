# ==========================================
# MONEDA
# ==========================================
# Formatea importes. Es el ÚNICO sitio donde
# vive el símbolo de la moneda.
#
# Antes el "$ " estaba escrito dentro de cuatro
# funciones distintas: utils/contrato_pdf.py,
# dos métodos dinero() en la interfaz y otra
# copia local en contrato_form.py. Cuatro copias
# significa que cambiar la moneda obligaba a
# tocar cuatro archivos y era fácil olvidar uno.
# Aquí hay una, y las cuatro usan esta.
#
# ---------------------------------------------------------
# CÓMO SE CONFIGURA
# ---------------------------------------------------------
# Tres ajustes en la tabla configuracion:
#
#   moneda_codigo   "USD"       código ISO
#   moneda_simbolo  "$"         símbolo
#   moneda_formato  "simbolo_espacio"   cómo se juntan
#
# Formatos admitidos:
#
#   simbolo_espacio   $ 1,500.00     <- el de siempre
#   simbolo_pegado    $1,500.00
#   simbolo_despues   1,500.00 $
#   codigo_espacio    USD 1,500.00
#   codigo_pegado     USD1,500.00
#   codigo_despues    1,500.00 USD
#
# Y dos más, por si el separador de miles no es el
# de siempre:
#
#   moneda_separador_miles      ","  -> 1,500.00
#   moneda_separador_decimales  "."  -> 1,500.00
#
# Para euros:  moneda_codigo = EUR, simbolo = EUR,
# formato = simbolo_espacio, separador_miles = "."
# y separador_decimales = ",". Así sale
# "EUR 36.500,00".
#
# ---------------------------------------------------------
# POR QUÉ NO HAY UNA IMPORTACIÓN DE database AQUÍ
# ---------------------------------------------------------
# Los ajustes se leen de la tabla configuracion, que
# vive en database/. Importar desde aquí
# invierte la capa: gui/ y database/ usan utils/,
# no al revés.
#
# La lectura se hace igual, pero con un import
# dentro de la función y solo la PRIMERA vez: a
# partir de ahí manda la caché. main.py la
# calienta al arrancar, así que en la aplicación
# ese import no llega a ejecutarse nunca.
#
# Es la única excepción a "no importes dentro de
# funciones" de todo el proyecto, y está aquí para
# que se sepa por qué.
# ==========================================


# ==========================================
# VALORES POR DEFECTO
# ==========================================

CONFIG_POR_DEFECTO = {
    "codigo": "USD",
    "simbolo": "$",
    "formato": "simbolo_espacio",
    "separador_miles": ",",
    "separador_decimales": "."
}


FORMATOS = [
    "simbolo_espacio",
    "simbolo_pegado",
    "simbolo_despues",
    "codigo_espacio",
    "codigo_pegado",
    "codigo_despues"
]


# ==========================================
# CACHÉ
# ==========================================

# El valor aplicado. None = todavía no se ha
# leído de la base, así que se lee al primer
# formato_dinero().

_config = None


def aplicar_config(config):
    """
    Fija la configuración en memoria.

    La llama database.configuracion al leer los
    ajustes, y ConfiguracionView después de
    guardar. Así un cambio de moneda se ve sin
    reiniciar.
    """

    global _config

    _config = _normalizar(config)


def config_actual():
    """
    La configuración en uso.

    Si todavía no se ha leído de la base, la lee
    ahora. Si tampoco eso funciona (base caída,
    datos iniciales corruptos), cae a los valores
    por defecto: es preferible enseñar un importe
    sin símbolo raro que no enseñar nada.
    """

    global _config

    if _config is not None:

        return _config

    try:

        from database.configuracion import (
            leer_moneda
        )

        _config = _normalizar(leer_moneda())

    except Exception:

        # Cualquier fallo aquí se traga a
        # propósito: formatear un importe nunca
        # debe ser el motivo de que la pantalla no
        # se abra.

        _config = dict(CONFIG_POR_DEFECTO)

    return _config


def olvidar_config():
    """
    Vacía la caché. Solo para las pruebas.
    """

    global _config

    _config = None


def _normalizar(config):
    """
    Rellena lo que falte y descarta lo que no
    sirva. Un ajuste con basura no puede romper la
    aplicación, se ignora.
    """

    limpio = dict(CONFIG_POR_DEFECTO)

    if not isinstance(config, dict):

        return limpio

    codigo = config.get("codigo")

    if codigo and len(str(codigo).strip()) <= 10:

        limpio["codigo"] = str(codigo).strip()

    simbolo = config.get("simbolo")

    if simbolo and len(str(simbolo).strip()) <= 5:

        limpio["simbolo"] = str(simbolo).strip()

    formato = config.get("formato")

    if formato in FORMATOS:

        limpio["formato"] = formato

    for clave in ("separador_miles",
                  "separador_decimales"):

        valor = config.get(clave)

        if valor and len(str(valor)) == 1:

            limpio[clave] = str(valor)

    return limpio


# ==========================================
# FORMATO
# ==========================================

def _es_cero(texto):
    """
    ¿El número formateado es un cero, quitando el
    signo, los separadores y el punto decimal?

    Se usa para no escribir "-$ 0.00".
    """

    limpio = texto.lstrip("-+").replace(",", "")

    limpio = limpio.replace(".", "")

    return all(d == "0" for d in limpio)


def formatear_numero(valor, config=None):
    """
    El número solo, con sus separadores.
    1234.5 -> "1,234.50"
    """

    ajustes = config or config_actual()

    try:

        numero = float(valor)

    except (TypeError, ValueError):

        numero = 0.0

    miles = ajustes["separador_miles"]
    decimales = ajustes["separador_decimales"]

    # ------------------------------
    # PARTE ENTERA Y CENTIMOS
    # ------------------------------
    # La parte entera se TRUNCA, no se redondea.
    #
    # Redondearla daba dos importes mal escritos:
    # 0.99 salía "1.99" y -1500.75 salía "-1501.75",
    # que es peor que no enseñar nada: el cliente
    # leería una cantidad que no es la que se le
    # debe.
    #
    # Se separa primero por millares y luego por
    # decimales, porque hacerlo al revés falla: en
    # "1.234,56" el punto ya no es separador de
    # miles y no se puede volver a buscar.

    negativo = numero < 0

    absoluto = abs(numero)

    # ------------------------------
    # RUTA DIRECTA
    # ------------------------------
    # Con los separadores de siempre se usa el
    # format() de Python y se acaba el asunto.
    #
    # No es una vía rápida: es una garantía. El
    # formato de antes era exactamente
    # format(valor, ",.2f"), y repetirlo da el
    # MISMO resultado byte a byte, incluidos los
    # empates del redondeo en coma flotante
    # (0.995 sale "0.99" en Python y saldría
    # "1.00" armando el número a mano). Montar el
    # entero y los céntimos por separado solo hace
    # falta cuando los separadores cambian.

    por_defecto = (
        miles == CONFIG_POR_DEFECTO["separador_miles"]
        and decimales
        == CONFIG_POR_DEFECTO["separador_decimales"]
    )

    if por_defecto:

        texto = format(numero, ",.2f")

        # format() ya pone el signo, así que aquí no
        # hay que tocarlo... salvo que el número sea
        # tan pequeño que redondee a cero: -0.004 sale
        # "-0.00", que es un negativo cero.

        if numero < 0 and _es_cero(texto):

            return texto.lstrip("-")

        return texto

    entero_num = int(absoluto)

    centimos_num = round((absoluto - entero_num) * 100)

    if centimos_num >= 100:

        # Por ejemplo 0.999 con dos decimales:
        # los céntimos redondean a 100 y hay que
        # llevarlos al entero.

        entero_num += 1

        centimos_num -= 100

    entero = f"{entero_num:,}".replace(",", "\x00")
    entero = entero.replace("\x00", miles)

    if miles == decimales:

        # Con los dos separadores iguales el
        # resultado sería ambiguo ("1.234.56" vs
        # "1.234,56"), así que se avisa con el
        # separador por defecto en vez de
        # imprimir algo que no se puede leer.

        entero = entero.replace(
            miles, CONFIG_POR_DEFECTO["separador_miles"]
        )

    centimos = f"{centimos_num:02d}"

    # Un saldo de -0.004 se redondea a 0, y escribir
    # "-$ 0.00" es un negativo cero que confunde. El
    # signo sale solo si queda algo de verdad detrás,
    # mirando el número ya redondeado.

    cifras = f"{entero}{centimos}".replace(
        miles, ""
    ).replace(" ", "")

    if negativo and not _es_cero(cifras):

        return f"-{entero}{decimales}{centimos}"

    return f"{entero}{decimales}{centimos}"


def formato_dinero(valor, config=None):
    """
    Importe con el símbolo de la moneda.

    Devuelve exactamente "$ 36,500.00" con la
    configuración por defecto, que es lo que se
    ha visto siempre.

    El signo va ANTES de la moneda y no después.
    Antes salía "$ -1,500.75", que se lee como si
    el signo fuera parte de la cifra. Es un
    defecto antiguo, corregido aquí porque un saldo
    ligeramente negativo (por el margen de
    redondeo al saldar una venta) es justo el caso
    en que importa leer bien la cifra.
    """

    ajustes = config or config_actual()

    numero = formatear_numero(valor, ajustes)

    if numero.startswith("-"):

        signo = "-"

        numero = numero[1:]

    else:

        signo = ""

    formato = ajustes["formato"]

    simbolo = ajustes["simbolo"]
    codigo = ajustes["codigo"]

    if formato == "simbolo_pegado":

        return f"{signo}{simbolo}{numero}"

    if formato == "simbolo_despues":

        return f"{signo}{numero} {simbolo}"

    if formato == "codigo_espacio":

        return f"{signo}{codigo} {numero}"

    if formato == "codigo_pegado":

        return f"{signo}{codigo}{numero}"

    if formato == "codigo_despues":

        return f"{signo}{numero} {codigo}"

    return f"{signo}{simbolo} {numero}"


def prefijo_moneda(config=None):
    """
    El texto que va delante de un campo numérico.

    Sale del formato elegido: "$ 1,500.00" deja
    "$ ", pero "1,500.00 $" no deja nada delante y
    el campo se vería sin moneda. Con un código
    sería "USD ".

    Devuelve cadena vacía si el formato pone la
    moneda detrás: prefijarla y además ponerla
    detrás mostraría dos veces.
    """

    ajustes = config or config_actual()

    formato = ajustes["formato"]

    if formato == "simbolo_pegado":

        return ajustes["simbolo"]

    if formato in ("simbolo_despues", "codigo_despues"):

        return ""

    if formato == "codigo_pegado":

        return ajustes["codigo"]

    if formato == "codigo_espacio":

        return f"{ajustes['codigo']} "

    return f"{ajustes['simbolo']} "


# ==========================================
# VALIDACIÓN
# ==========================================

def validar_config(config):
    """
    Comprueba la configuración de la moneda.

    Devuelve (es_valido, mensaje), como el resto
    de validadores del proyecto.

    Va en utils/validaciones.py? No: este módulo
    no importa nada de PySide6 ni de la base, y
    los validadores sí viven allí. Se deja aquí
    porque solo tiene sentido junto a las
    constantes que define.
    """

    if not isinstance(config, dict):

        return (False, "La configuración no es válida.")

    codigo = (config.get("codigo") or "").strip()

    if not codigo:

        return (
            False,
            "El código de moneda no puede estar vacío."
        )

    if len(codigo) > 10:

        return (
            False,
            "El código de moneda es demasiado largo."
        )

    simbolo = config.get("simbolo")

    if simbolo is not None and len(
            str(simbolo).strip()
    ) > 5:

        return (
            False,
            "El símbolo de moneda es demasiado largo."
        )

    formato = config.get("formato")

    if formato not in FORMATOS:

        return (
            False,
            f"'{formato}' no es un formato de moneda "
            "válido."
        )

    for clave, nombre in (
        ("separador_miles", "miles"),
        ("separador_decimales", "decimales")
    ):

        valor = config.get(clave)

        if valor is None or len(str(valor)) != 1:

            return (
                False,
                "El separador de "
                f"{nombre} debe ser un solo carácter."
            )

    return (True, "")
