# ==========================================
# COBRANZA Y GARANTÍAS
# ==========================================
# Lo que hay que proteger:
#
#   1. La cartera NO CUENTA de más. El saldo que ve
#      el cobrador tiene que ser lo que el cliente
#      debe de verdad, y no lo que se pactó.
#
#   2. Vencida se deduce de la fecha, no del campo de
#      estado. Consultar el estado daría la respuesta
#      equivocada justo cuando importa.
#
#   3. Una garantía no se libera con deuda viva: es
#      devolverle al cliente su respaldo.
#
#   4. Un gravamen no se certifica: se registra lo que
#      el concesionario afirma, y se avisa de que hay
#      que validarlo con un abogado.
#
#   5. El orden de urgencia es por retraso, no por
#      importe: el cliente que debe poco y va muy
#      atrasado va primero.
# ==========================================


from datetime import date
from decimal import Decimal

import pytest

from database.contratos import crear_contrato
from database.ventas import registrar_venta


import database.cobranza as K
import database.financiera as F
import database.garantias as G


from errores import PermisoDenegado


D = Decimal


def dos_decimales(valor):

    return D(str(valor)).quantize(D("0.01"))


_CONTADOR = [0]


def hacer_contrato(
    precio=10000000.0,
    anticipo=6000000.0,
    cuotas=12,
    saldo=4000000.0,
    primer_vencimiento="2026-11-01"
):

    """
    Monta una venta, un contrato y su cronograma.

    Devuelve el diccionario del fixture
    contrato_financiado.
    """

    import sesion as ms

    from database.marcas import insertar_marca
    from database.autos import insertar_auto
    from database.clientes import insertar_cliente

    # El nombre tiene que ser único: marcas.nombre es
    # UNIQUE y dos contratos con el mismo precio en
    # una misma prueba reventarían aquí.

    _CONTADOR[0] += 1

    id_marca = insertar_marca(
        f"Marca Cobranza {_CONTADOR[0]}"
    )

    id_auto = insertar_auto(
        id_marca,
        f"Modelo {_CONTADOR[0]}",
        2025,
        precio,
        "Blanco",
        5
    )

    id_cliente = insertar_cliente(
        f"Cliente {_CONTADOR[0]}",
        "Cobranza",
        None,
        None,
        None
    )

    id_venta, _ = registrar_venta(
        id_cliente, id_auto, "2026-10-01", precio
    )

    id_contrato, numero = crear_contrato(
        venta_id=id_venta,
        forma_pago="Anticipo + cuotas",
        anticipo=anticipo,
        cantidad_cuotas=cuotas,
        saldo_financiado=dos_decimales(saldo),
        periodicidad="mensual",
        primer_vencimiento=date.fromisoformat(
            primer_vencimiento
        )
    )

    total, motivo = F.generar_cronograma(id_contrato)

    assert total == cuotas, motivo

    return {
        "id_contrato": id_contrato,
        "id_venta": id_venta,
        "numero": numero,
        "cliente_id": id_cliente,
        "cuotas": F.obtener_cuotas(id_contrato)
    }


def pagar(datos, numero_cuota, importe, fecha="2026-11-01"):

    for cuota in datos["cuotas"]:

        if cuota["numero"] == numero_cuota:

            id_pago, motivo = F.registrar_pago_cuota(
                cuota["id"], importe, fecha, "Efectivo"
            )

            assert id_pago is not None, motivo

            return id_pago

    raise AssertionError(
        f"No hay cuota número {numero_cuota}"
    )


def id_cuota(datos, numero):

    for cuota in datos["cuotas"]:

        if cuota["numero"] == numero:

            return cuota["id"]

    raise AssertionError(f"No hay cuota número {numero}")


@pytest.fixture
def cartera(como_administrador):
    """Un contrato financiado sin cobrar nada."""

    return hacer_contrato()


# ==========================================
# CUENTAS POR COBRAR
# ==========================================

class TestCuentasPorCobrar:

    def test_el_saldo_es_el_que_se_debe(
        self, cartera
    ):
        """
        El saldo pendiente es lo financiado MENOS lo
        cobrado, no lo financiado.

        Es la diferencia más importante de la cartera.
        Un contrato de 10 millones con 4 millones
        pagados debe 6; si la cartera dijera que debe
        10, el cobrador iría a pedir de más y el
        cliente se quedaría sin saber por qué.
        """

        filas = K.cuentas_por_cobrar()

        assert len(filas) == 1

        assert dos_decimales(filas[0]["saldo"]) == (
            D("4000000.00")
        )

    def test_el_saldo_baja_al_pagar(self, cartera):

        cuota = cartera["cuotas"][0]

        pagar(cartera, 1, dos_decimales(cuota["importe"]))

        filas = K.cuentas_por_cobrar()

        assert dos_decimales(filas[0]["saldo"]) < (
            D("4000000.00")
        )

    def test_el_anticipo_no_cuenta_como_cobranza(
        self, cartera
    ):
        """
        La entrega inicial ya se cobró al vender. El
        saldo de la cartera no la incluye, porque
        saldo_financiado ya es lo que quedó por pagar.
        """

        filas = K.cuentas_por_cobrar()

        assert dos_decimales(filas[0]["saldo"]) != (
            D("10000000.00")
        )

    def test_un_contrato_pagado_no_aparece(
        self, cartera
    ):
        """
        Una venta totalmente cobrada no es una cuenta
        por cobrar. Si apareciera, la cartera sumaria
        una deuda que ya no existe y el total seria
        mentira.
        """

        total = 0

        for cuota in cartera["cuotas"]:

            pagar(
                cartera,
                cuota["numero"],
                dos_decimales(cuota["importe"]),
                cuota["fecha_vencimiento"].isoformat()
            )

            total += 1

        assert total == 12

        filas = K.cuentas_por_cobrar()

        assert filas == []

    def test_una_venta_a_contado_no_aparece(
        self, como_administrador
    ):
        """
        Una venta al contado no tiene saldo financiado,
        así que no es una cuenta por cobrar. Sin esta
        comprobación, la cartera metería en su lista
        todas las ventas de efectivo del concesionario.
        """

        from database.marcas import insertar_marca
        from database.autos import insertar_auto
        from database.clientes import insertar_cliente

        id_auto = insertar_auto(
            insertar_marca("Marca Contado"),
            "Modelo Contado",
            2025,
            1000.0,
            "Rojo",
            1
        )

        id_venta, _ = registrar_venta(
            insertar_cliente(
                "Cliente", "Contado", None, None, None
            ),
            id_auto,
            "2026-10-01",
            1000.0
        )

        crear_contrato(venta_id=id_venta, forma_pago="Contado")

        filas = K.cuentas_por_cobrar()

        assert all(
            f["id_contrato"] != 1 for f in filas
        )

    def test_orden_por_urgencia_no_por_importe(
        self, como_administrador
    ):
        """
        La lista de trabajo de la cobranza va por
        retraso, no por importe.

        Ordenar por saldo deja al final al cliente que
        debe 80.000 y lleva 40 días de atraso, detrás
        de uno que debe 3.000 y no ha pagado nunca. La
        urgencia la marca el retraso.
        """

        pequeno = hacer_contrato(
            precio=3000000.0,
            anticipo=0.0,
            cuotas=6,
            saldo=3000000.0,
            primer_vencimiento="2026-01-10"
        )

        grande = hacer_contrato(
            precio=90000000.0,
            anticipo=89920000.0,
            cuotas=12,
            saldo=80000.0,
            primer_vencimiento="2026-09-01"
        )

        filas = K.cuentas_por_cobrar()

        assert len(filas) == 2

        # El que debe MENOS va primero: es el que más
        # días lleva de retraso.

        assert filas[0]["contrato_id"] == pequeno["id_contrato"]

        assert filas[1]["contrato_id"] == grande["id_contrato"]

    def test_los_dias_de_atraso_son_los_mayores(
        self, como_administrador
    ):
        """
        Los días de atraso son los de la cuota más
        antigua sin pagar, no los del primer
        vencimiento del cronograma.
        """

        datos = hacer_contrato(
            primer_vencimiento="2026-01-10"
        )

        # Pagar las tres primeras: la deuda más
        # antigua pendiente pasa a ser la cuarta.

        for numero in (1, 2, 3):

            cuota = datos["cuotas"][numero - 1]

            pagar(
                datos, numero,
                dos_decimales(cuota["importe"]),
                cuota["fecha_vencimiento"].isoformat()
            )

        filas = K.cuentas_por_cobrar()

        esperada = (
            date.today() - filas[0]["proximo_vencimiento"]
        ).days

        assert filas[0]["dias_atraso"] == esperada

        assert filas[0]["dias_atraso"] > 30


# ==========================================
# VENCIDAS Y POR VENCER
# ==========================================

class TestVencidas:

    def test_las_vencidas_se_detectan_por_fecha(
        self, como_administrador
    ):
        """
        Vencida se deduce de la fecha, no del campo
        estado.

        La comprobación pone a mano el estado de una
        cuota que ya está pagada: aunque su fecha haya
        pasado, no está vencida.

        Si la cartera preguntara al campo estado en vez
        de a la fecha, ocurriría lo contrario: una cuota
        vencida sin marcar saldría como "pendiente" y no
        se contaría como vencida. El fallo iría justo al
        revés, que es peor: el cobrador no llamaría a
        quien le debe más tiempo.
        """

        datos = hacer_contrato(
            primer_vencimiento="2026-01-10"
        )

        # La primera se cobró entera, pero su fecha
        # ya pasó hace meses.

        cuota = datos["cuotas"][0]

        pagar(
            datos, 1, dos_decimales(cuota["importe"]),
            "2026-01-10"
        )

        vencidas = K.cuotas_vencidas()

        numeros = [f["numero"] for f in vencidas]

        assert 1 not in numeros, (
            "una cuota pagada no está vencida aunque su "
            "fecha haya pasado"
        )

        assert 2 in numeros

    def test_una_cuota_anulada_no_esta_vencida(
        self, como_administrador
    ):

        datos = hacer_contrato(
            primer_vencimiento="2026-01-10"
        )

        F.anular_cuota(
            id_cuota(datos, 1), "No aplica"
        )

        vencidas = K.cuotas_vencidas()

        assert 1 not in [f["numero"] for f in vencidas]

    def test_una_cuota_pagada_no_esta_vencida(
        self, como_administrador
    ):

        datos = hacer_contrato(
            primer_vencimiento="2026-01-10"
        )

        # Pagar solo las tres primeras NO deja la
        # cartera sin vencidas.
        #
        # Y cuántas quedan vencidas NO son las nueve
        # que sobran: hoy es 2026-10-03 y el primer
        # vencimiento es el 2026-01-10 con periodicidad
        # mensual, así que las cuotas caen el 10 de
        # cada mes. Han vencido las nueve primeras (de
        # enero a septiembre) y las tres últimas (octubre,
        # noviembre y diciembre) todavía no vencen.

        for numero in (1, 2, 3):

            cuota = datos["cuotas"][numero - 1]

            pagar(
                datos, numero,
                dos_decimales(cuota["importe"]),
                cuota["fecha_vencimiento"].isoformat()
            )

        vencidas = K.cuotas_vencidas()

        numeros = [f["numero"] for f in vencidas]

        assert numeros == [4, 5, 6, 7, 8, 9]

        # Pagando las que quedaban, ya no queda ninguna
        # vencida.

        for numero in range(4, 13):

            cuota = datos["cuotas"][numero - 1]

            pagar(
                datos, numero,
                dos_decimales(cuota["importe"]),
                cuota["fecha_vencimiento"].isoformat()
            )

        assert K.cuotas_vencidas() == []

    def test_las_por_vencer_son_las_futuras(
        self, cartera
    ):

        por_vencer = K.cuotas_por_vencer(dias=30)

        assert len(por_vencer) > 0

        for cuota in por_vencer:

            assert cuota["fecha_vencimiento"] >= (
                date.today()
            )

            assert cuota["saldo"] > 0

    def test_el_aviso_sale_del_ajuste(
        self, cartera, ajustes_financiera
    ):

        ajustes_financiera("financiera_dias_aviso", 40)

        con_40 = K.cuotas_por_vencer()

        ajustes_financiera("financiera_dias_aviso", 5)

        con_5 = K.cuotas_por_vencer()

        assert len(con_40) > len(con_5)

    def test_el_importe_vencido_suma(
        self, como_administrador
    ):

        datos = hacer_contrato(
            primer_vencimiento="2026-01-10"
        )

        filas = K.cuentas_por_cobrar()

        fila = filas[0]

        # Ninguna cuota se ha cobrado, pero solo nueve
        # han vencido: las de octubre, noviembre y
        # diciembre todavía no llegan (hoy es 2026-10-03).

        assert fila["cuotas_vencidas"] == 9

        # El importe vencido NO es el saldo entero: son
        # las nueve cuotas que ya pasaron su fecha, y las
        # tres últimas todavía no vencieron.
        #
        # La aritmética exacta importa: las once
        # primeras valen 333.333,33 y la última lleva el
        # residuo, 333.333,37. Nueve de las doce son
        # 2.999.999,97, no 3.000.000. Por eso el módulo
        # no multiplica ni reparte: suma lo que hay.

        assert dos_decimales(
            fila["importe_vencido"]
        ) == D("2999999.97")

        assert dos_decimales(
            fila["importe_vencido"]
        ) < dos_decimales(fila["saldo"])

        # Cobrando las tres primeras, quedan seis
        # vencidas y el importe vencido baja. Un contador
        # que no bajara es un contador que cuenta cuotas
        # ya cobradas.

        vencido_antes = dos_decimales(fila["importe_vencido"])

        for numero in (1, 2, 3):

            cuota = datos["cuotas"][numero - 1]

            pagar(
                datos, numero,
                dos_decimales(cuota["importe"]),
                cuota["fecha_vencimiento"].isoformat()
            )

        fila = K.cuentas_por_cobrar()[0]

        assert fila["cuotas_vencidas"] == 6

        assert dos_decimales(
            fila["importe_vencido"]
        ) < vencido_antes


# ==========================================
# RESÚMENES
# ==========================================

class TestResumenes:

    def test_el_resumen_cuadra_con_la_lista(
        self, como_administrador
    ):

        hacer_contrato()
        hacer_contrato()

        filas = K.cuentas_por_cobrar()

        resumen = K.resumen_cartera()

        suma = sum(
            dos_decimales(f["saldo"]) for f in filas
        )

        assert resumen["contratos"] == len(filas)

        assert dos_decimales(resumen["saldo_total"]) == (
            suma
        )

    def test_sin_cartera_no_rompe(self, como_administrador):

        resumen = K.resumen_cartera()

        assert resumen["contratos"] == 0

        assert resumen["saldo_total"] == D("0.00")

    def test_envejecer_por_tramos(self, cartera):

        envejecer = K.envejecer_cartera()

        etiquetas = [t["etiqueta"] for t in envejecer]

        assert etiquetas == [
            "Al día",
            "1 a 30 días",
            "31 a 60 días",
            "61 a 90 días",
            "91 a 180 días",
            "Más de 180 días"
        ]

        total = sum(
            dos_decimales(t["importe"]) for t in envejecer
        )

        assert dos_decimales(total) == D("4000000.00")

    def test_una_deuda_muy_vieja_cae_en_su_tramo(
        self, como_administrador
    ):

        hacer_contrato(
            primer_vencimiento="2025-01-10"
        )

        envejecer = K.envejecer_cartera()

        ultimo = envejecer[-1]

        assert ultimo["etiqueta"] == "Más de 180 días"

        assert dos_decimales(ultimo["importe"]) > 0

        assert ultimo["contratos"] == 1

    def test_concentracion_calcula_el_porcentaje(
        self, como_administrador
    ):

        grande = hacer_contrato(
            precio=90000000.0,
            anticipo=0.0,
            cuotas=12,
            saldo=90000000.0
        )

        del grande

        hacer_contrato(
            precio=3000000.0,
            anticipo=0.0,
            cuotas=6,
            saldo=3000000.0
        )

        principales, porcentaje = K.concentracion_cartera()

        assert len(principales) == 2

        assert 0 < porcentaje <= 100

        # El primero es el que más debe.

        assert dos_decimales(principales[0]["saldo"]) > (
            dos_decimales(principales[1]["saldo"])
        )

    def test_sin_cartera_la_concentracion_no_rompe(
        self, como_administrador
    ):

        principales, porcentaje = K.concentracion_cartera()

        assert principales == []

        assert porcentaje == 0

    def test_detalle_de_cobranza(self, cartera):

        detalle = K.detalle_cobranza(cartera["id_contrato"])

        assert detalle is not None

        assert len(detalle["cuotas"]) == 12

        assert detalle["resumen_cuotas"]["total_cuotas"] == 12

        assert detalle["numero"].startswith("CTR-")

    def test_detalle_de_un_contrato_inexistente(
        self, cartera
    ):

        assert K.detalle_cobranza(999999) is None


# ==========================================
# GARANTÍAS
# ==========================================

class TestGarantias:

    def test_registrar_una_garantia(self, cartera):

        id_garantia, motivo = G.registrar_garantia(
            cartera["id_contrato"],
            "prenda",
            descripcion="Prenda del vehículo"
        )

        assert id_garantia is not None, motivo

        garantias = G.obtener_garantias(cartera["id_contrato"])

        assert len(garantias) == 1

        assert garantias[0]["tipo"] == "prenda"

        assert garantias[0]["estado"] == "pendiente"

    def test_no_hay_dos_garantias_del_mismo_tipo(
        self, cartera
    ):
        """
        Dos aval del mismo contrato sin liberar o
        significan que hay uno y se registered dos, o
        que hay dos. Impide además que un doble clic
        cree dos.
        """

        G.registrar_garantia(
            cartera["id_contrato"], "aval"
        )

        id_garantia, motivo = G.registrar_garantia(
            cartera["id_contrato"], "aval"
        )

        assert id_garantia is None

        assert "sin liberar" in motivo

    def test_tipo_inventado(self, cartera):

        id_garantia, motivo = G.registrar_garantia(
            cartera["id_contrato"], "magia"
        )

        assert id_garantia is None

        assert "no válido" in motivo

    def test_no_se_garantiza_un_contrato_cancelado(
        self, cartera
    ):

        from database.contratos import cambiar_estado

        cambiar_estado(
            cartera["id_contrato"], "cancelado"
        )

        id_garantia, motivo = G.registrar_garantia(
            cartera["id_contrato"], "prenda"
        )

        assert id_garantia is None

        assert "cancelado" in motivo.lower()

    def test_no_se_libera_con_deuda_viva(self, cartera):
        """
        Liberar una garantía con saldo pendiente es
        devolverle al cliente el respaldo de una deuda
        viva. Por eso se comprueba el saldo real, no el
        saldo_financiado del contrato.
        """

        id_garantia, _ = G.registrar_garantia(
            cartera["id_contrato"], "prenda"
        )

        G.cambiar_estado_garantia(
            id_garantia, "inscrita",
            numero_inscripcion="INS-001",
            fecha_inscripcion=date(2026, 10, 5)
        )

        ok, motivo = G.cambiar_estado_garantia(
            id_garantia, "liberada",
            fecha_liberacion=date(2026, 10, 10)
        )

        assert ok is False

        assert "pendientes" in motivo

    def test_se_libera_si_no_debe_nada(self, cartera):
        """
        Pagada toda la deuda, la garantía se puede
        liberar. Es el camino normal al terminar un
        crédito.
        """

        id_garantia, _ = G.registrar_garantia(
            cartera["id_contrato"], "prenda"
        )

        G.cambiar_estado_garantia(
            id_garantia, "inscrita",
            numero_inscripcion="INS-002",
            fecha_inscripcion=date(2026, 10, 5)
        )

        for cuota in cartera["cuotas"]:

            pagar(
                cartera, cuota["numero"],
                dos_decimales(cuota["importe"]),
                cuota["fecha_vencimiento"].isoformat()
            )

        ok, motivo = G.cambiar_estado_garantia(
            id_garantia, "liberada",
            fecha_liberacion=date(2026, 11, 1)
        )

        assert ok is True, motivo

    def test_inscribir_necesita_numero_y_fecha(
        self, cartera
    ):

        id_garantia, _ = G.registrar_garantia(
            cartera["id_contrato"], "prenda"
        )

        ok, motivo = G.cambiar_estado_garantia(
            id_garantia, "inscrita"
        )

        assert ok is False

        assert "inscripción" in motivo

    def test_liberar_necesita_fecha(self, cartera):

        id_garantia, _ = G.registrar_garantia(
            cartera["id_contrato"], "prenda"
        )

        ok, motivo = G.cambiar_estado_garantia(
            id_garantia, "liberada"
        )

        assert ok is False

        assert "fecha" in motivo.lower()

    def test_no_se_puede_saltar_el_pendiente(self, cartera):
        """
        De "pendiente" a "liberada" no: una garantía
        que no se inscribió no se libera, porque no
        está en ningún registro.
        """

        id_garantia, _ = G.registrar_garantia(
            cartera["id_contrato"], "prenda"
        )

        ok, motivo = G.cambiar_estado_garantia(
            id_garantia, "liberada",
            fecha_liberacion=date(2026, 11, 1)
        )

        assert ok is False

        assert "no se puede pasar" in motivo.lower()

    def test_no_se_libera_dos_veces(self, cartera):

        id_garantia, _ = G.registrar_garantia(
            cartera["id_contrato"], "prenda"
        )

        G.cambiar_estado_garantia(
            id_garantia, "rechazada"
        )

        ok, motivo = G.cambiar_estado_garantia(
            id_garantia, "liberada",
            fecha_liberacion=date(2026, 11, 1)
        )

        assert ok is False

        assert "no se puede pasar" in motivo.lower()

    def test_el_gravamen_avisa_de_validarlo(
        self, cartera
    ):
        """
        Un gravamen es una inscripción registral. Aquí
        solo se registra lo que el concesionario
        afirma, y queda escrito que hay que validarlo
        con un abogado y un escribano.

        Si el aviso desapareciera, alguien leería
        "inscrita" y daría por hecho que está inscrito
        en el Registro Público.
        """

        assert "Registro Público" in G.AVISO_GRAVAMEN

        assert "escribano" in G.AVISO_GRAVAMEN

        assert "abogado" in G.AVISO_GRAVAMEN

    def test_el_gravamen_deja_el_aviso_en_el_rastro(
        self, cartera
    ):

        from database.auditoria import obtener_auditoria

        antes = len(obtener_auditoria())

        G.registrar_garantia(
            cartera["id_contrato"],
            "tipo_mora",
            es_gravamen=1
        )

        despues = obtener_auditoria()

        assert len(despues) == antes + 2

        # obtener_auditoria() devuelve tuplas: la
        # descripción es el índice 5.

        textos = " ".join(
            (f[5] or "") for f in despues
        )

        assert "Registro Público" in textos

    def test_liberar_un_gravamen_avisa_de_la_baja(
        self, cartera
    ):

        from database.auditoria import obtener_auditoria

        id_garantia, _ = G.registrar_garantia(
            cartera["id_contrato"], "tipo_mora",
            es_gravamen=1
        )

        G.cambiar_estado_garantia(
            id_garantia, "inscrita",
            numero_inscripcion="INS-G",
            fecha_inscripcion=date(2026, 10, 5)
        )

        for cuota in cartera["cuotas"]:

            pagar(
                cartera, cuota["numero"],
                dos_decimales(cuota["importe"]),
                cuota["fecha_vencimiento"].isoformat()
            )

        antes = len(obtener_auditoria())

        G.cambiar_estado_garantia(
            id_garantia, "liberada",
            fecha_liberacion=date(2026, 11, 1)
        )

        despues = obtener_auditoria()

        assert len(despues) == antes + 2

        textos = " ".join(
            (f[5] or "") for f in despues[:2]
        )

        assert "Registro Público" in textos

    def test_garantias_pendientes_de_liberar(
        self, cartera
    ):
        """
        Una garantía inscrita con el contrato ya
        saldado está pendiente de baja: hay que dar de
        baja el gravamen en el registro.
        """

        id_garantia, _ = G.registrar_garantia(
            cartera["id_contrato"], "prenda"
        )

        G.cambiar_estado_garantia(
            id_garantia, "inscrita",
            numero_inscripcion="INS-003",
            fecha_inscripcion=date(2026, 10, 5)
        )

        urgente, por_liberar = (
            G.garantias_pendientes_de_liberar()
        )

        assert len(por_liberar) == 0, (
            "todavía debe dinero, no hay nada que liberar"
        )

        for cuota in cartera["cuotas"]:

            pagar(
                cartera, cuota["numero"],
                dos_decimales(cuota["importe"]),
                cuota["fecha_vencimiento"].isoformat()
            )

        urgente, por_liberar = (
            G.garantias_pendientes_de_liberar()
        )

        assert len(por_liberar) == 1

        assert por_liberar[0]["id"] == id_garantia

    def test_resumen_de_garantias(self, cartera):

        G.registrar_garantia(cartera["id_contrato"], "aval")

        G.registrar_garantia(
            cartera["id_contrato"], "seguro"
        )

        resumen = G.resumen_de_garantias(
            cartera["id_contrato"]
        )

        assert resumen["total"] == 2

        assert resumen["pendientes"] == 2


# ==========================================
# PERMISOS
# ==========================================

class TestPermisos:

    def test_el_vendedor_no_registra_garantias(
        self, como_administrador
    ):
        """
        Tramitar una garantía es de la administración.

        El contrato se monta como administrador porque
        insertar_marca() y registrar_venta() también lo
        son: el vendedor recibe una venta ya cerrada y
        lo que hace es gestionarla, no crearla desde
        cero.
        """

        datos = hacer_contrato()

        import sesion as ms

        from database.usuarios import insertar_usuario

        id_vendedor = insertar_usuario(
            "vendedor_garantias",
            "Vendedor Garantias",
            "ClaveGarantias2026",
            "vendedor"
        )

        ms.iniciar_sesion((
            id_vendedor,
            "vendedor_garantias",
            "Vendedor Garantias",
            "vendedor"
        ))

        with pytest.raises(PermisoDenegado):

            G.registrar_garantia(
                datos["id_contrato"], "aval"
            )

    def test_el_vendedor_no_libera_garantias(
        self, como_administrador
    ):
        """
        Liberar es devolverle al cliente su respaldo.
        Ni el administrador lo hace sin más: se
        comprueba que no se le debe nada, y su permiso
        no es el de cualquiera.
        """

        datos = hacer_contrato()

        id_garantia, _ = G.registrar_garantia(
            datos["id_contrato"], "aval"
        )

        import sesion as ms

        from database.usuarios import insertar_usuario

        id_vendedor = insertar_usuario(
            "vendedor_libera",
            "Vendedor Libera",
            "ClaveLibera2026",
            "vendedor"
        )

        ms.iniciar_sesion((
            id_vendedor,
            "vendedor_libera",
            "Vendedor Libera",
            "vendedor"
        ))

        with pytest.raises(PermisoDenegado):

            G.cambiar_estado_garantia(
                id_garantia, "rechazada"
            )

    def test_el_vendedor_ve_las_garantias(
        self, como_administrador
    ):
        """
        Ver sí, escribir no.

        Qué garantía respalda la venta es información
        que el vendedor necesita para hablar con el
        cliente; lo que se hace con ella no es suyo.
        """

        datos = hacer_contrato()

        G.registrar_garantia(datos["id_contrato"], "aval")

        import sesion as ms

        from database.usuarios import insertar_usuario

        id_vendedor = insertar_usuario(
            "vendedor_ve",
            "Vendedor Ve",
            "ClaveVe2026",
            "vendedor"
        )

        ms.iniciar_sesion((
            id_vendedor,
            "vendedor_ve",
            "Vendedor Ve",
            "vendedor"
        ))

        garantias = G.obtener_garantias(
            datos["id_contrato"]
        )

        assert len(garantias) == 1

        assert garantias[0]["tipo"] == "aval"

    def test_el_vendedor_no_cobra_cuotas(
        self, como_administrador
    ):
        """
        Cobrar una cuota NO: es de la administración.

        Antes esta prueba decía que sí, y era
        cierto: registrar_pago_cuota() llevaba
        VER_CONTRATOS, que el vendedor tiene. Bastaba
        llamar a la función para quedarse con el
        dinero de un crédito sin pasar por ninguna
        caja. Registrar una venta lo puede hacer el
        vendedor porque es su trabajo; la cobranza de
        un crédito es de quien responde de que ese
        dinero llegó.

        Y la comprobación de saldo sigue siendo la
        misma para quien sí puede cobrar: es una
        condición de la operación, no un privilegio.
        Eso se comprueba aparte, con la
        administración.
        """

        from errores import PermisoDenegado

        datos = hacer_contrato()

        import sesion as ms

        from database.usuarios import insertar_usuario

        id_vendedor = insertar_usuario(
            "vendedor_cobra",
            "Vendedor Cobra",
            "ClaveCobra2026",
            "vendedor"
        )

        ms.iniciar_sesion((
            id_vendedor,
            "vendedor_cobra",
            "Vendedor Cobra",
            "vendedor"
        ))

        cuota = datos["cuotas"][0]

        with pytest.raises(PermisoDenegado):

            F.registrar_pago_cuota(
                cuota["id"],
                dos_decimales(cuota["importe"]),
                cuota["fecha_vencimiento"].isoformat(),
                "Efectivo"
            )

        # Y la cuota sigue como estaba: un intento
        # denegado no puede haber movido un céntimo.

        assert (
            F.obtener_cuota(cuota["id"])["saldo"]
            == dos_decimales(cuota["importe"])
        )

    def test_el_administrador_tampoco_pasa_del_saldo(
        self, como_administrador
    ):
        """
        Y quien sí puede cobrar no puede pasarse del
        saldo de la cuota.

        Es la otra mitad de la comprobación, y va
        aquí para que quede claro que el permiso no
        sustituye a la validación: con permiso se
        puede cobrar, pero no de más.
        """

        datos = hacer_contrato()

        cuota = F.obtener_cuota(datos["cuotas"][1]["id"])

        id_pago, motivo = F.registrar_pago_cuota(
            cuota["id"],
            dos_decimales(cuota["importe"]) + D("1.00"),
            "2026-12-01",
            "Efectivo"
        )

        assert id_pago is None

        assert "saldo" in motivo.lower()
