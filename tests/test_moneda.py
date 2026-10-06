# ==========================================
# MONEDA CONFIGURABLE
# ==========================================
# Lo que hay que proteger:
#   - el formato por defecto reproduce EXACTAMENTE
#     el "$ " que estaba escrito en el código
#   - los seis formatos funcionan
#   - el signo va antes de la moneda
#   - una configuración basura no rompe la
#     aplicación: se ignora y se usa el defecto
#   - leer de la base y guardar da la vuelta
#     completa, y se aplica sin reiniciar
# ==========================================


import pytest

from utils import moneda

from database.configuracion import (
    MONEDA_POR_DEFECTO,
    leer_moneda,
    actualizar_moneda
)

from utils.contrato_pdf import formato_dinero as formato_del_pdf


@pytest.fixture(autouse=True)
def _restaura_la_moneda():
    """
    Cada prueba deja la moneda como estaba.

    Sin esto, una prueba que cambie a euros
    dejaría el resto del archivo formateando
    importes en euros y los fallos aparecerían
    donde no tocaban.
    """

    antes = moneda.config_actual()

    yield

    moneda.aplicar_config(antes)


def euros(**cambios):
    propuesta = {
        "codigo": "EUR",
        "simbolo": "EUR",
        "formato": "simbolo_espacio",
        "separador_miles": ".",
        "separador_decimales": ","
    }

    propuesta.update(cambios)

    return propuesta


class TestFormatoPorDefecto:

    """
    Lo importante: cambiar a moneda configurable
    NO puede haber cambiado un solo importe de
    los que se veían antes.
    """

    def test_es_el_de_siempre(self):
        assert moneda.formato_dinero(
            36500
        ) == "$ 36,500.00"

    def test_importes_grandes(self):
        assert moneda.formato_dinero(
            30000000
        ) == "$ 30,000,000.00"

        assert moneda.formato_dinero(
            999999999.99
        ) == "$ 999,999,999.99"

    def test_decimales(self):
        assert moneda.formato_dinero(
            1234.5
        ) == "$ 1,234.50"

        assert moneda.formato_dinero(
            0.99
        ) == "$ 0.99"

    def test_cero(self):
        assert moneda.formato_dinero(0) == "$ 0.00"

    def test_el_pdf_usa_el_mismo(self):
        """
        El PDF delegaba en otro sitio. Ahora van
        los dos por la misma función, y este
        comprueba que sigue dando lo mismo.
        """

        assert formato_del_pdf(
            36500
        ) == "$ 36,500.00"

    def test_acepta_decimal_de_mysql(self):
        from decimal import Decimal

        assert moneda.formato_dinero(
            Decimal("36500.00")
        ) == "$ 36,500.00"

    def test_acepta_texto_no_numerico(self):
        """
        Un None o un texto roto no pueden tirar
        la pantalla: sale a cero.
        """

        assert moneda.formato_dinero(None) == "$ 0.00"
        assert moneda.formato_dinero(
            "abc"
        ) == "$ 0.00"


class TestSeparadores:

    def test_formato_europeo(self):
        assert moneda.formato_dinero(
            36500, euros()
        ) == "EUR 36.500,00"

    def test_miles_grandes_europeo(self):
        assert moneda.formato_dinero(
            30000000, euros()
        ) == "EUR 30.000.000,00"

    def test_solo_el_numero(self):
        """
        Lo usan las tablas, que no llevan símbolo.
        """

        assert moneda.formatear_numero(
            36500
        ) == "36,500.00"

        assert moneda.formatear_numero(
            36500, euros()
        ) == "36.500,00"

    def test_separadores_iguales_no_generan_ambigua(
        self):
        """
        Con los dos separadores iguales el
        resultado no se podría leer, así que
        se avisa con el separador de siempre en
        vez de imprimir algo inútil.
        """

        raro = euros(
            separador_miles=".",
            separador_decimales="."
        )

        resultado = moneda.formato_dinero(
            36500, raro
        )

        # El entero vuelve al separador de siempre
        # para que el importe se pueda leer.

        assert resultado == "EUR 36,500.00"


class TestFormatos:

    def test_los_seis(self):
        esperado = {
            "simbolo_espacio": "$ 1,234.50",
            "simbolo_pegado": "$1,234.50",
            "simbolo_despues": "1,234.50 $",
            "codigo_espacio": "USD 1,234.50",
            "codigo_pegado": "USD1,234.50",
            "codigo_despues": "1,234.50 USD"
        }

        for formato, texto in esperado.items():

            propuesta = dict(
                MONEDA_POR_DEFECTO, formato=formato
            )

            assert moneda.formato_dinero(
                1234.5, propuesta
            ) == texto, formato

    def test_todos_estan_en_la_lista(self):
        assert len(moneda.FORMATOS) == 6

    def test_prefijo_segun_el_formato(self):
        """
        El prefijo va en el campo numérico del
        formulario de venta. Con la moneda detrás
        no debe prefijar nada, o saldría dos veces.
        """

        caso = lambda f: moneda.prefijo_moneda(
            dict(MONEDA_POR_DEFECTO, formato=f)
        )

        assert caso("simbolo_espacio") == "$ "
        assert caso("simbolo_pegado") == "$"
        assert caso("simbolo_despues") == ""
        assert caso("codigo_espacio") == "USD "
        assert caso("codigo_pegado") == "USD"
        assert caso("codigo_despues") == ""

    def test_no_duplica_la_moneda(self):
        """
        Con el símbolo detrás, el campo numérico
        no lleva prefijo y el importe ya sale
        completo. Nunca pueden aparecer los dos.
        """

        propuesta = dict(
            MONEDA_POR_DEFECTO,
            formato="simbolo_despues"
        )

        assert moneda.prefijo_moneda(
            propuesta
        ) == ""

        assert moneda.formato_dinero(
            1234.5, propuesta
        ).count("$") == 1


class TestSigno:

    def test_el_signo_va_antes_de_la_moneda(self):
        """
        Antes salía "$ -1,500.75", que se lee como
        si el signo fuera parte de la cifra.
        """

        assert moneda.formato_dinero(
            -1500.75
        ) == "-$ 1,500.75"

    def test_signo_en_todos_los_formatos(self):

        for formato in moneda.FORMATOS:

            propuesta = dict(
                MONEDA_POR_DEFECTO, formato=formato
            )

            resultado = moneda.formato_dinero(
                -1500.75, propuesta
            )

            assert resultado.startswith("-"), formato

    def test_no_hay_negativo_cero(self):
        """
        -0.004 se redondea a cero. Escribir
        "-$ 0.00" es un negativo cero que
        confunde a quien lo lee.
        """

        assert moneda.formato_dinero(
            -0.004
        ) == "$ 0.00"

    def test_negativo_cero_en_euros(self):
        assert moneda.formato_dinero(
            -0.004, euros()
        ) == "EUR 0,00"

    def test_un_centimo_si_lleva_signo(self):
        assert moneda.formato_dinero(
            -0.01
        ) == "-$ 0.01"


class TestValidacion:

    def test_la_de_defecto_es_valida(self):
        valido, mensaje = moneda.validar_config(
            MONEDA_POR_DEFECTO
        )

        assert valido is True
        assert mensaje == ""

    def test_codigo_vacio(self):
        valido, mensaje = moneda.validar_config(
            dict(MONEDA_POR_DEFECTO, codigo="  ")
        )

        assert valido is False
        assert "código" in mensaje

    def test_formato_inventado(self):
        valido, mensaje = moneda.validar_config(
            dict(MONEDA_POR_DEFECTO,
                 formato="inventado")
        )

        assert valido is False
        assert "formato" in mensaje.lower()

    def test_separador_de_dos_caracteres(self):
        valido, mensaje = moneda.validar_config(
            dict(MONEDA_POR_DEFECTO,
                 separador_miles="..")
        )

        assert valido is False
        assert "un solo carácter" in mensaje

    def test_no_es_un_diccionario(self):
        valido, mensaje = moneda.validar_config(
            None
        )

        assert valido is False

    def test_config_basura_se_ignora(self):
        """
        Un ajuste guardado con basura no puede
        romper la aplicación: se descarta y se usa
        el valor por defecto de ese campo.
        """

        limpio = moneda._normalizar({
            "codigo": "",
            "formato": "inventado",
            "separador_miles": "no es uno",
            "simbolo": None
        })

        assert limpio["codigo"] == "USD"
        assert limpio["formato"] == "simbolo_espacio"
        assert limpio["separador_miles"] == ","

    def test_basura_tampoco_tira_la_app(self):
        moneda.aplicar_config({
            "codigo": "X" * 500,
            "formato": "no_existe"
        })

        # Debe devolver algo sin reventar.

        assert moneda.formato_dinero(
            100
        ).endswith("100.00")


class TestBaseDeDatos:

    # ------------------------------
    # LA API ES UNA MONEDA, NO CINCO
    # ATRIBUTOS
    # ------------------------------

    def test_va_y_viene(self, como_administrador):
        """
        Lo que se guarda es lo que se lee.

        Y al guardar se elige UNA moneda, no cinco
        atributos sueltos: el símbolo, el formato, los
        dos separadores y los decimales salen del
        catálogo.
        """

        ok, motivo = actualizar_moneda("PYG")

        assert ok is True, motivo

        moneda.olvidar_config()

        ajustes = leer_moneda()

        assert ajustes["codigo"] == "PYG"

        # Todo lo demás vino del catálogo.

        assert ajustes["simbolo"] == "Gs."
        assert ajustes["formato"] == "simbolo_espacio"
        assert ajustes["separador_miles"] == "."
        assert ajustes["separador_decimales"] == ""
        assert ajustes["decimales"] == 0

        assert moneda.formato_dinero(36500) == (
            "Gs. 36.500"
        )

    def test_se_aplica_sin_reiniciar(
        self, como_administrador
    ):
        """
        Guardar tiene que notarse al momento: si solo
        se guardara en la base, habría que reiniciar
        para verlo, y nadie lo haría.
        """

        assert moneda.formato_dinero(100) == (
            "$ 100.00"
        )

        actualizar_moneda("PYG")

        assert moneda.formato_dinero(100) == (
            "Gs. 100"
        )

        actualizar_moneda("USD")

        assert moneda.formato_dinero(100) == (
            "$ 100.00"
        )

    def test_solo_hay_dos_monedas(
        self, como_administrador
    ):
        """
        Ni una más, ni una menos.

        Se puede elegir entre PYG y USD. Una moneda
        inventada se rechaza con un mensaje que dice
        cuáles hay, que es lo único que le sirve a
        quien lo ha tecleado mal.
        """

        assert set(moneda.MONEDAS) == {"PYG", "USD"}

        for codigo in ("EUR", "MXN", "", "guarani", "1"):

            ok, motivo = actualizar_moneda(codigo)

            assert ok is False, f"{codigo!r} se aceptó"

            assert "PYG" in motivo

        # Con espacio o en minúsculas sí se acepta:
        # quien lo teclea en el desplegable no lo
        # hace, pero un script o un `.env` pueden.

        assert actualizar_moneda(" pyg ")[0] is True

        assert actualizar_moneda("usd")[0] is True

    def test_no_se_puede_escribir_el_simbolo(
        self, como_administrador
    ):
        """
        El símbolo sale del catálogo.

        Con la firma de un solo argumento es imposible
        pasar un símbolo, y no es una casualidad: la
        combinación de "guaraní con dos decimales" o
        "dólar con el punto de miles" salía de teclear
        cinco cosas, y ninguna combinación produce un
        error al guardarlo. Solo un importe que no se
        puede leer, que se descubre en un contrato.
        """

        import inspect

        parametros = list(
            inspect.signature(
                actualizar_moneda
            ).parameters
        )

        assert parametros == ["codigo"], parametros

    def test_el_vendedor_no_cambia_la_moneda(
        self, como_vendedor
    ):
        from errores import PermisoDenegado

        with pytest.raises(PermisoDenegado):

            actualizar_moneda("PYG")

    def test_queda_rastro(self, como_administrador):
        from database.auditoria import obtener_auditoria

        antes = len(obtener_auditoria())

        assert moneda.config_actual()["codigo"] == "USD"

        actualizar_moneda("PYG")

        registros = obtener_auditoria()

        assert len(registros) == antes + 1

        assert registros[0][3] == "CONFIGURACION"
        assert "Moneda" in (registros[0][5] or "")

    def test_el_rastro_dice_que_cambio(
        self, como_administrador
    ):
        """
        El rastro tiene que decir qué se movió: un
        "Moneda actualizada" a secas no sirve para
        reconstruir qué pasó.
        """

        from database.auditoria import obtener_auditoria

        assert moneda.config_actual()["codigo"] == "USD"

        actualizar_moneda("PYG")

        registros = obtener_auditoria()

        texto = registros[0][5] or ""

        assert "PYG" in texto

        # Y dice que no se ha convertido nada, que es
        # lo que alguien va a preguntar después de
        # cambiar el ajuste.

        assert "No se convierte" in texto

    def test_no_convierte_ningun_importe(
        self, como_administrador, datos_base
    ):
        """
        Cambiar la moneda no toca ningún valor.

        Es lo que dice el punto 6 del encargo, y es
        lo más importante: una venta de 25.000
        dólares sigue siendo 25.000 después de pasar
        la aplicación a guaraníes. Lo que cambia es
        cómo se enseña, no cuánto vale.
        """

        from database.ventas import registrar_venta

        _, id_auto, id_cliente = datos_base

        id_venta, _ = registrar_venta(
            id_cliente, id_auto, "2026-03-01", 25000.0
        )

        from database.pagos import saldo_venta

        precio_antes, _, saldo_antes = saldo_venta(
            id_venta
        )

        actualizar_moneda("PYG")

        precio_despues, _, saldo_despues = saldo_venta(
            id_venta
        )

        assert precio_antes == precio_despues
        assert saldo_antes == saldo_despues

        # Y tampoco aparece ningún tipo de cambio por
        # la puerta de atrás.

        assert "factor" not in (
            __import__(
                "database.configuracion",
                fromlist=["x"]
            ).__doc__ or ""
        ).lower()

    def test_la_venta_guarda_su_moneda(
        self, como_administrador, datos_base
    ):
        """
        Cada venta guarda con qué moneda se hizo.

        Sin esto, una venta es un número suelto que se
        reescribe cada vez que alguien cambia un ajuste,
        y el mismo documento dice dos cosas distintas.
        """

        from database.ventas import (
            moneda_de_venta,
            registrar_venta
        )

        _, id_auto, id_cliente = datos_base

        assert moneda.config_actual()["codigo"] == "USD"

        id_venta, _ = registrar_venta(
            id_cliente, id_auto, "2026-03-01", 25000.0
        )

        assert moneda_de_venta(id_venta) == "USD"

        # Ahora se cambia la moneda y se hace otra
        # venta: cada una con la suya.

        actualizar_moneda("PYG")

        id_otra, _ = registrar_venta(
            id_cliente, id_auto, "2026-03-02", 2500000.0
        )

        assert moneda_de_venta(id_venta) == "USD"

        assert moneda_de_venta(id_otra) == "PYG"

        # Y una venta inexistente no revienta.

        assert moneda_de_venta(999999) is None


