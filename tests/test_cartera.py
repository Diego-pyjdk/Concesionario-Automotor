"""
Pruebas de la cartera, del detalle del contrato y de
los formularios de la financiera.

Las pruebas de la GUI no se podeLPON a que las
pantallas se construyan y a que pinten lo que deben.
Es lo único que detecta un NameError de runtime, un
import que sobra o un parametro mal pasado: compilar
no lo detecta y los datos estan bien, lo que estaba
mal era como se leian.
"""

import os

from datetime import date
from decimal import Decimal

import pytest

import database.financiera as F
import database.cobranza as C

from database.contratos import crear_contrato

from database.ventas import registrar_venta

from errores import PermisoDenegado


# ==========================================
# HELPERS
# ==========================================

def _prepara_qt():

    """
    Deja una QApplication con la hoja de estilos puesta
    y los cuadros de dialogo parcheados.

    Sin esto, construir una vista tumba el proceso
    con un fallo de segmentacion y pytest no llega ni
    a escribir el informe.

    ------------------------------
    # POR QUÉ LA HOJA DE ESTILOS
    # ------------------------------

    Porque sin ella las MEDIDAS mienten.

    Los botones de acción llevan `objectName` y su
    regla dice `font-size: 11px` y `padding: 0`. Sin
    la hoja, Qt mide con la fuente por defecto y con su
    relleno: "Eliminar" pide 110 px en vez de los 72 que
    pide de verdad, y cualquier prueba que compare el
    ancho puesto con `sizeHint()` dice que los quince
    botones de la aplicación están recortados. No lo
    están: la medición es la que está mal.

    `main.py` aplica la hoja al arrancar, asi que aquí
    se hace lo mismo. Una prueba de interfaz que mide
    sobre una interfaz que no es la de la aplicacion
    mide otra cosa.
    """

    os.environ["QT_QPA_PLATFORM"] = "offscreen"

    from PySide6.QtWidgets import (
        QApplication,
        QMessageBox,
        QInputDialog
    )

    if QApplication.instance() is None:

        QApplication([])

    # La hoja se pone SIEMPRE, no solo la primera vez.
    #
    # Otro archivo de pruebas puede haber creado la
    # QApplication antes, y entonces el `if` la
    # saltaba: las medidas salían sin estilo y
    # cualquier botón parecía recortado. Dependiendo del
    # ORDEN de los archivos, unas pruebas veían un ancho
    # y otras otro.
    #
    # `setStyleSheet` es idempotente, así que repetirlo no
    # cuesta nada.

    raiz = os.path.dirname(os.path.dirname(
        os.path.abspath(__file__)
    ))

    hoja = os.path.join(raiz, "gui", "estilo.css")

    if os.path.exists(hoja):

        with open(hoja, encoding="utf-8") as archivo:

            QApplication.instance().setStyleSheet(
                archivo.read()
            )

    QApplication.instance().processEvents()

    for nombre in (
        "warning", "information", "critical",
        "question", "about"
    ):

        setattr(
            QMessageBox,
            nombre,
            staticmethod(lambda *a, **k: QMessageBox.Ok)
        )

    QInputDialog.getItem = staticmethod(
        lambda *a, **k: ("", False)
    )

    QInputDialog.getText = staticmethod(
        lambda *a, **k: ("", False)
    )


def _saldo_de_cuota(id_cuota):

    return Decimal(str(F.obtener_cuota(id_cuota)["saldo"]))


@pytest.fixture
def venta_con_contrato(
    como_administrador, datos_base
):

    """
    Una venta de 100.000 con 40.000 de anticipo y
    seis cuotas de 10.000, con el cronograma ya
    generado y la primera vencida.
    """

    _, id_auto, id_cliente = datos_base

    id_venta, _ = registrar_venta(
        id_cliente, id_auto, "2026-01-10", 100000.0
    )

    id_contrato, numero = crear_contrato(
        venta_id=id_venta,
        forma_pago="Anticipo + cuotas",
        anticipo=40000.0,
        cantidad_cuotas=6,
        saldo_financiado=Decimal("60000.00"),
        periodicidad="mensual",
        primer_vencimiento=date(2026, 2, 10)
    )

    assert id_contrato is not None, numero

    total, motivo = F.generar_cronograma(id_contrato)

    assert total == 6, motivo

    return {
        "id_contrato": id_contrato,
        "id_venta": id_venta,
        "numero": numero,
        "cuotas": F.obtener_cuotas(id_contrato)
    }


# ==========================================
# LOS BOTONES DE LAS FILAS
# ==========================================
# Todas las pruebas de arriba CONSTRUYEN una vista.
# Construir no es usar: un metodo que llama a otro que
# ya no existe revienta al pulsar, no al abrir.
#
# `ver_venta()` estuvo roto porque le faltaba
# `buscar_venta()`, y no se noto con 428 pruebas
# porque ninguna pulsaba nada. Estas Si.


@pytest.fixture
def sin_ventanas():
    """
    Impide que se abra un dialogo de verdad.

    Importa que sea UNA FIXTURE y no un parche dentro
    del metodo: si se restaura al terminar de
    construir la vista, la llamada siguiente vuelve a
    tener el `exec` de verdad y la prueba se queda
    colgada en un modal sin decir donde. Se perdio una
    hora justo asi, con `faulthandler_timeout`.

    Se parchea `QDialog.exec` de PySide6, no el de
    cada formulario: todos heredan de el, y parchear
    los de uno en uno se olvidaria alguno.
    """

    import PySide6.QtWidgets as ventana

    original = ventana.QDialog.exec

    ventana.QDialog.exec = lambda self: 0

    try:

        yield

    finally:

        ventana.QDialog.exec = original


def _construye(ruta, clase, sesion=None):

    _prepara_qt()

    import importlib

    modulo = importlib.import_module(ruta)

    return getattr(modulo, clase)()


class TestLosBotonesDeLasFilas:

    def test_ver_venta_no_revisa(
        self,
        como_administrador,
        venta_con_contrato,
        sin_ventanas
    ):

        """
        El boton **Ver** de una venta.

        Es el que estaba roto: `ver_venta()` buscaba
        la venta con `buscar_venta()`, que se habia
        borrado al arreglar el camino del contrato, y
        fallaba con un `AttributeError` al pulsar. La
        venta aparecia en la lista y no se abria.
        """

        from database.pagos import registrar_pago

        registrar_pago(
            venta_con_contrato["id_venta"],
            1000.0,
            "2026-10-05",
            "Efectivo"
        )

        vista = _construye("gui.ventas_view", "VentasView")

        try:

            assert vista.tabla.rowCount() >= 1

            assert vista.leer_id_venta(0) is not None

            # El metodo que usa el boton. Antes de
            # esto, el AttributeError salia aqui.

            vista.ver_venta(0)

        finally:

            vista.deleteLater()

    def test_buscar_venta_devuelve_la_fila(
        self,
        como_administrador,
        venta_con_contrato,
        sin_ventanas
    ):

        """
        `buscar_venta()` existe y anda.

        Se comprueba por separado y no solo a través
        de `ver_venta()`: que el boton funcione no dice
        que encuentre la fila correcta, solo que no
        revienta. Y un `None` silencioso en
        `ver_venta()` sale como un "No se encontro la
        venta." que parece un problema de datos.
        """

        from database.ventas import obtener_ventas

        vista = _construye("gui.ventas_view", "VentasView")

        try:

            esperada = next(
                v for v in obtener_ventas()
                if v[0] == venta_con_contrato["id_venta"]
            )

            assert vista.buscar_venta(
                venta_con_contrato["id_venta"]
            ) == esperada

            assert vista.buscar_venta(999999) is None

        finally:

            vista.deleteLater()

    def test_todos_los_botones_de_ventas(
        self,
        como_administrador,
        venta_con_contrato,
        sin_ventanas
    ):

        """
        Los tres botones de la fila de una venta.

        Todos, en el mismo archivo y a la vez, para
        que un metodo que llame a otro que se borre se
        note en la siguiente carrera y no en un aviso
        del usuario.
        """

        vista = _construye("gui.ventas_view", "VentasView")

        try:

            for nombre in (
                "ver_venta",
                "crear_contrato",
                "eliminar_venta"
            ):

                getattr(vista, nombre)(0)

        finally:

            vista.deleteLater()

    def test_los_botones_de_contratos(
        self,
        como_administrador,
        venta_con_contrato,
        sin_ventanas
    ):

        """
        Los de la fila de un contrato.

        `CarteraView` no se comprueba aqui: sus
        botones usan las palabras clave de sus
        callbacks, no el indice de fila, y salen en
        sus propias pruebas.
        """

        vista = _construye(
            "gui.contratos_view", "ContratosView"
        )

        try:

            assert vista.tabla.rowCount() >= 1

            vista.ver_detalle(0)

        finally:

            vista.deleteLater()


# ==========================================
# LA CARTERA SE CONSTRUYE Y PINTA
# ==========================================

class TestCarteraView:

    def test_se_construye_y_pinta_la_deuda(
        self, venta_con_contrato
    ):

        _prepara_qt()

        from gui.cartera_view import CarteraView

        vista = CarteraView()

        try:

            # ------------------------------
            # UNA FILA POR CONTRATO
            # ------------------------------
            # Con un contrato financiado, con
            # saldo, tiene que haber exactamente
            # una fila. Ni cero (no se leeria nada) ni
            # dos (estaria contando el contrato dos
            # veces).

            assert vista.tabla.rowCount() == 1

            # Y el saldo que sale es el PENDIENTE, no
            # el financiado: un contrato pagado del
            # todo no puede aparecer debiendo su
            # precio entero.

            fila = [
                vista.tabla.item(0, columna).text()
                for columna in range(8)
            ]

            assert fila[0] == venta_con_contrato["numero"]

            assert venta_con_contrato["numero"] in fila[0]

            # ------------------------------
            # LAS CUATRO PESTAÑAS
            # ------------------------------

            assert vista.pestanas.count() == 4

            # ------------------------------
            # EL ANTIGUEDAD TIENE LOS
            # TRAMOS
            # ------------------------------

            assert vista.tabla_antiguedad.rowCount() > 0

        finally:

            vista.deleteLater()

    def test_una_cuota_vencida_aparece_en_su_pestana(
        self, venta_con_contrato
    ):

        _prepara_qt()

        # ------------------------------
        # VENCER LA PRIMERA
        # ------------------------------
        # No se fuerza con un UPDATE: se registra
        # un pago y se anula, que es el camino de
        # verdad, y procesar_vencidas() la marca sola.
        #
        # La razon: una prueba que pone "vencida" a
        # mano solo comprueba que la vista pinta lo
        # que hay en la tabla. La interest en si
        # misma la comprueba test_financiera.py.

        id_cuota = venta_con_contrato["cuotas"][0]["id"]

        id_pago, motivo = F.registrar_pago_cuota(
            id_cuota,
            Decimal("10000.00"),
            "2026-02-10",
            "Efectivo"
        )

        assert id_pago is not None, motivo

        correcto, resultado = F.anular_pago(
            id_pago, "Prueba: devolver la cuota"
        )

        assert correcto, resultado

        F.procesar_vencidas()

        from gui.cartera_view import CarteraView

        vista = CarteraView()

        try:

            # La cuota vuelve a estar pendiente...

            assert _saldo_de_cuota(id_cuota) == (
                Decimal("10000.00")
            )

            # ...y como su fecha ya paso, sale en la
            # pestaña de vencidas con su retraso.

            assert vista.tabla_vencidas.rowCount() >= 1

            textos = [
                vista.tabla_vencidas.item(
                    fila, 6
                ).text()
                for fila in range(
                    vista.tabla_vencidas.rowCount()
                )
            ]

            assert any(
                "d." in texto for texto in textos
            ), textos

            # Y el contrato entero sale marcado como
            # vencido en la lista principal.

            assert vista.tabla.rowCount() == 1

        finally:

            vista.deleteLater()

    def test_el_vendedor_no_ve_la_cartera(
        self, venta_con_contrato, como_vendedor
    ):

        """
        La cartera no se construye para el vendedor.

        Y no solo se esconde el boton: la VISTA no
        llega a existir, porque la seccion lleva
        permiso de lectura. Y las consultas de
        database/cobranza.py tambien lo piden, que es
        lo único que protege si alguien las llama desde
        un script.
        """

        _prepara_qt()

        from gui.ventana_principal import VentanaPrincipal

        secciones = [
            (texto, vista, permiso)
            for texto, vista, permiso
            in VentanaPrincipal.SECCIONES
        ]

        assert len(secciones) == 11

        visibles = []

        for texto, vista, permiso in secciones:

            from permisos import tiene_permiso

            if tiene_permiso(permiso):

                visibles.append(texto)

        assert not any(
            "Cartera" in texto for texto in visibles
        ), visibles

        # Y la consulta de datos, directamente.

        with pytest.raises(PermisoDenegado):

            C.cuentas_por_cobrar()

        with pytest.raises(PermisoDenegado):

            C.resumen_cartera()

        with pytest.raises(PermisoDenegado):

            C.cuotas_vencidas()


# ==========================================
# EL DETALLE DEL CONTRATO
# ==========================================

class TestContratoDetalle:

    def test_se_construye_y_muestra_el_cronograma(
        self, venta_con_contrato
    ):

        _prepara_qt()

        from gui.contrato_detalle_dialog import (
            ContratoDetalleDialog
        )

        dialogo = ContratoDetalleDialog(
            None, venta_con_contrato["id_contrato"]
        )

        try:

            # ------------------------------
            # LAS CUATRO PESTANAS
            # ------------------------------
            # El historial sale porque el
            # administrador tiene permiso de
            # auditoria.

            assert dialogo.pestanas.count() == 4

            assert dialogo.tabla_cuotas.rowCount() == 6

            assert dialogo.pestanas.currentIndex() == 0

            # ------------------------------
            # LOS BOTONES DE COBRO
            # ------------------------------

            assert dialogo.boton_cobrar.isEnabled()

            # El cronograma ya existe, así que no se
            # puede generar otro.

            assert not dialogo.boton_generar.isEnabled()

            # ------------------------------
            # EL SALDO EN LAS CUATRO
            # CIFRAS
            # ------------------------------

            importes = [
                etiqueta.text()
                for etiqueta
                in dialogo.etiquetas_dinero.values()
            ]

            assert any(
                "60,000.00" in texto
                for texto in importes
            ), importes

        finally:

            dialogo.deleteLater()

    def test_el_vendedor_no_ve_el_historial(
        self, venta_con_contrato, como_vendedor
    ):

        """
        El historial exige VER_AUDITORIA, así que la
        pestaña no se AÑADE.

        Y no se añade en vez de deshabilitarse: una
        pestaña que al pinchar no dice nada es peor
        que no tenerla, porque parece un fallo.
        """

        _prepara_qt()

        from gui.contrato_detalle_dialog import (
            ContratoDetalleDialog
        )

        dialogo = ContratoDetalleDialog(
            None, venta_con_contrato["id_contrato"]
        )

        try:

            assert dialogo.pestanas.count() == 3

            titulos = [
                dialogo.pestanas.tabText(i)
                for i in range(dialogo.pestanas.count())
            ]

            assert not any(
                "Historial" in titulo
                for titulo in titulos
            ), titulos

            # Y aunque se le pregunte directamente,
            # no lo da.

            with pytest.raises(PermisoDenegado):

                from database.auditoria import (
                    historial_contrato
                )

                historial_contrato(
                    venta_con_contrato["id_contrato"]
                )

        finally:

            dialogo.deleteLater()

    def test_el_detalle_avisa_de_un_contrato_que_no_existe(
        self, como_administrador
    ):

        """
        Un id que no existe no revienta el dialogo.

        Se pinta el motivo y se deja cerrar. Un
        dialogo que reventa al construirse deja la
        pantalla en blanco sin decir por que, que es
        como se responde a un usuario.
        """

        _prepara_qt()

        from gui.contrato_detalle_dialog import (
            ContratoDetalleDialog
        )

        dialogo = ContratoDetalleDialog(None, 999999)

        try:

            assert dialogo.titulo.text() == (
                "Contrato no encontrado"
            )

            assert "no existe" in (
                dialogo.etiqueta_pie.text().lower()
            )

        finally:

            dialogo.deleteLater()

    def test_el_detalle_avisa_de_la_garantia_registral(
        self, venta_con_contrato
    ):

        """
        El aviso de que un gravamen hay que
        validarlo sale SIEMPRE, con garantías o sin
        ellas.

        Sin garantías es donde más importa: es el
        momento de dar de alta la primera, y es
        cuando se decide sin tener delante nada que
        lo recuerde.
        """

        _prepara_qt()

        from gui.contrato_detalle_dialog import (
            ContratoDetalleDialog
        )

        import database.garantias as G

        dialogo = ContratoDetalleDialog(
            None, venta_con_contrato["id_contrato"]
        )

        try:

            assert G.AVISO_GRAVAMEN in (
                dialogo.aviso_registral.text()
            )

        finally:

            dialogo.deleteLater()


# ==========================================
# LOS FORMULARIOS
# ==========================================

class TestPagoCuotaForm:

    def test_propone_el_saldo_completo(
        self, venta_con_contrato
    ):

        """
        El importe por defecto es el saldo entero.

        Es lo que se cobra casi siempre, y tener que
        escribirlo cada vez es una fuente de erratas:
        3.208.333,33 tecleado a mano, con el
        separador mal, son 320.833,33.
        """

        _prepara_qt()

        from gui.formularios.pago_cuota_form import (
            PagoCuotaForm
        )

        id_cuota = venta_con_contrato["cuotas"][1]["id"]

        formulario = PagoCuotaForm(None, id_cuota)

        try:

            saldo = Decimal(
                str(F.obtener_cuota(id_cuota)["saldo"])
            )

            assert formulario.campo_importe.value() == (
                float(saldo)
            )

            # Y no admite m\u00e1s que el saldo: el
            # error se evita en el campo, y la
            # validaci\u00f3n de verdad la hace la capa
            # de datos con la cuota bloqueada.

            assert formulario.campo_importe.maximum() == (
                float(saldo)
            )

            # Y el contexto dice a QUI\u00e9 y de QU\u00c9.

            contexto = formulario.etiqueta_contexto.text()

            assert venta_con_contrato["numero"] in (
                contexto
            )

        finally:

            formulario.deleteLater()

    def test_no_deja_cobrar_una_cuota_pagada(
        self, venta_con_contrato
    ):

        _prepara_qt()

        from gui.formularios.pago_cuota_form import (
            PagoCuotaForm
        )

        id_cuota = venta_con_contrato["cuotas"][0]["id"]

        F.registrar_pago_cuota(
            id_cuota,
            Decimal("10000.00"),
            "2026-02-10",
            "Efectivo"
        )

        formulario = PagoCuotaForm(None, id_cuota)

        try:

            # El boton se apaga y se explica por que,
            # en vez de dejar un formulario lleno de
            # campos que no sirven para nada.

            assert not formulario.boton_guardar.isEnabled()

            assert not formulario.campo_importe.isEnabled()

            assert any(
                "pagada" in motivo
                for motivo in formulario.motivos
            ), formulario.motivos

        finally:

            formulario.deleteLater()

    def test_no_deja_cobrar_una_cuota_anulada(
        self, venta_con_contrato
    ):

        _prepara_qt()

        from gui.formularios.pago_cuota_form import (
            PagoCuotaForm
        )

        id_cuota = venta_con_contrato["cuotas"][0]["id"]

        correcto, resultado = F.anular_cuota(
            id_cuota, "Prueba"
        )

        assert correcto, resultado

        formulario = PagoCuotaForm(None, id_cuota)

        try:

            assert not formulario.boton_guardar.isEnabled()

            assert any(
                "anulada" in motivo
                for motivo in formulario.motivos
            ), formulario.motivos

        finally:

            formulario.deleteLater()


class TestGarantiaForm:

    def test_se_construye_con_el_aviso(
        self, venta_con_contrato
    ):

        _prepara_qt()

        from gui.formularios.garantia_form import (
            GarantiaForm
        )

        formulario = GarantiaForm(
            None, venta_con_contrato["id_contrato"]
        )

        try:

            assert formulario.campo_tipo.count() > 0

            # El aviso sale con el formulario reci\u00e9n
            # creado y con la garant\u00eda todav\u00eda sin
            # registrar.

            import database.garantias as G

            assert G.AVISO_GRAVAMEN in (
                formulario.etiqueta_aviso.text()
            )

            # Y se avisa de que marcar "inscrita"
            # no inscribe nada.

            formulario.campo_estado.setCurrentIndex(1)

            assert "INSCRITA" in (
                formulario.etiqueta_aviso.text().upper()
            )

            # Con "pendiente" se vuelve al aviso normal.

            formulario.campo_estado.setCurrentIndex(0)

            assert formulario.etiqueta_aviso.text() == (
                G.AVISO_GRAVAMEN
            )

        finally:

            formulario.deleteLater()

    def test_el_campo_de_inscripcion_solo_abilita_si_esta_inscrita(
        self, venta_con_contrato
    ):

        """
        Los datos registrales solo se rellenan si el
        estado es "inscrita".

        "Pendiente" significa pendiente: guardar un
        n\u00famero de inscripci\u00f3n con ella pondr\u00eda en la
        base algo que no ha pasado, y esa fila es la
        que luego se lee para saber si el gravamen
        est\u00e1 o no.
        """

        _prepara_qt()

        from gui.formularios.garantia_form import (
            GarantiaForm
        )

        formulario = GarantiaForm(
            None, venta_con_contrato["id_contrato"]
        )

        try:

            formulario.campo_estado.setCurrentIndex(0)

            assert not formulario.campo_numero.isEnabled()

            formulario.campo_estado.setCurrentIndex(1)

            assert formulario.campo_numero.isEnabled()

        finally:

            formulario.deleteLater()


# ==========================================
# EL FORMULARIO DE CONTRATO
# ==========================================

class TestContratoForm:

    def test_la_previa_muestra_el_cronograma(
        self, como_administrador, datos_base
    ):

        """
        La vista previa del cronograma.

        Es la parte del formulario mas importante y
        la mas fácil de hacer mal: si la vista previa
        repartiera el saldo con otra formula, la
        ultima cuota del papel seria distinta de la
        que ve el cliente.
        """

        _prepara_qt()

        from gui.formularios.contrato_form import (
            ContratoForm
        )

        _, id_auto, id_cliente = datos_base

        id_venta, _ = registrar_venta(
            id_cliente, id_auto, "2026-01-10", 100000.0
        )

        formulario = ContratoForm(None, id_venta)

        try:

            formulario.campo_forma_pago.setCurrentText(
                "Anticipo + cuotas"
            )

            formulario.campo_anticipo.setText("40000")

            formulario.campo_cuotas.setValue(6)

            formulario.actualizar_todo()

            assert formulario.tabla_previa.rowCount() == 6

            # ------------------------------
            # LA SUMA CUADRA
            # ------------------------------

            suma = sum(
                Decimal(
                    formulario.tabla_previa.item(
                        fila, 2
                    ).text().replace(",", "")
                    .replace("$", "").strip()
                )
                for fila in range(6)
            )

            assert suma == Decimal("60000.00"), suma

            # ------------------------------
            # Y LOS VENCIMIENTOS AVANZAN
            # POR MESES
            # ------------------------------

            fechas = [
                formulario.tabla_previa.item(
                    fila, 1
                ).text()
                for fila in range(6)
            ]

            assert len(set(fechas)) == 6, fechas

        finally:

            formulario.deleteLater()

    def test_la_periodicidad_por_defecto_es_mensual(
        self, como_administrador, datos_base
    ):

        """
        No semanal.

        TODAS_LAS_PERIODICIDADES empieza por "semanal",
        asi que un combo reci\u00e9n creado queda en
        semanal y un cr\u00e9dito de doce cuotas se
        repartir\u00eda en doce semanas. El dato se toma
        por findData(), no por la posici\u00f3n.
        """

        _prepara_qt()

        from gui.formularios.contrato_form import (
            ContratoForm
        )

        _, id_auto, id_cliente = datos_base

        id_venta, _ = registrar_venta(
            id_cliente, id_auto, "2026-01-10", 100000.0
        )

        formulario = ContratoForm(None, id_venta)

        try:

            assert formulario.campo_periodicidad.currentData() == (
                "mensual"
            )

        finally:

            formulario.deleteLater()

    def test_contado_no_admite_anticipo_ni_cuotas(
        self, como_administrador, datos_base
    ):

        """
        "Contado" desactiva los dos campos.

        Y los desactiva en vez de vaciarlos: si se
        vaciaran, al volver a "Anticipo + cuotas"
        habria que reescribirlos, y un usuario que
        prueba las dos formas perdería lo que tenía.
        """

        _prepara_qt()

        from gui.formularios.contrato_form import (
            ContratoForm
        )

        _, id_auto, id_cliente = datos_base

        id_venta, _ = registrar_venta(
            id_cliente, id_auto, "2026-01-10", 100000.0
        )

        formulario = ContratoForm(None, id_venta)

        try:

            formulario.campo_anticipo.setText("40000")

            formulario.campo_cuotas.setValue(6)

            formulario.campo_forma_pago.setCurrentText(
                "Contado"
            )

            assert not formulario.campo_anticipo.isEnabled()

            assert not formulario.campo_cuotas.isEnabled()

            # El texto se conserva.

            assert formulario.campo_anticipo.text() == (
                "40000"
            )

            assert formulario.campo_cuotas.value() == 6

            formulario.campo_forma_pago.setCurrentText(
                "Anticipo + cuotas"
            )

            assert formulario.campo_anticipo.isEnabled()

            assert formulario.campo_anticipo.text() == (
                "40000"
            )

        finally:

            formulario.deleteLater()

    def test_no_deja_firmar_saldo_cero_con_cuotas(
        self, como_administrador, datos_base
    ):

        _prepara_qt()

        from gui.formularios.contrato_form import (
            ContratoForm
        )

        _, id_auto, id_cliente = datos_base

        id_venta, _ = registrar_venta(
            id_cliente, id_auto, "2026-01-10", 100000.0
        )

        formulario = ContratoForm(None, id_venta)

        try:

            formulario.campo_forma_pago.setCurrentText(
                "Anticipo + cuotas"
            )

            formulario.campo_anticipo.setText("100000")

            formulario.campo_cuotas.setValue(12)

            error = formulario.validar()

            assert error is not None

            assert "financiar" in error.lower(), error

        finally:

            formulario.deleteLater()
# ==========================================
# LOS BOTONES DE LA CARTERA
# ==========================================
# La columna de acciones de la cartera NO EXISTIA.
#
# `crear_tabla()` no la anade: solo le pone el ancho
# fijo. Si el indice queda fuera de la lista de
# cabeceros, la columna no se crea, `setCellWidget()`
# no pone nada, y los botones NO SE VEN. Sin error, sin
# aviso y sin una sola prueba que lo note, porque
# construccion no es pintura: la tabla se llenaba y
# todos los demas botones de la aplicacion salian.
#
# El cobro de una cuota tampoco se podia hacer desde
# la cartera: solo desde el detalle del contrato.
# Para cobrar habia que abrir el contrato.


class TestLosBotonesDeLaCartera:

    def _fila_de_acciones(self, tabla, columna):
        """
        El contenedor de los botones de una fila, o
        None.

        Se busca la columna con `setCellWidget` en vez
        de suponer el indice: si la columna no existe,
        la prueba tiene que FALLAR diciendo que no
        existe, no reventar con un AttributeError que
        no explica nada.
        """

        for indice in range(tabla.columnCount()):

            if tabla.cellWidget(0, indice) is not None:

                return tabla.cellWidget(0, indice)

        return None

    def test_la_columna_de_acciones_existe(
        self,
        como_administrador,
        venta_con_contrato,
        sin_ventanas
    ):

        """
        La columna de acciones existe Y tiene botones.

        La comprobacion del ancho de columna y la del
        texto de las celdas no servian: sin columna no
        hay celdas, asi que una lista vacia de
        comprobaciones sobre celdas vacias pasa
        siempre.
        """

        vista = _construye("gui.cartera_view", "CarteraView")

        try:

            assert vista.tabla.rowCount() >= 1, (
                "no hay filas que comprobar"
            )

            from gui.cartera_view import (
                COLUMNA_ACCIONES_CARTERA
            )

            assert COLUMNA_ACCIONES_CARTERA < (
                vista.tabla.columnCount()
            ), (
                "la columna de acciones no existe: "
                f"el indice {COLUMNA_ACCIONES_CARTERA} "
                f"está fuera de una tabla de "
                f"{vista.tabla.columnCount()} columnas. "
                "Falta 'Acciones' en la lista."
            )

            contenedor = self._fila_de_acciones(
                vista.tabla,
                COLUMNA_ACCIONES_CARTERA
            )

            assert contenedor is not None, (
                "la celda de acciones está vacía"
            )

        finally:

            vista.deleteLater()

    def test_los_tres_botones_del_administrador(
        self,
        como_administrador,
        venta_con_contrato,
        sin_ventanas
    ):

        """
        El administrador ve Adelantado, Cobrar y Ver.

        Los tres, por este orden: desde la cartera, que
        esta ordenada por retraso, la pregunta del
        cajero es "y si este senor quiere dejar pagado
        el mes que viene?", y esa va primero.

        Y los tres tienen que ser ANCHOS DISTINTOS de
        texto, porque ponerlos a mano hace que el mas
        largo salga con puntos suspensivos.
        """

        vista = _construye("gui.cartera_view", "CarteraView")

        try:

            contenedor = self._fila_de_acciones(
                vista.tabla, 8
            )

            assert contenedor is not None

            textos = [
                contenedor.layout().itemAt(c).widget().text()
                for c in range(contenedor.layout().count())
            ]

            assert textos == [
                "Adelantado", "Cobrar", "Ver"
            ], f"los botones son {textos}"

            for c in range(contenedor.layout().count()):

                boton = contenedor.layout().itemAt(c).widget()

                assert (
                    boton.width() >= boton.sizeHint().width()
                ), (
                    f"el boton '{boton.text()}' se recorta"
                )

        finally:

            vista.deleteLater()

    def test_el_vendedor_no_tiene_cartera(
        self,
        como_vendedor,
        venta_con_contrato,
        sin_ventanas
    ):

        """
        El vendedor no ve la cartera. Ni una fila.

        No es que se la enseñen vacia: `cuentas_por_
        cobrar` pide VER_FINANCIERA y el vendedor no lo
        tiene, asi que la consulta no se hace y la tabla
        sale sin pintar. Que saliera con datos seria un
        fallo de permisos, no un detalle de la interfaz.

        Y el boton de cobrar tampoco existe para el, que
        es lo que importa: `cobrar_adelantado()` cae al
        detalle, donde tampoco puede cobrar.
        """

        vista = _construye("gui.cartera_view", "CarteraView")

        try:

            assert vista.puede_gestionar is False

            assert vista.tabla.rowCount() == 0, (
                "el vendedor ve la cartera, y deberia "
                "verla vacia porque no tiene permiso"
            )

            # Y si se le pide cobrar, cae al detalle en
            # vez de abrir el formulario de cobro.

            vista.cobrar_adelantado(
                venta_con_contrato["id_contrato"]
            )

        finally:

            vista.deleteLater()

    def test_las_tres_tablas_tienen_columna(
        self,
        como_administrador,
        venta_con_contrato,
        sin_ventanas
    ):

        """
        Las cuatro tablas, no solo la primera.

        Vencidas y por vencer tenian el mismo fallo que
        "Por cobrar": siete cabeceros y el indice 7.
        Antigiuedad no lleva botones y se construct
        sin columna.
        """

        vista = _construye("gui.cartera_view", "CarteraView")

        try:

            from gui.cartera_view import (
                COLUMNA_ACCIONES_CUOTA
            )

            for nombre in (
                "tabla", "tabla_vencidas", "tabla_por_vencer"
            ):

                tabla = getattr(vista, nombre)

                assert COLUMNA_ACCIONES_CUOTA < (
                    tabla.columnCount()
                ), (
                    f"{nombre}: la columna de acciones "
                    f"no existe "
                    f"({COLUMNA_ACCIONES_CUOTA} de "
                    f"{tabla.columnCount()} columnas)"
                )

        finally:

            vista.deleteLater()

    def test_los_botones_no_se_recortan(
        self,
        como_administrador,
        venta_con_contrato,
        sin_ventanas
    ):

        """
        Ningun boton de ninguna tabla se recorta.

        El ancho va con `setFixedSize()`, asi que el
        layout no lo puede encoger: si se queda corto,
        el texto sale cortado y no se sabe si "Cobrar"
        es "Cobrar" o "Cobram...".

        Se recorre la tabla de ACCIONES de cada vista
        que tenga, no una lista de nombres: si alguien
        anade una quinta columna con botones y no la
        anade aqui, el recorte se nota en su pantalla y
        no aqui.
        """

        vistas = (
            ("gui.cartera_view", "CarteraView"),
            ("gui.ventas_view", "VentasView"),
            ("gui.contratos_view", "ContratosView"),
            ("gui.clientes_view", "ClientesView"),
            ("gui.autos_view", "AutosView"),
            ("gui.marcas_view", "MarcasView"),
            ("gui.usuarios_view", "UsuariosView")
        )

        vistas = [
            (ruta, clase)
            for ruta, clase in vistas
            if ruta != "gui.cartera_view"
        ]

        import PySide6.QtWidgets as ventana

        recortados = []

        for ruta, clase in vistas:

            vista = _construye(ruta, clase)

            try:

                tabla = vista.tabla

                for fila in range(tabla.rowCount()):

                    for columna in range(
                        tabla.columnCount()
                    ):

                        celda = tabla.cellWidget(
                            fila, columna
                        )

                        if celda is None:

                            continue

                        for c in range(
                            celda.layout().count()
                        ):

                            boton = (
                                celda.layout()
                                .itemAt(c)
                                .widget()
                            )

                            if not isinstance(
                                boton, ventana.QPushButton
                            ):

                                continue

                            if boton.width() < (
                                boton.sizeHint().width()
                            ):

                                recortados.append(
                                    f"{clase} "
                                    f"'{boton.text()}' "
                                    f"{boton.width()}"
                                    f"<"
                                    f"{boton.sizeHint().width()}"
                                )

            finally:

                vista.deleteLater()

        assert not recortados, (
            "botones con el texto cortado: "
            + ", ".join(recortados)
        )


# ==========================================
# EL COBRO ADELANTADO EN PANTALLA
# ==========================================


class TestElFormularioDeAdelantado:

    @pytest.fixture
    def pregunta_que_si(self, monkeypatch):
        """
        `QMessageBox.question` responde SI.

        `_prepara_qt()` lo deja en `Ok`, que es lo
        natural al parchear a ciegas, y entonces
        `confirmar()` devuelve falso y el formulario se
        calla: el cobro no se hace y parece que el
        boton esta roto cuando lo que esta roto es el
        parche.

        OJO al orden: `_prepara_qt()` vuelve a parchear
        los cinco metodos cada vez que se la llama, asi
        que este parche tiene que poner DESPUES de
        `_prepara_qt()`, no antes. Por eso se fuerza
        aqui y no con un simple `monkeypatch`, que
        se dejaria pisar.
        """

        import PySide6.QtWidgets as ventana

        original = ventana.QMessageBox.question

        ventana.QMessageBox.question = staticmethod(
            lambda *a, **k: ventana.QMessageBox.Yes
        )

        try:

            yield

        finally:

            ventana.QMessageBox.question = original

    def _formulario(self, id_contrato, con_confirmacion=False):

        _prepara_qt()

        if con_confirmacion:

            # Vuelve a parchear DESPUES de
            # `_prepara_qt()`, que es la que pisa los
            # cinco metodos. Con el orden al reves, el
            # parche se pierde y `confirmar()` falla.

            import PySide6.QtWidgets as ventana

            ventana.QMessageBox.question = staticmethod(
                lambda *a, **k: ventana.QMessageBox.Yes
            )

        from gui.formularios.pago_adelantado_form import (
            PagoAdelantadoForm
        )

        return PagoAdelantadoForm(None, id_contrato)

    def test_se_construye_y_propone_una_cuota(
        self,
        como_administrador,
        venta_con_contrato,
        sin_ventanas
    ):

        """
        Abre con la primera cuota puesta.

        Es lo mas probable y ahorra tener que escribir
        un numero de una cuota que el usuario acaba de
        ver en pantalla.
        """

        formulario = self._formulario(
            venta_con_contrato["id_contrato"]
        )

        try:

            assert formulario.campo_importe.value() == (
                10000.0
            )

            assert formulario.tabla.rowCount() == 1

            assert formulario.boton_guardar.isEnabled()

        finally:

            formulario.deleteLater()

    def test_la_vista_previa_es_el_reparto_real(
        self,
        como_administrador,
        venta_con_contrato,
        sin_ventanas
    ):

        """
        Lo que se ve antes de cobrar es lo que se
        guarda.

        Sale de la MISMA funcion que reparte, `F
        .repartir_adelanto()`. Si esta pantalla
        calculara el reparto por su cuenta, el cliente
        veria un reparto y le aplicarian otro.
        """

        formulario = self._formulario(
            venta_con_contrato["id_contrato"]
        )

        try:

            formulario.sumar_una_cuota()

            assert formulario.campo_importe.value() == (
                20000.0
            )

            assert formulario.tabla.rowCount() == 2

            esperado, sobra = F.repartir_adelanto(
                venta_con_contrato["cuotas"],
                Decimal("20000.00")
            )

            assert sobra == Decimal("0.00")

            for indice, parte in enumerate(esperado):

                celda_n = formulario.tabla.item(
                    indice, 0
                ).text()

                assert celda_n == str(parte["numero"])

        finally:

            formulario.deleteLater()

    def test_lo_que_sobra_no_le_deja_cobrar(
        self,
        como_administrador,
        venta_con_contrato,
        sin_ventanas
    ):

        """
        Si el importe no cabe, el boton se apaga.

        Con un solo plan de 60.000 y 70.000 escritos, el
        sobrante de 10.000 no tiene donde imputarse. El
        boton apagado lo deja claro ANTES de que el
        cajero escriba el numero: un error despues de
        haber tecleado 70.000 cuesta mas que una
        etiqueta.
        """

        formulario = self._formulario(
            venta_con_contrato["id_contrato"]
        )

        try:

            formulario.campo_importe.setValue(70000.0)

            assert formulario.sobrante == Decimal(
                "10000.00"
            )

            assert not formulario.boton_guardar.isEnabled()

        finally:

            formulario.deleteLater()

    def test_cobra_dos_meses_y_lo_dice(
        self,
        como_administrador,
        venta_con_contrato,
        sin_ventanas,
        pregunta_que_si
    ):

        """
        El recorrido entero: dos meses, un recibo.

        Y que los recibos que devuelve sean UNO, no dos:
        el cliente se lleva un papel.
        """

        formulario = self._formulario(
            venta_con_contrato["id_contrato"],
            con_confirmacion=True
        )

        try:

            formulario.sumar_una_cuota()

            formulario.guardar()

            assert formulario.result() == 1, (
                "el formulario no se cerro con exito"
            )

            assert len(formulario.recibos) == 2

            assert len(set(formulario.recibos)) == 1, (
                "un cobro de dos cuotas tiene que "
                f"salir con un recibo, no con dos: "
                f"{formulario.recibos}"
            )

            for numero in (1, 2):

                cuota = next(
                    c for c in F.obtener_cuotas(
                        venta_con_contrato["id_contrato"]
                    )
                    if c["numero"] == numero
                )

                assert cuota["estado"] == F.ESTADO_PAGADA

        finally:

            formulario.deleteLater()

    def test_el_resumen_no_arrastra_el_anterior(
        self,
        como_administrador,
        venta_con_contrato,
        sin_ventanas
    ):

        """
        El resumen se arma desde cero, siempre.

        Antes, cuando el plan era más largo que
        `CUOTAS_A_MOSTRAR`, el texto se **concatenaba
        al anterior**: el resumen que se leía describía
        el importe que había ANTES, no el que se iba a
        cobrar.

        Y no lo que más duele: el recorte solo salta a
        partir de la cuota 13, así que con un contrato
        corto la prueba pasaba sin tocar el caso.
        """

        formulario = self._formulario(
            venta_con_contrato["id_contrato"]
        )

        try:

            formulario.sumar_una_cuota()

            assert formulario.campo_importe.value() == (
                20000.0
            )

            assert "2 cuota(s)" in (
                formulario.etiqueta_resumen.text()
            )

            # Al cambiar el importe, el resumen tiene
            # que hablar del NUEVO.

            formulario.campo_importe.setValue(30000.0)

            nuevo = formulario.etiqueta_resumen.text()

            assert "3 cuota(s)" in nuevo, (
                "el resumen sigue hablando del importe "
                f"anterior: '{nuevo}'"
            )

            assert "2 cuota(s)" not in nuevo

            # Y al volver atrás también.

            formulario.sumar_todo()

            assert formulario.campo_importe.value() == (
                60000.0
            )

            assert "6 cuota(s)" in (
                formulario.etiqueta_resumen.text()
            )

        finally:

            formulario.deleteLater()

    def test_el_boton_de_adelantado_abre_el_formulario(
        self,
        como_administrador,
        venta_con_contrato,
        sin_ventanas
    ):
        """
        El boton de la cartera existe y llega al
        formulario.

        Se llama al metodo entero, no a la mitad: asi
        si el formulario no se puede construir, o si el
        metodo pasa mal el id del contrato, sale aqui y
        no cuando alguien pulse en pantalla.
        """

        vista = _construye("gui.cartera_view", "CarteraView")

        try:

            vista.cobrar_adelantado(
                venta_con_contrato["id_contrato"]
            )

        finally:

            vista.deleteLater()


# ==========================================
# LOS RECIBOS, AGRUPADOS
# ==========================================


class TestLosRecibosAgrupados:

    def _detalle(self, id_contrato):

        _prepara_qt()

        from gui.contrato_detalle_dialog import (
            ContratoDetalleDialog
        )

        return ContratoDetalleDialog(None, id_contrato)

    def test_un_cobro_de_dos_cuotas_es_un_recibo(
        self,
        como_administrador,
        venta_con_contrato,
        sin_ventanas
    ):
        """
        Un cobro adelantado es UN recibo con N partes.

        Si se eligiera por pago, aparecerian dos lineas
        con el mismo numero y habria que elegir "cual de
        estos dos", cuando el cliente no compro dos
        cobros: compro uno. Y el PDF de uno solo
        diria diez mil de un total de veinte, que es
        justo el papel que no sirve.
        """

        partes, motivo = F.registrar_pago_adelantado(
            venta_con_contrato["id_contrato"],
            Decimal("20000.00"),
            "2026-02-10",
            "Efectivo"
        )

        assert partes is not None, motivo

        detalle = self._detalle(
            venta_con_contrato["id_contrato"]
        )

        try:

            grupos = detalle.agrupar_por_recibo()

            assert len(grupos) == 1, (
                f"{len(grupos)} recibos para un cobro"
            )

            assert len(grupos[0]["pagos"]) == 2

            assert grupos[0]["total"] == Decimal(
                "20000.00"
            )

            # Las cuotas en orden, no como las devuelva
            # la consulta: obtener_pagos_detalle() viene
            # por fecha descendente y el papel saldría
            # al reves.

            assert grupos[0]["cuotas"] == "1, 2"

        finally:

            detalle.deleteLater()

    def test_dos_cobros_separados_son_dos_recibos(
        self,
        como_administrador,
        venta_con_contrato,
        sin_ventanas
    ):
        """
        Y dos actos distintos siguen siendo dos
        recibos.
        """

        F.registrar_pago_adelantado(
            venta_con_contrato["id_contrato"],
            Decimal("20000.00"),
            "2026-02-10",
            "Efectivo"
        )

        F.registrar_pago_adelantado(
            venta_con_contrato["id_contrato"],
            Decimal("10000.00"),
            "2026-03-10",
            "Efectivo"
        )

        detalle = self._detalle(
            venta_con_contrato["id_contrato"]
        )

        try:

            grupos = detalle.agrupar_por_recibo()

            assert len(grupos) == 2

            assert sorted(
                g["total"] for g in grupos
            ) == [
                Decimal("10000.00"), Decimal("20000.00")
            ]

        finally:

            detalle.deleteLater()

    def test_un_pago_anulado_no_sale(
        self,
        como_administrador,
        venta_con_contrato,
        sin_ventanas
    ):
        """
        Anular una de las dos partes deja el recibo con
        la otra, y con la suma de la otra.

        El papel de un cobro que ya no existe es peor que
        no imprimir nada: el cliente lo lleva al banco y
        lo presenta. Y el que queda tiene que decir lo que
        quedo, no las veinte mil de antes.

        Anular las dos lo deja sin recibos, que es lo
        que se comprueba al final.
        """

        partes, motivo = F.registrar_pago_adelantado(
            venta_con_contrato["id_contrato"],
            Decimal("20000.00"),
            "2026-02-10",
            "Efectivo"
        )

        assert partes is not None, motivo

        from database.financiera import anular_pago

        from database.pagos import obtener_pagos_detalle

        pagos = obtener_pagos_detalle(
            venta_con_contrato["id_venta"]
        )

        assert len(pagos) == 2

        for pago in pagos:

            anulado, motivo = anular_pago(
                pago["id"], "Prueba"
            )

            assert anulado, motivo

        detalle = self._detalle(
            venta_con_contrato["id_contrato"]
        )

        try:

            assert detalle.agrupar_por_recibo() == [], (
                "un cobro con las dos partes anuladas "
                "no puede tener recibo que imprimir"
            )

            # Y las cuotas volvieron a su saldo.

            for cuota in F.obtener_cuotas(
                venta_con_contrato["id_contrato"]
            ):

                assert Decimal(cuota["saldo"]) == Decimal(
                    cuota["importe"]
                )

        finally:

            detalle.deleteLater()

