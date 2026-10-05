# ==========================================
# AUDITORÍA CON VALOR ANTERIOR Y NUEVO
# ==========================================
# La auditoría tiene tres columnas nuevas: valor_anterior,
# valor_nuevo y referencia. Aquí se comprueba que se
# escriben, que se leen y que no rompen lo que ya
# funcionaba.
#
# Y dos cosas que se rompieron al añadirlas y que
# pasaron desapercibidas:
#
#   1. registrar_accion() dejó de reenviar usuario_id
#      y usuario_nombre a registrar_cambio(). Con una
#      sesión abierta, un login fallido contra una
#      cuenta INEXISTENTE pasó a quedar anotado a
#      nombre de quien estuviera sentado delante.
#      El propio código de auditoría dice que eso no
#      debe pasar, y ahora hay una prueba que lo
#      comprueba.
#
#   2. obtener_auditoria() pasó a devolver nueve
#      columnas. Los índices del 0 al 5 no cambian, así
#      que las vistas siguen funcionando; las nuevas
#      van al final a propósito.
# ==========================================


import os

from datetime import date
from decimal import Decimal

import pytest

import sesion as modulo_sesion

from database.auditoria import (
    registrar_accion,
    registrar_cambio,
    obtener_auditoria,
    obtener_historial,
    obtener_cambios
)

from database.contratos import crear_contrato

from database.conexion import obtener_conexion

from database.ventas import registrar_venta

import database.financiera as F


# ==========================================
# ESCRIBIR
# ==========================================

def _prepara_qt():
    """
    Deja una QApplication y los cuadros de diálogo
    parcheados.

    Sin esto, construir una vista tumba el proceso con
    un fallo de segmentación y pytest no llega ni a
    escribir el informe.
    """

    os.environ["QT_QPA_PLATFORM"] = "offscreen"

    from PySide6.QtWidgets import QApplication, QMessageBox

    for nombre in (
        "warning", "information", "critical",
        "question", "about"
    ):

        setattr(
            QMessageBox,
            nombre,
            staticmethod(lambda *a, **k: QMessageBox.Ok)
        )

    if QApplication.instance() is None:

        QApplication([])


class TestRegistrarCambio:

    def test_escribe_valor_anterior_y_nuevo(
        self, como_administrador
    ):
        """
        Un cambio sin valor anterior ni nuevo no se
        puede auditar: nadie sabe si el saldo era
        200.000 o 2.000.000 antes de que alguien lo
        tocara.
        """

        registrar_cambio(
            "prueba",
            "PRUEBA",
            "Se cambió el saldo",
            valor_anterior="saldo 200.000,00",
            valor_nuevo="saldo 2.000.000,00"
        )

        registros = obtener_auditoria()

        assert registros[0][3] == "PRUEBA"

        assert registros[0][6] == "saldo 200.000,00"

        assert registros[0][7] == "saldo 2.000.000,00"

    def test_sin_valores_no_falla(
        self, como_administrador
    ):
        """
        Una acción corriente sigue funcionando: no
        todos los movimientos son cambios.
        """

        registrar_accion("prueba", "PRUEBA", "Algo pasó")

        registros = obtener_auditoria()

        assert registros[0][6] is None

        assert registros[0][7] is None

    def test_la_referencia_se_busca(
        self, como_administrador
    ):
        """
        Buscar por referencia y no por texto dentro de
        la descripción: el resultado no puede depender
        de cómo se escribió esa vez.
        """

        registrar_cambio(
            "prueba",
            "PRUEBA",
            "Se cambió algo",
            referencia="CTR-2026-99999"
        )

        historial = obtener_historial("CTR-2026-99999")

        assert len(historial) == 1

        assert historial[0][8] == "CTR-2026-99999"

    def test_un_valor_largo_se_corta(
        self, como_administrador
    ):
        """
        La columna es VARCHAR(255). Si alguien pasa un
        texto más largo y no se corta, el INSERT falla
        y la modificación se queda SIN RASTRO: es
        preferible un valor anterior truncado a que no
        quede constancia.
        """

        registrar_cambio(
            "prueba",
            "PRUEBA",
            "Texto largo",
            valor_anterior="A" * 900,
            valor_nuevo="B" * 900
        )

        registros = obtener_auditoria()

        assert len(registros[0][6]) == 255

        assert len(registros[0][7]) == 255


# ==========================================
# LEER
# ==========================================

class TestLeer:

    def test_nueve_columnas(self, como_administrador):
        """
        El contrato de columnas pasa a nueve:
        id, fecha_hora, usuario_nombre, accion, modulo,
        descripcion, valor_anterior, valor_nuevo,
        referencia.

        Las seis primeras NO cambian de sitio, que es lo
        que permite no tocar las vistas que ya las
        usaban por posición.
        """

        registrar_cambio(
            "prueba",
            "PRUEBA",
            "Algo",
            valor_anterior="antes",
            valor_nuevo="despues",
            referencia="REF-1"
        )

        registro = obtener_auditoria()[0]

        assert len(registro) == 9

        assert registro[8] == "REF-1"

    def test_el_historial_devuelve_lo_mismo(
        self, como_administrador
    ):

        registrar_cambio(
            "prueba", "UNO", "Primero",
            valor_anterior="a", valor_nuevo="b",
            referencia="REF-2"
        )

        registrar_cambio(
            "prueba", "DOS", "Segundo",
            valor_anterior="c", valor_nuevo="d",
            referencia="REF-2"
        )

        registrar_cambio(
            "prueba", "TRES", "Otro",
            referencia="REF-OTRA"
        )

        historial = obtener_historial("REF-2")

        assert len(historial) == 2

        # Del más reciente al más antiguo.

        assert historial[0][3] == "DOS"

        assert historial[1][3] == "UNO"

    def test_cambios_solo_los_que_cambian(
        self, como_administrador
    ):
        """
        obtener_cambios() responde a "¿qué se ha
        tocado?", que obtener_auditoria() no contesta:
        ahí también están los inicios de sesión.
        """

        registrar_accion("acceso", "LOGIN", "Entró")

        registrar_cambio(
            "configuracion", "CONFIGURACION", "Cambió",
            valor_anterior="3", valor_nuevo="5"
        )

        cambios = obtener_cambios()

        acciones = [f[3] for f in cambios]

        assert "CONFIGURACION" in acciones

        assert "LOGIN" not in acciones

    def test_cambios_con_la_caja_si_se_pide(
        self, como_administrador
    ):
        """
        Los movimientos de dinero no son "cambios" de
        un dato, pero quien audita la caja los quiere.
        """

        registrar_accion("ventas", "VENTA", "Venta")

        sin_caja = obtener_cambios()

        acciones = [f[3] for f in sin_caja]

        assert "VENTA" not in acciones

        con_caja = obtener_cambios(
            dejar_registros_financiera=True
        )

        acciones = [f[3] for f in con_caja]

        assert "VENTA" in acciones


# ==========================================
# LA REGRESIÓN
# ==========================================

class TestLoginFallidoSinAtribuir:

    def test_no_se_atribuye_a_quien_esta_conectado(
        self, como_administrador
    ):
        """
        Un intento fallido contra una cuenta que NO
        EXISTE tiene que quedar sin atribuir: ni con el
        id ni con el nombre de quien esté sentado
        delante.

        Atribuirlo a otro usuario es peor que no
        atribuirlo: el rastro afirmaría que el admin
        intentó entrar con una cuenta ajena, cuando lo
        que pasó es justo lo contrario.
        """

        from database.usuarios import autenticar

        modulo_sesion.cerrar_sesion()

        import sesion as ms

        conexion = obtener_conexion()

        cursor = conexion.cursor(dictionary=True)

        cursor.execute(
            "SELECT id FROM usuarios ORDER BY id LIMIT 1"
        )

        id_admin = cursor.fetchone()["id"]

        cursor.close()

        conexion.close()

        ms.iniciar_sesion((
            id_admin, "admin", "Admin", "administrador"
        ))

        # Hay sesión abierta: es precisamente el caso
        # en el que el fallo se atribuía al admin.

        autenticar("cuenta_inexistente", "lo_que_sea")

        fallidos = [
            f for f in obtener_auditoria()
            if f[3] == "LOGIN_FALLIDO"
        ]

        assert fallidos, "el fallo no quedó registrado"

        assert fallidos[0][2] == "cuenta_inexistente", (
            "el intento se atribuyó a "
            f"{fallidos[0][2]!r} en vez de al nombre "
            "escrito"
        )

    def test_el_id_queda_a_nulo(
        self, como_administrador
    ):
        """
        usuario_id a NULL, no el del admin. El
        centinela SIN_INFORMAR existe justo para poder
        decir "no hay usuario" sin que se confunda con
        "no me han dicho cuál".
        """

        from database.usuarios import autenticar

        modulo_sesion.cerrar_sesion()

        import sesion as ms

        conexion = obtener_conexion()

        cursor = conexion.cursor(dictionary=True)

        cursor.execute(
            "SELECT id FROM usuarios ORDER BY id LIMIT 1"
        )

        id_admin = cursor.fetchone()["id"]

        cursor.close()

        conexion.close()

        ms.iniciar_sesion((
            id_admin, "admin", "Admin", "administrador"
        ))

        autenticar("otra_inexistente", "x")

        modulo_sesion.cerrar_sesion()

        conexion = obtener_conexion()

        cursor = conexion.cursor(dictionary=True)

        cursor.execute("""
            SELECT usuario_id, usuario_nombre
            FROM auditoria
            WHERE accion = 'LOGIN_FALLIDO'
            ORDER BY id DESC
            LIMIT 1
        """)

        fila = cursor.fetchone()

        cursor.close()

        conexion.close()

        assert fila["usuario_id"] is None

        assert fila["usuario_nombre"] == "otra_inexistente"

    def test_registrar_accion_reenvia_el_usuario(
        self, como_administrador
    ):
        """
        La comprobación directa del reenvío.

        registrar_accion() delega en registrar_cambio().
        Si al delegar se le olvidara usuario_id o
        usuario_nombre, cualquier llamada que los pase
       aria a usar la sesion. Aqui se ve sin filtros de
        por medio.
        """

        registrar_accion(
            "prueba",
            "PRUEBA",
            "Con usuario propio",
            usuario_id=None,
            usuario_nombre="fulano"
        )

        registros = obtener_auditoria()

        conexion = obtener_conexion()

        cursor = conexion.cursor(dictionary=True)

        cursor.execute("""
            SELECT usuario_id, usuario_nombre
            FROM auditoria
            WHERE accion = 'PRUEBA'
            ORDER BY id DESC
            LIMIT 1
        """)

        fila = cursor.fetchone()

        cursor.close()

        conexion.close()

        assert fila["usuario_id"] is None

        assert fila["usuario_nombre"] == "fulano"

        del registros

    def test_sin_usuario_usa_la_sesion(
        self, como_administrador
    ):
        """
        Lo contrario del anterior: si NO se dice nada,
        se usa la sesión. El centinela distingue los dos
        casos y ambos tienen que seguir funcionando.
        """

        registrar_accion("prueba", "PRUEBA", "Sin decir nada")

        conexion = obtener_conexion()

        cursor = conexion.cursor(dictionary=True)

        cursor.execute("""
            SELECT usuario_id, usuario_nombre
            FROM auditoria
            WHERE accion = 'PRUEBA'
            ORDER BY id DESC
            LIMIT 1
        """)

        fila = cursor.fetchone()

        cursor.close()

        conexion.close()

        assert fila["usuario_id"] is not None

        assert fila["usuario_nombre"] == "admin"


# ==========================================
# INTEGRIDAD CON LA FINANCIERA
# ==========================================

class TestConLaFinanciera:

    def test_el_rastro_registra_el_cronograma(
        self, como_administrador, datos_base
    ):

        _, id_auto, id_cliente = datos_base

        id_venta, _ = registrar_venta(
            id_cliente, id_auto, "2026-10-01", 1000000.0
        )

        id_contrato, _ = crear_contrato(
            venta_id=id_venta,
            forma_pago="Anticipo + cuotas",
            anticipo=400000.0,
            cantidad_cuotas=6,
            saldo_financiado=Decimal("100000.00"),
            periodicidad="mensual",
            primer_vencimiento=date(2026, 11, 1)
        )


        F.generar_cronograma(id_contrato)

        registros = obtener_auditoria()

        acciones = [f[3] for f in registros]

        assert "CRONOGRAMA" in acciones

    def test_el_rastro_no_crece_si_nada_cambia(
        self, como_administrador
    ):
        """
        procesar_vencidas() con nada que marcar no deja
        rastro. Si lo dejara, abrir la cartera llenaría
        la auditoría de "0 vencidas marcadas" y los
        cambios de verdad quedarían enterrados.
        """

        antes = len(obtener_auditoria())

        cambios = F.procesar_vencidas()

        assert cambios == 0

        assert len(obtener_auditoria()) == antes

    def test_cada_pago_deja_valor_anterior_y_nuevo(
        self, como_administrador, datos_base
    ):
        """
        La prueba de que el rastro sirve para algo: con
        los valores de antes y después, el historial de
        una cuota cuenta su historia sin tener que
        recalcular nada.
        """

        _, id_auto, id_cliente = datos_base

        id_venta, _ = registrar_venta(
            id_cliente, id_auto, "2026-10-01", 1000000.0
        )

        id_contrato, numero = crear_contrato(
            venta_id=id_venta,
            forma_pago="Anticipo + cuotas",
            anticipo=400000.0,
            cantidad_cuotas=6,
            saldo_financiado=Decimal("100000.00"),
            periodicidad="mensual",
            primer_vencimiento=date(2026, 11, 1)
        )


        F.generar_cronograma(id_contrato)

        cuotas = F.obtener_cuotas(id_contrato)

        F.registrar_pago_cuota(
            cuotas[0]["id"],
            cuotas[0]["importe"],
            "2026-11-01",
            "Efectivo",
            recibo="REC-HIST-1"
        )

        historial = obtener_historial("REC-HIST-1")

        assert len(historial) == 1

        entrada = historial[0]

        # El valor nuevo tiene que traer el saldo a
        # cero, que es lo que hace la cuota "pagada".

        assert "0.00" in entrada[7]

        assert "Pagada" in entrada[7]

        # Y el anterior, el saldo entero.

        assert str(cuotas[0]["importe"].quantize(
            Decimal("0.01")
        )) in entrada[6].replace(",", "")

    def test_la_vista_se_construye(
        self, como_administrador
    ):
        """
        La vista de auditoría se construye al abrir la
        ventana principal, y antes de esto reventaba
        AHÍ, con la aplicación sin arrancar.

        La causa: mostrar_registros() desempaquetaba el
        registro en seis variables con

            a, b, c, d, e, f = registro

        y obtener_auditoria() pasó a devolver nueve. El
        desempaquetado revienta en cuanto cae una columna
        de más, y revienta al pintar la pantalla, no en
        los datos: no hay mensaje útil, solo una ventana
        que no abre.

        Esta prueba construye la vista de verdad. Es la
        única que detecta ese tipo de fallo, porque
        compilar no lo detecta y los datos están
        correctos: lo que estaba mal era cómo se leían.
        """

        _prepara_qt()

        # Se registra ANTES de construir la vista.

        # La tabla se llena al construirse. Con el
        # rastro vacío construiría sin error y sin
        # pintar nada, que es justo lo que hay que
        # comprobar: una vista que se construye y no
        # muestra un solo registro parece que
        # funciona.

        registrar_cambio(
            "prueba",
            "PRUEBA",
            "Cambio visible",
            valor_anterior="saldo 100,00",
            valor_nuevo="saldo 900,00"
        )

        from gui.auditoria_view import AuditoriaView

        vista = AuditoriaView()

        try:

            assert vista.tabla.rowCount() >= 1, (
                "la vista se construyó pero no muestra "
                "ningún registro, con lo que hay datos"
            )

            # El cambio con valor anterior y nuevo se
            # ve en la celda, no se pierde por el camino.

            vista.cargar_datos()

            textos = [
                vista.tabla.item(fila, 4).text()
                for fila in range(vista.tabla.rowCount())
            ]

            assert any(
                "saldo 100,00" in t and "saldo 900,00" in t
                for t in textos
            ), "el valor anterior y el nuevo no salen"

        finally:

            vista.deleteLater()

    def test_el_csv_no_revisa(
        self, como_administrador, tmp_path
    ):
        """
        La exportación a CSV tenía el mismo
        desempaquetado de seis variables, en la misma
        vista. Ese no reventaba al arrancar: reventaba
        al exportar, que es cuando el usuario ya ha
        hecho su trabajo y va a perderlo.

        Se comprueba el fichero entero, no solo que no
        salte excepción.
        """

        _prepara_qt()

        registrar_cambio(
            "prueba",
            "PRUEBA",
            "Cambio exportable",
            valor_anterior="antes",
            valor_nuevo="despues",
            referencia="REF-CSV"
        )

        from gui.auditoria_view import AuditoriaView

        vista = AuditoriaView()

        destino = tmp_path / "auditoria.csv"

        try:

            vista.exportar_csv(str(destino))

            contenido = destino.read_text(
                encoding="utf-8-sig"
            )

            lineas = contenido.strip().splitlines()

            assert len(lineas) >= 2

            # La cabecera lleva las nueve columnas.

            assert lineas[0].count(";") == 8

            # Y alguna fila trae el valor anterior y el
            # nuevo.

            assert any(
                "antes" in linea and "despues" in linea
                for linea in lineas[1:]
            ), lineas[:3]

        finally:

            vista.deleteLater()

    def test_el_vendedor_no_lee_la_auditoria(
        self, como_vendedor
    ):
        """
        Leer el rastro es de la administración. Un
        vendedor no ve ni sus propios movimientos.
        """

        from errores import PermisoDenegado

        with pytest.raises(PermisoDenegado):

            obtener_auditoria()

        with pytest.raises(PermisoDenegado):

            obtener_historial("REF-1")

        with pytest.raises(PermisoDenegado):

            obtener_cambios()