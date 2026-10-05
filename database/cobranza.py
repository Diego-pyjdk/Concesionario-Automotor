# ==========================================
# COBRANZA: CUENTAS POR COBRAR
# ==========================================
# Lo que se debe y por quién, para poder ir a
# cobrarlo. No calcula intereses moratorios ni fija
# plazos legales de cobranza: eso depende de la
# normativa vigente y de lo que establezca cada
# contrato, y hay que revisarlo con un asesor.
#
# Lo que sí hace:
#
#   1. Decir cuánto se debe en total y por
#      contrato.
#
#   2. Separar lo vencido de lo que aún no vence, y
#      decir cuántos días lleva cada cosa retrasada.
#
#   3. Ordenar por urgencia, para que la lista de
#      trabajo sea "a quién llamar primero", no
#      "todos los deudores por orden alfabético".
#
#   4. Envejecer la cartera: cuánto tiempo lleva
#      parada cada deuda. Un cliente con tres meses
#      de atraso es un problema distinto de uno con
#      quince días.
#
#
# ----------------------------------------------------
# POR QUÉ NO HAY UNA TABLA DE "COBRANZAS"
# ----------------------------------------------------
# Una deuda no es una fila: es un contrato con saldo
# y cuotas sin pagar. Si se guardara en una tabla
# propia, habría que mantenerla sincronizada con el
# contrato y con cada pago, y bastaría un cobro mal
# registrado para que la cartera dijera una cosa y la
# base otra.
#
# Lo que hay son CONSULTAS. La verdad sigue estando
# en cuotas.saldo, que es lo que mantiene
# registrar_pago_cuota(). Aquí solo se pregunta.


from datetime import date
from datetime import timedelta
from decimal import Decimal

from database.conexion import obtener_conexion

from database.financiera import leer_ajustes

from permisos import (
    requiere_permiso,
    VER_FINANCIERA
)

# SÍ llevan permiso, y no por formalidad.
#
# La cartera es la lista de quién debe, de cuánto y
# con qué teléfono para llamar. Un vendedor que la
# pudiera leer sabría a cuánto debe cada cliente del
# concesionario, no solo los suyos.
#
# Decir que "es una lectura y las lecturas no llevan
# permiso" confundía leer datos con leer lo ajeno. Un
# reporte de ventas es lo primero; la deuda de cada
# cliente con su número de teléfono es lo segundo.
#
# Y lleva el MISMO permiso que la sección que la
# pinta: si la vista no se construye sin él, tampoco
# se pueden pedir los datos por debajo.


CERO = Decimal("0.00")


# ==========================================
# LA CONSULTA BASE
# ==========================================
# Una sola definición, usada por todas las
# funciones. Cada una añade sus filtros encima en
# vez de reescribir el FROM entero, porque seis
# copias de un JOIN de siete tablas divergen: en
# cuanto una necesita una columna más, las otras
# cinco se quedan desactualizadas sin que nada lo
# avise.

CONSULTA_CARTERA = """
    SELECT
        contratos.id AS contrato_id,
        contratos.numero,
        contratos.venta_id,
        contratos.estado AS contrato_estado,
        contratos.fecha,
        contratos.precio_venta,
        contratos.anticipo,
        contratos.saldo_financiado,
        contratos.monto_cuota,
        contratos.cantidad_cuotas,
        contratos.periodicidad,
        clientes.id AS cliente_id,
        clientes.nombre AS cliente_nombre,
        clientes.apellido AS cliente_apellido,
        clientes.telefono AS cliente_telefono,
        clientes.email AS cliente_email,
        clientes.documento AS cliente_documento,
        marcas.nombre AS marca,
        autos.modelo AS modelo,
        autos.anio,
        COALESCE(
            usuarios.nombre_usuario,
            '(cuenta eliminada)'
        ) AS vendedor,
        COALESCE(
            (
                SELECT COALESCE(SUM(pagos.importe), 0)
                FROM pagos
                WHERE pagos.venta_id = contratos.venta_id
                  AND pagos.estado = 'convalidado'
            ),
            0
        ) AS pagado,
        COALESCE(
            (
                SELECT COUNT(*)
                FROM cuotas
                WHERE cuotas.contrato_id = contratos.id
            ),
            0
        ) AS total_cuotas,
        COALESCE(
            (
                SELECT COUNT(*)
                FROM cuotas
                WHERE cuotas.contrato_id = contratos.id
                  AND cuotas.estado = 'pagada'
            ),
            0
        ) AS cuotas_pagadas,
        COALESCE(
            (
                SELECT COUNT(*)
                FROM cuotas
                WHERE cuotas.contrato_id = contratos.id
                  AND (
                    cuotas.estado = 'vencida'
                    OR (
                        cuotas.estado <> 'anulada'
                        AND cuotas.saldo > 0
                        AND cuotas.fecha_vencimiento < %s
                    )
                  )
            ),
            0
        ) AS cuotas_vencidas,
        COALESCE(
            (
                SELECT SUM(cuotas.saldo)
                FROM cuotas
                WHERE cuotas.contrato_id = contratos.id
                  AND (
                    cuotas.estado = 'vencida'
                    OR (
                        cuotas.estado <> 'anulada'
                        AND cuotas.saldo > 0
                        AND cuotas.fecha_vencimiento < %s
                    )
                  )
            ),
            0
        ) AS importe_vencido,
        COALESCE(
            (
                SELECT MIN(cuotas.fecha_vencimiento)
                FROM cuotas
                WHERE cuotas.contrato_id = contratos.id
                  AND cuotas.estado <> 'anulada'
                  AND cuotas.saldo > 0
            ),
            NULL
        ) AS proximo_vencimiento
    FROM contratos
    INNER JOIN clientes
        ON contratos.cliente_id = clientes.id
    INNER JOIN autos
        ON contratos.auto_id = autos.id
    INNER JOIN marcas
        ON autos.marca_id = marcas.id
    LEFT JOIN usuarios
        ON contratos.usuario_id = usuarios.id
"""

# La fecha de corte va en la consulta dos veces: una
# para contar vencidas y otra para sumarlas.
#
# Se pasa como parámetro al ejecutar, una vez, y
# MySQL la usa dos veces. No se escribe la fecha en
# el texto de la consulta: una fecha con comillas
# dentro de una cadena es unainyeccion esperando que
# alguien la toque, y aquí no hay por qué arriesgarse
# (el valor viene de date.today() o de un parámetro,
# nunca de un campo del usuario).


def _preparar(fila, hoy):
    """
    Convierte una fila cruda en lo que la vista
    pinta: importes como Decimal y días como número.

    Se hace aquí y no en la consulta porque MySQL
    devuelve las fechas como datetime.date y los
    DECIMAL como Decimal, y la vista necesita las dos
    cosas ya limpias.
    """

    # El saldo pendiente REAL: lo financiado menos lo
    # cobrado.
    #
    # No es saldo_financiado: ese es el saldo que se
    # pactó, no lo que queda. Un contrato de 10
    # millones con 4 millones pagados debe 6, y si
    # la cartera dijera que debe 10 el vendedor iría a
    # cobrar de más.

    pagado = Decimal(str(fila["pagado"]))

    saldo = (
        Decimal(str(fila["saldo_financiado"])) - pagado
    )

    fila["pagado"] = pagado
    fila["saldo"] = saldo
    fila["importe_vencido"] = Decimal(
        str(fila["importe_vencido"])
    )

    # Cuántos días lleva el más viejo sin pagar.
    # Se toma el máximo, no el del primer vencimiento:
    # si en un contrato hay una cuota de hace seis
    # meses y otra de mañana, las dos se cobran por
    # lo mismo y la más antigua es la que manda.

    fila["dias_atraso"] = _dias_atraso(
        fila["proximo_vencimiento"],
        hoy
    )

    # Cuántas cuotas quedan por pagar.

    fila["cuotas_pendientes"] = (
        fila["total_cuotas"]
        - fila["cuotas_pagadas"]
    )

    # Cuántos días lleva la deuda más antigua sin
    #deuda por anticipo.

    fila["dias_deuda"] = fila["dias_atraso"]

    return fila


def _dias_atraso(fecha, hoy):

    if fecha is None:

        return 0

    return max(0, (hoy - fecha).days)


def ejecutar_consulta(extra_where=None, extra_valores=None,
                      hoy=None, orden=None, limite=None):
    """
    Ejecuta la consulta de cartera con los filtros
    que se le pasen.

    Envolviendo una consulta tan larga en una
    función, todas las funciones de este módulo la
    llaman en vez de reescribirla, y así el JOIN no
    puede divergir entre unas y otras.

    El orden se resuelve en DOS pasos, y no por
    casualidad: "dias_atraso" y "saldo" no son
    columnas de la base, se calculan en _preparar()
    con Python. Pedir a MySQL "ORDER BY dias_atraso"
    falla con "Unknown column".

    Así que MySQL ordena por lo que SÍ existe (para no
    traer veinte mil filas y ordenarlas en Python),
    y Python reordena por el campo que de verdad
    importa. Al ser una lista pequeña, el segundo
    paso no cuesta nada.
    """

    if hoy is None:

        hoy = date.today()

    valores = [hoy, hoy]

    consulta = CONSULTA_CARTERA

    condiciones = []

    if extra_where:

        consulta += " WHERE " + extra_where

        if extra_valores:

            valores.extend(extra_valores)

    # Un orden de MYSQL siempre, aunque quien llama
    # haya pedido ordenar por un campo de Python:
    # si no, el ORDER BY se omite y MySQL devuelve las
    # filas en el orden que le dé.

    consulta += " ORDER BY contratos.id"

    if limite:

        consulta += f" LIMIT {int(limite)}"

    conexion = obtener_conexion()
    cursor = conexion.cursor(dictionary=True)

    cursor.execute(consulta, tuple(valores))

    filas = cursor.fetchall()

    cursor.close()
    conexion.close()

    preparadas = [_preparar(f, hoy) for f in filas]

    if orden:

        preparadas = _ordenar(preparadas, orden)

    return preparadas


def _ordenar(filas, orden):
    """
    Ordena por los campos calculados.

    El orden llega como texto ("dias_atraso DESC,
    saldo DESC") porque así se lee en la llamada, pero
    no se pasa a MySQL: se aplica aquí, en Python.

    Se admiten varios campos separados por comas y la
    palabra DESC o ASC, que es lo justo para estas
    listas y ni una coma más.
    """

    for parte in reversed(orden.split(",")):

        trozo = parte.strip()

        if not trozo:

            continue

        palabras = trozo.split()

        campo = palabras[0]

        descendente = len(palabras) > 1 and (
            palabras[1].upper() == "DESC"
        )

        filas.sort(
            key=lambda f: (
                f.get(campo) is None,
                f.get(campo)
            ),
            reverse=descendente
        )

    return filas


# ==========================================
# CUENTAS POR COBRAR
# ==========================================

# El filtro de "todavía debe dinero", una sola vez.

# La condición NO puede ser
#
#     contratos.saldo_financiado > 0
#
# porque saldo_financiado es lo que se FINANCIÓ, y
# ese número no baja nunca: no se toca cuando se cobra.
# Un cliente que pagó las doce cuotas del crédito
# seguiría apareciendo en la cartera pidiendo 4.000.000
# que ya no debe, y el cobrador iría a reclamárselos.
#
# El saldo real es lo financiado menos lo cobrado, y
# por eso la condición repite la resta con el mismo
# subselect que trae el "pagado". Es la línea más
# importante de este módulo.

SALDO_PENDIENTE_POR_CONTRATO = """
    contratos.estado = %s
    AND contratos.saldo_financiado > 0
    AND (
        contratos.saldo_financiado
        - COALESCE(
            (
                SELECT SUM(pagos.importe)
                FROM pagos
                WHERE pagos.venta_id = contratos.venta_id
                  AND pagos.estado = 'convalidado'
            ),
            0
          )
    ) > 0
"""


# La misma condición con el estado ya puesto, para las
# funciones que solo miran contratos activos y no
# aceptan otro estado.

SALDO_PENDIENTE_ACTIVO = (
    SALDO_PENDIENTE_POR_CONTRATO.replace(
        "contratos.estado = %s",
        "contratos.estado = 'activo'"
    )
)

@requiere_permiso(VER_FINANCIERA)

def cuentas_por_cobrar(estado="activo", hoy=None):
    """
    Todos los contratos con saldo pendiente.

    Devuelve la lista ordenada por urgencia: primero
    lo que lleva más retraso, y dentro de eso, lo que
    más debe.

    Es la lista de trabajo de la cobranza. Ordenar
    por saldo de mayor a menor parece lo intuitivo, y
    es un error: deja al final al cliente que debe
    80.000 y va con 40 días de atraso, detrás de uno
    que debe 3.000 y no ha pagado nunca. La urgencia
    la marca el retraso, no el importe.
    """

    if hoy is None:

        hoy = date.today()

    return ejecutar_consulta(
        extra_where=SALDO_PENDIENTE_POR_CONTRATO,
        extra_valores=[estado],
        hoy=hoy,
        orden="dias_atraso DESC, saldo DESC"
    )

@requiere_permiso(VER_FINANCIERA)

@requiere_permiso(VER_FINANCIERA)

@requiere_permiso(VER_FINANCIERA)

def cuotas_por_vencer(dias=None, hoy=None, limite=None):
    """
    Las CUOTAS concretas que vencen pronto, no los
    contratos.

    cuentas_por_cobrar() devuelve contratos, y para
    llamar por teléfono eso sirve. Pero para saber
    "¿qué vence esta semana?" hace falta la cuota:
    un contrato con 12 cuotas puede tener tres
    vencidas y las otras nueve bien, y la pregunta
    del cajero es por la cuota.
    """

    if dias is None:

        ajustes = leer_ajustes()

        dias = ajustes["dias_aviso"]

    if hoy is None:

        hoy = date.today()

    desde = hoy

    hasta = hoy + timedelta(days=int(dias))

    conexion = obtener_conexion()
    cursor = conexion.cursor(dictionary=True)

    consulta = """
        SELECT
            cuotas.id,
            cuotas.numero,
            cuotas.fecha_vencimiento,
            cuotas.importe,
            cuotas.saldo,
            cuotas.estado,
            contratos.id AS contrato_id,
            contratos.numero AS contrato_numero,
            CONCAT(
                clientes.nombre, ' ', clientes.apellido
            ) AS cliente,
            clientes.telefono,
            marcas.nombre AS marca,
            autos.modelo AS modelo
        FROM cuotas
        INNER JOIN contratos
            ON cuotas.contrato_id = contratos.id
        INNER JOIN clientes
            ON contratos.cliente_id = clientes.id
        INNER JOIN autos
            ON contratos.auto_id = autos.id
        INNER JOIN marcas
            ON autos.marca_id = marcas.id
        WHERE contratos.estado = 'activo'
          AND cuotas.estado <> 'anulada'
          AND cuotas.saldo > 0
          AND cuotas.fecha_vencimiento BETWEEN %s AND %s
        ORDER BY cuotas.fecha_vencimiento, cuotas.numero
    """

    valores = [desde, hasta]

    if limite:

        consulta += " LIMIT %s"

        valores.append(int(limite))

    cursor.execute(consulta, tuple(valores))

    filas = cursor.fetchall()

    cursor.close()
    conexion.close()

    for fila in filas:

        fila["dias_para_vencer"] = (
            fila["fecha_vencimiento"] - hoy
        ).days

        fila["dias_atraso"] = max(
            0,
            (hoy - fila["fecha_vencimiento"]).days
        )

        fila["saldo"] = Decimal(str(fila["saldo"]))

    return filas

@requiere_permiso(VER_FINANCIERA)

def cuotas_vencidas(hoy=None, limite=None):
    """
    Las CUOTAS concretas que ya vencieron y siguen
    con saldo.

    Vencida no significa lo que diga el campo estado:
    se recalcula por la fecha. Una cuota que alguien
    marcó a mano y que luego se pagó no está vencida,
    y una que nadie marcó y que pasó su fecha sí lo
    está. Consultar el estado daría la primera
    respuesta; la fecha da la correcta.
    """

    if hoy is None:

        hoy = date.today()

    ajustes = leer_ajustes()

    limite_vencida = hoy - timedelta(
        days=ajustes["dias_gracia"]
    )

    conexion = obtener_conexion()
    cursor = conexion.cursor(dictionary=True)

    consulta = """
        SELECT
            cuotas.id,
            cuotas.numero,
            cuotas.fecha_vencimiento,
            cuotas.importe,
            cuotas.saldo,
            cuotas.estado,
            contratos.id AS contrato_id,
            contratos.numero AS contrato_numero,
            CONCAT(
                clientes.nombre, ' ', clientes.apellido
            ) AS cliente,
            clientes.telefono,
            marcas.nombre AS marca,
            autos.modelo AS modelo
        FROM cuotas
        INNER JOIN contratos
            ON cuotas.contrato_id = contratos.id
        INNER JOIN clientes
            ON contratos.cliente_id = clientes.id
        INNER JOIN autos
            ON contratos.auto_id = autos.id
        INNER JOIN marcas
            ON autos.marca_id = marcas.id
        WHERE contratos.estado = 'activo'
          AND cuotas.estado <> 'anulada'
          AND cuotas.saldo > 0
          AND cuotas.fecha_vencimiento < %s
        ORDER BY cuotas.fecha_vencimiento, cuotas.numero
    """

    valores = [limite_vencida]

    if limite:

        consulta += " LIMIT %s"

        valores.append(int(limite))

    cursor.execute(consulta, tuple(valores))

    filas = cursor.fetchall()

    cursor.close()
    conexion.close()

    for fila in filas:

        fila["dias_atraso"] = (
            hoy - fila["fecha_vencimiento"]
        ).days

        fila["saldo"] = Decimal(str(fila["saldo"]))

    return filas


# ==========================================
# RESÚMENES
# ==========================================
@requiere_permiso(VER_FINANCIERA)

def resumen_cartera(hoy=None):
    """
    Los totales de la cartera, para el panel.

    Devuelve un diccionario con: contratos (cuántos
    hay con saldo), saldo_total, vencido,
    importe_vencido, por_vencer, clientes_vencidos y
    dias_promedio_vencimiento.
    """

    if hoy is None:

        hoy = date.today()

    ajustes = leer_ajustes()

    filas = cuentas_por_cobrar(hoy=hoy)

    saldo_total = CERO

    vencido = CERO

    importe_vencido = CERO

    clientes_vencidos = set()

    dias_sumados = 0

    dias_con_datos = 0

    for fila in filas:

        saldo_total += fila["saldo"]

        importe_vencido += fila["importe_vencido"]

        if fila["cuotas_vencidas"] > 0:

            vencido += fila["saldo"]

            clientes_vencidos.add(fila["cliente_id"])

        if fila["dias_atraso"] > 0:

            dias_sumados += fila["dias_atraso"]

            dias_con_datos += 1

    return {
        "contratos": len(filas),
        "saldo_total": saldo_total,
        "vencido": vencido,
        "importe_vencido": importe_vencido,
        "por_vencer": saldo_total - importe_vencido,
        "clientes_vencidos": len(clientes_vencidos),
        "dias_promedio": (
            dias_sumados / dias_con_datos
            if dias_con_datos else 0
        ),
        "dias_aviso": ajustes["dias_aviso"]
    }

@requiere_permiso(VER_FINANCIERA)

def envejecer_cartera(hoy=None):
    """
    La cartera por antigüedad de la deuda.

    Devuelve una lista de (etiqueta, importe, contratos)
    con estos tramos:

        Al día          no ha vencido ninguna cuota
        1 a 30 días     retraso corto
        31 a 60
        61 a 90
        91 a 180
        Más de 180      deuda parada mucho tiempo

    El último tramo es el que importa: una deuda con
    seis meses suele necesitar una gestión distinta
    (convenio, garantía, venta de cartera), y mezclarlo
    con "tres días de retraso" en un solo número
    esconde justo el problema que hay que ver.

    El importe es el saldo del contrato entero, no
    solo lo vencido: se debe todo, y lo que se está
    midiendo es desde cuándo arrastra.
    """

    if hoy is None:

        hoy = date.today()

    TRAMOS = [
        ("Al día", 0, 0),
        ("1 a 30 días", 1, 30),
        ("31 a 60 días", 31, 60),
        ("61 a 90 días", 61, 90),
        ("91 a 180 días", 91, 180),
        ("Más de 180 días", 181, 1000000)
    ]

    filas = cuentas_por_cobrar(hoy=hoy)

    resultado = []

    for etiqueta, desde, hasta in TRAMOS:

        importe = CERO

        contratos = 0

        for fila in filas:

            dias = fila["dias_atraso"]

            if desde <= dias <= hasta:

                importe += fila["saldo"]

                contratos += 1

        resultado.append({
            "etiqueta": etiqueta,
            "importe": importe,
            "contratos": contratos,
            "desde": desde,
            "hasta": hasta
        })

    return resultado

@requiere_permiso(VER_FINANCIERA)

def concentracion_cartera(hoy=None, limite=5):
    """
    Los cinco deudores más grandes y qué parte de la
    cartera tienen.

    Devuelve (filas, porcentaje_total).

    Existe por una razón práctica: si el 40 % de lo
    que se debe está en manos de dos personas, saber
    eso cambia cómo se dirige el negocio. No se puede
    ver con el total solo.
    """

    filas = cuentas_por_cobrar(hoy=hoy)

    total = CERO

    for fila in filas:

        total += fila["saldo"]

    if total <= CERO:

        return ([], 0)

    # Ordena por saldo y quédate con los primeros.

    principales = sorted(
        filas,
        key=lambda f: f["saldo"],
        reverse=True
    )[:limite]

    acumulado = CERO

    resultado = []

    for fila in principales:

        acumulado += fila["saldo"]

        resultado.append({
            "contrato_numero": fila["numero"],
            "cliente": (
                f"{fila['cliente_nombre']} "
                f"{fila['cliente_apellido']}"
            ),
            "saldo": fila["saldo"],
            "porcentaje": (
                float(fila["saldo"]) / float(total) * 100
            ),
            "dias_atraso": fila["dias_atraso"]
        })

    porcentaje = (
        float(acumulado) / float(total) * 100
    )

    return (resultado, round(porcentaje, 1))


# ==========================================
# DETALLE DE UN CONTRATO
# ==========================================
@requiere_permiso(VER_FINANCIERA)

def detalle_cobranza(id_contrato, hoy=None):
    """
    Todo lo relativo a la cobranza de un contrato.

    Devuelve un diccionario con el contrato de
    cartera, sus cuotas, sus pagos y los totales.
    Es lo que necesita la pantalla de detalle para
    pintar una sola vez y no pedir cuatro cosas.
    """

    # ------------------------------
    # LOS IMPORTS, DENTRO
    # ------------------------------
    # No es lo normal en este proyecto, y la razon
    # es que este archivo no los tiene arriba.
    #
    # Lo que hace es solo AMAGARLOS con resumen_de_
    # cuotas() y obtener_cuotas(), que son de
    # database/financiera.py. Ese modulo importa
    # leer_ajustes() de aqu\u00ed, as\u00ed que importarlo arriba
    # ser\u00eda un c\u00edrculo.
    #
    # Es la \u00fanica excepci\u00f3n, y est\u00e1 escrita para que
    # se note. El resto del c\u00f3digo mantiene la regla de
    # "no importes dentro de funciones".

    from database.financiera import (
        obtener_cuotas,
        resumen_de_cuotas
    )

    from database.pagos import obtener_pagos

    if hoy is None:

        hoy = date.today()

    # El contrato, por id, con la misma consulta base.

    filas = ejecutar_consulta(
        extra_where="contratos.id = %s",
        extra_valores=[id_contrato],
        hoy=hoy
    )

    if not filas:

        return None

    contrato = filas[0]

    contrato["cuotas"] = obtener_cuotas(id_contrato)

    contrato["resumen_cuotas"] = resumen_de_cuotas(
        id_contrato
    )

    contrato["pagos"] = obtener_pagos(contrato["venta_id"])

    return contrato
