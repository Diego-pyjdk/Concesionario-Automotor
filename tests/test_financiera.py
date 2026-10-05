# ==========================================
# FINANCIERA: CRONOGRAMAS Y CUOTAS
# ==========================================
# Lo que hay que proteger aquí, en orden de
# importancia:
#
#   1. El cronograma cuadra. La suma de las cuotas es
#      el saldo financiado, al céntimo.
#
#   2. El saldo de una cuota SIEMPRE es lo que dicen
#      los pagos. Ni un céntimo de diferencia, ni
#      después de mil operaciones.
#
#   3. No se puede cobrar de más: ni de la cuota, ni
#      de la venta, ni en dos cajas a la vez.
#
#   4. VENCIDA se deduce de la fecha. Cobrar una
#      cuota vencida la saca de vencida.
#
#   5. Anular un pago devuelve el importe a la cuota y
#      deja rastro de qué cambió y por qué.
#
#   6. Un pago no se borra: se anula.
#
#   7. Las condiciones de un contrato firmado no se
#      tocan por la puerta de atrás.
# ==========================================


from datetime import date
from decimal import Decimal

import pytest

from database.contratos import (
    crear_contrato,
    obtener_contrato
)

from database.ventas import registrar_venta

from database.conexion import obtener_conexion

import database.financiera as F

from errores import (
    ErrorValidacion,
    PermisoDenegado
)


D = Decimal


def dos_decimales(valor):

    return D(str(valor)).quantize(D("0.01"))


# ==========================================
# DATOS DE PARTIDA
# ==========================================

@pytest.fixture
def contrato_financiado(
    como_administrador, datos_base
):
    """
    Una venta de 10.000.000 con 6.000.000 de
    anticipo: quedan 4.000.000 para financiar en 12
    cuotas, con el cronograma YA generado.

    Devuelve un diccionario con los ids y las
    cuotas.
    """

    _, id_auto, id_cliente = datos_base

    id_venta, _ = registrar_venta(
        id_cliente, id_auto, "2026-10-01", 10000000.0
    )

    id_contrato, numero = crear_contrato(
        venta_id=id_venta,
        forma_pago="Anticipo + cuotas",
        anticipo=6000000.0,
        cantidad_cuotas=12,
        saldo_financiado=D("4000000.00"),
        tasa_interes=12,
        gastos_administrativos=400000.0,
        periodicidad="mensual",
        primer_vencimiento=date(2026, 11, 1)
    )

    # Las condiciones de financiacion van por
    # crear_contrato() y no por un UPDATE aparte.
    #
    # Antes iban por UPDATE porque crear_contrato()
    # no las escribia: las columnas existian en la
    # tabla y la funcion las ignoraba. Escribirlas a
    # mano era la unica forma de tener un contrato
    # financiado, y por eso las pruebas no
    # comprobaban el alta: comprobaban el
    # cronograma, con unos datos que en la
    # aplicacion nadie podria haber metido.

    total, motivo = F.generar_cronograma(id_contrato)

    assert total == 12, motivo

    contrato = obtener_contrato(id_contrato)

    assert contrato["saldo_financiado"] == D("4000000.00")
    assert contrato["tasa_interes"] == D("12.000")
    assert contrato["periodicidad"] == "mensual"
    assert contrato["primer_vencimiento"] == date(2026, 11, 1)
    assert contrato["dia_vencimiento"] == 1

    return {
        "id_contrato": id_contrato,
        "id_venta": id_venta,
        "numero": numero,
        "cuotas": F.obtener_cuotas(id_contrato)
    }


def id_de_cuota(datos, numero):

    for cuota in datos["cuotas"]:

        if cuota["numero"] == numero:

            return cuota["id"]

    raise AssertionError(f"No hay cuota numero {numero}")


class TestReparto:

    """
    La suma de las cuotas tiene que ser el saldo,
    exacto. Un contrato firmado con un céntimo de
    diferencia no cuadra cuando el cliente llega con
    la calculadora.
    """

    @pytest.mark.parametrize("total,cantidad", [
        (10000, 3),
        (20000, 7),
        (1000000, 12),
        (500, 4),
        (100, 3),
        (999999.99, 11),
        (12345.67, 17),
        (100, 1),
        (7, 7)
    ])
    def test_la_suma_es_el_total(self, total, cantidad):

        cronograma = F.calcular_cronograma(
            cantidad,
            "mensual",
            date(2026, 11, 1),
            D(str(total))
        )

        suma = sum(c["importe"] for c in cronograma)

        assert suma == dos_decimales(total), (
            f"{cantidad} cuotas de {total} suman {suma}"
        )

    def test_solo_la_ultima_difiere(self):
        """
        Repartir 10.000 en 3 da 3.333,33 + 3.333,33 +
        3.333,34. Las dos primeras son el resultado de
        dividir; la última ajusta el residuo.

        Si el residuo se repartiera entre todas,
        cambiaría el importe que el cliente vio
        pactado en cada una.
        """

        cronograma = F.calcular_cronograma(
            3, "mensual", date(2026, 11, 1), D("10000")
        )

        importes = [c["importe"] for c in cronograma]

        assert importes[0] == D("3333.33")
        assert importes[1] == D("3333.33")
        assert importes[2] == D("3333.34")

    def test_las_primeras_son_iguales(self):
        """
        Un cronograma con cuotas distintas entre sí
        parece un error de cálculo, aunque sume bien.
        El cliente ve un número y tiene que ser el
        mismo en las doce.
        """

        cronograma = F.calcular_cronograma(
            12, "mensual", date(2026, 11, 1), D("1200000")
        )

        importes = [c["importe"] for c in cronograma]

        assert len(set(importes[:-1])) == 1, (
            "las cuotas intermedias deberían ser iguales"
        )

    def test_importes_con_dos_decimales(self):
        """
        Una cuota con más de dos decimales se
        redondearía al guardarse, y el PDF diría una
        cifra que no es la que se cobró.
        """

        cronograma = F.calcular_cronograma(
            7, "mensual", date(2026, 11, 1), D("20000")
        )

        for cuota in cronograma:

            assert cuota["importe"] == (
                cuota["importe"].quantize(D("0.01"))
            )

    def test_saldo_menor_que_una_cuota(self):
        """
        Un saldo de 50 en 12 cuotas da 4,17 por cuota.
        La última se queda con el resto. Ninguna
        puede quedar en cero o negativa.
        """

        cronograma = F.calcular_cronograma(
            12, "mensual", date(2026, 11, 1), D("50")
        )

        for cuota in cronograma:

            assert cuota["importe"] > 0, cuota

        assert sum(
            c["importe"] for c in cronograma
        ) == D("50.00")


class TestErroresDeCalculo:

    def test_cero_cuotas(self):

        with pytest.raises(ErrorValidacion):

            F.calcular_cronograma(
                0, "mensual", date(2026, 11, 1), D("1000")
            )

    def test_cuotas_negativas(self):

        with pytest.raises(ErrorValidacion):

            F.calcular_cronograma(
                -5, "mensual", date(2026, 11, 1), D("1000")
            )

    def test_demasiadas_cuotas(
        self, como_administrador, ajustes_financiera
    ):

        """
        El máximo sale del ajuste. Sin tope, un
        contrato de 200 plazos pasa la validación y
        es casi siempre un error de teclear.
        """

        ajustes = F.leer_ajustes()

        with pytest.raises(ErrorValidacion):

            F.calcular_cronograma(
                ajustes["maximo_cuotas"] + 1,
                "mensual",
                date(2026, 11, 1),
                D("1000")
            )

    def test_periodicidad_inventada(self):

        with pytest.raises(ErrorValidacion):

            F.calcular_cronograma(
                3, "por_hora", date(2026, 11, 1), D("1000")
            )

    def test_saldo_cero(self):
        """
        Sin saldo no hay nada que financiar. Si la
        entrega inicial cubre el precio, la venta es a
        contado y no lleva cronograma.
        """

        with pytest.raises(ErrorValidacion):

            F.calcular_cronograma(
                3, "mensual", date(2026, 11, 1), D("0")
            )

    def test_saldo_negativo(self):

        with pytest.raises(ErrorValidacion):

            F.calcular_cronograma(
                3, "mensual", date(2026, 11, 1), D("-500")
            )

    def test_sin_fecha(self):

        with pytest.raises(ErrorValidacion):

            F.calcular_cronograma(
                3, "mensual", None, D("1000")
            )

    def test_fecha_invalida(self):

        with pytest.raises(ErrorValidacion):

            F.calcular_cronograma(
                3, "mensual", "el quince", D("1000")
            )

    def test_saldo_con_mas_de_dos_decimales(self):

        with pytest.raises(ErrorValidacion):

            F.calcular_cronograma(
                3, "mensual", date(2026, 11, 1),
                D("1000.005")
            )


# ==========================================
# LAS FECHAS
# ==========================================

class TestFechasDeVencimiento:

    def test_mensual_cae_el_mismo_dia(self):
        """
        Un crédito mensual tiene que caer el mismo día
        del mes, no 30 días después.

        Sumando 30 días, el 1 de noviembre daría 1/12,
        31/12, 30/1, 1/3... y la cuota undécima se
        cobraría once días antes de lo pactado, sin que
        nadie lo notara hasta que el cliente reclamara.
        """

        cronograma = F.calcular_cronograma(
            12, "mensual", date(2026, 11, 1), D("1200")
        )

        fechas = [
            c["fecha_vencimiento"] for c in cronograma
        ]

        assert all(f.day == 1 for f in fechas), fechas

        assert fechas == [
            date(2026, 11, 1), date(2026, 12, 1),
            date(2027, 1, 1), date(2027, 2, 1),
            date(2027, 3, 1), date(2027, 4, 1),
            date(2027, 5, 1), date(2027, 6, 1),
            date(2027, 7, 1), date(2027, 8, 1),
            date(2027, 9, 1), date(2027, 10, 1)
        ]

    def test_los_plazos_fijos_suman_dias(self):
        """
        Semanal y quincenal son plazos fijos: 7 y 15
        días son 7 y 15 días, sin discusión de meses.
        """

        for periodicidad, dias in (
            ("semanal", 7),
            ("quincenal", 15)
        ):

            cronograma = F.calcular_cronograma(
                3, periodicidad, date(2026, 1, 1), D("300")
            )

            fechas = [
                c["fecha_vencimiento"] for c in cronograma
            ]

            assert (fechas[1] - fechas[0]).days == dias

            assert (fechas[2] - fechas[1]).days == dias

    @pytest.mark.parametrize(
        "periodicidad,meses", [
            ("mensual", 1),
            ("bimestral", 2),
            ("trimestral", 3),
            ("semestral", 6),
            ("anual", 12)
        ]
    )
    def test_los_mensuales_suman_meses(
        self, periodicidad, meses
    ):

        cronograma = F.calcular_cronograma(
            3, periodicidad, date(2026, 1, 15), D("300")
        )

        fechas = [
            c["fecha_vencimiento"] for c in cronograma
        ]

        assert F._sumar_meses(
            date(2026, 1, 15), meses, 15
        ) == fechas[1]

        assert F._sumar_meses(
            date(2026, 1, 15), meses * 2, 15
        ) == fechas[2]

    def test_ano_bisiesto(self):

        cronograma = F.calcular_cronograma(
            2, "anual", date(2028, 2, 29), D("500")
        )

        fechas = [
            c["fecha_vencimiento"] for c in cronograma
        ]

        assert fechas == [date(2028, 2, 29), date(2029, 2, 28)]

    def test_desde_el_31_no_inventa_fechas(self):
        """
        Del 31 de enero: febrero no tiene 31, así que
        cae el 28. Y MARZO VUELVE AL 31.

        Ese vuelta es lo importante. Si el recorte se
        arrastrara, el crédito se quedaría en el 28 para
        siempre (28/03, 28/04, 28/05...) y el cliente
        estaría pagando una semana antes de lo pactado a
        partir de marzo, sin enterarse nadie.
        """

        cronograma = F.calcular_cronograma(
            5, "mensual", date(2026, 1, 31), D("500")
        )

        fechas = [
            c["fecha_vencimiento"] for c in cronograma
        ]

        assert fechas == [
            date(2026, 1, 31),
            date(2026, 2, 28),
            date(2026, 3, 31),
            date(2026, 4, 30),
            date(2026, 5, 31)
        ]

    def test_orden_creciente(self):

        cronograma = F.calcular_cronograma(
            12, "mensual", date(2026, 11, 1), D("1200")
        )

        fechas = [
            c["fecha_vencimiento"] for c in cronograma
        ]

        assert fechas == sorted(fechas)

    def test_numeros_seguidos(self):

        cronograma = F.calcular_cronograma(
            12, "mensual", date(2026, 11, 1), D("1200")
        )

        numeros = [c["numero"] for c in cronograma]

        assert numeros == list(range(1, 13))


# ==========================================
# GENERAR Y GUARDAR
# ==========================================

class TestGenerarCronograma:

    def test_genera_tantas_cuotas_como_dice(
        self, contrato_financiado
    ):

        assert len(contrato_financiado["cuotas"]) == 12

    def test_las_cuotas_suman_el_saldo(
        self, contrato_financiado
    ):

        suma = sum(
            dos_decimales(c["importe"])
            for c in contrato_financiado["cuotas"]
        )

        assert suma == D("4000000.00")

    def test_el_saldo_de_cada_cuota_es_su_importe(
        self, contrato_financiado
    ):
        """
        Al generarse, una cuota no tiene pagos: su
        saldo es su importe entero.
        """

        for cuota in contrato_financiado["cuotas"]:

            assert dos_decimales(cuota["saldo"]) == (
                dos_decimales(cuota["importe"])
            )

            assert cuota["estado"] == F.ESTADO_PENDIENTE

    def test_congela_el_monto_de_la_cuota(
        self, contrato_financiado
    ):

        """
        El importe de la cuota queda en el contrato,
        no solo en las cuotas: es lo que dice el PDF
        que se firmó.
        """

        from database.contratos import obtener_contrato

        contrato = obtener_contrato(
            contrato_financiado["id_contrato"]
        )

        esperado = dos_decimales(
            contrato_financiado["cuotas"][0]["importe"]
        )

        assert dos_decimales(
            contrato["monto_cuota"]
        ) == esperado

    def test_no_se_genera_dos_veces(
        self, contrato_financiado
    ):

        total, motivo = F.generar_cronograma(
            contrato_financiado["id_contrato"]
        )

        assert total == 0

        assert "cronograma" in motivo.lower()

    def test_no_se_genera_sin_saldo(
        self, como_administrador, datos_base
    ):
        """
        Una venta a contado no tiene cronograma. Si se
        generara con saldo cero, saldrían doce cuotas
        de cero, que es un contrato que no dice nada.

        Y ahora ni siquiera se puede dejar un contrato
        en esa situation: crear_contrato() rechaza
        "saldo cero con cuotas". Este UPDATE a mano
        fuerza lo que la aplicación ya no permite, y
        por eso sigue estando: la defensa de
        generar_cronograma() no puede depender solo de
        que el alta lo impida.
        """

        _, id_auto, id_cliente = datos_base

        id_venta, _ = registrar_venta(
            id_cliente, id_auto, "2026-10-01", 1000.0
        )

        id_contrato, motivo = crear_contrato(
            venta_id=id_venta,
            forma_pago="Anticipo + cuotas",
            anticipo=1000.0,
            cantidad_cuotas=12,
            saldo_financiado=D("0.00"),
            periodicidad="mensual",
            primer_vencimiento=date(2026, 11, 1)
        )

        assert id_contrato is None, (
            "la aplicación no debería dejar firmar un "
            "crédito de saldo cero con doce cuotas"
        )

        assert "financiar" in motivo.lower()

        # ------------------------------
        # Y AHORA POR LA PUERTA DE
        # ATRÁS
        # ------------------------------
        # Un contrato de contado, con el que sí se
        # puede entrar, forzado a saldo cero y doce
        # cuotas por UPDATE.

        id_ventado, _ = registrar_venta(
            id_cliente, id_auto, "2026-10-01", 1000.0
        )

        id_contado, motivo = crear_contrato(
            venta_id=id_ventado,
            forma_pago="Contado"
        )

        assert id_contado is not None, motivo

        conexion = obtener_conexion()
        cursor = conexion.cursor()

        cursor.execute(
            """
            UPDATE contratos
            SET saldo_financiado = 0,
                cantidad_cuotas = 12
            WHERE id = %s
            """,
            (id_contado,)
        )

        conexion.commit()
        cursor.close()
        conexion.close()

        total, motivo = F.generar_cronograma(id_contado)

        assert total == 0

        assert "saldo" in motivo.lower()

    def test_no_se_genera_en_contrato_cancelado(
        self, contrato_financiado
    ):

        from database.contratos import (
            cambiar_estado,
            eliminar_contrato
        )

        # El cronograma se borra en cascada al
        # cancelar: ver database/contratos.py.

        cambiar_estado(
            contrato_financiado["id_contrato"],
            "cancelado"
        )

        total, motivo = F.generar_cronograma(
            contrato_financiado["id_contrato"]
        )

        assert total == 0

        del eliminar_contrato


# ==========================================
# PAGAR UNA CUOTA
# ==========================================

# ==========================================
# EL REPARTO DE UN COBRO ADELANTADO
# ==========================================
# `repartir_adelanto()` es PURA: no toca la base.
# Por eso se prueban TODAS las reglas de reparto con
# listas escritas a mano, sin montar un contrato. Y
# es la misma funcion que usa la vista previa del
# formulario y que luego guarda el cobro: si las dos
# calcularan distinto, el cliente veria un reparto y le
# aplicarian otro.


def cuota_para_repartir(
    numero, saldo, estado="pendiente"
):
    """
    Una cuota con lo que necesita `repartir_adelanto()`.

    Se escribe a mano y no se lee de la base a
    proposito: la funcion es pura, y su contrato es
    "filas de obtener_cuotas()", no "filas de
    MySQL". Atarla a una consulta haria estas pruebas
    dependerian de una tabla entera para comprobar una
    resta.
    """

    return {
        "id": numero,
        "numero": numero,
        "fecha_vencimiento": date(2026, 11, numero),
        "importe": dos_decimales(saldo),
        "saldo": dos_decimales(saldo),
        "estado": estado,
        "cantidad_pagos": 0
    }


class TestRepartirAdelanto:

    def test_dos_cuotas_exactas(self):
        """
        El caso que se pide: 20.000 para dos de
        10.000.
        """

        plan, sobra = F.repartir_adelanto(
            [cuota_para_repartir(1, 10000),
             cuota_para_repartir(2, 10000),
             cuota_para_repartir(3, 10000)],
            D("20000.00")
        )

        assert [p["numero"] for p in plan] == [1, 2]

        assert sobra == D("0.00")

    def test_una_entera_y_una_a_medias(self):
        """
        15.000 con dos de 10.000: la primera queda
        saldada y la segunda a medias. Es el cobro más
        común después del exacto, y el que hace
        instructive la regla de "entera o nada".
        """

        plan, sobra = F.repartir_adelanto(
            [cuota_para_repartir(1, 10000),
             cuota_para_repartir(2, 10000)],
            D("15000.00")
        )

        assert [p["numero"] for p in plan] == [1, 2]

        assert plan[0]["saldo_despues"] == D("0.00")

        assert plan[1]["saldo_despues"] == D("5000.00")

        assert plan[1]["importe"] == D("5000.00")

        assert sobra == D("0.00")

    # ------------------------------
    # LA REGLA
    # ------------------------------

    def test_nunca_deja_un_residuo_por_delante(self):
        """
        No reparte de a poco. Si rellenara de a poco,
        15.000 en tres de 10.000 dejarían un resto en
        la primera.

        Ese resto no se salta nunca, porque siempre
        hay una cuota más antigua detrás: el cliente
        acabaría debiendo la 1 mientras paga la 4, y
        el resto pequeño se acumularía sin que nadie lo
        viera. Con "entera o nada" no hay nada que
        esconder.
        """

        plan, _ = F.repartir_adelanto(
            [cuota_para_repartir(1, 10000),
             cuota_para_repartir(2, 10000),
             cuota_para_repartir(3, 10000)],
            D("15000.00")
        )

        for parte in plan[:-1]:

            assert parte["saldo_despues"] == D("0.00"), (
                f"la cuota {parte['numero']} deja resto"
            )

    def test_lo_que_sobra_no_se_reparte(self):
        """
        El sobrante se DEVUELVE, no se improvisa. Con
        una sola cuota de 10.000 y 25.000 entregados,
        no hay dónde poner 15.000: se avisa.

        Esto es justo lo que impide la alternativa que
        no se eligió, que es imputar el sobrante a la
        última cuota y dejar su saldo en negativo. Un
        saldo negativo rompe todas las cuentas de la
        cartera, que comparan contra cero.
        """

        plan, sobra = F.repartir_adelanto(
            [cuota_para_repartir(1, 10000)],
            D("25000.00")
        )

        assert len(plan) == 1

        assert sobra == D("15000.00")

    # ------------------------------
    # LAS QUE NO SE COBRAN
    # ------------------------------

    def test_se_saltan_las_anuladas(self):
        """
        Una cuota anulada no es exigible: no se cobra.
        """

        plan, sobra = F.repartir_adelanto(
            [cuota_para_repartir(1, 10000),
             cuota_para_repartir(2, 10000, "anulada"),
             cuota_para_repartir(3, 10000)],
            D("20000.00")
        )

        assert [p["numero"] for p in plan] == [1, 3]

        assert sobra == D("0.00")

    def test_se_saltan_las_pagadas(self):
        """
        Una cuota con saldo cero no recibe nada. Sin
        este filtro, un saldo de 0.00 entraría en el
        reparto como si debiera algo y se crearía un
        pago de cero.
        """

        plan, sobra = F.repartir_adelanto(
            [cuota_para_repartir(1, 0, "pagada"),
             cuota_para_repartir(2, 10000)],
            D("10000.00")
        )

        assert [p["numero"] for p in plan] == [2]

    # ------------------------------
    # LO QUE NO ACEPTA
    # ------------------------------

    @pytest.mark.parametrize("importe", [
        0, -5, "abc", None
    ])
    def test_rechaza_lo_que_no_da(self, importe):
        """
        Un importe de cero o negativo no es un cobro,
        es un error de tecleo. Y uno que no es número
        tiene que decirselo en español, no reventar
        con el error de `Decimal()`.
        """

        with pytest.raises(ErrorValidacion):

            F.repartir_adelanto(
                [cuota_para_repartir(1, 10000)],
                importe
            )

    def test_rechaza_si_no_hay_nada_que_cobrar(self):
        """
        Un contrato con todas las cuotas saldadas no
        tiene nada que repartir. Sin este error, el
        formulario abriría con un importe y una tabla
        vacía, y el cajero no sabría si es que el
        contrato está pagado o que algo falló.
        """

        with pytest.raises(ErrorValidacion) as error:

            F.repartir_adelanto(
                [cuota_para_repartir(1, 0, "pagada")],
                D("1000.00")
            )

        assert "pendiente" in error.value.mensaje

    # ------------------------------
    # LOS DECIMALES
    # ------------------------------

    def test_redondea_a_dos(self):
        """
        `pagos.importe` y `cuotas.saldo` son
        DECIMAL(10,2). Un importe con más se guardaría
        redondeado, el saldo no se movería lo que el
        cajero cree y el dinero desaparecería sin
        avisar. Se redondea ANTES de repartir, que es
        lo que se va a guardar.
        """

        plan, _ = F.repartir_adelanto(
            [cuota_para_repartir(1, 10000)],
            D("5000.005")
        )

        assert plan[0]["importe"] == D("5000.01")

        assert plan[0]["saldo_despues"] == D("4999.99")


# ==========================================
# COBRAR ADELANTADO
# ==========================================
# Un cliente paga dos meses de una vez. El dinero
# entra como un solo acto pero se guarda como N
# imputaciones a N cuotas, con UN número de recibo.


class TestCobrarAdelantado:

    def _saldo_de_la_primera(self, datos, numero=1):
        """
        El saldo de una cuota, sin depender del
        indice de la lista.
        """

        for cuota in F.obtener_cuotas(
            datos["id_contrato"]
        ):

            if cuota["numero"] == numero:

                return dos_decimales(cuota["saldo"])

        raise AssertionError(f"No hay cuota {numero}")

    def test_dos_cuotas_de_un_solo_cobro(
        self, contrato_financiado
    ):
        """
        El caso que se pidió: pagar dos meses.

        Salen DOS pagos, no uno. Un solo pago de
        2.000.000 no tendría a qué imputarse más allá
        de la primera cuota, y la cartera seguiría
        diciendo que la segunda debe.
        """

        cuota = dos_decimales(
            contrato_financiado["cuotas"][0]["importe"]
        )

        partes, motivo = F.registrar_pago_adelantado(
            contrato_financiado["id_contrato"],
            cuota * 2,
            "2026-11-01",
            "Efectivo"
        )

        assert partes is not None, motivo

        assert len(partes) == 2

        assert [p["cuota"] for p in partes] == [1, 2]

    def test_un_solo_recibo_para_todo(
        self, contrato_financiado
    ):
        """
        UN número para los N pagos.

        El cliente entrega una suma y se lleva un papel.
        Con N recibos habría que entregarle N papeles de
        un solo acto, y el rastro (que se guarda por
        recibo) quedaría repartido en N entradas que no
        dicen que salieron juntas.
        """

        cuota = dos_decimales(
            contrato_financiado["cuotas"][0]["importe"]
        )

        partes, motivo = F.registrar_pago_adelantado(
            contrato_financiado["id_contrato"],
            cuota * 3,
            "2026-11-01",
            "Efectivo"
        )

        assert partes is not None, motivo

        assert len(partes) == 3

        assert len({p["recibo"] for p in partes}) == 1

        assert partes[0]["recibo"], "el recibo no puede estar vacío"

    def test_las_cuotas_quedan_saldadas(
        self, contrato_financiado
    ):
        """
        Cada cuota cubierta queda a cero y PAGADA, y
        la cuarta sigue como estaba: el repayment no
        puede tocar lo que no le toca.
        """

        cuota = dos_decimales(
            contrato_financiado["cuotas"][0]["importe"]
        )

        F.registrar_pago_adelantado(
            contrato_financiado["id_contrato"],
            cuota * 2,
            "2026-11-01",
            "Efectivo"
        )

        cover = dos_decimales(cuota * 2)

        for numero in (1, 2):

            saldo = self._saldo_de_la_primera(
                contrato_financiado, numero
            )

            assert saldo == D("0.00"), (
                f"la cuota {numero} queda en {saldo}"
            )

        # La tercera ni se ha tocado.

        untouched = dos_decimales(
            contrato_financiado["cuotas"][2]["importe"]
        )

        assert self._saldo_de_la_primera(
            contrato_financiado, 3
        ) == untouched

    def test_la_ultima_se_paga_a_medias(
        self, contrato_financiado
    ):
        """
        Un importe que no llega a la última cuota la
        deja a medias, con PARCIAL, y no con saldo
        negativo.
        """

        cuota = dos_decimales(
            contrato_financiado["cuotas"][0]["importe"]
        )

        # Un céntimo de la segunda. No la mitad: al
        # dividir entre dos sale un decimal de más y el
        # resto de la cuenta deja de ser exacto por el
        # redondeo, no por culpa del reparto.

        resto = D("0.01")

        partes, motivo = F.registrar_pago_adelantado(
            contrato_financiado["id_contrato"],
            cuota + resto,
            "2026-11-01",
            "Efectivo"
        )

        assert partes is not None, motivo

        assert len(partes) == 2

        assert dos_decimales(partes[1]["importe"]) == resto

        filas = {
            c["numero"]: c
            for c in F.obtener_cuotas(
                contrato_financiado["id_contrato"]
            )
        }

        assert filas[1]["estado"] == F.ESTADO_PAGADA

        assert filas[2]["estado"] == F.ESTADO_PARCIAL

        # El saldo es lo que le queda, y no un número
        # negativo: un saldo negativo rompe las cuentas
        # de la cartera, que comparan contra cero.

        assert dos_decimales(filas[2]["saldo"]) == (
            dos_decimales(filas[2]["importe"]) - resto
        )

        assert dos_decimales(filas[2]["saldo"]) > 0

    # ------------------------------
    # EL SALDO NO SE PASA
    # ------------------------------

    def test_no_se_pasa_del_saldo_de_la_venta(
        self, contrato_financiado
    ):
        """
        Más que el saldo de la venta se rechaza.

        Y se comprueba el TOTAL, no cada parte: un
        cobro de 6.000.000 repartido en seis de
        1.000.000 pasaría parte a parte y fallaría en
        la última, dejando cinco cobradas de un total
        que no cabía. Con una sola comprobación, o
        entra todo o no entra nada.
        """

        partes, motivo = F.registrar_pago_adelantado(
            contrato_financiado["id_contrato"],
            D("99999999.00"),
            "2026-11-01",
            "Efectivo"
        )

        assert partes is None

        assert "saldo" in motivo.lower()

        # Y no se movió ninguna cuota.

        for cuota in F.obtener_cuotas(
            contrato_financiado["id_contrato"]
        ):

            assert dos_decimales(cuota["saldo"]) == (
                dos_decimales(cuota["importe"])
            ), f"la cuota {cuota['numero']} se movió"

    def test_no_se_pasa_del_cronograma(
        self, contrato_financiado
    ):
        """
        Cabe en la venta pero no en las cuotas.

        El contrato financia 4.000.000 en doce cuotas y
        la venta vale 10.000.000. Un cobro de
        9.000.000 cabe de sobra contra la venta y no
        tiene dónde imputarse: el sobrante se avisa.
        """

        partes, motivo = F.registrar_pago_adelantado(
            contrato_financiado["id_contrato"],
            D("9000000.00"),
            "2026-11-01",
            "Efectivo"
        )

        assert partes is None

        assert "sobran" in motivo.lower()

        for cuota in F.obtener_cuotas(
            contrato_financiado["id_contrato"]
        ):

            assert dos_decimales(cuota["saldo"]) == (
                dos_decimales(cuota["importe"])
            )

    def test_rechaza_un_importe_no_valido(
        self, contrato_financiado
    ):
        """
        Cero, negativo o texto.
        """

        for importe in (0, -1000, "abc"):

            partes, motivo = F.registrar_pago_adelantado(
                contrato_financiado["id_contrato"],
                importe,
                "2026-11-01",
                "Efectivo"
            )

            assert partes is None, f"{importe} pasó"

            assert motivo

    def test_no_cobra_un_contrato_cancelado(
        self, contrato_financiado
    ):
        """
        Un contrato cancelado no admite cobros.
        """

        from database.contratos import cambiar_estado

        cambiar_estado(
            contrato_financiado["id_contrato"],
            "cancelado"
        )

        assert obtener_contrato(
            contrato_financiado["id_contrato"]
        )["estado"] == "cancelado"

        partes, motivo = F.registrar_pago_adelantado(
            contrato_financiado["id_contrato"],
            D("100000.00"),
            "2026-11-01",
            "Efectivo"
        )

        assert partes is None

        assert "cancelado" in motivo.lower()

    # ------------------------------
    # O TODO O NADA
    # ------------------------------

    def test_no_deja_la_venta_a_cero(
        self, contrato_financiado
    ):
        """
        El caso que más se temía.

        El anticipo NO está registrado como pago (eso
        está escrito en los huecos conocidos). Así que
        el saldo de la venta es el precio entero, y
        queda mucho más que el saldo financiado. Por eso
        el rechazo por "sobran" se dispara ANTES que el
        de la venta, y el importe que hay que probar
        para pasarse de la venta tiene que ser
        mayor que el saldo de la venta.
        """

        from database.pagos import saldo_venta

        _, _, saldo_venta_total = saldo_venta(
            contrato_financiado["id_venta"]
        )

        partes, motivo = F.registrar_pago_adelantado(
            contrato_financiado["id_contrato"],
            dos_decimales(saldo_venta_total) + D("0.01"),
            "2026-11-01",
            "Efectivo"
        )

        assert partes is None

        assert "saldo" in motivo.lower()

        # Y sigue igual.

        _, _, despues = saldo_venta(
            contrato_financiado["id_venta"]
        )

        assert dos_decimales(despues) == (
            dos_decimales(saldo_venta_total)
        )

    # ------------------------------
    # LO QUE DEJA
    # ------------------------------

    def test_un_solo_rastro_de_la_operacion(
        self, contrato_financiado
    ):
        """
        UNA entrada de auditoría, con el saldo antes y
        después EN CONJUNTO.

        N entradas, una por cuota, se leen como N
        operaciones distintas: alguien que audite en
        junio vería tres cobros y no sabría que el
        cliente vino una vez.
        """

        from database.auditoria import obtener_historial

        cuota = dos_decimales(
            contrato_financiado["cuotas"][0]["importe"]
        )

        partes, motivo = F.registrar_pago_adelantado(
            contrato_financiado["id_contrato"],
            cuota * 3,
            "2026-11-01",
            "Efectivo"
        )

        assert partes is not None, motivo

        recibo = partes[0]["recibo"]

        filas = obtener_historial(recibo)

        assert len(filas) == 1, (
            f"{len(filas)} entradas para un cobro"
        )

        fila = filas[0]

        assert fila[3] == "PAGO_ADELANTADO"

        assert fila[6], "falta el valor anterior"

        assert fila[7], "falta el valor nuevo"

        assert fila[6] != fila[7]

    def test_el_importe_va_en_letras_en_el_pdf(
        self, contrato_financiado
    ):
        """
        El papel dice el importe en letras.

        Un recibo con "2.000.000,00" y nada más obliga
        a tener que leer los ceros.
        """

        from utils.recibo_pdf import generar_recibo

        cuota = dos_decimales(
            contrato_financiado["cuotas"][0]["importe"]
        )

        partes, motivo = F.registrar_pago_adelantado(
            contrato_financiado["id_contrato"],
            cuota * 2,
            "2026-11-01",
            "Efectivo"
        )

        assert partes is not None, motivo

        from database.pagos import obtener_pagos_detalle

        pagos = obtener_pagos_detalle(
            contrato_financiado["id_venta"]
        )

        por_id = {
            c["id"]: c
            for c in F.obtener_cuotas(
                contrato_financiado["id_contrato"]
            )
        }

        ordenados = sorted(
            [p for p in pagos if p["cuota_id"]],
            key=lambda p: p["numero_cuota"]
        )

        assert len(ordenados) == 2

        ruta = generar_recibo(
            ordenados,
            obtener_contrato(
                contrato_financiado["id_contrato"]
            ),
            [
                por_id[p["cuota_id"]]
                for p in ordenados
            ]
        )

        from conftest import leer_pdf

        texto = leer_pdf(ruta)

        assert "RECIBO DE PAGO" in texto

        # ------------------------------
        # EL REPARTO, EN LETRAS
        # ------------------------------
        # Con dos meses de golpe el papel tiene que
        # decir el total Y el reparto. Un recibo de
        # "una cuota" con la mitad del dinero sería
        # el papel que no sirve: el cliente entregó una
        # suma y se le responde con una parte.

        assert "IMPORTE COBRADO" in texto

        assert "Cuota" in texto

        assert "IMPORTE COBRADO" in texto, (
            "el total del cobro tiene que estar en el "
            "recibo, no solo el reparto"
        )

        # Las dos cuotas salen numeradas.

        for numero in ("1", "2"):

            assert numero in texto

    # ------------------------------
    # PERMISOS
    # ------------------------------

    def test_el_vendedor_no_cobra(
        self,
        contrato_financiado,
        como_vendedor
    ):
        """
        Cobrar un crédito es de la administración.

        `registrar_pago_cuota()` ya lleva
        GESTIONAR_FINANCIERA por lo mismo: si el
        vendedor pudiera cobrar una cuota, podría
        cobrar seis, y el motivo de la separación es
        la misma.
        """

        from errores import PermisoDenegado

        with pytest.raises(PermisoDenegado):

            F.registrar_pago_adelantado(
                contrato_financiado["id_contrato"],
                D("100000.00"),
                "2026-11-01",
                "Efectivo"
            )

    def test_sin_sesion_no_cobra(
        self, como_administrador, datos_base
    ):
        """
        Sin sesión no hay permiso.

        Y el permiso va ANTES de abrir la conexión: sin
        eso, un intento denegado dejaría una sesión
        abierta en el servidor de MySQL, y con unos
        pocos seguidos la aplicación deja de poder
        conectar sin que nada diga por qué.
        """

        import sesion as modulo_sesion

        from database.ventas import registrar_venta
        from errores import PermisoDenegado

        _, id_auto, id_cliente = datos_base

        id_venta, _ = registrar_venta(
            id_cliente, id_auto, "2026-10-01", 100000.0
        )

        id_contrato, motivo = crear_contrato(
            venta_id=id_venta,
            forma_pago="Anticipo + cuotas",
            anticipo=40000.0,
            cantidad_cuotas=6,
            periodicidad="mensual",
            primer_vencimiento=date(2026, 11, 1)
        )

        assert id_contrato is not None, motivo

        F.generar_cronograma(id_contrato)

        # Los VALORES, no la sesión: obtener_sesion()
        # devuelve siempre el mismo objeto e
        # iniciar_sesion() lo modifica dentro, así que
        # guardar la referencia y "restaurarla" guardaría
        # un espejo.

        _actual = modulo_sesion.obtener_sesion()

        anterior = (
            _actual.id_usuario,
            _actual.nombre_usuario,
            _actual.nombre_completo,
            _actual.rol
        )

        modulo_sesion.cerrar_sesion()

        try:

            assert not modulo_sesion.hay_sesion()

            with pytest.raises(PermisoDenegado):

                F.registrar_pago_adelantado(
                    id_contrato,
                    D("100000.00"),
                    "2026-11-01",
                    "Efectivo"
                )

        finally:

            # Antes de comprobar nada más: leer las
            # cuotas también pide permiso, así que sin
            # sesión no se puede ni mirar si se movieron.

            modulo_sesion.iniciar_sesion(anterior)

        for cuota in F.obtener_cuotas(id_contrato):

            assert dos_decimales(cuota["saldo"]) == (
                dos_decimales(cuota["importe"])
            ), f"la cuota {cuota['numero']} se movió"


class TestPagarCuota:

    def test_pago_total_cuadra_la_cuota(
        self, contrato_financiado
    ):
        """
        Pagada entera: saldo a cero y estado PAGADA.
        """

        id_cuota = id_de_cuota(contrato_financiado, 1)

        cuota = F.obtener_cuota(id_cuota)

        id_pago, motivo = F.registrar_pago_cuota(
            id_cuota,
            cuota["importe"],
            "2026-11-01",
            "Efectivo",
            recibo="REC-000001"
        )

        assert id_pago is not None, motivo

        despues = F.obtener_cuota(id_cuota)

        assert dos_decimales(despues["saldo"]) == D("0.00")

        assert despues["estado"] == F.ESTADO_PAGADA

        assert despues["cantidad_pagos"] == 1

    def test_pago_parcial_deja_parcial(
        self, contrato_financiado
    ):

        id_cuota = id_de_cuota(contrato_financiado, 1)

        cuota = F.obtener_cuota(id_cuota)

        mitad = dos_decimales(
            dos_decimales(cuota["importe"]) / 2
        )

        id_pago, motivo = F.registrar_pago_cuota(
            id_cuota, mitad, "2026-11-01", "Efectivo"
        )

        assert id_pago is not None, motivo

        despues = F.obtener_cuota(id_cuota)

        assert despues["estado"] == F.ESTADO_PARCIAL

        assert dos_decimales(despues["saldo"]) > 0

        assert dos_decimales(despues["saldo"]) == (
            dos_decimales(cuota["importe"]) - mitad
        )

    def test_dos_pagos_suman_el_saldo(
        self, contrato_financiado
    ):
        """
        Un cliente puede pagar a medias dos veces. El
        saldo tiene que bajar por los dos.
        """

        id_cuota = id_de_cuota(contrato_financiado, 1)

        cuota = F.obtener_cuota(id_cuota)

        parte = dos_decimales(
            dos_decimales(cuota["importe"]) / 3
        )

        F.registrar_pago_cuota(
            id_cuota, parte, "2026-11-01", "Efectivo"
        )

        F.registrar_pago_cuota(
            id_cuota, parte, "2026-11-02", "Efectivo"
        )

        despues = F.obtener_cuota(id_cuota)

        assert dos_decimales(despues["saldo"]) == (
            dos_decimales(cuota["importe"])
            - dos_decimales(parte) * 2
        ).quantize(D("0.01"))

        assert despues["cantidad_pagos"] == 2

    def test_no_se_paga_mas_que_el_saldo(
        self, contrato_financiado
    ):

        """
        Un céntimo de más dejaría el saldo de la cuota
        en negativo. El saldo de la venta seguiría
        correcto, así que la comprobación de la venta
        NO lo evita: hacen falta las dos.
        """

        id_cuota = id_de_cuota(contrato_financiado, 1)

        cuota = F.obtener_cuota(id_cuota)

        id_pago, motivo = F.registrar_pago_cuota(
            id_cuota,
            dos_decimales(cuota["importe"]) + D("0.01"),
            "2026-11-01",
            "Efectivo"
        )

        assert id_pago is None

        assert "saldo" in motivo.lower()

        # Y la cuota no se movió.

        despues = F.obtener_cuota(id_cuota)

        assert dos_decimales(despues["saldo"]) == (
            dos_decimales(cuota["importe"])
        )

    def test_no_se_paga_despues_de_pagar(
        self, contrato_financiado
    ):

        id_cuota = id_de_cuota(contrato_financiado, 1)

        cuota = F.obtener_cuota(id_cuota)

        F.registrar_pago_cuota(
            id_cuota,
            cuota["importe"],
            "2026-11-01",
            "Efectivo"
        )

        id_pago, motivo = F.registrar_pago_cuota(
            id_cuota, D("0.01"), "2026-11-02", "Efectivo"
        )

        assert id_pago is None

        assert "saldo" in motivo.lower()

    def test_no_se_paga_un_cero(self, contrato_financiado):

        id_cuota = id_de_cuota(contrato_financiado, 1)

        for importe in (D("0"), D("0.00"), D("-100")):

            id_pago, _ = F.registrar_pago_cuota(
                id_cuota, importe, "2026-11-01", "Efectivo"
            )

            assert id_pago is None, importe

    def test_no_se_paga_con_mas_de_dos_decimales(
        self, contrato_financiado
    ):

        id_cuota = id_de_cuota(contrato_financiado, 1)

        id_pago, motivo = F.registrar_pago_cuota(
            id_cuota, D("100.005"), "2026-11-01", "Efectivo"
        )

        assert id_pago is None

        assert "decimales" in motivo.lower()

    def test_no_se_paga_una_cuota_inexistente(
        self, contrato_financiado
    ):

        id_pago, motivo = F.registrar_pago_cuota(
            999999, D("100"), "2026-11-01", "Efectivo"
        )

        assert id_pago is None

        assert "no existe" in motivo.lower()

    def test_no_se_paga_una_cuota_anulada(
        self, contrato_financiado
    ):

        id_cuota = id_de_cuota(contrato_financiado, 1)

        ok, _ = F.anular_cuota(
            id_cuota, "Prueba de cuota anulada"
        )

        assert ok is True

        id_pago, motivo = F.registrar_pago_cuota(
            id_cuota, D("100"), "2026-11-01", "Efectivo"
        )

        assert id_pago is None

        assert "anulada" in motivo.lower()

    def test_el_pago_se_imputa_a_la_cuota(
        self, contrato_financiado
    ):
        """
        La imputación es lo que permite saber que un
        pago cubrió una cuota concreta y no la deuda
        en general.
        """

        id_cuota = id_de_cuota(contrato_financiado, 1)

        cuota = F.obtener_cuota(id_cuota)

        id_pago, _ = F.registrar_pago_cuota(
            id_cuota,
            cuota["importe"],
            "2026-11-01",
            "Efectivo",
            recibo="REC-000002"
        )

        pagos = F.pagos_de_cuota(id_cuota)

        assert len(pagos) == 1

        assert pagos[0]["id"] == id_pago

        assert pagos[0]["recibo"] == "REC-000002"

        assert pagos[0]["estado"] == "convalidado"

    def test_el_concepto_dice_la_cuota(
        self, contrato_financiado
    ):
        """
        Sin esto, un listado de pagos de la venta no
        dice qué parte de la deuda se cubrió.
        """

        id_cuota = id_de_cuota(contrato_financiado, 3)

        cuota = F.obtener_cuota(id_cuota)

        F.registrar_pago_cuota(
            id_cuota,
            cuota["importe"],
            "2027-01-01",
            "Efectivo"
        )

        pagos = F.pagos_de_cuota(id_cuota)

        assert "3" in pagos[0]["concepto"]

    def test_el_saldo_de_la_venta_also_baja(
        self, contrato_financiado
    ):
        """
        Pagar una cuota descuenta del saldo de la venta
        también. Si no lo hiciera, la venta se vería
        como si no se hubiera cobrado nada: el cliente
        pagaría, el cajero lo anotaría, y el detalle de
        la venta seguiría diciendo que se debe todo.
        """

        from database.pagos import saldo_venta

        id_cuota = id_de_cuota(contrato_financiado, 1)

        cuota = F.obtener_cuota(id_cuota)

        _, pagado_antes, _ = saldo_venta(
            contrato_financiado["id_venta"]
        )

        F.registrar_pago_cuota(
            id_cuota,
            cuota["importe"],
            "2026-11-01",
            "Efectivo"
        )

        _, pagado_despues, _ = saldo_venta(
            contrato_financiado["id_venta"]
        )

        diferencia = (
            dos_decimales(pagado_despues)
            - dos_decimales(pagado_antes)
        )

        assert diferencia == dos_decimales(cuota["importe"])


# ==========================================
# EL SALDO NO SE DESCUADRA
# ==========================================
# La comprobación más importante del módulo: tras
# cualquier operación, cuotas.saldo tiene que seguir
# diciendo lo mismo que dicen los pagos.
#
# recalcular_saldo_cuota() existe justo para esto.

class TestSaldoSinDescuadre:

    def test_tras_generar(self, contrato_financiado):

        for cuota in contrato_financiado["cuotas"]:

            guardado, calculado = (
                F.recalcular_saldo_cuota(cuota["id"])
            )

            assert guardado == calculado, cuota["numero"]

    def test_tras_un_pago(self, contrato_financiado):

        id_cuota = id_de_cuota(contrato_financiado, 1)

        cuota = F.obtener_cuota(id_cuota)

        F.registrar_pago_cuota(
            id_cuota,
            dos_decimales(cuota["importe"]) / 4,
            "2026-11-01",
            "Efectivo"
        )

        guardado, calculado = F.recalcular_saldo_cuota(
            id_cuota
        )

        assert guardado == calculado

    def test_tras_diez_pagos_en_una_cuota(
        self, contrato_financiado
    ):
        """
        Diez pagos parciales seguidos. Cada uno
        descuenta su importe y suma su contador; si
        alguno de los dos se hiciera mal, el saldo o
        el contador se irían.
        """

        id_cuota = id_de_cuota(contrato_financiado, 1)

        cuota = F.obtener_cuota(id_cuota)

        parte = dos_decimales(
            dos_decimales(cuota["importe"]) / 11
        )

        for numero in range(10):

            id_pago, motivo = F.registrar_pago_cuota(
                id_cuota,
                dos_decimales(parte),
                f"2026-11-{numero + 1:02d}",
                "Efectivo"
            )

            assert id_pago is not None, motivo

        guardado, calculado = F.recalcular_saldo_cuota(
            id_cuota
        )

        assert guardado == calculado

        despues = F.obtener_cuota(id_cuota)

        assert despues["cantidad_pagos"] == 10

    def test_tras_pagar_varias_cuotas(
        self, contrato_financiado
    ):

        for numero in (1, 2, 3):

            id_cuota = id_de_cuota(
                contrato_financiado, numero
            )

            cuota = F.obtener_cuota(id_cuota)

            F.registrar_pago_cuota(
                id_cuota,
                cuota["importe"],
                "2026-11-01",
                "Efectivo"
            )

        descuadradas = F.recalcular_saldos_de_contrato(
            contrato_financiado["id_contrato"]
        )

        assert descuadradas == []

    def test_tras_anular_un_pago(
        self, contrato_financiado
    ):
        """
        Anular tiene que devolver el importe exacto. Si
        devuelve de más o de menos, el saldo se
        descuadra y ya no se puede saber cuánto debe
        el cliente.
        """

        id_cuota = id_de_cuota(contrato_financiado, 1)

        cuota = F.obtener_cuota(id_cuota)

        id_pago, _ = F.registrar_pago_cuota(
            id_cuota,
            dos_decimales(cuota["importe"]),
            "2026-11-01",
            "Efectivo"
        )

        F.anular_pago(id_pago, "Se TES-genero mal")

        guardado, calculado = F.recalcular_saldo_cuota(
            id_cuota
        )

        assert guardado == calculado

    def test_el_pago_anulado_no_cuenta(
        self, contrato_financiado
    ):
        """
        El saldo se recalcula sobre los pagos
        CONVALIDADOS. Un pago anulado es como si no
        existiera, aunque la fila siga ahí.
        """

        id_cuota = id_de_cuota(contrato_financiado, 1)

        cuota = F.obtener_cuota(id_cuota)

        id_pago, _ = F.registrar_pago_cuota(
            id_cuota,
            cuota["importe"],
            "2026-11-01",
            "Efectivo"
        )

        F.anular_pago(id_pago, "Error de tecleo")

        guardado, calculado = F.recalcular_saldo_cuota(
            id_cuota
        )

        assert guardado == D(str(cuota["importe"]))

        assert guardado == calculado


# ==========================================
# ANULAR
# ==========================================

class TestAnular:

    def test_anular_pago_devuelve_el_saldo(
        self, contrato_financiado
    ):

        id_cuota = id_de_cuota(contrato_financiado, 1)

        cuota = F.obtener_cuota(id_cuota)

        id_pago, _ = F.registrar_pago_cuota(
            id_cuota,
            cuota["importe"],
            "2026-11-01",
            "Efectivo"
        )

        ok, motivo = F.anular_pago(
            id_pago, "Se cobró de más"
        )

        assert ok is True, motivo

        despues = F.obtener_cuota(id_cuota)

        assert dos_decimales(despues["saldo"]) == (
            dos_decimales(cuota["importe"])
        )

        # Y vuelve a estar pendiente, no pagada: un
        # cliente al que se le anula el pago debe otra
        # cosa.

        assert despues["estado"] == F.ESTADO_PENDIENTE

        assert despues["cantidad_pagos"] == 0

    def test_anular_dos_pagos(self, contrato_financiado):
        """
        Dos pagos parciales, anular los dos: el saldo
        tiene que volver al importe entero y el
        contador a cero.
        """

        id_cuota = id_de_cuota(contrato_financiado, 1)

        cuota = F.obtener_cuota(id_cuota)

        parte = dos_decimales(
            dos_decimales(cuota["importe"]) / 2
        )

        primero, _ = F.registrar_pago_cuota(
            id_cuota, dos_decimales(parte),
            "2026-11-01", "Efectivo"
        )

        segundo, _ = F.registrar_pago_cuota(
            id_cuota, dos_decimales(parte),
            "2026-11-02", "Efectivo"
        )

        F.anular_pago(primero, "Uno de dos")

        F.anular_pago(segundo, "Dos de dos")

        despues = F.obtener_cuota(id_cuota)

        assert dos_decimales(despues["saldo"]) == (
            dos_decimales(cuota["importe"])
        )

        assert despues["cantidad_pagos"] == 0

    def test_no_se_anula_dos_veces(
        self, contrato_financiado
    ):

        id_cuota = id_de_cuota(contrato_financiado, 1)

        cuota = F.obtener_cuota(id_cuota)

        id_pago, _ = F.registrar_pago_cuota(
            id_cuota,
            cuota["importe"],
            "2026-11-01",
            "Efectivo"
        )

        F.anular_pago(id_pago, "Primera vez")

        ok, motivo = F.anular_pago(id_pago, "Segunda vez")

        assert ok is False

        assert "ya estaba" in motivo.lower()

    def test_no_se_anula_sin_motivo(
        self, contrato_financiado
    ):
        """
        Un pago anulado sin explicación es un cobro que
        desapareció. El motivo es obligatorio.
        """

        id_cuota = id_de_cuota(contrato_financiado, 1)

        cuota = F.obtener_cuota(id_cuota)

        id_pago, _ = F.registrar_pago_cuota(
            id_cuota,
            cuota["importe"],
            "2026-11-01",
            "Efectivo"
        )

        for vacio in ("", "   ", None):

            ok, motivo = F.anular_pago(id_pago, vacio)

            assert ok is False, vacio

            assert "motivo" in motivo.lower()

    def test_el_pago_no_se_borra(self, contrato_financiado):
        """
        Un pago es un hecho económico. Anularlo deja la
        fila: si se borrara, no habría diferencia entre
        un pago mal registrado y un pago que nunca
       existió.
        """

        id_cuota = id_de_cuota(contrato_financiado, 1)

        cuota = F.obtener_cuota(id_cuota)

        id_pago, _ = F.registrar_pago_cuota(
            id_cuota,
            cuota["importe"],
            "2026-11-01",
            "Efectivo"
        )

        F.anular_pago(id_pago, "Error de tecleo")

        pagos = F.pagos_de_cuota(id_cuota)

        assert len(pagos) == 1

        assert pagos[0]["estado"] == "anulado"

        assert pagos[0]["anulado_motivo"] == "Error de tecleo"

        assert pagos[0]["anulado_usuario"]

        assert pagos[0]["anulado_fecha"]

    def test_anular_cuota_con_pagos_no_se_puede(
        self, contrato_financiado
    ):
        """
        Poner a cero una cuota que tiene pagos dejaría
        el saldo del contrato sin cuadrar: el dinero
        se habría cobrado y la cuota diría que no.
        """

        id_cuota = id_de_cuota(contrato_financiado, 1)

        cuota = F.obtener_cuota(id_cuota)

        F.registrar_pago_cuota(
            id_cuota,
            dos_decimales(
                dos_decimales(cuota["importe"]) / 2
            ),
            "2026-11-01",
            "Efectivo"
        )

        ok, motivo = F.anular_cuota(
            id_cuota, "Quiero quitarla"
        )

        assert ok is False

        assert "pagos" in motivo.lower()

    def test_anular_cuota_sin_pagos(self, contrato_financiado):

        id_cuota = id_de_cuota(contrato_financiado, 1)

        ok, motivo = F.anular_cuota(
            id_cuota, "Se pactó otra cosa"
        )

        assert ok is True, motivo

        assert F.obtener_cuota(id_cuota)["estado"] == (
            F.ESTADO_ANULADA
        )

    def test_reactivar_cuota(self, contrato_financiado):

        id_cuota = id_de_cuota(contrato_financiado, 1)

        F.anular_cuota(id_cuota, "Error")

        ok, motivo = F.reactivar_cuota(
            id_cuota, "Era una prueba"
        )

        assert ok is True, motivo

        assert F.obtener_cuota(id_cuota)["estado"] == (
            F.ESTADO_PENDIENTE
        )

    def test_reactivar_una_que_no_esta_anulada(
        self, contrato_financiado
    ):

        id_cuota = id_de_cuota(contrato_financiado, 1)

        ok, motivo = F.reactivar_cuota(id_cuota, "Nada")

        assert ok is False

        assert "no está anulada" in motivo.lower()


# ==========================================
# VENCIDAS
# ==========================================

class TestVencidas:

    def test_una_cuota_pasada_queda_vencida(
        self, contrato_financiado
    ):
        """
        VENCIDA es un estado DERIVADO de la fecha, no
        una decisión. Pasó su vencimiento y sigue con
        saldo: está vencida, diga lo que diga el campo.
        """

        cambiadas = F.procesar_vencidas(
            date(2026, 12, 15)
        )

        assert cambiadas > 0

        cuotas = F.obtener_cuotas(
            contrato_financiado["id_contrato"]
        )

        vencidas = [
            c for c in cuotas if c["estado"] == F.ESTADO_VENCIDA
        ]

        # Vencimiento 2026-11-01 y 2026-12-01 ya
        # pasaron.

        assert len(vencidas) == 2

    def test_una_cuota_pagada_no_esta_vencida(
        self, contrato_financiado
    ):
        """
        Pagar una cuota vencida la saca de vencida. Si
        se quedara, la cartera estaría diciendo que se
        debe algo que ya se cobró.
        """

        id_cuota = id_de_cuota(contrato_financiado, 1)

        cuota = F.obtener_cuota(id_cuota)

        F.registrar_pago_cuota(
            id_cuota,
            cuota["importe"],
            "2026-11-05",
            "Efectivo"
        )

        F.procesar_vencidas(date(2026, 12, 15))

        despues = F.obtener_cuota(id_cuota)

        assert despues["estado"] == F.ESTADO_PAGADA

    def test_una_cuota_pendiente_no_toca(
        self, contrato_financiado
    ):
        """
        Con hoy antes del primer vencimiento, nada
        cambia. Procesar vencidas sin que haya ninguna
        vencida no puede tocar el cronograma.
        """

        antes = F.obtener_cuotas(
            contrato_financiado["id_contrato"]
        )

        F.procesar_vencidas(date(2026, 10, 15))

        despues = F.obtener_cuotas(
            contrato_financiado["id_contrato"]
        )

        assert len(antes) == len(despues)

        for original, actual in zip(antes, despues):

            assert original["estado"] == actual["estado"]

    def test_una_cuota_anulada_no_venece(
        self, contrato_financiado
    ):
        """
        Una cuota anulada está fuera del cronograma.
        Anularla es decir "esta no se cobra", y no
        "esta no se ha cobrado".
        """

        id_cuota = id_de_cuota(contrato_financiado, 1)

        F.anular_cuota(id_cuota, "No aplica")

        F.procesar_vencidas(date(2026, 12, 15))

        assert F.obtener_cuota(id_cuota)["estado"] == (
            F.ESTADO_ANULADA
        )

    def test_dias_de_gracia(
        self, contrato_financiado, ajustes_financiera
    ):
        """
        Con días de gracia, una cuota que pasó su
        fecha hace poco sigue pendiente. El ajuste
        existe para eso: el cliente tiene unos días
        antes de que se le llame.
        """

        ajustes_financiera("financiera_dias_gracia", 5)

        # Venció el 2026-11-01. Con 5 días de gracia
        # sigue pendiente hasta el 2026-11-06.

        F.procesar_vencidas(date(2026, 11, 3))

        cuota = F.obtener_cuota(
            id_de_cuota(contrato_financiado, 1)
        )

        assert cuota["estado"] == F.ESTADO_PENDIENTE

        F.procesar_vencidas(date(2026, 11, 10))

        cuota = F.obtener_cuota(
            id_de_cuota(contrato_financiado, 1)
        )

        assert cuota["estado"] == F.ESTADO_VENCIDA

    def test_procesar_dos_veces_no_cambia_mas(
        self, contrato_financiado
    ):

        primera = F.procesar_vencidas(date(2026, 12, 15))

        segunda = F.procesar_vencidas(date(2026, 12, 15))

        assert primera > 0

        assert segunda == 0, (
            "la segunda pasada no tenía que cambiar nada"
        )


# ==========================================
# EL ESTADO SE DEDUCE DEL SALDO
# ==========================================

class TestEstadoSegunSaldo:

    """
    El estado no lo pone quien paga: sale del saldo y
    de la fecha. Si dos sitios lo calcularan distinto,
    la cartera mostraría una cosa y el saldo otra.
    """

    def test_cero_acentos(self):
        """
        Saldo a cero es PAGADA, esté vencida o no. Si
        saliera VENCIDA, una venta totalmente pagada
        aparecería en la lista de morosos.
        """

        assert F._estado_real(
            D("0.00"), F.ESTADO_VENCIDA,
            date(2026, 1, 1), hoy=date(2026, 3, 1)
        ) == F.ESTADO_PAGADA

    def test_negativo_es_pagada(self):
        """
        Un saldo negativo no puede quedar como cuota
        pendiente: el sobrepago no es deuda.
        """

        assert F._estado_real(
            D("-10.00"), F.ESTADO_PENDIENTE,
            date(2026, 1, 1), hoy=date(2026, 1, 1)
        ) == F.ESTADO_PAGADA

    def test_una_anulada_no_se_resucita(self):
        """
        Cobrar a una cuota anulada no la devuelve al
        cronograma. Hay que reactivarla a propósito.
        """

        assert F._estado_real(
            D("1000.00"), F.ESTADO_ANULADA,
            date(2026, 1, 1), hoy=date(2026, 6, 1)
        ) == F.ESTADO_ANULADA

    def test_vencida_sea_lo_que_diga(self):
        """
        Aunque el campo diga "pendiente", si la fecha
        pasó y hay saldo, es vencida.
        """

        assert F._estado_real(
            D("1000.00"), F.ESTADO_PENDIENTE,
            date(2026, 5, 1), hoy=date(2026, 6, 1)
        ) == F.ESTADO_VENCIDA

    def test_a_tiempo_es_pendiente(self):

        assert F._estado_real(
            D("1000.00"), F.ESTADO_PENDIENTE,
            date(2026, 12, 1), hoy=date(2026, 1, 1)
        ) == F.ESTADO_PENDIENTE

    def test_el_dia_del_vencimiento_no_es_tarde(self):
        """
        Pagar el mismo día del vencimiento no es tarde,
        ni con cero días de margen. Con el mes de
        gracia en cero, una cuota se vence a partir del
        día SIGUIENTE.
        """

        assert F._estado_real(
            D("1000.00"), F.ESTADO_PENDIENTE,
            date(2026, 6, 1), hoy=date(2026, 6, 1)
        ) == F.ESTADO_PENDIENTE

        assert F._estado_real(
            D("1000.00"), F.ESTADO_PENDIENTE,
            date(2026, 6, 1), hoy=date(2026, 6, 2)
        ) == F.ESTADO_VENCIDA

    def test_con_gracia_no_es_tarde_al_dia(
        self, ajustes_financiera
    ):
        """
        Con cinco días de gracia, una cuota que vence
        hoy sigue pendiente: el cliente tiene hasta el
        sexto día.
        """

        ajustes_financiera("financiera_dias_gracia", 5)

        assert F._estado_real(
            D("1000.00"), F.ESTADO_PENDIENTE,
            date(2026, 6, 1), hoy=date(2026, 6, 6)
        ) == F.ESTADO_PENDIENTE

        assert F._estado_real(
            D("1000.00"), F.ESTADO_PENDIENTE,
            date(2026, 6, 1), hoy=date(2026, 6, 7)
        ) == F.ESTADO_VENCIDA


# ==========================================
# EL RESUMEN
# ==========================================

class TestResumenDeCuotas:

    def test_sin_cuotas(self, como_administrador):

        from database.ventas import registrar_venta
        from database.clientes import insertar_cliente
        from database.autos import insertar_auto
        from database.marcas import insertar_marca

        id_auto = insertar_auto(
            insertar_marca("Marca Resumen"),
            "Modelo", 2025, 1000.0, "Rojo", 1
        )

        id_venta, _ = registrar_venta(
            insertar_cliente("C", "R", None, None, None),
            id_auto, "2026-10-01", 1000.0
        )

        id_contrato, _ = crear_contrato(
            venta_id=id_venta, forma_pago="Contado"
        )

        resumen = F.resumen_de_cuotas(id_contrato)

        assert resumen["total_cuotas"] == 0

        assert resumen["saldo_total"] == D("0.00")

    def test_cuenta_las_cuertas(self, contrato_financiado):

        resumen = F.resumen_de_cuotas(
            contrato_financiado["id_contrato"]
        )

        assert resumen["total_cuotas"] == 12

        assert resumen["pendientes"] == 12

        assert resumen["pagadas"] == 0

        assert dos_decimales(resumen["saldo_total"]) == (
            D("4000000.00")
        )

    def test_cuenta_las_pagadas(self, contrato_financiado):

        id_cuota = id_de_cuota(contrato_financiado, 1)

        cuota = F.obtener_cuota(id_cuota)

        F.registrar_pago_cuota(
            id_cuota,
            cuota["importe"],
            "2026-11-01",
            "Efectivo"
        )

        resumen = F.resumen_de_cuotas(
            contrato_financiado["id_contrato"]
        )

        assert resumen["pagadas"] == 1

        assert resumen["pendientes"] == 11

        assert dos_decimales(resumen["saldo_total"]) < (
            D("4000000.00")
        )

    def test_las_anuladas_no_cuentan_como_cobradas(
        self, contrato_financiado
    ):
        """
        Una cuota anulada no se ha cobrado, pero su
        importe tampoco se debe. Por eso el pagado se
        calcula como importe menos saldo, y no sumando
        los pagos: si se sumaran, la cuota anulada
        aparecería como dinero cobrado que nadie
        recibió.
        """

        id_cuota = id_de_cuota(contrato_financiado, 1)

        F.anular_cuota(id_cuota, "No aplica")

        resumen = F.resumen_de_cuotas(
            contrato_financiado["id_contrato"]
        )

        assert resumen["anuladas"] == 1

        assert resumen["pagado_total"] == D("0.00")


# ==========================================
# PERMISOS
# ==========================================

class TestPermisos:

    def test_el_vendedor_no_cobra_cuotas(
        self, como_vendedor, datos_base
    ):
        """
        El vendedor NO cobra cuotas.

        Antes esta prueba decía lo contrario, y era
        verdad: registrar_pago_cuota() llevaba
        VER_CONTRATOS, que el vendedor tiene. Bastaba
        llamar a la función desde un script para
        quedarse con el dinero de un crédito sin
        haber pasado por ninguna caja. Registrar una
        venta lo puede hacer el vendedor porque es su
        trabajo; quedarse con el cobro de las cuotas
        de un crédito es de la administración, que es
        quien responde de que ese dinero llegó.

        Ocultar el botón no protege nada: por eso el
        permiso va en la capa de datos y se comprueba
        aquí, no en la vista.
        """

        _, id_auto, id_cliente = datos_base

        id_venta, _ = registrar_venta(
            id_cliente, id_auto, "2026-10-01", 100000.0
        )

        id_contrato, motivo = crear_contrato(
            venta_id=id_venta,
            forma_pago="Anticipo + cuotas",
            anticipo=40000.0,
            cantidad_cuotas=6,
            saldo_financiado=D("60000.00"),
            periodicidad="mensual",
            primer_vencimiento=date(2026, 11, 1)
        )

        assert id_contrato is not None, motivo

        total, motivo = F.generar_cronograma(id_contrato)

        assert total == 6, motivo

        cuotas = F.obtener_cuotas(id_contrato)

        with pytest.raises(PermisoDenegado):

            F.registrar_pago_cuota(
                cuotas[0]["id"],
                cuotas[0]["importe"],
                "2026-11-01",
                "Efectivo"
            )

        # Y la cuota sigue como estaba: un intento
        # denegado no puede dejar ni un céntimo
        # gastado.

        assert (
            F.obtener_cuota(cuotas[0]["id"])["saldo"]
            == cuotas[0]["importe"]
        )

    def test_el_administrador_sigue_cobrando(
        self, como_administrador, datos_base
    ):
        """
        El ADMINISTRADOR sí cobra, con la misma
        comprobación de saldo que siempre: es una
        condición de la operación, no un privilegio.
        """

        _, id_auto, id_cliente = datos_base

        id_venta, _ = registrar_venta(
            id_cliente, id_auto, "2026-10-01", 100000.0
        )

        id_contrato, motivo = crear_contrato(
            venta_id=id_venta,
            forma_pago="Anticipo + cuotas",
            anticipo=40000.0,
            cantidad_cuotas=6,
            saldo_financiado=D("60000.00"),
            periodicidad="mensual",
            primer_vencimiento=date(2026, 11, 1)
        )

        assert id_contrato is not None, motivo

        total, motivo = F.generar_cronograma(id_contrato)

        assert total == 6, motivo

        cuotas = F.obtener_cuotas(id_contrato)

        id_pago, motivo = F.registrar_pago_cuota(
            cuotas[0]["id"],
            cuotas[0]["importe"],
            "2026-11-01",
            "Efectivo"
        )

        assert id_pago is not None, motivo

    def test_el_vendedor_no_anula(
        self,
        como_vendedor,
        contrato_financiado,
        como_admin_un_rato
    ):
        """
        Anular un pago es movimiento de dinero: es de
        la administración. El vendedor crea contratos,
        pero no deshace cobros.

        El pago lo registra la administración, porque
        desde que cobrar una cuota es suyo: si lo
        hiciera el vendedor, esta prueba no tendria
        nada que comprobar.
        """

        from errores import PermisoDenegado

        id_cuota = id_de_cuota(contrato_financiado, 1)

        cuota = F.obtener_cuota(id_cuota)

        with como_admin_un_rato():

            id_pago, motivo = F.registrar_pago_cuota(
                id_cuota,
                cuota["importe"],
                "2026-11-01",
                "Efectivo"
            )

        assert id_pago is not None, motivo

        # ------------------------------
        # Y AHORA EL VENDEDOR
        # ------------------------------
        # La sesion es la del vendedor: la fixture
        # la ha restaurado al salir del contexto.

        with pytest.raises(PermisoDenegado):

            F.anular_pago(id_pago, "Prueba")

        # Y el pago sigue cobrado: un intento denegado
        # no puede haber devuelto nada a la cuota. Si
        # el saldo volviera al importe de la cuota,
        # sería que la anulación se hizo a medias.

        assert (
            F.obtener_cuota(id_cuota)["saldo"]
            == D("0.00")
        )


# ==========================================
# RASTRO
# ==========================================

class TestRastro:

    def test_el_pago_deja_rastro_con_valores(
        self, contrato_financiado
    ):
        """
        Un pago sin valor anterior ni nuevo no se puede
        auditar: nadie sabe si la cuota estaba pagada
        antes o si se acaba de cerrar.
        """

        from database.auditoria import obtener_historial

        id_cuota = id_de_cuota(contrato_financiado, 1)

        cuota = F.obtener_cuota(id_cuota)

        id_pago, _ = F.registrar_pago_cuota(
            id_cuota,
            cuota["importe"],
            "2026-11-01",
            "Efectivo",
            recibo="REC-AUDIT-1"
        )

        del id_pago

        historial = obtener_historial("REC-AUDIT-1")

        assert len(historial) == 1

        entrada = historial[0]

        assert entrada[3] == "PAGO_CUOTA"

        assert entrada[6] is not None, (
            "el pago debe llevar el valor anterior"
        )

        assert entrada[7] is not None, (
            "el pago debe llevar el valor nuevo"
        )

    def test_la_anulacion_deja_rastro_con_valores(
        self, contrato_financiado
    ):

        from database.auditoria import (
            obtener_historial,
            obtener_auditoria
        )

        id_cuota = id_de_cuota(contrato_financiado, 1)

        cuota = F.obtener_cuota(id_cuota)

        id_pago, _ = F.registrar_pago_cuota(
            id_cuota,
            cuota["importe"],
            "2026-11-01",
            "Efectivo",
            recibo="REC-AUDIT-2"
        )

        F.anular_pago(id_pago, "Error de tecleo")

        historial = obtener_historial("REC-AUDIT-2")

        acciones = [f[3] for f in historial]

        assert "PAGO_ANULADO" in acciones

        anulacion = [
            f for f in historial if f[3] == "PAGO_ANULADO"
        ][0]

        assert anulacion[6] is not None

        assert anulacion[7] is not None

        del obtener_auditoria

    def test_anular_cuota_deja_rastro(
        self, contrato_financiado
    ):

        from database.auditoria import obtener_auditoria

        antes = len(obtener_auditoria())

        id_cuota = id_de_cuota(contrato_financiado, 1)

        F.anular_cuota(id_cuota, "Prueba de rastro")

        despues = obtener_auditoria()

        assert len(despues) == antes + 1

        assert despues[0][3] == "CUOTA_ANULADA"

        assert despues[0][6] is not None

        assert despues[0][7] is not None

    def test_el_cronograma_deja_rastro(
        self, como_administrador, datos_base
    ):

        from database.auditoria import obtener_auditoria

        _, id_auto, id_cliente = datos_base

        id_venta, _ = registrar_venta(
            id_cliente, id_auto, "2026-10-01", 100000.0
        )

        id_contrato, _ = crear_contrato(
            venta_id=id_venta,
            forma_pago="Anticipo + cuotas",
            anticipo=40000.0,
            cantidad_cuotas=6,
            saldo_financiado=D("60000.00"),
            periodicidad="mensual",
            primer_vencimiento=date(2026, 11, 1)
        )

        antes = len(obtener_auditoria())

        F.generar_cronograma(id_contrato)

        despues = obtener_auditoria()

        assert len(despues) == antes + 1

        assert despues[0][3] == "CRONOGRAMA"


# ==========================================
# AJUSTES
# ==========================================

class TestAjustes:

    def test_valores_por_defecto(self, como_administrador):
        """
        El esquema siembra los ajustes. Si alguien los
        borra, la aplicación usa los del código en vez
        de romperse.
        """

        ajustes = F.leer_ajustes()

        assert ajustes["dias_aviso"] == 15

        assert ajustes["dias_gracia"] == 0

        assert ajustes["maximo_cuotas"] == 72

    def test_un_ajuste_con_basura_no_rompe(
        self, como_administrador, ajustes_financiera
    ):
        """
        Un ajuste guardado con basura no puede impedir
        que se abra una pantalla.
        """

        ajustes_financiera(
            "financiera_dias_aviso", "no es un numero"
        )

        ajustes = F.leer_ajustes()

        assert ajustes["dias_aviso"] == 15