# ==========================================
# CONTRATOS
# ==========================================
# Lo que hay que proteger aquí:
#   - el número (CTR-2026-00001) es único por
#     construcción y no depende de contar filas
#   - una venta solo admite un contrato vivo
#   - los estados solo avanzan por TRANSICIONES
#   - una venta con contrato vivo no se anula
#   - el PDF sale con los datos congelados
# ==========================================


import os

import pytest

from database.ventas import registrar_venta

from database.contratos import (
    ESTADOS,
    TRANSICIONES,
    formatear_numero,
    nombre_archivo,
    obtener_contratos,
    obtener_contrato,
    ventas_sin_contrato,
    contrato_de_venta,
    venta_bloqueada_por_contrato,
    crear_contrato,
    cambiar_estado,
    eliminar_contrato
)

from utils.contrato_pdf import (
    generar_contrato,
    ruta_documento,
    cuota_importe,
    escapar,
    sustituir_no_mapeables
)


@pytest.fixture
def venta_lista(datos_base):
    """
    Una venta ya registrada, que es el punto de
    partida de cualquier contrato.
    """

    _, id_auto, id_cliente = datos_base

    id_venta, _ = registrar_venta(
        id_cliente, id_auto, "2026-03-10", 25000.0
    )

    return id_venta


class TestNumero:

    def test_formato_con_el_anio(
        self, como_administrador
    ):
        assert formatear_numero(1, 2026) == "CTR-2026-00001"

    def test_ano_por_defecto_es_el_actual(
        self, como_administrador
    ):
        numero = formatear_numero(1)

        assert numero.startswith("CTR-")
        assert numero.endswith("-00001")

    def test_el_numero_usa_el_id_del_contrato(
        self, como_administrador, venta_lista
    ):
        """
        El número se arma con el id del propio
        contrato dentro de la misma transacción.
        Es único por construcción: no depende de
        contar filas ni de que dos personas creen
        contratos a la vez.
        """

        id_contrato, numero = crear_contrato(
            venta_id=venta_lista,
            forma_pago="Contado"
        )

        assert id_contrato is not None

        contrato = obtener_contrato(id_contrato)

        assert contrato["numero"] == formatear_numero(
            id_contrato, contrato["fecha"].year
        )

    def test_archivo_named_por_el_numero(
        self, como_administrador
    ):
        assert nombre_archivo(
            "CTR-2026-00001"
        ) == "contrato_CTR-2026-00001.pdf"


class TestCrear:

    def test_crea_con_venta_lista(
        self, como_administrador, venta_lista
    ):
        id_contrato, motivo = crear_contrato(
            venta_id=venta_lista,
            forma_pago="Contado"
        )

        assert id_contrato is not None
        assert motivo.startswith("CTR-")

    def test_nace_en_activo(
        self, como_administrador, venta_lista
    ):
        id_contrato, _ = crear_contrato(
            venta_id=venta_lista,
            forma_pago="Contado"
        )

        assert obtener_contrato(
            id_contrato
        )["estado"] == "activo"

    def test_no_hay_dos_contratos_vivos(
        self, como_administrador, venta_lista
    ):
        crear_contrato(
            venta_id=venta_lista,
            forma_pago="Contado"
        )

        id_contrato, motivo = crear_contrato(
            venta_id=venta_lista,
            forma_pago="Contado"
        )

        assert id_contrato is None
        assert motivo

    def test_rechaza_venta_inexistente(
        self, como_administrador
    ):
        id_contrato, motivo = crear_contrato(
            venta_id=99999,
            forma_pago="Contado"
        )

        assert id_contrato is None
        assert "venta" in motivo.lower()

    def test_guarda_anticipo_y_cuotas(
        self, como_administrador, venta_lista
    ):
        id_contrato, _ = crear_contrato(
            venta_id=venta_lista,
            forma_pago="Anticipo + cuotas",
            anticipo=5000.0,
            cantidad_cuotas=12,
            observaciones="Entrega en junio"
        )

        contrato = obtener_contrato(id_contrato)

        assert float(contrato["anticipo"]) == 5000.0
        assert contrato["cantidad_cuotas"] == 12
        assert contrato["observaciones"] == (
            "Entrega en junio"
        )

    def test_rechaza_anticipo_mayor_que_el_precio(
        self, como_administrador, venta_lista
    ):
        id_contrato, motivo = crear_contrato(
            venta_id=venta_lista,
            forma_pago="Contado",
            anticipo=99999.0
        )

        assert id_contrato is None
        assert "anticipo" in motivo.lower()

    def test_rechaza_cuotas_sin_forma_de_pago(
        self, como_administrador, venta_lista
    ):
        id_contrato, motivo = crear_contrato(
            venta_id=venta_lista,
            forma_pago="Contado",
            cantidad_cuotas=6
        )

        assert id_contrato is None

    def test_vendedor_si_puede_crear(
        self, como_vendedor, venta_lista
    ):
        """
        Firmar un contrato es parte del trabajo del
        vendedor. Lo que no puede es cancelarlo.
        """

        id_contrato, numero = crear_contrato(
            venta_id=venta_lista,
            forma_pago="Contado"
        )

        assert id_contrato is not None


class TestEstados:

    def test_activo_pasa_a_finalizado(
        self, como_administrador, venta_lista
    ):
        id_contrato, _ = crear_contrato(
            venta_id=venta_lista,
            forma_pago="Contado"
        )

        cambiar_estado(id_contrato, "finalizado")

        assert obtener_contrato(
            id_contrato
        )["estado"] == "finalizado"

    def test_finalizado_no_vuelve_a_activo(
        self, como_administrador, venta_lista
    ):
        """
        Un contrato firmado es histórico. TRANSICIONES
        es el único sitio donde se decide qué paso
        es legal.
        """

        id_contrato, _ = crear_contrato(
            venta_id=venta_lista,
            forma_pago="Contado"
        )

        cambiar_estado(id_contrato, "finalizado")

        ok, motivo = cambiar_estado(
            id_contrato, "activo"
        )

        assert ok is False
        assert motivo
        assert obtener_contrato(
            id_contrato
        )["estado"] == "finalizado"

    def test_cancelado_puede_reactivarse(
        self, como_administrador, venta_lista
    ):
        """
        Un contrato cancelado no surte efecto, así
        que sí se puede volver a activar.
        """

        id_contrato, _ = crear_contrato(
            venta_id=venta_lista,
            forma_pago="Contado"
        )

        cambiar_estado(id_contrato, "cancelado")

        ok, motivo = cambiar_estado(
            id_contrato, "activo"
        )

        assert ok is True, motivo

    def test_estado_inexistente(
        self, como_administrador, venta_lista
    ):
        id_contrato, _ = crear_contrato(
            venta_id=venta_lista,
            forma_pago="Contado"
        )

        ok, motivo = cambiar_estado(
            id_contrato, "inventado"
        )

        assert ok is False
        assert motivo

    def test_todas_las_transiciones_son_validas(
        self, como_administrador
    ):
        """
        Los estados de TRANSICIONES tienen que estar
        en ESTADOS: si no, cambiar_estado aceptaría
        un estado que el resto del código no sabe
        pintar.
        """

        for origen, destinos in TRANSICIONES.items():

            assert origen in ESTADOS

            for destino in destinos:

                assert destino in ESTADOS


class TestVentaConContrato:

    def test_no_se_puede_anular(
        self, como_administrador, venta_lista
    ):
        """
        La clave foranea ya lo impide, pero
        eliminar_venta() lo comprueba antes para
        poder devolver False en vez de saltar por
        la excepción.
        """

        from database.ventas import eliminar_venta

        crear_contrato(
            venta_id=venta_lista,
            forma_pago="Contado"
        )

        # Devuelve el numero del contrato, no
        # True: la vista lo enseña para que se
        # sepa cual es el que estorba.

        bloqueo = venta_bloqueada_por_contrato(venta_lista)

        assert bloqueo
        assert bloqueo.startswith("CTR-")

        assert eliminar_venta(venta_lista) is False

    def test_cancelado_no_bloquea(
        self, como_administrador, venta_lista
    ):
        """
        Un contrato cancelado no surte efecto, así
        que no impide anular la venta ni impide
        rehacer el contrato.
        """

        from database.ventas import eliminar_venta

        id_contrato, _ = crear_contrato(
            venta_id=venta_lista,
            forma_pago="Contado"
        )

        cambiar_estado(id_contrato, "cancelado")

        assert venta_bloqueada_por_contrato(
            venta_lista
        ) is None

        assert eliminar_venta(venta_lista) is True

    def test_sin_contrato_no_bloquea(
        self, como_administrador, venta_lista
    ):
        assert venta_bloqueada_por_contrato(
            venta_lista
        ) is None


class TestConsultas:

    def test_ventas_sin_contrato(
        self, como_administrador, venta_lista
    ):
        assert venta_lista in [
            v[0] for v in ventas_sin_contrato()
        ]

        id_contrato, _ = crear_contrato(
            venta_id=venta_lista,
            forma_pago="Contado"
        )

        assert venta_lista not in [
            v[0] for v in ventas_sin_contrato()
        ]

    def test_contrato_de_venta(
        self, como_administrador, venta_lista
    ):
        assert contrato_de_venta(venta_lista) is None

        id_contrato, _ = crear_contrato(
            venta_id=venta_lista,
            forma_pago="Contado"
        )

        assert contrato_de_venta(
            venta_lista
        )["id"] == id_contrato

    def test_filtrar_por_estado(
        self, como_administrador
    ):
        id_uno, _ = crear_contrato(
            venta_id=self._venta(),
            forma_pago="Contado"
        )

        assert len(obtener_contratos()) == 1

        cambiar_estado(id_uno, "cancelado")

        assert len(
            obtener_contratos(estado="activo")
        ) == 0

        assert len(
            obtener_contratos(estado="cancelado")
        ) == 1

    def _venta(self, datos_base=None):
        """
        Cada contrato necesita su propia venta:
        una venta solo admite un contrato vivo.
        """

        from database.marcas import insertar_marca
        from database.autos import insertar_auto
        from database.clientes import insertar_cliente

        id_marca = insertar_marca("Marca Contrato")

        id_auto = insertar_auto(
            id_marca, "Modelo", 2025,
            20000.0, "Blanco", 5
        )

        id_cliente = insertar_cliente(
            "Cliente", "Nuevo", None, None, None
        )

        id_venta, _ = registrar_venta(
            id_cliente, id_auto, "2026-04-01", 20000.0
        )

        return id_venta

    def test_eliminar_devuelve_ok(
        self, como_administrador, venta_lista
    ):
        id_contrato, _ = crear_contrato(
            venta_id=venta_lista,
            forma_pago="Contado"
        )

        ok, motivo = eliminar_contrato(id_contrato)

        assert ok is True, motivo
        assert obtener_contrato(id_contrato) is None

    def test_tras_eliminar_se_puede_rehacer(
        self, como_administrador, venta_lista
    ):
        """
        La ruta para rehacer un contrato es
        cancelar el anterior y crear el nuevo.
        """

        id_antiguo, _ = crear_contrato(
            venta_id=venta_lista,
            forma_pago="Contado"
        )

        cambiar_estado(id_antiguo, "cancelado")

        id_nuevo, motivo = crear_contrato(
            venta_id=venta_lista,
            forma_pago="Contado"
        )

        assert id_nuevo is not None, motivo
        assert id_nuevo != id_antiguo


class TestPdf:

    def test_se_genera_el_archivo(
        self, como_administrador, venta_lista,
        tmp_path, monkeypatch
    ):
        """
        Se escribe en una carpeta temporal: si no,
        cada prueba deja un PDF en
        documentos/contratos/.
        """

        import utils.contrato_pdf as pdf

        destino = str(tmp_path)

        monkeypatch.setattr(
            pdf, "ruta_documento",
            lambda numero: os.path.join(
                destino, pdf.nombre_archivo(numero)
            )
        )

        id_contrato, _ = crear_contrato(
            venta_id=venta_lista,
            forma_pago="Contado"
        )

        contrato = obtener_contrato(id_contrato)

        ruta = generar_contrato(contrato)

        assert os.path.exists(ruta)
        assert ruta.endswith(".pdf")
        assert os.path.getsize(ruta) > 1000

    def test_cuota_calculada(
        self, como_administrador, venta_lista
    ):
        id_contrato, _ = crear_contrato(
            venta_id=venta_lista,
            forma_pago="Anticipo + cuotas",
            anticipo=5000.0,
            cantidad_cuotas=10
        )

        contrato = obtener_contrato(id_contrato)

        # 25000 - 5000 = 20000 en 10 cuotas.

        assert cuota_importe(contrato) == 2000.0

    def test_sin_cuotas_no_hay_importe(
        self, como_administrador, venta_lista
    ):
        id_contrato, _ = crear_contrato(
            venta_id=venta_lista,
            forma_pago="Contado"
        )

        contrato = obtener_contrato(id_contrato)

        assert cuota_importe(contrato) is None

    def test_escapar_el_marcado(
        self, como_administrador
    ):
        """
        Paragraph lee <, > y & como marcado. Un
        precio o una observación con esos signos
        rompe el párrafo entero.
        """

        assert escapar("a < b") == "a &lt; b"
        assert escapar("P&D") == "P&amp;D"

    def test_no_mapeables_se_vuelven_interrogacion(
        self, como_administrador
    ):
        """
        reportlab sustituye en silencio lo que la
        fuente no sabe por el glifo .notdef de
        Helvetica, que es una "n": un emoji
        salía como "nn".
        """

        assert sustituir_no_mapeables(
            "coche 🚗"
        ) == "coche ?"

    def test_el_euro_se_conserva(
        self, como_administrador
    ):
        """
        El € está en WinAnsi, así que se
        conserva: no todo lo no-ASCII es
        descartable.
        """

        assert sustituir_no_mapeables(
            "1.500 €"
        ) == "1.500 €"
