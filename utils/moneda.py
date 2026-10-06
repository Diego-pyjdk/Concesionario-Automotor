# ==========================================
# MONEDA
# ==========================================
# Formatea importes. Es el ÚNICO sitio del proyecto
# donde vive la moneda: el símbolo, el separador de
# miles, cuántos decimales se muestran y cómo se
# junta el símbolo con la cifra.
#
# Antes el "$ " estaba escrito dentro de cuatro
# funciones distintas: utils/contrato_pdf.py, dos
# métodos dinero() en la interfaz y otra copia local
# en contrato_form.py. Cuatro copias significa que
# cambiar la moneda obligaba a tocar cuatro archivos
# y era fácil olvidar uno. Aquí hay una, y las cuatro
# usan esta.
#
# ---------------------------------------------------------
# LO QUE SE GUARDA, Y LO QUE ES
# ---------------------------------------------------------
# Cinco ajustes en la tabla configuracion:
#
#   moneda_codigo   "USD"   código ISO
#   moneda_simbolo  "$"     símbolo
#   moneda_formato  "simbolo_espacio"
#   moneda_separador_miles     ","
#   moneda_separador_decimales "."
#   moneda_decimals  "2"     cuántos decimales se muestran
#
# ---------------------------------------------------------
# MONEDAS
# ---------------------------------------------------------
# Solo hay dos, y son CATÁLOGO, no texto libre:
#
#   PYG   Guaraní paraguayo   Gs. 1.500        0 decimales
#   USD   Dólar estadounidense   $ 1,500.00       2 decimales
#
# Cada una trae sus cinco atributos, y elegirlas en
# Configuración elige las cinco cosas a la vez. Es lo
# que hace imposible la combinación que antes se
# podía teclear sin darse cuenta: guaraníes con dos
# decimales (el guaraní no tiene subunitario) o
# dólares con punto de miles y coma de decimales.
#
# ---------------------------------------------------------
# POR QUÉ "Gs." Y NO "₲"
# ---------------------------------------------------------
# El símbolo oficial del guaraní es U+20B2, ₲. Aquí se
# usa "Gs." por dos razones:
#
#   1. Las fuentes base-14 de reportlab (Helvetica,
#      Courier) no lo tienen. Los PDF saldrían con un
#      "?" donde debería estar el símbolo, y un
#      contrato con interrogantes en el importe es un
#      documento que no se puede defender.
#
#   2. ₲ no está en cp1252, que es lo que hay detrás
#      de WinAnsiEncoding. Habría que incrustar una
#      fuente de verdad solo para un signo.
#
# "Gs." es como se escribe de todas formas en un
# documento de este país, así que no se pierde nada.
#
# ---------------------------------------------------------
# POR QUÉ EL GUARANÍ NO TIENE DECIMALES
# ---------------------------------------------------------
# Porque no tiene subunitario en la práctica: no hay
# moneda fraccionaria que circula, y los precios se
# escriben en números enteros. Poner "Gs. 1.500,00"
# inventa una precisión que no existe, y un contador
# que mole a "Gs. 1.500,00" y a "Gs. 1.500" por igual
# tiene dos cifras distintas para lo mismo.
#
# El redondeo es a la hora de MOSTRAR. En la base los
# importes siguen siendo DECIMAL(15,2): si alguien
# teclea 1500,50 en guaraníes, se guarda y se muestra
# como 1.501. El truncamiento ya se aplicaba antes para
# no escribir un céntimo que no existe, pero en una
# moneda sin céntimos truncar 1.499,90 a "1.499"
# estaría exagerando la deuda. Redondear es lo
# correcto cuando no hay a quién pagar un medio.
#
# ---------------------------------------------------------
# POR QUÉ NO HAY UNA IMPORTACIÓN DE database AQUÍ
# ---------------------------------------------------------
# Los ajustes se leen de la tabla configuracion, que
# vive en database/. Importar desde aquí invierte la
# capa: gui/ y database/ usan utils/, no al revés.
#
# La lectura se hace igual, pero con un import dentro
# de la función y solo la PRIMERA vez: a partir de ahí
# manda la caché. main.py la calienta al arrancar, así
# que en la aplicación ese import no llega a
# ejecutarse nunca.
#
# Es la única excepción a "no importes dentro de
# funciones" de todo el proyecto, y está aquí para que
# se sepa por qué.
# ==========================================


# ==========================================
# EL CATÁLOGO
# ==========================================

MONEDAS = {
    "PYG": {
        "codigo": "PYG",
        "nombre": "Guaraní paraguayo",
        "simbolo": "Gs.",
        "formato": "simbolo_espacio",
        "separador_miles": ".",
        "separador_decimales": "",
        "decimales": 0
    },
    "USD": {
        "codigo": "USD",
        "nombre": "Dólar estadounidense",
        "simbolo": "$",
        "formato": "simbolo_espacio",
        "separador_miles": ",",
        "separador_decimales": ".",
        "decimales": 2
    }
}

CODIGOS = list(MONEDAS.keys())


def nombre_de(codigo):
    """
    El nombre legible de una moneda, o el código si no
    la conocemos.
    """

    entrada = MONEDAS.get(str(codigo or "").strip().upper())

    if not entrada:

        return str(codigo or "") or "—"

    return entrada["nombre"]


# ==========================================
# VALORES POR DEFECTO
# ==========================================
# Los del dólar, que es lo que se ha visto siempre.
# Con esta configuración, formato_dinero() da byte a
# byte lo mismo que daba antes de existir este módulo:
# los atajos de redondeo de Python y los de aquí
# coinciden también en los empates.

CONFIG_POR_DEFECTO = {
    "codigo": "USD",
    "simbolo": "$",
    "formato": "simbolo_espacio",
    "separador_miles": ",",
    "separador_decimales": ".",
    "decimales": 2
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
# TECLADO
# ==========================================
# ------------------------------
# POR QUÉ UN TOPE DE 13 CIFRAS
# ------------------------------
# Las columnas de dinero son DECIMAL(15,2): 13 cifras
# enteras. El tope de los campos coincide con ese
# techo, porque un campo que deja escribir 15.000
# millones y una base que no los guarda es peor que un
# campo que avisa: el dato se pierde al guardar, y se
# pierde sin avisar.
#
# El tope BAJO sería 999.999.999, que es lo que había
# antes. En guaraníes un vehículo normal cuesta entre
# 30 y 100 millones, así que ese tope estaba a un paso
# de biting el caso corriente, no el extremo.

DIGITOS_MAXIMOS = 13

MAXIMO_IMPORTE = 10 ** DIGITOS_MAXIMOS - 1 + 0.99

IMPORTE_MAXIMO_DECIMALES = 2


# ==========================================
# CACHÉ
# ==========================================
# El valor aplicado. None = todavía no se ha leído de
# la base, así que se lee al primer formato_dinero().

_config = None


def aplicar_config(config):
    """
    Fija la configuración en memoria.

    La llama database.configuracion al leer los
    ajustes, y ConfiguracionView después de guardar.
    Así un cambio de moneda se ve sin reiniciar.
    """

    global _config

    _config = _normalizar(config)


def config_actual():
    """
    La configuración en uso.

    Si todavía no se ha leído de la base, la lee ahora.
    Si tampoco eso funciona (base caída, datos
    iniciales corruptos), cae a los valores por
    defecto: es preferible enseñar un importe sin
    símbolo raro que no enseñar nada.
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

        # Cualquier fallo aquí se traga a propósito:
        # formatear un importe nunca debe ser el motivo
        # de que la pantalla no se abra.

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
    Rellena lo que falte y descarta lo que no sirva.
    Un ajuste con basura no puede romper la
    aplicación, se ignora.
    """

    limpio = dict(CONFIG_POR_DEFECTO)

    if not isinstance(config, dict):

        return limpio

    codigo = config.get("codigo")

    if codigo and len(str(codigo).strip()) <= 10:

        limpio["codigo"] = str(codigo).strip().upper()

    simbolo = config.get("simbolo")

    if simbolo is not None and len(
            str(simbolo).strip()) <= 5:

        limpio["simbolo"] = str(simbolo).strip()

    formato = config.get("formato")

    if formato in FORMATOS:

        limpio["formato"] = formato

    for clave in (
        "separador_miles",
        "separador_decimales"
    ):

        valor = config.get(clave)

        if valor is None:

            continue

        if clave == "separador_decimales":

            # Cadena vacía es válida: significa que la
            # moneda no muestra decimales. Antes esto se
            # confundía con "viene vacío", y por eso
            # una moneda sin decimales no se podía
            # guardar.

            if valor == "":

                limpio[clave] = ""

            elif len(str(valor)) == 1:

                limpio[clave] = str(valor)

        elif len(str(valor)) == 1:

            limpio[clave] = str(valor)

    decimales = config.get("decimales")

    try:

        numero = int(decimales)

    except (TypeError, ValueError):

        numero = None

    if numero is not None and 0 <= numero <= 6:

        limpio["decimales"] = numero

    return limpio


def config_de(codigo):
    """
    Los ajustes de UNA moneda concreta, por su código.

    Es lo que permite que un contrato histórico siga
    enseñándose con la moneda con la que se firmó, sin
    que el cambio de configuración lo reescriba:

        formato_dinero(25000, moneda=contrato["moneda"])

    Si el código no está en el catálogo (una moneda
    guardada de una versión anterior, o un texto mal
    puesto a mano) cae a la configuración EN USO, que
    es lo mejor que se puede hacer sin inventar un
    formato.
    """

    entrada = MONEDAS.get(str(codigo or "").strip().upper())

    if not entrada:

        return config_actual()

    return dict(entrada)


# ==========================================
# FORMATO
# ==========================================

def _es_cero(texto):
    """
    ¿El número formateado es un cero, quitando el
    signo y los separadores?

    Se usa para no escribir "-$ 0.00" ni "-Gs. 0".

    Se quitan los dos separadores y, con ello, todos
    los puntos, incluido el decimal. Es lo único que
    funciona cuando los dos son distintos y cuando la
    moneda no tiene decimales.
    """

    limpio = texto.lstrip("-+")

    for simbolo in (
        config_actual()["separador_miles"],
        config_actual()["separador_decimales"],
        ",",
        "."
    ):

        limpio = limpio.replace(simbolo, "")

    return all(
        d == "0" for d in limpio
        if d.isdigit()
    )


def _partes(valor, decimales):
    """
    Separa un número en (entero, decimales) ya
    redondeados, como cadenas sin signo.

    Se separa primero por millares y luego por
    decimales, porque hacerlo al revés falla: en
    "1.234,56" el punto ya no es separador de miles y
    no se puede volver a buscar.
    """

    negativo = valor < 0

    absoluto = abs(valor)

    factor = 10 ** decimales

    # ------------------------------
    # REDONDEAR MEDIO ARRIBA, NO AL
    # EMPARE
    # ------------------------------
    # `round()` en Python empata al par: round(1500.5)
    # es 1500, porque 1500 es par. Eso es lo correcto
    # en matemáticas y lo INCORRECTO en dinero, donde un
    # medio siempre se va hacia arriba.
    #
    # En guaraníes no hay medio: el redondeo es al
    # entero entero. Sumar medio antes de truncar lo
    # convierte en el "medio arriba" que se espera al
    # contar un importe, en lugar del redondeo bancario
    # que nadie espera en una factura.
    #
    # Solo afecta a las monedas sin la ruta corta: con
    # los separadores de siempre y dos decimales entra
    # `format()`, que ya lo hace bien (y que además
    # resuelve los empates como Python, que es lo que
    # ha visto siempre el usuario).

    escalado = int(absoluto * factor + 0.5)

    entero = escalado // factor

    resto = escalado - entero * factor

    texto_entero = f"{entero:,}".replace(",", "\x00")

    if decimales:

        texto_decimales = f"{resto:0{decimales}d}"

    else:

        texto_decimales = ""

    return (negativo, texto_entero, texto_decimales)


def _ajustes(config):
    """
    Los ajustes que hay que usar, ya completos.

    ------------------------------
    # POR QUÉ NORMALIZA SIEMPRE
    # ------------------------------

    Porque `config` es un diccionario que puede venir
    de tres sitios: de la caché (completo), del
    catálogo (completo) o de una llamada suelta que
    solo quiere cambiar una cosa:

        formato_dinero(1234.5, {"separador_miles": "."})

    Antes de las seis claves eso reventaba con un
    `KeyError: 'decimales'` en la pantalla, al pintar
    un importe. Un formateador que necesita que le
    pases las seis claves no se puede usar para probar
    un cambio.

    `_normalizar()` rellena lo que falte con los
    valores por defecto. No es que "avise de que no
    puede": es que un importe siempre sale.

    Y no se llama a `config_actual()` si ya viene un
    diccionario, así que probar una moneda no cambia
    la de la aplicación.
    """

    if config is None:

        return config_actual()

    return _normalizar(config)


def formatear_numero(valor, config=None):
    """
    El número solo, con sus separadores y sus
    decimales.

        USD   1234.5  ->  "1,234.50"
        PYG   1500    ->  "1.500"

    `config` es un diccionario de ajustes. Si no se
    pasa, usa la moneda en curso.
    """

    ajustes = _ajustes(config)

    try:

        numero = float(valor)

    except (TypeError, ValueError):

        numero = 0.0

    miles = ajustes["separador_miles"]
    marca = ajustes["separador_decimales"]
    decimales = ajustes["decimales"]

    # ------------------------------
    # LA RUTA DE SIEMPRE IGUAL
    # ------------------------------
    # Con los separadores de siempre y dos decimales se
    # usa el `format()` de Python y se acaba el asunto.
    #
    # No es una vía rápida: es una garantía. El formato
    # de antes era exactamente `format(valor, ",.2f")`, y
    # repetirlo da el MISMO resultado byte a byte,
    # incluidos los empates del redondeo en coma
    # flotante:
    #
    #     format(0.995, ",.2f")  ->  "0.99"
    #     round(0.995 * 100)     ->  100  ->  "1.00"
    #
    # Armar el entero y los céntimos por separado
    # resuelve los empates distinto que Python, y eso
    # salía en pantalla como importes mal escritos
    # ("0.99" se veía "1.99"). Por eso esta
    # comprobación va ANTES de construir nada a mano: es
    # el motivo de que con dólares no haya cambiado ni
    # un byte.
    #
    # Solo se construye a mano cuando la moneda cambia
    # de verdad: separadores distintos, o una moneda sin
    # decimales, que antes no se podía ni expresar.

    igual_que_siempre = (
        miles == CONFIG_POR_DEFECTO["separador_miles"]
        and marca == CONFIG_POR_DEFECTO["separador_decimales"]
        and decimales == CONFIG_POR_DEFECTO["decimales"]
    )

    if igual_que_siempre:

        texto = format(numero, ",.2f")

        if numero < 0 and _es_cero(texto):

            return texto.lstrip("-")

        return texto

    negativo, entero, ceros = _partes(numero, decimales)

    entero = entero.replace("\x00", miles)

    if miles == marca and marca:

        # Con los dos separadores iguales el resultado
        # sería ambiguo ("1.234.56" vs "1.234,56"), así
        # que se avisa con el separador por defecto en
        # vez de imprimir algo que no se puede leer.

        entero = entero.replace(
            miles, CONFIG_POR_DEFECTO["separador_miles"]
        )

    texto = f"{entero}{marca}{ceros}"

    # Un saldo de -0.004 se redondea a 0, y escribir
    # "-$ 0.00" es un negativo cero que confunde. El
    # signo sale solo si queda alguna cifra de verdad
    # detrás.

    if negativo and not _es_cero(texto):

        return f"-{texto}"

    return texto


def formato_dinero(valor, config=None, moneda=None):
    """
    Importe con el símbolo de la moneda. LA función
    que se usa en todas partes.

        USD  1234.5  ->  "$ 1,234.50"
        PYG  1500    ->  "Gs. 1.500"

    ------------------------------
    # EL SEGUNDO PARÁMETRO
    # ------------------------------

    `moneda` es el CÓDIGO de una moneda concreta
    (la que trae `contratos.moneda`), y tiene prioridad
    sobre `config` y sobre la moneda en curso.

    Es lo que evita que un contrato histórico cambie de
    abajo arriba: si está guardado como USD, se
    enseñará con dólares aunque el concesionario haya
    pasado a guaraníes. Un contrato firmado dice lo
    que decía, y reescribir su presentación porque
    alguien cambió un ajuste es exactamente el defecto
    que un documento firmado no puede tener.
    """

    if moneda:

        ajustes = config_de(moneda)

    elif config:

        ajustes = _ajustes(config)

    else:

        ajustes = config_actual()

    numero = formatear_numero(valor, ajustes)

    signo = ""

    if numero.startswith("-"):

        signo = "-"

        numero = numero[1:]

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


def prefijo_moneda(config=None, moneda=None):
    """
    El texto que va delante de un campo numérico.

    Sale del formato elegido: "$ 1,500.00" deja "$ ",
    pero "1,500.00 $" no deja nada delante y el campo se
    vería sin moneda. Con un código sería "USD ".

    Devuelve cadena vacía si el formato pone la moneda
    detrás: prefijarla y además ponerla detrás
    mostraría dos veces.
    """

    if moneda:

        ajustes = config_de(moneda)

    else:

        ajustes = _ajustes(config)

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
# LEER UN IMPORTE ESCRITO
# ==========================================
# Al revés que formatear: pasar de lo que hay escrito
# a un número. Lo que se escribe NO tiene por qué
# tener el formato de la moneda en curso, porque puede
# venir de un PDF, de un correo o de una persona que
# escribe como se le da la gana.

# Lo que se acepta siempre, salga la moneda que salga:
#   "Gs. 1.500"      "1.500"      "1,500"
#   "$ 1,500.00"     "1500"       "1500,50"
#
# Lo que NO se acepta, porque no se puede saber qué
# significa:
#   "1.500,50"       (punto de miles con coma de
#                     decimales: ¿mil quinientos con
#                     cincuenta, o uno coma cinco
#                     millones?)


# Lo que NO es cifra, separador ni signo y se quita
# antes de decidir nada: el símbolo de la moneda
# ("Gs.", "$") y su código ("PYG", "USD").
#
# Se quita por LISTA NEGRA y no por lista de letras,
# porque el símbolo no tiene por qué ser una letra:
# "$" no lo es. Con una lista de letras, "$ 1,500.00"
# llegaba entero hasta el final y `Decimal("$ 150000")`
# reventaba: el texto que produce `formato_dinero()`
# en dólares no se podía volver a leer, que es
# exactamente para lo que sirve esta función.
#
# Se deja el signo porque un saldo en negativo tiene
# que seguir siendo negativo.

QUITAR_NO_NUMERO = str.maketrans(
    "",
    "",
    "abcdefghijklmnopqrstuvwxyz"
    "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    "$€£¥₲"
    " "
)


def _es_millares(limpio, separador):
    """
    ¿El texto son grupos de millares bien formados?

    "1.234.567" sí, y "1.234.567.89" no: el último
    grupo tiene dos cifras.

    Sin esta comprobación, "1.2.3" se leía como 123 y
    "1.23.456" como 123.456: dos números inventados a
    partir de una errata, y en silencio. Un importe mal
    leído es peor que uno que no se entiende, porque no
    avisa de que esté mal.
    """

    grupos = limpio.split(separador)

    if len(grupos) < 2:

        return False

    if not grupos[0] or not grupos[0].isdigit():

        return False

    for grupo in grupos[1:]:

        if not grupo.isdigit() or len(grupo) != 3:

            return False

    return True


def parsear_importe(texto, config=None):
    """
    Lee un importe escrito y lo devuelve como Decimal.

    Devuelve None si no se puede leer. NO lanza
    excepciones: el que llama decide qué hacer con un
    texto que no es un número.

    ------------------------------
    # POR QUÉ ESTE NOMBRE Y NO OTRO
    # ------------------------------

    Porque este texto lo produce `formatear_numero()`
    en otro sitio y hay que poder deshacerlo sin
    adivinar.

    La versión anterior de esto estaba escrita en dos
    sitios, y en los dos con el separador de miles
    COSIDO A LA COMA:

        float(datos[4].replace(",", ""))

    Ese era el punto más frágil de la aplicación: con
    guaraníes, que usan el punto de miles, "25.000.000"
    no se parsea, y el "Editar" de cualquier vehículo
    de más de 999 reventaba con un ValueError. Y si
    alguien lo cambiaba por `replace(".", "")` sin
    pensar, "25.000.000" se leía como 25. Un error
    silencioso que vale mil veces menos.

    Aquí se decide por la FORMA del texto, no por lo
    que haya escrito quien llama:

      - Si hay punto Y coma, el punto es de miles
        (porque un número no lleva dos puntos).
      - Si hay coma Y punto, la coma es de miles.
      - Si hay dos puntos, es ambigüedad y no se
        admite: es preferible decir que no se entiende
        antes que devolver una cifra mil veces menor.

    Se acepta como separador de miles el espacio y el
    apóstrofo, porque es como escribe mucha gente y
    no cambia el valor.
    """

    from decimal import (
        Decimal,
        InvalidOperation
    )

    if texto is None:

        return None

    if isinstance(texto, (int, float, Decimal)):

        return Decimal(str(texto))

    limpio = str(texto).strip()

    if not limpio:

        return None

    # El signo se queda: un saldo en negativo tiene
    # que seguir siendo negativo.

    if limpio.startswith("-"):

        signo = "-"
        limpio = limpio[1:]

    elif limpio.endswith("-"):

        signo = "-"
        limpio = limpio[:-1]

    else:

        signo = ""

    # ------------------------------
    # 1. EL NÚMERO, Y SOLO EL NÚMERO
    # ------------------------------
    # Se quita el símbolo de la moneda, su código y los
    # espacios. `translate()` con la tabla de arriba
    # quita esos caracteres y devuelve el resto: no hay
    # que recorrerlos uno a uno, que es lo que se hacía
    # antes con la lista de letras, y el resultado era
    # dejar el texto SIN quitar nada, que es lo
    # contrario de lo que decía la variable. Con aquel
    # error, "40000" se quedaba sin cifras y la función
    # devolvía None para cualquier importe escrito.
    #
    # Y se empieza por la PRIMERA CIFRA, no por el
    # principio: "Gs." deja un punto suelto detrás, y
    # "1.500" con un punto delante se leía como
    # separador de miles mal formado en vez de 1.500.
    # El símbolo de una moneda puede llevar punto
    # ("Gs."), y ese punto no forma parte del número.

    limpio = limpio.translate(QUITAR_NO_NUMERO)

    limpio = limpio.replace("'", "")

    limpio = limpio.replace("\t", "")

    if not limpio:

        return None

    inicio = None

    for posicion, caracter in enumerate(limpio):

        if caracter.isdigit():

            inicio = posicion

            break

    if inicio is None:

        return None

    limpio = limpio[inicio:]

    # ------------------------------
    # 2. EL ÚLTIMO SEPARADOR ES EL
    # DECIMAL
    # ------------------------------
    # Por la FORMA, no por la configuración: este texto
    # puede venir de un PDF, de un correo o de alguien
    # que escribe como se le da la gana.
    #
    # Y la regla es una sola, y es correcta porque en un
    # número el separador decimal va DESPUÉS del de
    # miles:
    #
    #     "1.500,00"   el último es la coma  -> 1500.00
    #     "1,500.00"   el último es el punto -> 1500.00
    #
    # Antes esta decisión comparaba CUÁNTAS veces
    # aparecía cada uno, que en "1,500.00" da uno y uno y
    # no dice nada, y el resultado era 1.50000: un
    # número mil veces menor, en silencio.
    #
    # Con un solo separador, la misma regla dice que es
    # el decimal, salvo que lo que vaya detrás tenga
    # exactamente tres cifras: "1.500" son mil quinientos
    # y "1500,00" son mil quinientos con cincuenta.

    if not _es_millares(limpio, ".") and (
        "," not in limpio
    ):

        # Varios puntos y ningún otro separador: solo
        # pueden ser de miles.

        if limpio.count(".") > 1:

            if not _es_millares(limpio, "."):

                return None

            limpio = limpio.replace(".", "")

    if "," in limpio and "." in limpio:

        if limpio.rfind(",") > limpio.rfind("."):

            limpio = limpio.replace(".", "")

            limpio = limpio.replace(",", ".")

        else:

            limpio = limpio.replace(",", "")

    elif "," in limpio:

        partes = limpio.split(",")

        if len(partes) > 2:

            if not _es_millares(limpio, ","):

                return None

            limpio = limpio.replace(",", "")

        elif len(partes[1]) == 3 and partes[0]:

            # "1,500" son mil quinientos.

            limpio = limpio.replace(",", "")

        else:

            limpio = limpio.replace(",", ".")

    elif limpio.count(".") > 1:

        if not _es_millares(limpio, "."):

            return None

        limpio = limpio.replace(".", "")

    elif "." in limpio:

        partes = limpio.split(".")

        if len(partes[1]) == 3 and partes[0].isdigit():

            # "1.500" son mil quinientos.

            limpio = limpio.replace(".", "")

    try:

        return Decimal(signo + limpio)

    except (InvalidOperation, ValueError):

        return None


def es_importe(texto, config=None):
    """
    ¿Lo escrito es un importe legible?

    Devuelve (es_valido, mensaje), como el resto de
    validadores del proyecto.
    """

    if parsear_importe(texto, config) is None:

        return (
            False,
            "No se entiende como número. Se admite "
            "el punto o la coma como separador de "
            "miles, pero no los dos a la vez."
        )

    return (True, "")


# ==========================================
# PARA LOS CAMPOS DE ESCRITURA
# ==========================================

def decimales_de_teclado(config=None):
    """
    Cuántos decimales puede escribir el usuario.

    Es `decimales` con un mínimo de 1, porque
    `QDoubleSpinBox` con 0 decimales y `singleStep` 1
    no deja escribir nada que no sea entero y en
    algunos estilos se ve raro al teclear.

    La moneda sin decimales NO se recorta aquí: el
    campo acepta el número entero que es lo que se
    escribe, y el redondeo a la hora de mostrar lo
    hace `formatear_numero()`.
    """

    ajustes = _ajustes(config)

    return max(1, int(ajustes["decimales"]))


def paso_de_teclado(config=None):
    """
    De cuánto en cuánto salta la flechita del campo.

    En guaraníes un salto de 100 va de 100.000 a
    100.100, y para llegar al siguiente millón hay
    que pulsarla cientos de veces. Un salto de
    100.000 va directo de un millón al siguiente,
    que es como se recorre una lista de precios.
    En dólares el salto de 100 es razonable.
    """

    ajustes = _ajustes(config)

    if int(ajustes["decimales"]) == 0:

        return 100000.0

    return 100.0


def maximo_teclado(config=None):
    """
    El tope que pueden escribir los campos.

    Es el de la base, no un número inventado: un campo
    que deja escribir más de lo que MySQL guarda
    pierde el dato al guardar, y sin avisar.
    """

    return MAXIMO_IMPORTE


# ==========================================
# VALIDACIÓN
# ==========================================

def validar_config(config):
    """
    Comprueba la configuración de la moneda.

    Devuelve (es_valido, mensaje), como el resto de
    validadores del proyecto.

    Va en utils/validaciones.py? No: este módulo no
    importa nada de PySide6 ni de la base, y los
    validadores sí viven allí. Se deja aquí porque solo
    tiene sentido junto a las constantes que define.
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

        if valor is None:

            return (
                False,
                "El separador de "
                f"{nombre} debe ser un solo carácter."
            )

        if clave == "separador_decimales":

            # Vacío es válido: es lo que dice que la
            # moneda no usa decimales.

            if len(str(valor)) > 1:

                return (
                    False,
                    "El separador de decimales debe "
                    "ser un solo carácter, o ninguno si "
                    "la moneda no usa decimales."
                )

        elif len(str(valor)) != 1:

            return (
                False,
                "El separador de "
                f"{nombre} debe ser un solo carácter."
            )

    try:

        numero = int(config.get("decimales"))

    except (TypeError, ValueError):

        return (
            False,
            "La cantidad de decimales debe ser un "
            "número."
        )

    if not 0 <= numero <= 6:

        return (
            False,
            "La cantidad de decimales debe estar "
            "entre 0 y 6."
        )

    return (True, "")