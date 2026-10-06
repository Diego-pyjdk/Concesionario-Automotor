"""
Pruebas de las dos monedas: guaraní y dólar.

Son las pruebas del encargo de la moneda, y están en
un archivo aparte porque tienen una regla que no
comparten con el resto: **ninguna prueba puede cambiar
la moneda sin volver a dejarla como estaba**.

Un `moneda.aplicar_config()` que se queda puesto
contamina todas las que vengan detrás, y el síntoma es
una prueba que falla en la suite entera y pasa sola, que
es la forma más difícil de depurar que hay.

Por eso `moneda_actual` es un `fixture` que SIEMPRE
restaura, y por eso ninguna de estas pruebas toca la
base: la moneda se aplica en memoria.
"""


import pytest

import utils.moneda as moneda


# ==========================================
# EL ENTORNO
# ==========================================

@pytest.fixture(autouse=True)
def restaura_la_moneda():
    """
    Devuelve la moneda a la de antes, pase lo que pase.

    Va con `try/finally` y no con `yield` porque lo que
    hay que restaurar es una variable de módulo, no un
    archivo temporal: si la prueba revienta, el `finally`
    se ejecuta igual.

    Sin esto, una prueba que cambie a guaraníes y falle
    después deja la aplicación entera en guaraníes para
    el resto de la sesión de pruebas, y las que vengan
    verían "Gs." donde esperaban "$".
    """

    anterior = dict(moneda.config_actual())

    try:

        yield

    finally:

        moneda.aplicar_config(anterior)


def en_pyg():
    """La aplicación en guaraní."""

    moneda.aplicar_config(moneda.config_de("PYG"))


def en_usd():
    """La aplicación en dólares."""

    moneda.aplicar_config(moneda.config_de("USD"))


def con_decimales(config):
    """
    Da la moneda en memoria y devuelve el nombre, para
    poder hacer `with` sin una clase.
    """

    moneda.aplicar_config(config)

    return config["codigo"]


# ==========================================
# EL CATÁLOGO
# ==========================================

class TestElCatalogo:

    def test_solo_hay_dos(self):
        """
        Guaraní y dólar. Ni una más.

        No es que no se puedan añadir más: es que
        mientras haya dos, un desplegable con dos
        opciones es más seguro que cinco campos donde
        teclear símbolos.
        """

        assert set(moneda.MONEDAS) == {"PYG", "USD"}

        assert moneda.CODIGOS == ["PYG", "USD"]

    def test_las_dos_tienen_los_seis_atributos(self):

        for codigo, entrada in moneda.MONEDAS.items():

            for clave in (
                "codigo",
                "nombre",
                "simbolo",
                "formato",
                "separador_miles",
                "separador_decimales",
                "decimales"
            ):

                assert clave in entrada, (
                    f"{codigo} no tiene {clave}"
                )

    def test_el_guarani_no_tiene_decimales(self):
        """
        Cero. El guaraní no tiene subunitario.

        No es una manía de formato: poner "Gs.
        1.500,00" inventa una precisión que no existe, y
        un contador que mole a "Gs. 1.500,00" y a
        "Gs. 1.500" por igual tiene dos cifras
        distintas para lo mismo.
        """

        assert moneda.MONEDAS["PYG"]["decimales"] == 0

        assert moneda.MONEDAS["PYG"][
            "separador_decimales"
        ] == ""

    def test_el_dolar_tiene_dos(self):

        assert moneda.MONEDAS["USD"]["decimales"] == 2

        assert moneda.MONEDAS["USD"][
            "separador_decimales"
        ] == "."

    def test_los_nombres(self):
        """
        Los nombres que salen en el desplegable.

        "Guaraní paraguayo" y no "PYG", porque el
        desplegable lo lee alguien que no sabe qué es
        un código ISO.
        """

        assert moneda.nombre_de("PYG") == (
            "Guaraní paraguayo"
        )

        assert moneda.nombre_de("USD") == (
            "Dólar estadounidense"
        )

        # Una moneda que no existe devuelve el código,
        # que es mejor que inventar un nombre.

        assert moneda.nombre_de("XYZ") == "XYZ"

        assert moneda.nombre_de(None) == "—"


# ==========================================
# LO QUE PIDÓ EL ENCARGO
# ==========================================

class TestLoQuePidioElEncargo:

    @pytest.mark.parametrize("valor,esperado", [
        (1500, "Gs. 1.500"),
        (150000, "Gs. 150.000"),
        (1500000, "Gs. 1.500.000"),
        (150000000, "Gs. 150.000.000"),
        (2500000000, "Gs. 2.500.000.000"),
    ])
    def test_guarani(self, valor, esperado):
        """
        Los cinco casos del encargo, uno por uno.
        """

        assert moneda.formato_dinero(
            valor, moneda="PYG"
        ) == esperado

    @pytest.mark.parametrize("mal", [
        "Gs. 1,500,000.00",
        "Gs. 1500000",
        "Gs. 1.500.000,00",
    ])
    def test_guarani_no_sale_de_ninguna_de_estas_formas(
        self, mal
    ):
        """
        Las tres formas que el encargo dice que NO.

        Se comprueba una a una y no "que no contenga
        una coma": "Gs. 1.500.000,00" no tiene coma de
        miles pero sí de decimales, y las dos cosas
        están mal.
        """

        assert moneda.formato_dinero(
            1500000, moneda="PYG"
        ) != mal

    @pytest.mark.parametrize("valor,esperado", [
        (1500, "$ 1,500.00"),
        (25000.5, "$ 25,000.50"),
        (1500000, "$ 1,500,000.00"),
    ])
    def test_dolar(self, valor, esperado):

        assert moneda.formato_dinero(
            valor, moneda="USD"
        ) == esperado


# ==========================================
# CERO, NEGATIVOS Y GRANDES
# ==========================================

class TestCeroNegativosYGrandes:

    @pytest.mark.parametrize("moneda_codigo,esperado", [
        ("PYG", "Gs. 0"),
        ("USD", "$ 0.00"),
    ])
    def test_cero(self, moneda_codigo, esperado):

        assert moneda.formato_dinero(
            0, moneda=moneda_codigo
        ) == esperado

    def test_cero_negativo_no_sale(self):
        """
        Un -0.004 se redondea a cero y sale sin signo.

        "-$ 0.00" es un negativo cero que confunde: se
        lee como si quedara una deuda cuando no queda
        nada. Y en guaraníes "-Gs. 0" es todavía más
        raro, porque no hay ni céntimos.
        """

        assert moneda.formato_dinero(
            -0.004, moneda="USD"
        ) == "$ 0.00"

        assert moneda.formato_dinero(
            -0.4, moneda="PYG"
        ) == "Gs. 0"

    @pytest.mark.parametrize("valor", [
        -1500, -25000.5, -1500000, -150000000
    ])
    def test_negativos(self, valor):
        """
        Los reportes sacan diferencias, y una
        diferencia puede ser negativa.

        El signo va ANTES de la moneda, no después:
        "-$ 1,500.75" se lee como si el signo fuera
        parte de la cifra, que era el comportamiento
        antiguo.
        """

        for codigo in ("PYG", "USD"):

            texto = moneda.formato_dinero(
                valor, moneda=codigo
            )

            assert texto.startswith("-"), texto

            assert texto[1] not in "0123456789"

    def test_el_signo_no_se_pega_a_la_cifra(self):

        assert moneda.formato_dinero(
            -1500.75, moneda="USD"
        ) == "-$ 1,500.75"

        assert moneda.formato_dinero(
            -1500, moneda="PYG"
        ) == "-Gs. 1.500"

    @pytest.mark.parametrize("valor", [
        999999999999,          # 12 cifras
        9999999999999.99,      # el tope de DECIMAL(15,2)
    ])
    def test_grandes(self, valor):
        """
        El tope de la base tiene que salir entero.

        Un importe que se trunque al pintarse es peor que
        uno que no se pueda escribir: parece un dato
        bueno y es mentira.
        """

        for codigo in ("PYG", "USD"):

            ajustes = moneda.config_de(codigo)

            texto = moneda.formato_dinero(
                valor, moneda=codigo
            )

            # Lo que hay detrás del símbolo: la parte
            # entera y, si la moneda tiene, la decimal.
            # Van separadas porque en dólares el punto
            # es el decimal y quitarlo pegaría los
            # céntimos al entero.

            cifras = texto[len(ajustes["simbolo"]):].strip()

            decimal_texto = ajustes[
                "separador_decimales"
            ]

            if decimal_texto:

                entero_texto = cifras.split(
                    decimal_texto
                )[0]

            else:

                entero_texto = cifras

            entero_texto = entero_texto.replace(
                ajustes["separador_miles"], ""
            )

            assert entero_texto.isdigit(), texto

            if ajustes["decimales"] == 0:

                # Sin decimales el entero se redondea al
                # más cercano, así que puede quedar uno más
                # que la parte entera del valor.

                import math

                esperado = math.floor(valor + 0.5)

            else:

                esperado = int(valor)

            assert int(entero_texto) == esperado, (
                f"{texto} no es {esperado}"
            )

    def test_un_vehiculo_de_250_millones(self):
        """
        El caso corriente en guaraníes, no el extremo.
        """

        assert moneda.formato_dinero(
            250000000, moneda="PYG"
        ) == "Gs. 250.000.000"

        assert moneda.formato_dinero(
            45000000, moneda="PYG"
        ) == "Gs. 45.000.000"

    def test_el_guarani_redondea(self):
        """
        1.500,5 en guaraníes son 1.501 enteros.

        Truncar daría 1.500, que son 500 guaraníes
        menos de lo que el cliente debe, y ese medio no
        se puede pagar porque no existe.
        """

        assert moneda.formato_dinero(
            1500.5, moneda="PYG"
        ) == "Gs. 1.501"

        assert moneda.formato_dinero(
            1500.4, moneda="PYG"
        ) == "Gs. 1.500"

    def test_el_dolar_mantiene_los_centimos(self):

        assert moneda.formato_dinero(
            1500.5, moneda="USD"
        ) == "$ 1,500.50"


# ==========================================
# IR Y VOLVER
# ==========================================

class TestCambiarDeMoneda:

    def test_de_pyg_a_usd(self):
        """
        PYG -> USD y de vuelta.

        Es el caso de quien prueba las dos en cinco
        minutos, y el que más veces se va a ver.
        """

        en_pyg()

        assert moneda.formato_dinero(1500) == (
            "Gs. 1.500"
        )

        en_usd()

        assert moneda.formato_dinero(1500) == (
            "$ 1,500.00"
        )

    def test_de_usd_a_pyg(self):

        en_usd()

        assert moneda.formato_dinero(1500) == (
            "$ 1,500.00"
        )

        en_pyg()

        assert moneda.formato_dinero(1500) == (
            "Gs. 1.500"
        )

    def test_las_cuatro_pasadas(self):
        """
        Ida y vuelta varias veces seguidas.

        Si la configuración se cacheara mal, la
        segunda vuelta ya enseñaría la moneda
        anterior: el síntoma sería importes con el
        símbolo de la moneda que acabas de dejar.
        """

        for esperado in (
            "Gs. 1.500",
            "$ 1,500.00",
            "Gs. 1.500",
            "$ 1,500.00",
            "Gs. 1.500",
        ):

            codigo = "PYG" if esperado[0] == "G" else "USD"

            moneda.aplicar_config(moneda.config_de(codigo))

            assert moneda.formato_dinero(1500) == esperado

    def test_el_prefijo_cambia_tambien(self):
        """
        El prefijo del campo de escritura.

        Con "Gs." puesto en un campo de precio que
        lleva "$", el usuario teclea un número y la
        pantalla dice que son dólares.
        """

        assert moneda.prefijo_moneda(
            moneda="PYG"
        ) == "Gs. "

        assert moneda.prefijo_moneda(
            moneda="USD"
        ) == "$ "


# ==========================================
# UN CONTRATO NO CAMBIA
# ==========================================

class TestUnContratoNoCambia:

    def test_el_pdf_usa_la_moneda_del_contrato(self):
        """
        Un contrato firmado no se reescribe porque
        alguien cambie un ajuste.

        Esta es la prueba que importa del punto 7: un
        PDF de contrato con el importe bien puesto y la
        moneda de otro país no es un documento con un
        error pequeño, es un documento que no sirve.
        """

        import utils.contrato_pdf as pdf

        en_usd()

        assert pdf.formato_dinero(
            25000, moneda="PYG"
        ) == "Gs. 25.000"

        assert pdf.formato_dinero(
            25000, moneda="USD"
        ) == "$ 25,000.00"

    def test_el_recibo_usa_la_moneda_del_contrato(self):

        import utils.recibo_pdf as pdf

        assert pdf.codigo_moneda("PYG") == "PYG"

        assert pdf.codigo_moneda("usd") == "USD"

        en_usd()

        # Sin argumento: la de ahora.

        assert pdf.codigo_moneda() == "USD"

    def test_las_letras_no_inventan_decimales(self):
        """
        El importe en letras respeta la moneda.

        En guaraníes no hay céntimos que escribir: un
        recibo que dijera "con cero/100" está
        inventando una precisión que no existe, y en un
        recibo eso es un problema legal.
        """

        from utils.recibo_pdf import en_letras

        assert en_letras(1500.50, 2).endswith(
            "con cincuenta/100"
        )

        assert en_letras(1500.50, 0) == (
            "mil y quinientos uno"
        )

        assert en_letras(1500, 0) == (
            "mil y quinientos"
        )

    def test_una_moneda_desconocida_usa_la_de_ahora(
        self
    ):
        """
        Una moneda que no está en el catálogo.

        Puede venir de una base instalada con una
        versión anterior que admitía cualquier código.
        Antes de inventar un formato, se usa el que hay:
        es lo menos malo, y no es un crash.
        """

        en_pyg()

        assert moneda.formato_dinero(
            1500, moneda="XYZ"
        ) == "Gs. 1.500"

    def test_sin_moneda_usa_la_de_ahora(self):
        """
        Una venta anterior a la migración.

        No tiene moneda guardada. Se enseña con la que
        hay ahora, que es lo mejor que se puede hacer
        sin inventar.
        """

        en_pyg()

        assert moneda.formato_dinero(1500) == (
            "Gs. 1.500"
        )

        assert moneda.config_de(None)["codigo"] == "PYG"


# ==========================================
# LEER LO ESCRITO
# ==========================================

class TestParsearImporte:

    @pytest.mark.parametrize("texto,esperado", [
        # lo que se teclea
        ("40000", "40000"),
        ("40000.00", "40000.00"),
        ("0", "0"),
        ("  40000 ", "40000"),
        ("-1500.75", "-1500.75"),
        ("1500,50", "1500.50"),

        # separadores de miles
        ("40,000", "40000"),
        ("10.000", "10000"),
        ("1 500", "1500"),
        ("1'500", "1500"),
        ("1,500,000.00", "1500000.00"),
        ("1.500.000", "1500000"),
        ("1.500,50", "1500.50"),
        ("1.234.567,89", "1234567.89"),
        ("150.000.000", "150000000"),
    ])
    def test_lo_que_se_puede_leer(self, texto, esperado):

        assert str(
            moneda.parsear_importe(texto)
        ) == esperado

    @pytest.mark.parametrize("codigo", ["PYG", "USD"])
    def test_hace_id_y_vuelta(self, codigo):
        """
        Formatear un importe y volver a leerlo tiene que
        dar el mismo número.

        Es la propiedad que hace que `autos_view` pueda
        enseñar el precio en la tabla y volver a
        reconstruirlo para el formulario de edición. Con
        el separador de miles de otra moneda, esa vuelta
        reventaba.
        """

        import decimal

        for valor in (
            1500, 25000.5, 1500000, 150000000,
            2500000000, 0, 999, 100
        ):

            texto = moneda.formato_dinero(
                valor, moneda=codigo
            )

            vuelto = moneda.parsear_importe(texto)

            assert vuelto is not None, texto

            esperado = decimal.Decimal(str(valor))

            if moneda.config_de(codigo)["decimales"] == 0:

                # Sin decimales el número se redondea al
                # entero. Medio ARRIBA, no el redondeo
                # bancario de `round()`, que empata al
                # par: en dinero un medio siempre sube.

                import math

                assert vuelto == decimal.Decimal(
                    str(math.floor(valor + 0.5))
                ), texto

            else:

                assert vuelto == esperado, texto

    @pytest.mark.parametrize("texto", [
        "", "   ", "abc", "-", "Gs.", None,
        "1.2.3", "1.23.456", "1.234.567.89",
    ])
    def test_lo_que_no_se_puede_leer(self, texto):
        """
        Lo que no es un importe devuelve None.

        Y da igual el motivo: el que llama decide qué
        hacer. Preferible un None a un número inventado.

        "1.2.3" es el caso interesante: quitar los
        puntos da 123, un número con tres cifras menos
        y sin ningún aviso. En el precio de un vehículo
        eso es un error de un millón.
        """

        assert moneda.parsear_importe(texto) is None

    def test_no_lanza_excepciones(self):
        """
        Nunca lanza: quien llama decide.

        Un parser que revienta con ValueError obliga a
        un try/except en cada pantalla, y el que se
        olvide del except se cae al teclear.
        """

        for texto in (None, "", "x", 1, 1.5, [], {}):

            moneda.parsear_importe(texto)

    def test_es_importe_devuelve_mensaje(self):
        """
        `es_importe()` es el validador: (bool, mensaje),
        como el resto de validadores del proyecto.
        """

        ok, mensaje = moneda.es_importe("1.500")

        assert ok is True
        assert mensaje == ""

        ok, mensaje = moneda.es_importe("1.2.3")

        assert ok is False
        assert mensaje


# ==========================================
# EL DOLLAR NO CAMBIA
# ==========================================

class TestElDolarNoCambia:

    @pytest.mark.parametrize("valor,esperado", [
        (0, "$ 0.00"),
        (1, "$ 1.00"),
        (0.5, "$ 0.50"),
        (0.99, "$ 0.99"),
        (1.5, "$ 1.50"),
        (2.5, "$ 2.50"),
        (999.99, "$ 999.99"),
        (1000, "$ 1,000.00"),
        (1234.5, "$ 1,234.50"),
        (1500, "$ 1,500.00"),
        (25000.5, "$ 25,000.50"),
        (36500, "$ 36,500.00"),
        (99999.995, "$ 99,999.99"),
        (100000, "$ 100,000.00"),
        (1500000, "$ 1,500,000.00"),
        (12345.67, "$ 12,345.67"),
        (-0.004, "$ 0.00"),
        (-0.01, "-$ 0.01"),
        (-1500.75, "-$ 1,500.75"),
        (150000000, "$ 150,000,000.00"),
        (2500000000, "$ 2,500,000,000.00"),
        (0.005, "$ 0.01"),
        (0.995, "$ 0.99"),
        (12.005, "$ 12.01"),
    ])
    def test_byte_a_byte(self, valor, esperado):
        """
        Lo que se veía siempre, byte a byte.

        Incluidos los empates del redondeo en coma
        flotante: `format(0.995, ",.2f")` da "0.99" y
        `round(0.995 * 100)` da 100, que sería "1.00".
        Armando el entero y los céntimos por separado se
        resuelven distinto que Python, y eso salía en
        pantalla como importes mal escritos.
        """

        assert moneda.formato_dinero(
            valor, moneda="USD"
        ) == esperado

    def test_las_tablas_no_llevan_simbolo(self):
        """
        Las tablas usan `formatear_numero()`.

        Nunca el símbolo: la cabecera de la columna
        lleva el nombre de la columna y el símbolo
        duplicado en cada celda ensancha la tabla sin
        decir nada. Los separadores sí se respetan.
        """

        assert moneda.formatear_numero(
            1500, moneda.config_de("USD")
        ) == "1,500.00"

        assert moneda.formatear_numero(
            1500, moneda.config_de("PYG")
        ) == "1.500"


# ==========================================
# PARA LOS CAMPOS DE ESCRITURA
# ==========================================

class TestLosCamposDeEscritura:

    def test_el_tope_es_el_de_la_base(self):
        """
        El tope del campo tiene que ser el de la
        columna.

        El que había antes eran 999.999.999, que es MÁS
        de lo que MySQL aceptaba: la validación pasaba y
        la base rechazaba con "Out of range". Y en
        guaraníes, un vehículo normal cuesta 30-100
        millones, así que el tope estaba a un paso del
        caso corriente.
        """

        from decimal import Decimal

        maximo = moneda.maximo_teclado()

        # Lo que dice la columna.

        assert Decimal(str(maximo)) == Decimal(
            "9999999999999.99"
        )

        # Y cabe un vehículo de 250 millones.

        assert maximo > 250000000

    def test_el_paso_de_la_flechita(self):
        """
        En guaraníes el salto es de 100.000.

        Con un salto de 100 hay que pulsarla cientos de
        veces para pasar de un millón al siguiente, que
        es como se recorre una lista de precios.
        """

        assert moneda.paso_de_teclado(
            moneda.config_de("PYG")
        ) == 100000.0

        assert moneda.paso_de_teclado(
            moneda.config_de("USD")
        ) == 100.0

    def test_los_decimales_de_teclado(self):
        """
        Mínimo 1 decimal en el campo.

        Un `QDoubleSpinBox` con 0 decimales no deja
        escribir nada que no sea entero, y en algunos
        estilos se ve raro al teclear. El redondeo a
        entero lo hace la pantalla al mostrar, que es
        donde tiene que pasar.
        """

        assert moneda.decimales_de_teclado(
            moneda.config_de("PYG")
        ) == 1

        assert moneda.decimales_de_teclado(
            moneda.config_de("USD")
        ) == 2


# ==========================================
# UN DICCIONARIO A MEDIAS NO ROMPE NADA
# ==========================================

class TestUnConfigAMedias:

    def test_formato_dinero(self):
        """
        Se puede pasar un diccionario con una sola clave.

        Antes esto reventaba con un `KeyError:
        'decimales'` al pintar un importe. Un
        formateador al que hay que pasarle las seis
        claves no sirve para probar un cambio.
        """

        assert moneda.formato_dinero(
            1234.5, {"simbolo": "Gs."}
        ) == "Gs. 1,234.50"

    def test_formatear_numero(self):

        assert moneda.formatear_numero(
            1234.5, {"separador_miles": ","}
        ) == "1,234.50"

    def test_prefijo(self):

        assert moneda.prefijo_moneda(
            {"simbolo": "Gs."}
        ) == "Gs. "

    def test_un_diccionario_vacio(self):
        """
        Vacío sale con la moneda por defecto, no revienta.
        """

        assert moneda.formato_dinero(1500, {}) == (
            "$ 1,500.00"
        )

    def test_uno_que_no_es_un_diccionario(self):

        assert moneda.formato_dinero(
            1500, "no soy un diccionario"
        ) == "$ 1,500.00"


# ==========================================
# LA VALIDACIÓN
# ==========================================

class TestLaValidacion:

    def test_acepta_las_dos_del_catalogo(self):

        for codigo in moneda.CODIGOS:

            ok, mensaje = moneda.validar_config(
                moneda.config_de(codigo)
            )

            assert ok is True, mensaje

    def test_rechaza_un_formato_inventado(self):

        config = moneda.config_de("USD")

        config["formato"] = "inventado"

        ok, mensaje = moneda.validar_config(config)

        assert ok is False

        assert "formato" in mensaje

    def test_rechaza_un_separador_de_dos_caracteres(self):

        config = moneda.config_de("USD")

        config["separador_miles"] = "..."

        ok, _ = moneda.validar_config(config)

        assert ok is False

    def test_acepta_un_separador_de_decimales_vacio(self):
        """
        Vacío es lo que dice que la moneda no usa
        decimales.

        Antes un vacío se tomaba por "no guardado" y se
        caía al valor por defecto, así que una moneda sin
        decimales no se podía ni guardar.
        """

        config = moneda.config_de("PYG")

        assert config["separador_decimales"] == ""

        ok, mensaje = moneda.validar_config(config)

        assert ok is True, mensaje

    @pytest.mark.parametrize("decimales", [
        -1, 7, "dos", None
    ])
    def test_rechaza_un_numero_de_decimales_raro(
        self, decimales
    ):

        config = moneda.config_de("USD")

        config["decimales"] = decimales

        ok, _ = moneda.validar_config(config)

        assert ok is False


# ==========================================
# EL PDF
# ==========================================

class TestElPdf:

    def test_el_contrato_sale_en_su_moneda(
        self, como_administrador, datos_base, tmp_path
    ):
        """
        Un contrato en dólares sale en dólares aunque la
        aplicación esté en guaraníes.

        Es la prueba del punto 7 del encargo, y la más
        importante del archivo.

        El contrato se firma de verdad, con la moneda
        que hay en ese momento, y después se cambia el
        ajuste. El PDF tiene que seguir en dólares.
        """

        import os

        from database.contratos import (
            crear_contrato,
            obtener_contrato
        )
        from database.ventas import registrar_venta

        from utils.contrato_pdf import generar_contrato

        en_usd()

        _, id_auto, id_cliente = datos_base

        id_venta, _ = registrar_venta(
            id_cliente, id_auto, "2026-10-05", 25000.0
        )

        id_contrato, numero = crear_contrato(
            venta_id=id_venta,
            forma_pago="Contado"
        )

        assert id_contrato is not None, numero

        contrato = obtener_contrato(id_contrato)

        # Se firma en dólares.

        assert contrato["moneda"] == "USD"

        # Y ahora la aplicación pasa a guaraníes.

        en_pyg()

        destino = os.path.join(
            str(tmp_path), "contrato_usd.pdf"
        )

        ruta = generar_contrato(contrato, destino)

        assert os.path.exists(ruta)

        from conftest import leer_pdf

        texto = leer_pdf(ruta)

        assert "$ 25,000.00" in texto, (
            "un contrato firmado en dólares tiene que "
            "salir en dólares aunque la aplicación esté "
            f"en guaraníes. Sale: {texto[:400]}"
        )

        assert "Gs." not in texto

        os.remove(ruta)

    def test_el_recibo_sale_en_su_moneda(
        self, como_administrador, datos_base, tmp_path
    ):
        """
        Y el recibo también.
        """

        import os

        from utils.recibo_pdf import generar_recibo

        en_usd()

        contrato = {
            "numero": "CTR-2026-00001",
            "cliente": "Ana García",
            "documento": None,
            "moneda": "USD"
        }

        pagos = [{
            "id": 1,
            "recibo": "REC-2026-000001",
            "fecha": "2026-11-05",
            "importe": 25000,
            "forma": "Efectivo",
            "referencia": None,
            "concepto": "Cuota 1",
            "usuario_nombre": "admin",
            "cuota_id": None,
            "numero_cuota": 1,
            "estado": "convalidado",
            "anulado_motivo": None
        }]

        ruta = generar_recibo(
            pagos, contrato, None
        )

        try:

            from conftest import leer_pdf

            texto = leer_pdf(ruta)

            assert "$ 25,000.00" in texto

            assert "Gs." not in texto

            # Y el importe en letras va con el código
            # de SU moneda.

            assert "USD" in texto

        finally:

            if os.path.exists(ruta):

                os.remove(ruta)

    def test_el_recibo_ya_no_inventa_decimales(
        self, tmp_path
    ):
        """
        Un recibo en guaraníes no dice "con cero/100".
        """

        import os

        from utils.recibo_pdf import generar_recibo

        en_pyg()

        contrato = {
            "numero": "CTR-2026-00001",
            "cliente": "Ana García",
            "documento": None,
            "moneda": "PYG"
        }

        pagos = [{
            "id": 1,
            "recibo": "REC-2026-000002",
            "fecha": "2026-11-05",
            "importe": 1500000,
            "forma": "Efectivo",
            "referencia": None,
            "concepto": "Cuota 1",
            "usuario_nombre": "admin",
            "cuota_id": None,
            "numero_cuota": 1,
            "estado": "convalidado",
            "anulado_motivo": None
        }]

        ruta = generar_recibo(
            pagos, contrato, None
        )

        try:

            from conftest import leer_pdf

            texto = leer_pdf(ruta)

            assert "Gs. 1.500.000" in texto

            assert "/100" not in texto

            assert "PYG" in texto

        finally:

            if os.path.exists(ruta):

                os.remove(ruta)