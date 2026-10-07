"""
Revision general de la aplicacion (2026-10-07).

Recorre TODAS las pantallas, TODOS los dialogos y
TODOS los botones de accion, y comprueba que los dos
documentos (contrato y recibo) salen bien.

------------------------------
# POR QUE EXISTE
------------------------------

Construir una vista no es probarla. Un metodo que
llama a otro que ya no existe revienta al PULSAR, y
durante años solo se construyeron cuatro vistas en
toda la suite: por eso un `NameError` de una linea
puede vivir meses sin que ninguna prueba lo vea.

Este archivo empieza por los tres fallos reales que
salieron de la revision, y despues recorre el
sistema entero pulsando.

------------------------------
# AISLAMIENTO
------------------------------

Todo corre contra `pruebas_concesionario`, que crea
la fixture de sesion. La base real no se toca.
"""
import csv
import os
from datetime import date
from decimal import Decimal

import pytest

import database.financiera as F
from database.contratos import obtener_contrato, crear_contrato
from database.pagos import registrar_pago
from database.ventas import registrar_venta

from gui.vista_base import VistaBase


# ==========================================
# HELPERS
# ==========================================

def _prepara_qt():

    """
    QApplication sin pantalla, hoja puesta y dialogos
    parcheados.

    Se llama al PRINCIPIO de cada prueba que toca Qt,
    no como fixture: `_prepara_qt()` vuelve a parchear
    los cinco metodos de QMessageBox cada vez que se la
    llama, asi que un parche posterior se perderia.
    """

    os.environ["QT_QPA_PLATFORM"] = "offscreen"

    from PySide6.QtWidgets import (
        QApplication,
        QMessageBox,
        QInputDialog
    )

    if QApplication.instance() is None:

        QApplication([])

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


@pytest.fixture
def sin_ventanas():

    """Impide que un boton abra un dialogo de verdad."""

    import PySide6.QtWidgets as ventana

    original = ventana.QDialog.exec

    ventana.QDialog.exec = lambda self: 0

    try:

        yield

    finally:

        ventana.QDialog.exec = original


@pytest.fixture
def carga_sincrona():

    """
    Las vistas cargan de forma sincrona.

    Sin esto los listados pintan en un hilo aparte y
    ninguna prueba llega a ver la tabla con datos: se
    comprueba que el widget se construye, que es
    justamente lo que no basta.
    """

    anterior = VistaBase.diferir_carga

    VistaBase.diferir_carga = False

    try:

        yield

    finally:

        VistaBase.diferir_carga = anterior


@pytest.fixture
def venta_financiada(como_administrador, datos_base):

    """
    Una venta de 100.000 con 40.000 de anticipo y seis
    cuotas, con el cronograma generado.

    Es la base de la impresion: sin cuotas no hay
    recibo que imprimir.
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
        "id_cliente": id_cliente,
        "numero": numero,
        "cuotas": F.obtener_cuotas(id_contrato)
    }


# ==========================================
# 1. EL ERROR DE IMPRIMIR
# ==========================================

class TestImprimirRecibo:

    def test_elegir_recibo_devuelve_el_grupo_elegido(
        self,
        como_administrador,
        venta_financiada
    ):

        """
        El fallo quereported el usuario: al imprimir
        un recibo de un contrato con VARIOS cobros,
        la pantalla reventaba.

        `elegir_recibo()` construia la lista en `textos`
        y luego buscaba con `texts`: un NameError con
        dos recibos, y sin errores con uno solo, que es
        lo que hacia que pareciera aleatorio.

        Con un solo recibo el metodo ni se llama (se
        elige solo), asi que hace falta un contrato con
        dos cobros para reproducirlo.
        """

        _prepara_qt()

        from conftest import leer_pdf

        from PySide6.QtWidgets import QInputDialog

        from gui.contrato_detalle_dialog import (
            ContratoDetalleDialog
        )

        id_contrato = venta_financiada["id_contrato"]

        # ------------------------------
        # DOS COBROS DISTINTOS
        # ------------------------------

        cuotas = F.obtener_cuotas(id_contrato)

        for cuota in cuotas[:2]:

            ok, motivo = F.registrar_pago_cuota(
                cuota["id"],
                Decimal("10000.00"),
                date(2026, 3, 10),
                "Efectivo"
            )

            assert ok, motivo

        dialogo = ContratoDetalleDialog(
            None,
            id_contrato=id_contrato
        )

        grupos = dialogo.agrupar_por_recibo()

        assert len(grupos) == 2, (
            "Se esperaban dos recibos y hay %d: el "
            "escenario del fallo no se ha montado"
            % len(grupos)
        )

        # ------------------------------
        # EL USUARIO ELIGE EL SEGUNDO
        # ------------------------------

        # Se capturan las lineas que la pantalla ENSENA y se
        # devuelve la segunda. Asi la prueba no repite el
        # formato del rotulo: si ese formato cambia, la
        # prueba no se rompe, y lo que se comprueba es que
        # el indice elegido se traducen en el grupo
        # correcto.

        QInputDialog.getItem = staticmethod(
            lambda _p, _t, _e, items, *a, **k: (items[1], True)
        )

        grupo_elegido = dialogo.elegir_recibo(grupos)

        assert grupo_elegido is not None, (
            "Elegir un recibo no puede devolver None"
        )

        assert grupo_elegido is grupos[1], (
            "Se eligio el recibo equivocado: el grupo "
            "devuelto no corresponde a la linea elegida"
        )

        # ------------------------------
        # Y SI EL USUARIO SE CANCELA
        # ------------------------------

        QInputDialog.getItem = staticmethod(
            lambda *a, **k: ("", False)
        )

        assert dialogo.elegir_recibo(grupos) is None

    def test_el_recibo_impreso_sale_completo(
        self,
        como_administrador,
        venta_financiada
    ):

        """
        El PDF del recibo se genera y lleva el importe
        en letras, el numero de recibo y la cuota que
        cubre.

        Un recibo en blanco pasaria una comprobacion de
        "existe y pesa 500 bytes": `leer_pdf()` lee el
        TEXTO, que es lo unico que sirve.
        """

        _prepara_qt()

        from conftest import leer_pdf

        from PySide6.QtWidgets import QInputDialog

        from gui.contrato_detalle_dialog import (
            ContratoDetalleDialog
        )

        id_contrato = venta_financiada["id_contrato"]

        for cuota in F.obtener_cuotas(id_contrato)[:2]:

            ok, motivo = F.registrar_pago_cuota(
                cuota["id"],
                Decimal("10000.00"),
                date(2026, 3, 10),
                "Efectivo"
            )

            assert ok, motivo

        dialogo = ContratoDetalleDialog(
            None,
            id_contrato=id_contrato
        )

        grupos = dialogo.agrupar_por_recibo()

        esperado = grupos[1]["recibo"]

        # ------------------------------
        # EL BOTON "IMPRIMIR" DE VERDAD
        # ------------------------------

        # Se llama al metodo de la pantalla, no a una
        # reconstruccion de lo que hace: asi la prueba
        # cubre la eleccion del recibo, el orden de las
        # cuotas y la escritura del PDF, que es donde
        # estaba el fallo.

        rutas = []

        dialogo.avisar_documento = (
            lambda _que, ruta: rutas.append(ruta)
        )

        QInputDialog.getItem = staticmethod(
            lambda _p, _t, _e, items, *a, **k: (items[1], True)
        )

        dialogo.generar_recibo()

        assert len(rutas) == 1, (
            "Imprimir un recibo de un contrato con dos "
            "cobros no produjo ningun documento"
        )

        ruta = rutas[0]

        assert os.path.exists(ruta)

        texto = leer_pdf(ruta)

        assert "RECIBO" in texto.upper(), (
            "El PDF no se identifica como recibo"
        )

        assert str(esperado) in texto, (
            "El recibo impreso no lleva su numero: "
            "el cliente recibe un papel sin identificar"
        )

        assert "10,000.00" in texto or "10.000" in texto, (
            "El importe cobrado no aparece en el "
            "recibo:\n%s" % texto[:600]
        )

    def test_un_cobro_adelantado_imprime_un_solo_recibo(
        self,
        como_administrador,
        venta_financiada
    ):

        """
        Un cobro adelantado son N pagos con el MISMO
        recibo: el cliente se lleva UN papel.

        Si al imprimir se pidiera elegir, habria N
        lineas con el mismo numero y habria que
        inventar cual de las tres imprimir, cuando el
        cliente compro un cobro.
        """

        _prepara_qt()

        from database.financiera import registrar_pago_adelantado

        from gui.contrato_detalle_dialog import (
            ContratoDetalleDialog
        )

        id_contrato = venta_financiada["id_contrato"]

        pagos, motivo = registrar_pago_adelantado(
            id_contrato,
            Decimal("30000.00"),
            date(2026, 3, 10),
            "Transferencia"
        )

        # Devuelve la lista de pagos y un motivo si no
        # cupo: lo que importa es que sean tres filas con
        # el mismo recibo.

        assert len(pagos) == 3, motivo

        assert len({
            pago["recibo"] for pago in pagos
        }) == 1, (
            "Un cobro adelantado es UN papel: los tres "
            "pagos tienen que llevar el mismo recibo"
        )

        dialogo = ContratoDetalleDialog(
            None,
            id_contrato=id_contrato
        )

        grupos = dialogo.agrupar_por_recibo()

        assert len(grupos) == 1, (
            "Tres imputaciones del mismo cobro deben "
            "salir como un recibo, y han salido %d"
            % len(grupos)
        )

        assert len(grupos[0]["pagos"]) == 3


# ==========================================
# 2. EL DATO QUE NO ESTABA IMPORTADO
# ==========================================

class TestCartera:

    def test_por_vencer_acepta_un_plazo_que_no_es_numero(
        self,
        como_administrador,
        venta_financiada
    ):

        """
        `pintar_por_vencer` usa DIAS_AVISO_POR_DEFECTO
        como repuesto cuando el plazo tecleado no es un
        numero, y ese nombre no estaba importado en la
        pantalla: NameError y la pestaña entera
        desaparecia.

        El desplegable no es editable, asi que hoy solo
        se llega con un valor del sistema. Eso NO es una
        garantia: el mismo metodo lo llama el filtro de
        recargar(), y en cuanto el combo acepte texto
        libre (o el ajuste guarde un valor raro) el
        fallo vuelve, y es de los que nadie.debuggea
        porque el resto de la pantalla funciona.
        """

        _prepara_qt()

        from gui.cartera_view import CarteraView

        vista = CarteraView()

        vista.campo_dias_aviso.setCurrentText("")

        vista.pintar_por_vencer()

        vista.campo_dias_aviso.setCurrentText("no es un numero")

        vista.pintar_por_vencer()

        vista.cargar_datos()

    def test_todas_las_pestañas_se_pintan(
        self,
        como_administrador,
        venta_financiada
    ):

        """
        Las cuatro pestañas de la cartera se pintan
        con una cuota vencida de verdad.

        `F.procesar_vencidas()` marca por fecha: la cuota
        de febrero 2026 ya paso.
        """

        _prepara_qt()

        from gui.cartera_view import CarteraView

        F.procesar_vencidas()

        vista = CarteraView()

        vista.cargar_datos()

        assert vista.tabla.rowCount() >= 1, (
            "La cartera no muestra el contrato que "
            "sigue debiendo dinero"
        )

        assert vista.tabla_vencidas.rowCount() >= 1, (
            "Hay una cuota vencida desde febrero y la "
            "pestaña no la muestra"
        )

        assert vista.tabla_antiguedad.rowCount() >= 1, (
            "La tabla de antiguedad salio vacia con "
            "cartera vencida"
        )

    def test_se_cobra_una_cuota_desde_la_pantalla(
        self,
        como_administrador,
        venta_financiada,
        sin_ventanas
    ):

        """
        Pulsar el boton de cobrar de la cartera abre el
        formulario con la cuota puesta.

        Construir la vista no es usarla: este es el
        boton que el cajero pulsa cien veces al dia.
        """

        _prepara_qt()

        import PySide6.QtWidgets as ventana

        ventana.QDialog.exec = lambda self: 0

        from gui.cartera_view import CarteraView

        F.procesar_vencidas()

        vista = CarteraView()

        vista.cargar_datos()

        assert vista.tabla_vencidas.rowCount() > 0

        # ------------------------------
        # LOS TRES BOTONES DE UNA FILA
        # ------------------------------

        # Se llaman los metodos que usan los botones con
        # el id REAL que el boton capturaria. Si alguno
        # abriera un modal de verdad, el proceso se
        # quedaria aqui colgado sin decir donde: por eso
        # `QDialog.exec` esta parcheado en la fixture
        # `sin_ventanas` y no dentro del metodo.

        contrato_id = venta_financiada["id_contrato"]

        vista.cobrar_cuota(
            F.obtener_cuotas(contrato_id)[0]["id"]
        )

        vista.cobrar_adelantado(contrato_id)

        vista.cobrar_contrato(contrato_id)


# ==========================================
# 3. TODAS LAS VISTAS, LOS DOS ROLES
# ==========================================

class TestTodasLasVistas:

    def test_una_seccion_que_no_existe_no_tumba_la_ventana(
        self,
        como_administrador,
        datos_base
    ):

        """
        `definiciones` tiene una entrada por sección
        VISIBLE: el vendedor tiene seis y el
        administrador once.

        Un indice fuera de rango no llega desde un
        boton, pero si desde un atajo o un estado
        restaurado, y `definiciones[indice]` es un
        IndexError que tumba la ventana entera.
        """

        _prepara_qt()

        from gui.ventana_principal import VentanaPrincipal

        ventana = VentanaPrincipal()

        ventana.navegar(999)

        ventana.navegar(-1)

        ventana.navegar(0)

        assert ventana.paginas_creadas == {0}

    def _recorre(self, ventana_principal):

        # Solo las secciones que el rol tiene permitidas:
        # definiciones no tiene una entrada por seccion,
        # tiene una por seccion VISIBLE.

        for indice in range(len(ventana_principal.definiciones)):

            ventana_principal.navegar(indice)

        ventana_principal.navegar(0)

        QApplication_pump()

    def test_administrador_abre_las_once_secciones(
        self,
        como_administrador,
        datos_base
    ):

        """
        Once secciones, las once se construyen y se
        pintan.

        La cuenta es un contrato: un apartado nuevo o
        uno que se cae cambian estos numeros, y las
        pruebas avisan.
        """

        _prepara_qt()

        from gui.ventana_principal import VentanaPrincipal

        ventana = VentanaPrincipal()

        assert len(VentanaPrincipal.SECCIONES) == 11

        self._recorre(ventana)

        assert len(ventana.paginas_creadas) == 11, (
            "No se crearon todas las secciones: %s"
            % sorted(ventana.paginas_creadas)
        )

    def test_vendedor_abre_sus_seis_secciones(
        self,
        datos_base,
        como_vendedor
    ):

        """
        El vendedor ve seis. Ni Cartera, ni Reportes,
        ni Usuarios, ni Auditoria, ni Configuracion: no
        es que esten ocultos, es que la vista NI SE
        CONSTRUYE.
        """

        _prepara_qt()

        from gui.ventana_principal import VentanaPrincipal

        ventana = VentanaPrincipal()

        self._recorre(ventana)

        assert len(ventana.paginas_creadas) == 6, (
            "El vendedor abrio %d secciones y debe "
            "abrir 6: %s"
            % (len(ventana.paginas_creadas),
               sorted(ventana.paginas_creadas))
        )

        assert len(ventana.paginas_creadas) < 11


def QApplication_pump():

    """Deja correr los eventos pendientes."""

    from PySide6.QtWidgets import QApplication

    if QApplication.instance() is not None:

        for _ in range(3):

            QApplication.instance().processEvents()


# ==========================================
# 4. LOS DIALOGOS Y LOS FORMULARIOS
# ==========================================

class TestDialogos:

    def test_se_abren_todos(
        self,
        como_administrador,
        venta_financiada,
        datos_base,
        sin_ventanas
    ):

        _prepara_qt()

        from gui.fichas_dialog import (
            AutoFichaDialog,
            ClienteFichaDialog,
            UnidadForm,
        )
        from gui.contrato_detalle_dialog import (
            ContratoDetalleDialog
        )
        from gui.detalle_venta_dialog import (
            DetalleVentaDialog
        )
        from gui.seguimiento_dialog import (
            SeguimientoDialog,
            ContactoForm,
        )
        from gui.respaldo_dialog import RespaldoDialog
        from gui.formularios.auto_form import AutoForm
        from gui.formularios.marca_form import MarcaForm
        from gui.formularios.cliente_form import ClienteForm
        from gui.formularios.usuario_form import UsuarioForm
        from gui.formularios.venta_form import VentaForm
        from gui.formularios.contrato_form import ContratoForm
        from gui.formularios.pago_form import PagoForm
        from gui.formularios.pago_cuota_form import (
            PagoCuotaForm
        )
        from gui.formularios.pago_adelantado_form import (
            PagoAdelantadoForm
        )
        from gui.formularios.garantia_form import (
            GarantiaForm,
            FormularioInscripcion,
        )

        _, id_auto, id_cliente = datos_base

        id_contrato = venta_financiada["id_contrato"]

        id_venta = venta_financiada["id_venta"]

        # ------------------------------
        # LOS QUE LEEN DE LA BASE
        # ------------------------------

        AutoFichaDialog(None, id_auto)

        ClienteFichaDialog(None, id_cliente)

        ContratoDetalleDialog(None, id_contrato=id_contrato)

        DetalleVentaDialog(
            None,
            (
                id_venta,
                date(2026, 1, 10),
                "Cliente de prueba",
                "Toyota Corolla",
                100000.0,
                "Administrador"
            ),
            lambda _id: (Decimal("100000.00"),
                         Decimal("0.00"),
                         Decimal("100000.00")),
            moneda="USD"
        )

        SeguimientoDialog(None, id_contrato)

        RespaldoDialog(None)

        # ------------------------------
        # LOS FORMULARIOS DE ALTA
        # ------------------------------

        AutoForm(None, None)

        MarcaForm(None)

        ClienteForm(None, None)

        UsuarioForm(None, None)

        UnidadForm(None, id_auto)

        VentaForm(None)

        ContratoForm(None, id_venta)

        PagoForm(None, id_venta)

        PagoCuotaForm(None, F.obtener_cuotas(id_contrato)[0]["id"])

        PagoAdelantadoForm(None, id_contrato)

        GarantiaForm(None, id_contrato)

        FormularioInscripcion(None, id_contrato)

        ContactoForm(None, id_contrato)

    def test_ficha_cliente_abre_su_contrato(
        self,
        como_administrador,
        venta_financiada,
        datos_base,
        sin_ventanas
    ):

        """
        Doble clic sobre una venta de la ficha del
        cliente abre el contrato de esa venta.

        La fila y el contrato tienen que seguir siendo
        el mismo: si el indicesale descolocado, el
        doble clic abre el contrato de otro cliente.
        """

        _prepara_qt()

        from PySide6.QtWidgets import QMessageBox

        QMessageBox.question = staticmethod(
            lambda *a, **k: QMessageBox.No
        )

        from gui.fichas_dialog import ClienteFichaDialog

        dialogo = ClienteFichaDialog(
            None,
            venta_financiada["id_cliente"]
        )

        assert dialogo.ventas.rowCount() == 1, (
            "La ficha del cliente no lista su venta"
        )

        # Se comprueba el par DE LA FILA, que es el
        # contrato que tiene que abrir el doble clic.

        registro = dialogo.registros[0]

        assert registro["contrato_id"] == venta_financiada["id_contrato"]

        dialogo.abrir_contrato(0, 0)


# ==========================================
# 5. LOS BOTONES DE LAS LISTAS
# ==========================================

class TestBotonesDeFila:

    def test_editar_auto_relee_las_siete_columnas(
        self,
        como_administrador,
        datos_base,
        sin_ventanas
    ):

        """
        `leer_auto` deshace el separador de miles antes
        de convertir el precio.

        Sin el `replace`, editar un vehiculo de mas de
        999 revienta con ValueError. El precio de la
        fixture es a proposito de mas de 999.
        """

        _prepara_qt()

        from gui.autos_view import AutosView

        vista = AutosView()

        vista.cargar_datos()

        assert vista.tabla.rowCount() > 0

        datos = vista.leer_auto(0)

        assert len(datos) == 7, (
            "obtener_autos() devuelve 7 columnas y "
            "leer_auto() devolvio %d" % len(datos)
        )

        assert float(datos[4]) > 0

    def test_editar_auto_abre_el_formulario_con_los_datos(
        self,
        como_administrador,
        datos_base,
        sin_ventanas
    ):

        _prepara_qt()

        from gui.autos_view import AutosView

        vista = AutosView()

        vista.cargar_datos()

        vista.editar_auto(0)

    def test_ficha_de_auto_desde_la_lista(
        self,
        como_administrador,
        datos_base,
        sin_ventanas
    ):

        _prepara_qt()

        from gui.autos_view import AutosView

        vista = AutosView()

        vista.cargar_datos()

        vista.abrir_ficha(0)

    def test_ver_venta_desde_la_lista(
        self,
        como_administrador,
        venta_financiada,
        sin_ventanas
    ):

        _prepara_qt()

        import PySide6.QtWidgets as ventana

        ventana.QMessageBox.question = staticmethod(
            lambda *a, **k: ventana.QMessageBox.No
        )

        from gui.ventas_view import VentasView

        vista = VentasView()

        vista.cargar_datos()

        assert vista.tabla.rowCount() > 0

        vista.ver_venta(0)

    def test_ver_contrato_desde_la_lista(
        self,
        como_administrador,
        venta_financiada,
        sin_ventanas
    ):

        _prepara_qt()

        from gui.contratos_view import ContratosView

        vista = ContratosView()

        vista.cargar_datos()

        assert vista.tabla.rowCount() > 0

        vista.ver_detalle(0)

    def test_ficha_de_cliente_desde_la_lista(
        self,
        como_administrador,
        venta_financiada,
        sin_ventanas
    ):

        _prepara_qt()

        from gui.clientes_view import ClientesView

        vista = ClientesView()

        vista.cargar_datos()

        vista.abrir_ficha(0)

    def test_exportar_csv_de_auditoria(
        self,
        como_administrador,
        datos_base,
        tmp_path
    ):

        """
        El CSV sale con cabecera y con una fila por
        registro de la tabla que se esta viendo.

        Se exporta lo que hay EN PANTALLA: exportar la
        tabla entera cuando el filtro es "hoy" es
        escribir el informe de un dia con los datos de
        otro.
        """

        _prepara_qt()

        from gui.auditoria_view import AuditoriaView

        vista = AuditoriaView()

        vista.cargar_datos()

        ruta = tmp_path / "auditoria.csv"

        vista.exportar_csv(str(ruta))

        assert ruta.exists(), "El CSV no se escribio"

        with open(ruta, encoding="utf-8", newline="") as archivo:

            filas = list(csv.reader(archivo))

        assert len(filas) >= 1, "El CSV no lleva cabecera"

        assert len(filas) == vista.tabla.rowCount() + 1, (
            "El CSV tiene %d lineas y la tabla %d "
            "filas: no es lo mismo"
            % (len(filas), vista.tabla.rowCount())
        )

    def test_el_vendedor_no_gestiona(
        self,
        datos_base,
        como_vendedor
    ):

        """
        El vendedor ve los listados pero no los
        botones de borrar.

        La vista se crea por el MISMO camino que la
        aplicacion: es `VentanaPrincipal.crear_vista()`
        quien le dice que puede gestionar. Construirla a
        mano devolveria el valor por defecto (True) y la
        prueba no estaria mirando nada real.
        """

        _prepara_qt()

        from gui.autos_view import AutosView
        from gui.ventana_principal import VentanaPrincipal

        ventana = VentanaPrincipal()

        vista = ventana.crear_vista(AutosView, "Vehiculos")

        vista.cargar_datos()

        assert not vista.puede_gestionar, (
            "El vendedor no puede crear, editar ni "
            "borrar vehiculos, y la vista se los "
            "enseña igual"
        )


# ==========================================
# 6. LOS DOCUMENTOS
# ==========================================

class TestDocumentos:

    def test_contrato_con_texto_raro_sale_legible(
        self,
        como_administrador,
        venta_financiada
    ):

        """
        El texto que va en un Paragraph se escapa
        SIEMPRE.

        Un "&" en el nombre del cliente rompe el
        parrafo de reportlab y sale un documento que no
        se puede defender. Aqui el nombre lleva &, < y
        > a proposito.
        """

        _prepara_qt()

        from conftest import leer_pdf

        import mysql.connector

        from database.conexion import configuracion

        conexion = mysql.connector.connect(**configuracion())

        cursor = conexion.cursor()

        cursor.execute(
            "UPDATE clientes SET nombre = %s, apellido = %s "
            "WHERE id = %s",
            ("Pérez & Hijos <SA>", "Ñandú", venta_financiada["id_cliente"])
        )

        conexion.commit()

        cursor.close()

        conexion.close()

        from utils.contrato_pdf import generar_contrato

        contrato = obtener_contrato(venta_financiada["id_contrato"])

        ruta = generar_contrato(contrato)

        texto = leer_pdf(ruta)

        assert "P" in texto and "rez" in texto, (
            "El nombre del cliente no sale en el PDF:\n%s"
            % texto[:600]
        )

        assert venta_financiada["numero"] in texto, (
            "El numero de contrato no sale en el PDF"
        )

    def test_importe_en_letras_no_inventa_decimales(
        self,
        como_administrador,
        venta_financiada
    ):

        """
        El importe en letras usa los decimales de la
        MONEDA, no los del numero.

        Con guaranies no hay centimos que escribir, y un
        recibo que dice "con cero/100" esta inventando una
        precision que no existe.
        """

        _prepara_qt()

        from utils.recibo_pdf import en_letras

        # ------------------------------
        # SIN MONEDA FRACCIONARIA
        # ------------------------------

        assert "/100" not in en_letras(1500, 0)

        assert en_letras(1500, 0) == "mil y quinientos"

        # ------------------------------
        # Y CON MONEDA FRACCIONARIA
        # ------------------------------

        # 1500 no tiene centimos: escribir "cero/100"
        # seria inventar una precision que no existe, y en
        # un recibo eso es un problema.

        assert "/100" not in en_letras(1500, 2)

        assert "/100" in en_letras(1500.5, 2)

        # ------------------------------
        # EL REDONDEO ES MEDIO ARRIBA
        # ------------------------------

        # Truncar dejaria al cliente debiendo 500 guaranies
        # de mas: ese medio no existe y no se puede pagar.

        assert en_letras(1500.5, 0) == "mil y quinientos uno"


# ==========================================
# 7. LA LOGICA DEL CRONOGRAMA
# ==========================================

class TestCronograma:

    def test_el_dia_31_no_se_arrastra_al_mes_corto(
        self,
        como_administrador,
        datos_base
    ):

        """
        Un crédito firmado el 31 de enero vence el 28
        de febrero, y el mes SIGUIENTE vuelve al 31: el
        recorte es del mes que no tiene 31, no una
        decision que se arrastra.

        Con "sumar 30 dias" el dia se moveria para
        siempre.
        """

        _prepara_qt()

        from database.financiera import _sumar_meses

        assert _sumar_meses(
            date(2026, 1, 31), 1, 31
        ) == date(2026, 2, 28)

        assert _sumar_meses(
            date(2026, 1, 31), 2, 31
        ) == date(2026, 3, 31)

        assert _sumar_meses(
            date(2028, 1, 31), 1, 31
        ) == date(2028, 2, 29), (
            "2028 es bisiesto y febrero tiene 29"
        )

    def test_las_cuotas_suman_el_saldo_financiado(
        self,
        como_administrador,
        venta_financiada
    ):

        """
        La ultima cuota se lleva el residuo del
        redondeo.

        Si no, el cronograma del papel no cuadra con
        el saldo que el cliente debe, y se descubre
        cuando llega con la calculadora.
        """

        _prepara_qt()

        cuotas = F.obtener_cuotas(
            venta_financiada["id_contrato"]
        )

        total = sum(
            (cuota["importe"] for cuota in cuotas),
            Decimal("0.00")
        )

        assert total == Decimal("60000.00"), (
            "Las cuotas suman %s y el saldo financiado "
            "es 60000.00" % total
        )

    def test_repartir_pon_la_residuo_en_la_ultima(
        self,
        como_administrador
    ):

        _prepara_qt()

        from database.financiera import _repartir

        partes = _repartir(Decimal("10000.00"), 7)

        assert len(partes) == 7

        assert sum(partes) == Decimal("10000.00"), (
            "El reparto pierde o inventa dinero: %s"
            % sum(partes)
        )

        assert partes[-1] != partes[0], (
            "Las siete partes son iguales: no se esta "
            "llevando el residuo la ultima"
        )


# ==========================================
# 9. EL DINERO: LO ANULADO NO ES DINERO
# ==========================================

class TestLoAnuladoNoEsDinero:

    """
    Los tres fallos de la revision que eran de dinero,
    no de codigo.

    Un pago no se borra: se anula, y el anulado sigue
    en la tabla. Cualquier suma que no lo mire cuenta
    dinero que nunca se cobro.
    """

    def test_el_saldo_de_la_venta_ignora_lo_anulado(
        self,
        como_administrador,
        venta_financiada
    ):

        """
        El saldo de una venta NO baja por un pago
        anulado.

        Es la cifra que el cajero mira antes de decir
        que el auto esta pagado. Antes de este arreglo
        `saldo_venta()` sumaba la fila anulada y la
        venta aparecia saldada con un cobro que se
        habia anulado.
        """

        _prepara_qt()

        from database.financiera import anular_pago
        from database.pagos import saldo_venta

        id_venta = venta_financiada["id_venta"]

        cuota = F.obtener_cuotas(
            venta_financiada["id_contrato"]
        )[0]

        ok, motivo = F.registrar_pago_cuota(
            cuota["id"],
            Decimal("10000.00"),
            date(2026, 3, 10),
            "Efectivo"
        )

        assert ok, motivo

        _, pagado, saldo = saldo_venta(id_venta)

        assert float(pagado) == 10000.0
        assert float(saldo) == 90000.0

        # ------------------------------
        # SE ANULA ESE COBRO
        # ------------------------------

        from database.conexion import obtener_conexion

        conexion = obtener_conexion()
        cursor = conexion.cursor()
        cursor.execute(
            "SELECT id FROM pagos WHERE cuota_id = %s",
            (cuota["id"],)
        )
        id_pago = cursor.fetchone()[0]
        cursor.close()
        conexion.close()

        ok, motivo = anular_pago(
            id_pago,
            "Prueba: el cliente devolvio el dinero"
        )

        assert ok, motivo

        _, pagado, saldo = saldo_venta(id_venta)

        assert float(pagado) == 0.0, (
            "El pago sigue contado como cobrado con "
            "estado 'anulado': pagado = %s" % pagado
        )

        assert float(saldo) == 100000.0, (
            "La venta sigue apareciendo pagada con un "
            "cobro que se anulo"
        )

    def test_el_reporte_de_cobros_ignora_lo_anulado(
        self,
        como_administrador,
        venta_financiada
    ):

        _prepara_qt()

        from database.financiera import anular_pago
        from database.pagos import obtener_cobros

        cuota = F.obtener_cuotas(
            venta_financiada["id_contrato"]
        )[0]

        ok, motivo = F.registrar_pago_cuota(
            cuota["id"],
            Decimal("10000.00"),
            date(2026, 3, 10),
            "Efectivo"
        )

        assert ok, motivo

        entradas, total = obtener_cobros(
            date(2026, 1, 1),
            date(2026, 12, 31)
        )

        assert float(total) == 10000.0

        from database.conexion import obtener_conexion

        conexion = obtener_conexion()
        cursor = conexion.cursor()
        cursor.execute(
            "SELECT id FROM pagos WHERE cuota_id = %s",
            (cuota["id"],)
        )
        id_pago = cursor.fetchone()[0]
        cursor.close()
        conexion.close()

        anular_pago(id_pago, "Prueba")

        entradas, total = obtener_cobros(
            date(2026, 1, 1),
            date(2026, 12, 31)
        )

        assert float(total) == 0.0, (
            "El reporte de cobros del ano suma un pago "
            "anulado: %s" % total
        )

        assert entradas == 0

    def test_un_pago_de_cuota_no_se_borra(
        self,
        como_administrador,
        venta_financiada
    ):

        """
        Borrar un pago que esta imputado a una cuota
        descuadra el cronograma: el importe ya se le
        habia quitado a `cuotas.saldo` y nadie se lo
        devuelve.

        La respuesta correcta es(\\"anular\\" en el detalle del
        contrato), no(\\"borrar\\" desde la venta): por eso
        se rechaza con un motivo que lo dice.
        """

        _prepara_qt()

        from database.pagos import eliminar_pago

        cuota = F.obtener_cuotas(
            venta_financiada["id_contrato"]
        )[0]

        ok, motivo = F.registrar_pago_cuota(
            cuota["id"],
            Decimal("10000.00"),
            date(2026, 3, 10),
            "Efectivo"
        )

        assert ok, motivo

        from database.conexion import obtener_conexion

        conexion = obtener_conexion()
        cursor = conexion.cursor()
        cursor.execute(
            "SELECT id FROM pagos WHERE cuota_id = %s",
            (cuota["id"],)
        )
        id_pago = cursor.fetchone()[0]
        cursor.close()
        conexion.close()

        ok, motivo = eliminar_pago(id_pago)

        assert ok is False, (
            "Borrar un pago de cuota tiene que fallar: "
            "deja la cuota con un saldo que ya no es real"
        )

        assert "cuota" in motivo.lower(), (
            "El motivo tiene que explicar por que no se "
            "puede borrar y que hacer en su lugar: %s"
            % motivo
        )

        # ------------------------------
        # Y LA CUOTA SIGUE CUADRANDO
        # ------------------------------

        from database.conexion import obtener_conexion

        conexion = obtener_conexion()
        cursor = conexion.cursor()

        cursor.execute(
            "SELECT COUNT(*) FROM pagos WHERE id = %s",
            (id_pago,)
        )

        assert cursor.fetchone()[0] == 1, (
            "El pago se borro pese a estar asignado a "
            "una cuota"
        )

        cursor.close()
        conexion.close()

        from database.financiera import recalcular_saldo_cuota

        # Devuelve (saldo_calculado, saldo_guardado):
        # tienen que coincidir, que es lo que demuestra
        # que la cuota no se descolgó de sus pagos.

        calculado, guardado = recalcular_saldo_cuota(cuota["id"])

        assert calculado == guardado, (
            "La cuota guarda un saldo (%s) que no es el "
            "que suman sus pagos (%s)" % (guardado, calculado)
        )

    def test_un_pago_suelto_si_se_borra(
        self,
        como_administrador,
        venta_financiada
    ):

        """
        El caso de siempre: un pago suelto mal
        tecleado se borra, y el saldo vuelve a su
        valor.
        """

        _prepara_qt()

        from database.pagos import (
            eliminar_pago,
            obtener_pagos,
            saldo_venta,
        )

        id_venta = venta_financiada["id_venta"]

        id_pago, motivo = registrar_pago(
            id_venta,
            Decimal("5000.00"),
            date(2026, 3, 10),
            "Efectivo"
        )

        assert id_pago, motivo

        ok, motivo = eliminar_pago(id_pago)

        assert ok is True, motivo

        assert obtener_pagos(id_venta) == []

        _, pagado, saldo = saldo_venta(id_venta)

        assert float(pagado) == 0.0
        assert float(saldo) == 100000.0


# ==========================================
# 10. LO QUE BLOQUEA UN BORRADO
# ==========================================

class TestLoQueBloqueaUnBorrado:

    def test_un_contrato_con_cuotas_no_se_borra(
        self,
        como_administrador,
        venta_financiada
    ):

        """
        Borrar un contrato con cronograma no puede
        reventar con un error de MySQL.

        `cuotas.contrato_id` esta en ON DELETE
        RESTRICT: MySQL lo impide, pero lanzando la
        excepcion. La pantalla recibia un error de
        base de datos en vez de una frase, y el
        registro de errores se llenaba de "Fallo
        inesperado" por algo que el usuario puede
        evitar. Es el mismo motivo por el que
        `eliminar_venta()` consulta antes de borrar.
        """

        _prepara_qt()

        from database.contratos import (
            contrato_bloqueado_por,
            eliminar_contrato,
            obtener_contrato
        )

        id_contrato = venta_financiada["id_contrato"]

        bloqueo = contrato_bloqueado_por(id_contrato)

        assert bloqueo, (
            "Hay seis cuotas y aun asi no se detecta "
            "que el contrato esta bloqueado"
        )

        assert "6" in bloqueo, (
            "El motivo tiene que decir cuantas cuotas "
            "hay: %s" % bloqueo
        )

        ok, motivo = eliminar_contrato(id_contrato)

        assert ok is False, (
            "Un contrato con cronograma se ha borrado"
        )

        assert motivo == bloqueo, (
            "El motivo que ve el usuario tiene que ser "
            "el mismo que explica el bloqueo"
        )

        # ------------------------------
        # Y EL CONTRATO SIGUE AHI
        # ------------------------------

        assert obtener_contrato(id_contrato) is not None

    def test_el_motivo_va_a_la_pantalla(
        self,
        como_administrador,
        venta_financiada,
        sin_ventanas
    ):

        """
        Lo que dice la capa de datos es lo que ve el
        usuario, no un error generico.

        Antes el mensaje era "No se pudo completar la
        operacion" y el rastro era un IntegrityError.
        """

        _prepara_qt()

        import PySide6.QtWidgets as ventana

        ventana.QMessageBox.question = staticmethod(
            lambda *a, **k: ventana.QMessageBox.Yes
        )

        from gui.contratos_view import ContratosView

        vista = ContratosView()

        vista.cargar_datos()

        assert vista.tabla.rowCount() > 0

        vistos = []

        vista.mostrar_mensaje_error = (
            lambda texto: vistos.append(texto)
        )

        vista.eliminar_de(0)

        assert vistos, (
            "Borrar un contrato con cuotas no enseña "
            "ningun mensaje: el usuario no sabe por que"
        )

        assert "cuota" in vistos[0].lower(), (
            "El mensaje no dice que tiene cuotas: %s"
            % vistos[0]
        )

    def test_un_contrato_sin_movimientos_si_se_borra(
        self,
        como_administrador,
        venta_financiada,
        datos_base
    ):

        """
        El caso de siempre: un contrato al contado,
        sin cuotas ni cobros, se borra sin problema.

        Es lo que se hace con un contrato creado por
        error, y si esto tambien fallara el arreglo
        anterior dejaria al administrador sin poder
        limpiar nada.
        """

        _prepara_qt()

        from database.contratos import (
            contrato_bloqueado_por,
            crear_contrato,
            eliminar_contrato,
            obtener_contrato,
        )

        _, id_auto, id_cliente = datos_base

        id_venta, motivo = registrar_venta(
            id_cliente,
            id_auto,
            "2026-01-10",
            25000.0
        )

        assert id_venta, motivo

        id_contrato, numero = crear_contrato(
            venta_id=id_venta,
            forma_pago="Contado"
        )

        assert id_contrato is not None, numero

        assert contrato_bloqueado_por(id_contrato) is None

        ok, motivo = eliminar_contrato(id_contrato)

        assert ok is True, motivo

        assert obtener_contrato(id_contrato) is None


# ==========================================
# 11. EL CONTRATO IMPRESO
# ==========================================

class TestElContratoImpreso:

    def test_contrato_financiado_imprime_tasa_y_cronograma(
        self,
        como_administrador,
        venta_financiada
    ):

        """
        Un contrato financiado que no dice la tasa ni
        el detalle de las cuotas no es un documento
        que el cliente pueda firmar: no sabe que esta
        aceptando.

        Los datos estaban en la base desde que se
        firmo, pero no se imprimian. Esto se comprueba
        leyendo el TEXTO del PDF y no su tamano: un PDF
        en blanco pasaria una comprobacion de "existe y
        pesa 500 bytes".
        """

        _prepara_qt()

        from conftest import leer_pdf

        import mysql.connector

        from database.conexion import configuracion
        from database.contratos import obtener_contrato
        from utils.contrato_pdf import generar_contrato

        id_contrato = venta_financiada["id_contrato"]

        # ------------------------------
        # SE FIRMA CON UN 8 % DE INTERES
        # ------------------------------

        conexion = mysql.connector.connect(**configuracion())
        cursor = conexion.cursor()
        cursor.execute(
            "UPDATE contratos SET tasa_interes = %s, "
            "gastos_administrativos = %s WHERE id = %s",
            (8, 1500, id_contrato)
        )
        conexion.commit()
        cursor.close()
        conexion.close()

        ruta = generar_contrato(
            obtener_contrato(id_contrato),
            cuotas=F.obtener_cuotas(id_contrato)
        )

        texto = leer_pdf(ruta)

        assert "CRONOGRAMA DE PAGOS" in texto, (
            "El contrato financiado no imprime la tabla "
            "de vencimientos"
        )

        assert "Vencimiento" in texto

        assert "Tasa de inter" in texto, (
            "El contrato no dice la tasa: el cliente "
            "firma sin saber cuanto va a pagar de "
            "intereses"
        )

        # El 8 sale como 8 y no como 8,000: es un
        # porcentaje, no un millar.

        assert "8 % anual" in texto, (
            "La tasa se imprime con los ceros del "
            "DECIMAL(6,3): %s" % texto[:600]
        )

        assert "Gastos administrativos" in texto

        assert "Primer vencimiento" in texto

        assert "Saldo financiado" in texto

        # ------------------------------
        # UNA LINEA POR CUOTA
        # ------------------------------

        for cuota in F.obtener_cuotas(id_contrato):

            assert cuota["fecha_vencimiento"].strftime(
                "%d/%m/%Y"
            ) in texto, (
                "La cuota %s no sale en el cronograma"
                % cuota["numero"]
            )

    def test_el_pdf_imprime_las_clausulas(
        self,
        como_administrador,
        venta_financiada
    ):

        """
        Las clausulas son las condiciones que
        escribio el administrador. Si no se imprimen,
        el cliente firma sin ellas.
        """

        _prepara_qt()

        from conftest import leer_pdf

        import mysql.connector

        from database.conexion import configuracion
        from database.contratos import obtener_contrato
        from utils.contrato_pdf import generar_contrato

        clausula = (
            "El cliente paga los gastos de "
            "transferencia de cada cuota."
        )

        conexion = mysql.connector.connect(**configuracion())
        cursor = conexion.cursor()
        cursor.execute(
            "UPDATE contratos SET clausulas = %s WHERE id = %s",
            (clausula, venta_financiada["id_contrato"])
        )
        conexion.commit()
        cursor.close()
        conexion.close()

        ruta = generar_contrato(
            obtener_contrato(venta_financiada["id_contrato"]),
            cuotas=F.obtener_cuotas(
                venta_financiada["id_contrato"]
            )
        )

        texto = leer_pdf(ruta)

        assert "transferencia" in texto, (
            "Las clausulas del contrato no salen "
            "impresas:\n%s" % texto[-800:]
        )

    def test_contrato_al_contado_no_inventa_una_tasa(
        self,
        como_administrador,
        datos_base
    ):

        """
        En un contado no se imprime "Tasa 0 %": no hay
        credito, y una fila de ceros parece un dato
        olvidado en vez de una ausencia.
        """

        _prepara_qt()

        from conftest import leer_pdf

        from database.contratos import (
            crear_contrato,
            obtener_contrato,
        )
        from utils.contrato_pdf import generar_contrato

        _, id_auto, id_cliente = datos_base

        id_venta, motivo = registrar_venta(
            id_cliente, id_auto, "2026-01-10", 25000.0
        )

        assert id_venta, motivo

        id_contrato, numero = crear_contrato(
            venta_id=id_venta,
            forma_pago="Contado"
        )

        assert id_contrato is not None, numero

        ruta = generar_contrato(
            obtener_contrato(id_contrato)
        )

        texto = leer_pdf(ruta)

        assert "Tasa de inter" not in texto

        assert "CRONOGRAMA DE PAGOS" not in texto

        assert "Contado" in texto


# ==========================================
# 8. SIN FUGAS
# ==========================================

def test_el_recorrido_completo_no_deja_conexiones(
    como_administrador,
    venta_financiada,
    datos_base,
    sin_ventanas,
    carga_sincrona,
    sin_fugas_de_conexion
):

    """
    Despues de construir vistas, dialogos y formularios
    no queda ninguna sesion abierta en la base.

    Sin esto, la aplicacion funciona y a la tercera
    hora dice "MySQL no responde" sin explicacion.
    """

    _prepara_qt()

    import time

    from PySide6.QtWidgets import QApplication

    from gui.ventana_principal import VentanaPrincipal

    ventana = VentanaPrincipal()

    for indice in range(len(ventana.definiciones)):

        ventana.navegar(indice)

        QApplication_pump()

    # ------------------------------
    # ESPERAR A QUE TERMINEN LAS
    # CONSULTAS EN VOLO
    # ------------------------------

    # Una lectura que sigue corriendo mantiene su
    # conexion abierta, y el contador de fugas la
    # veria como una fuga que no es. Se espera a que
    # no quede ninguna pendiente.

    for _ in range(100):

        QApplication_pump()

        if not ventana.vistas:

            break

        pendientes = [
            len(v.trabajos.pendientes)
            for v in ventana.vistas.values()
            if hasattr(v, "trabajos")
        ]

        if not any(pendientes):
            break

        time.sleep(0.05)

    ventana.close()

    QApplication_pump()

    ventana.deleteLater()

    QApplication_pump()
