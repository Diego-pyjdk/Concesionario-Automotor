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
    obtener_moneda,
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

    def test_sin_ajustes_usa_los_defecto(
        self, como_administrador
    ):
        from database.conexion import obtener_conexion

        conexion = obtener_conexion()

        cursor = conexion.cursor()

        cursor.execute(
            "DELETE FROM configuracion "
            "WHERE clave LIKE 'moneda%%'"
        )

        conexion.commit()

        cursor.close()
        conexion.close()

        moneda.olvidar_config()

        ajustes = obtener_moneda()

        assert ajustes["codigo"] == "USD"
        assert moneda.formato_dinero(
            100
        ) == "$ 100.00"

    def test_va_y_viene(
        self, como_administrador
    ):
        """
        Lo que se guarda es lo que se lee.
        """

        ok, motivo = actualizar_moneda(
            "MXN", "$", "simbolo_pegado", ".", ","
        )

        assert ok is True, motivo

        moneda.olvidar_config()

        ajustes = leer_moneda()

        assert ajustes["codigo"] == "MXN"
        assert ajustes["formato"] == "simbolo_pegado"

        # Se guardó con miles "." y decimales ",", así
        # que el importe sale con el formato europeo.

        assert ajustes["separador_miles"] == "."
        assert ajustes["separador_decimales"] == ","

        assert moneda.formato_dinero(
            36500
        ) == "$36.500,00"

    def test_se_aplica_sin_reiniciar(
        self, como_administrador
    ):
        """
        Guardar tiene que notarse al momento: si
        solo se guardara en la base, habría que
        reiniciar para verlo, y nadie lo haría.
        """

        assert moneda.formato_dinero(
            100
        ) == "$ 100.00"

        actualizar_moneda(
            "GBP", "GBP", "codigo_despues", ",", "."
        )

        assert moneda.formato_dinero(
            100
        ) == "100.00 GBP"

    def test_rechaza_lo_invalido(
        self, como_administrador
    ):
        antes = moneda.config_actual()

        ok, motivo = actualizar_moneda(
            "EUR", "EUR", "simbolo_espacio",
            ",", ","
        )

        assert ok is False
        assert "no pueden ser el mismo" in motivo

        # Y no ha cambiado nada.

        assert moneda.config_actual() == antes

    def test_rechaza_formato_inventado(
        self, como_administrador
    ):
        ok, motivo = actualizar_moneda(
            "EUR", "€", "inventado", ".", ","
        )

        assert ok is False

    def test_el_vendedor_no_cambia_la_moneda(
        self, como_vendedor
    ):
        from errores import PermisoDenegado

        with pytest.raises(PermisoDenegado):

            actualizar_moneda(
                "EUR", "€", "simbolo_espacio", ".", ","
            )

    def test_queda_rastro(
        self, como_administrador
    ):
        from database.auditoria import obtener_auditoria

        antes = len(obtener_auditoria())

        # Un valor que no sea el de por defecto: si
        # se guardara lo mismo dos veces no habría
        # ningún cambio que anotar y la comprobación
        # no probaría nada.

        assert moneda.config_actual()["codigo"] == "USD"

        actualizar_moneda(
            "JPY", "¥", "codigo_despues", ",", "."
        )

        registros = obtener_auditoria()

        assert len(registros) == antes + 1

        assert registros[0][3] == "CONFIGURACION"
        assert "Moneda" in (registros[0][5] or "")

    def test_el_rastro_dice_que_cambio(
        self, como_administrador
    ):
        """
        El rastro tiene que decir qué campo se
        movió: un "Moneda actualizada" a secas no
        sirve de nada si hay que investigar.

        Cada prueba parte de un estado distinto
        para que haya algo que anotar: si dos
        pruebas guardan lo mismo, la segunda no
        registra ningún cambio y no probaría nada.
        """

        from database.auditoria import obtener_auditoria

        # Primero se pone algo conocido.

        actualizar_moneda(
            "USD", "$", "simbolo_espacio", ",", "."
        )

        # Y ahora se cambia todo.

        actualizar_moneda(
            "CHF", "CHF", "codigo_despues", "'", ","
        )

        descripcion = obtener_auditoria()[0][5] or ""

        assert "codigo" in descripcion
        assert "simbolo" in descripcion
        assert "formato" in descripcion
        assert "separador_miles" in descripcion
        assert "separador_decimales" in descripcion
