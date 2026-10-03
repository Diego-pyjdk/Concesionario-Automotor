# ==========================================
# PAGOS
# ==========================================
# Lo que hay que proteger:
#   - un pago no puede pasar del saldo
#   - un pago no se edita, se borra y se rehace
#   - una venta con dinero cobrado no se anula
#   - la comprobación del saldo va DENTRO de la
#     transacción, con la venta bloqueada
# ==========================================


import pytest

from database.ventas import registrar_venta, eliminar_venta

from database.contratos import (
    crear_contrato,
    obtener_contrato,
    obtener_contratos
)

from database.pagos import (
    FORMAS_PAGO,
    obtener_pagos,
    saldo_venta,
    pagos_de_venta,
    venta_bloqueada_por_pagos,
    registrar_pago,
    eliminar_pago,
    obtener_cobros
)


@pytest.fixture
def venta_con_saldo(como_administrador, datos_base):
    """
    Una venta de 25.000 con saldo entero, y su id.
    """

    _, id_auto, id_cliente = datos_base

    id_venta, _ = registrar_venta(
        id_cliente, id_auto, "2026-06-01", 25000.0
    )

    return id_venta


class TestSaldo:

    def test_sin_pagos_todo_pendiente(
        self, venta_con_saldo
    ):
        precio, pagado, saldo = saldo_venta(
            venta_con_saldo
        )

        assert float(precio) == 25000.0
        assert float(pagado) == 0
        assert float(saldo) == 25000.0

    def test_venta_inexistente(
        self, como_administrador
    ):
        assert saldo_venta(99999) is None

    def test_cuenta_los_pagos(
        self, venta_con_saldo
    ):
        registrar_pago(
            venta_con_saldo, 5000.0,
            "2026-06-02", "Efectivo"
        )

        registrar_pago(
            venta_con_saldo, 2000.0,
            "2026-06-03", "Transferencia bancaria"
        )

        precio, pagado, saldo = saldo_venta(
            venta_con_saldo
        )

        assert float(pagado) == 7000.0
        assert float(saldo) == 18000.0


class TestRegistrar:

    def test_devuelve_el_id(
        self, venta_con_saldo
    ):
        id_pago, motivo = registrar_pago(
            venta_con_saldo, 5000.0,
            "2026-06-02", "Efectivo"
        )

        assert isinstance(id_pago, int)
        assert motivo == ""

    def test_guarda_quien_cobro(
        self, venta_con_saldo
    ):
        registrar_pago(
            venta_con_saldo, 5000.0,
            "2026-06-02", "Efectivo"
        )

        pago = obtener_pagos(venta_con_saldo)[0]

        assert pago[6] == "admin"

    def test_rechaza_importe_mayor_que_el_saldo(
        self, venta_con_saldo
    ):
        id_pago, motivo = registrar_pago(
            venta_con_saldo, 30000.0,
            "2026-06-02", "Efectivo"
        )

        assert id_pago is None
        assert "saldo" in motivo.lower()

    def test_rechaza_importe_cero(
        self, venta_con_saldo
    ):
        id_pago, motivo = registrar_pago(
            venta_con_saldo, 0,
            "2026-06-02", "Efectivo"
        )

        assert id_pago is None

    def test_rechaza_importe_negativo(
        self, venta_con_saldo
    ):
        """
        Un importe negativo no es un pago: es un
        reembolso, y de eso se ocupa otro camino.
        """

        id_pago, motivo = registrar_pago(
            venta_con_saldo, -500,
            "2026-06-02", "Efectivo"
        )

        assert id_pago is None

    def test_rechaza_forma_inventada(
        self, venta_con_saldo
    ):
        id_pago, motivo = registrar_pago(
            venta_con_saldo, 100,
            "2026-06-02", "Bitcoin"
        )

        assert id_pago is None
        assert "forma de pago" in motivo.lower()

    def test_acepta_todas_las_formas(
        self, venta_con_saldo
    ):
        for forma in FORMAS_PAGO:

            id_pago, motivo = registrar_pago(
                venta_con_saldo, 1.0,
                "2026-06-02", forma
            )

            assert id_pago is not None, forma

        assert pagos_de_venta(venta_con_saldo) == len(
            FORMAS_PAGO
        )

    def test_rechaza_venta_inexistente(
        self, como_administrador
    ):
        id_pago, motivo = registrar_pago(
            99999, 100.0, "2026-06-02", "Efectivo"
        )

        assert id_pago is None
        assert "venta" in motivo.lower()

    def test_sin_fecha(
        self, venta_con_saldo
    ):
        id_pago, motivo = registrar_pago(
            venta_con_saldo, 100.0,
            None, "Efectivo"
        )

        assert id_pago is None

    def test_cobra_hasta_el_final(
        self, venta_con_saldo
    ):
        """
        Se puede dejar la venta a cero, y un peso
        más ya no.
        """

        id_pago, motivo = registrar_pago(
            venta_con_saldo, 25000.0,
            "2026-06-02", "Efectivo"
        )

        assert id_pago is not None, motivo

        _, _, saldo = saldo_venta(venta_con_saldo)

        assert float(saldo) == 0

        id_pago, motivo = registrar_pago(
            venta_con_saldo, 0.01,
            "2026-06-03", "Efectivo"
        )

        assert id_pago is None

    def test_el_residuo_se_puede_cobrar(
        self, venta_con_saldo
    ):
        """
        Repartir 20.000 en 7 cuotas deja un residuo
        de céntimos. Ese residuo tiene que poder
        cobrarse, porque si no la venta no se
        cerraría nunca.

        Y no hace falta margen de tolerancia para
        eso: el saldo sale de DECIMAL(10,2) menos la
        suma de otros DECIMAL(10,2), así que siempre
        es un múltiplo de un céntimo y se compara
        con exactitud.
        """

        registrar_pago(
            venta_con_saldo, 24999.98,
            "2026-06-02", "Efectivo"
        )

        _, _, saldo = saldo_venta(venta_con_saldo)

        assert float(saldo) == 0.02

        # El céntimo que queda se cobra.

        id_pago, motivo = registrar_pago(
            venta_con_saldo, 0.02,
            "2026-06-03", "Efectivo"
        )

        assert id_pago is not None, motivo

        _, _, saldo = saldo_venta(venta_con_saldo)

        assert float(saldo) == 0.0

    def test_un_centimo_de_mas_no_pasa(
        self, venta_con_saldo
    ):
        """
        Sobre una venta ya saldada, ni un céntimo
        entra.
        """

        registrar_pago(
            venta_con_saldo, 25000.0,
            "2026-06-02", "Efectivo"
        )

        id_pago, motivo = registrar_pago(
            venta_con_saldo, 0.01,
            "2026-06-03", "Efectivo"
        )

        assert id_pago is None
        assert "saldo" in motivo.lower()

    def test_rechaza_mas_de_dos_decimales(
        self, venta_con_saldo
    ):
        """
        pagos.importe es DECIMAL(10,2). Un importe
        con más decimales se guardaría redondeado y
        el dinero se perdería sin avisar: un pago de
        0.004 se guardaría como 0.00 y el saldo no se
        movería.

        Se rechaza en vez de redondear. Desde la
        interfaz es imposible llegar aquí (el campo
        tiene dos decimales), pero la capa de datos
        no se fía de eso.
        """

        for importe in (0.004, 0.001, 1000.005):

            id_pago, motivo = registrar_pago(
                venta_con_saldo, importe,
                "2026-06-03", "Efectivo"
            )

            assert id_pago is None, importe
            assert "decimales" in motivo.lower()

        # Y no se ha creado ninguna fila basura.

        assert obtener_pagos(venta_con_saldo) == []

    def test_no_deja_sobrepagar_encadenando(
        self, venta_con_saldo
    ):
        """
        La forma de colarse un céntimo de más sería
        encadenar pagos: cada uno pasa medio céntimo
        de margen, y veinte pagos dejarían diez
        céntimos de encima.

        Con la comparación exacta y sin margen, no
        hay por dónde: en cuanto el saldo llega a
        cero, el siguiente céntimo se rechaza.
        """

        registrar_pago(
            venta_con_saldo, 25000.0,
            "2026-06-02", "Efectivo"
        )

        aceptados = 0

        for numero in range(3, 30):

            id_pago, motivo = registrar_pago(
                venta_con_saldo, 0.01,
                f"2026-06-{numero:02d}", "Efectivo"
            )

            if id_pago is None:

                break

            aceptados += 1

        _, pagado, _ = saldo_venta(venta_con_saldo)

        assert float(pagado) == 25000.0

        assert aceptados == 0, (
            f"aceptó {aceptados} pagos de un céntimo "
            "sobre una venta ya saldada"
        )


class TestContrato:

    def test_se_asigna_el_contrato_solo(
        self, venta_con_saldo
    ):
        """
        Si la venta tiene contrato vivo, el pago
        queda enlazado a él sin que nadie lo pida.
        """

        id_contrato, numero = crear_contrato(
            venta_id=venta_con_saldo,
            forma_pago="Crédito"
        )

        registrar_pago(
            venta_con_saldo, 1000.0,
            "2026-06-02", "Efectivo"
        )

        from database.conexion import obtener_conexion

        conexion = obtener_conexion()
        cursor = conexion.cursor()

        cursor.execute(
            "SELECT contrato_id FROM pagos WHERE venta_id = %s",
            (venta_con_saldo,)
        )

        assert cursor.fetchone()[0] == id_contrato

        cursor.close()
        conexion.close()

    def test_sin_contrato_tambien_se_cobra(
        self, venta_con_saldo
    ):
        """
        Una venta en efectivo puede cobrarse sin
        llegar a firmar contrato.
        """

        id_pago, motivo = registrar_pago(
            venta_con_saldo, 1000.0,
            "2026-06-02", "Efectivo"
        )

        assert id_pago is not None, motivo

    def test_contrato_cancelado_no_se_asigna(
        self, venta_con_saldo
    ):
        id_contrato, numero = crear_contrato(
            venta_id=venta_con_saldo,
            forma_pago="Crédito"
        )

        from database.contratos import cambiar_estado

        cambiar_estado(id_contrato, "cancelado")

        registrar_pago(
            venta_con_saldo, 1000.0,
            "2026-06-02", "Efectivo"
        )

        from database.conexion import obtener_conexion

        conexion = obtener_conexion()
        cursor = conexion.cursor()

        cursor.execute(
            "SELECT contrato_id FROM pagos WHERE venta_id = %s",
            (venta_con_saldo,)
        )

        assert cursor.fetchone()[0] is None

        cursor.close()
        conexion.close()


class TestEliminar:

    def test_el_admin_borra_un_pago(
        self, venta_con_saldo
    ):
        id_pago, _ = registrar_pago(
            venta_con_saldo, 5000.0,
            "2026-06-02", "Efectivo"
        )

        ok, motivo = eliminar_pago(id_pago)

        assert ok is True, motivo
        assert obtener_pagos(venta_con_saldo) == []

    def test_el_vendedor_no_borra(
        self, como_vendedor, datos_base
    ):
        """
        Deshacer un cobro es raro y debe ser
        consciente: solo el administrador.
        """

        from errores import PermisoDenegado

        _, id_auto, id_cliente = datos_base

        id_venta, _ = registrar_venta(
            id_cliente, id_auto, "2026-06-01", 25000.0
        )

        id_pago, _ = registrar_pago(
            id_venta, 5000.0, "2026-06-02", "Efectivo"
        )

        with pytest.raises(PermisoDenegado):

            eliminar_pago(id_pago)

    def test_pago_inexistente(
        self, como_administrador
    ):
        ok, motivo = eliminar_pago(99999)

        assert ok is False
        assert motivo

    def test_borrar_devuelve_el_dinero_al_saldo(
        self, venta_con_saldo
    ):
        id_pago, _ = registrar_pago(
            venta_con_saldo, 5000.0,
            "2026-06-02", "Efectivo"
        )

        eliminar_pago(id_pago)

        _, pagado, saldo = saldo_venta(venta_con_saldo)

        assert float(pagado) == 0
        assert float(saldo) == 25000.0


class TestVentaConPagos:

    def test_no_se_anula_si_hay_dinero(
        self, venta_con_saldo
    ):
        """
        Si ya se cobró algo, anular la venta en
        silencio dejaría el dinero cobrado sin una
        venta detrás.
        """

        registrar_pago(
            venta_con_saldo, 5000.0,
            "2026-06-02", "Efectivo"
        )

        bloqueada, cuantos = venta_bloqueada_por_pagos(
            venta_con_saldo
        )

        assert bloqueada is True
        assert cuantos == 1

        assert eliminar_venta(venta_con_saldo) is False

    def test_sin_pagos_no_bloquea(
        self, venta_con_saldo
    ):
        bloqueada, cuantos = venta_bloqueada_por_pagos(
            venta_con_saldo
        )

        assert bloqueada is False
        assert cuantos == 0

    def test_anular_devuelve_el_stock(
        self, venta_con_saldo
    ):
        """
        La regla del stock sigue valiendo: anular
        una venta sin pagos devuelve la unidad.
        """

        from database.autos import obtener_autos

        def stock():

            for f in obtener_autos():

                if f[0] == 1:

                    return f[6]

        # Tras la venta hay 2 unidades.

        assert eliminar_venta(venta_con_saldo) is True


class TestAuditoria:

    def test_registrar_deja_rastro(
        self, venta_con_saldo
    ):
        from database.auditoria import obtener_auditoria

        registrar_pago(
            venta_con_saldo, 5000.0,
            "2026-06-02", "Efectivo"
        )

        registros = obtener_auditoria()

        assert registros[0][3] == "PAGO"

    def test_el_importe_no_se_registra_en_texto(
        self, venta_con_saldo
    ):
        """
        El rastro guarda el importe con separador
        de miles, no en claro: así una búsqueda
        por "5.000" no lo encuentra.
        """

        from database.auditoria import obtener_auditoria

        registrar_pago(
            venta_con_saldo, 5000.0,
            "2026-06-02", "Efectivo"
        )

        descripcion = obtener_auditoria()[0][5] or ""

        assert "5,000.00" in descripcion


class TestReporte:

    def test_cobros_por_periodo(
        self, venta_con_saldo
    ):
        registrar_pago(
            venta_con_saldo, 1000.0,
            "2026-06-02", "Efectivo"
        )
        registrar_pago(
            venta_con_saldo, 2000.0,
            "2026-06-03", "Efectivo"
        )

        entradas, total = obtener_cobros(
            desde="2026-06-01",
            hasta="2026-06-30"
        )

        assert entradas == 2
        assert float(total) == 3000.0

    def test_fuera_de_periodo(
        self, venta_con_saldo
    ):
        registrar_pago(
            venta_con_saldo, 1000.0,
            "2026-06-02", "Efectivo"
        )

        entradas, total = obtener_cobros(
            desde="2020-01-01",
            hasta="2020-12-31"
        )

        assert entradas == 0


class TestListado:

    def test_orden_por_fecha(
        self, venta_con_saldo
    ):
        registrar_pago(
            venta_con_saldo, 100.0,
            "2026-06-01", "Efectivo"
        )
        registrar_pago(
            venta_con_saldo, 200.0,
            "2026-06-03", "Efectivo"
        )

        pagos = obtener_pagos(venta_con_saldo)

        # Del más reciente al más antiguo.

        assert float(pagos[0][2]) == 200.0
        assert float(pagos[1][2]) == 100.0

    def test_contrato_de_columnas(
        self, venta_con_saldo
    ):
        registrar_pago(
            venta_con_saldo, 100.0,
            "2026-06-01", "Efectivo",
            referencia="OP 12345",
            concepto="Entrada"
        )

        pago = obtener_pagos(venta_con_saldo)[0]

        # id, fecha, importe, forma, referencia,
        # concepto, usuario_nombre

        assert len(pago) == 7
        assert pago[3] == "Efectivo"
        assert pago[4] == "OP 12345"
        assert pago[5] == "Entrada"
