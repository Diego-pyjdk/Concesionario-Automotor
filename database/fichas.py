import functools
import io
import mysql.connector
from PIL import Image
from database.cobranza import cuentas_por_cobrar
from errores import traducir_error
# Fichas ampliadas. Los contratos de columnas existentes no cambian.
from decimal import Decimal
from datetime import date
from database.conexion import obtener_conexion, conexiones_libres
from database.auditoria import registrar_accion
from errores import ErrorValidacion
from permisos import (
    requiere_permiso, VER_VEHICULOS, GESTIONAR_VEHICULOS,
    VER_CLIENTES, VER_FINANCIERA, GESTIONAR_FINANCIERA
)
import sesion


def traducir_mysql(funcion):
    @functools.wraps(funcion)
    def ejecutar(*args, **kwargs):
        try:
            return funcion(*args, **kwargs)
        except mysql.connector.Error as error:
            raise traducir_error(error) from error
    return ejecutar


@conexiones_libres
@traducir_mysql
@requiere_permiso(VER_VEHICULOS)
def ficha_auto(auto_id):
    conexion = obtener_conexion()
    cursor = conexion.cursor(dictionary=True)
    cursor.execute('''SELECT a.*, m.nombre AS marca, f.combustible,
        f.transmision, f.observaciones FROM autos a
        JOIN marcas m ON m.id=a.marca_id
        LEFT JOIN auto_fichas f ON f.auto_id=a.id WHERE a.id=%s''', (auto_id,))
    return cursor.fetchone()


@conexiones_libres
@traducir_mysql
@requiere_permiso(GESTIONAR_VEHICULOS)
def guardar_ficha(auto_id, combustible, transmision, observaciones):
    if len(combustible) > 40 or len(transmision) > 40 or len(observaciones) > 10000:
        raise ErrorValidacion('El texto de la ficha es demasiado largo.')
    conexion = obtener_conexion()
    cursor = conexion.cursor()
    cursor.execute('''INSERT INTO auto_fichas
        (auto_id,combustible,transmision,observaciones) VALUES (%s,%s,%s,%s)
        ON DUPLICATE KEY UPDATE combustible=VALUES(combustible),
        transmision=VALUES(transmision),observaciones=VALUES(observaciones)''',
        (auto_id, combustible, transmision, observaciones))
    conexion.commit()
    registrar_accion('vehiculos', 'MODIFICAR', f'Ficha del vehículo {auto_id}')


@conexiones_libres
@traducir_mysql
@requiere_permiso(VER_VEHICULOS)
def fotos_auto(auto_id):
    conexion = obtener_conexion()
    cursor = conexion.cursor(dictionary=True)
    cursor.execute('SELECT id,nombre,contenido FROM auto_fotos WHERE auto_id=%s ORDER BY id', (auto_id,))
    return cursor.fetchall()


@conexiones_libres
@traducir_mysql
@requiere_permiso(GESTIONAR_VEHICULOS)
def agregar_foto(auto_id, contenido, nombre):
    if not contenido or len(contenido) > 5 * 1024 * 1024:
        raise ErrorValidacion('Cada foto debe ocupar como máximo 5 MB.')
    try:
        with Image.open(io.BytesIO(contenido)) as imagen:
            if imagen.width * imagen.height > 40_000_000:
                raise ErrorValidacion('La imagen supera 40 megapíxeles.')
            imagen.verify()
    except (OSError, ValueError) as error:
        raise ErrorValidacion('El archivo no es una imagen válida.') from error
    conexion = obtener_conexion()
    cursor = conexion.cursor()
    cursor.execute('INSERT INTO auto_fotos (auto_id,contenido,nombre) VALUES (%s,%s,%s)',
                   (auto_id, contenido, nombre[:255]))
    conexion.commit()
    registrar_accion('vehiculos', 'MODIFICAR', f'Foto agregada al vehículo {auto_id}')
    return cursor.lastrowid


@conexiones_libres
@traducir_mysql
@requiere_permiso(GESTIONAR_VEHICULOS)
def eliminar_foto(foto_id):
    conexion = obtener_conexion()
    cursor = conexion.cursor()
    cursor.execute('DELETE FROM auto_fotos WHERE id=%s', (foto_id,))
    conexion.commit()
    registrar_accion('vehiculos', 'MODIFICAR', f'Foto {foto_id} eliminada')


@conexiones_libres
@traducir_mysql
@requiere_permiso(VER_VEHICULOS)
def unidades_auto(auto_id):
    conexion = obtener_conexion()
    cursor = conexion.cursor(dictionary=True)
    cursor.execute('''SELECT u.*, v.venta_id,
        CASE WHEN v.venta_id IS NULL THEN u.estado ELSE 'vendido' END AS situacion
        FROM unidades_vehiculo u LEFT JOIN venta_unidades v ON v.unidad_id=u.id
        WHERE u.auto_id=%s ORDER BY u.id''', (auto_id,))
    return cursor.fetchall()


@conexiones_libres
@traducir_mysql
@requiere_permiso(GESTIONAR_VEHICULOS)
def guardar_unidad(auto_id, vin, matricula, kilometraje, estado, observaciones, unidad_id=None):
    vin = vin.strip().upper()
    if not vin or len(vin) > 40:
        raise ErrorValidacion('Ingresa un chasis/VIN de hasta 40 caracteres.')
    if estado not in ('disponible', 'reservado', 'taller') or not 0 <= kilometraje <= 2147483647:
        raise ErrorValidacion('Estado o kilometraje inválido.')
    if len(matricula) > 30 or len(observaciones) > 10000:
        raise ErrorValidacion('Matrícula u observaciones demasiado largas.')
    conexion = obtener_conexion()
    conexion.start_transaction()
    cursor = conexion.cursor()
    cursor.execute('SELECT stock FROM autos WHERE id=%s FOR UPDATE', (auto_id,))
    auto = cursor.fetchone()
    if auto is None:
        raise ErrorValidacion('No existe el vehículo.')
    if unidad_id:
        cursor.execute('''SELECT u.id,v.venta_id FROM unidades_vehiculo u
            LEFT JOIN venta_unidades v ON v.unidad_id=u.id WHERE u.id=%s AND u.auto_id=%s''',
            (unidad_id, auto_id))
        unidad = cursor.fetchone()
        if not unidad or unidad[1]:
            raise ErrorValidacion('Una unidad vendida no puede modificarse.')
        cursor.execute('''UPDATE unidades_vehiculo SET vin=%s,matricula=%s,kilometraje=%s,
            estado=%s,observaciones=%s WHERE id=%s''',
            (vin, matricula or None, kilometraje, estado, observaciones, unidad_id))
    else:
        cursor.execute('''SELECT COUNT(*) FROM unidades_vehiculo u
            LEFT JOIN venta_unidades v ON v.unidad_id=u.id
            WHERE u.auto_id=%s AND v.venta_id IS NULL''', (auto_id,))
        if cursor.fetchone()[0] >= auto[0]:
            raise ErrorValidacion('Todas las unidades del stock ya están identificadas. Aumenta el stock si ingresó otro vehículo.')
        cursor.execute('''INSERT INTO unidades_vehiculo
            (auto_id,vin,matricula,kilometraje,estado,observaciones) VALUES (%s,%s,%s,%s,%s,%s)''',
            (auto_id, vin, matricula or None, kilometraje, estado, observaciones))
        unidad_id = cursor.lastrowid
    conexion.commit()
    registrar_accion('vehiculos', 'MODIFICAR', f'Unidad {unidad_id}: {vin}')
    return unidad_id


@conexiones_libres
@traducir_mysql
@requiere_permiso(VER_CLIENTES)
def ficha_cliente(cliente_id):
    conexion = obtener_conexion()
    cursor = conexion.cursor(dictionary=True)
    cursor.execute('SELECT * FROM clientes WHERE id=%s', (cliente_id,))
    cliente = cursor.fetchone()
    if not cliente:
        raise ErrorValidacion('No existe el cliente.')
    cursor.execute('''SELECT v.id,v.fecha,CONCAT(m.nombre,' ',a.modelo) AS vehiculo,
        v.precio,v.moneda,c.id AS contrato_id,c.numero,c.estado
        FROM ventas v JOIN autos a ON a.id=v.auto_id JOIN marcas m ON m.id=a.marca_id
        LEFT JOIN contratos c ON c.venta_id=v.id
        WHERE v.cliente_id=%s ORDER BY v.fecha DESC,v.id DESC''', (cliente_id,))
    return cliente, cursor.fetchall()


@conexiones_libres
@traducir_mysql
@requiere_permiso(VER_FINANCIERA)
def pagos_cliente(cliente_id):
    conexion = obtener_conexion()
    cursor = conexion.cursor(dictionary=True)
    cursor.execute('''SELECT p.id,p.fecha,p.importe,p.recibo,(p.estado='anulado') AS anulado,v.moneda,
        v.id AS venta_id FROM pagos p JOIN ventas v ON v.id=p.venta_id
        WHERE v.cliente_id=%s ORDER BY p.fecha DESC,p.id DESC''', (cliente_id,))
    pagos = cursor.fetchall()
    cursor.execute('''SELECT v.id,v.moneda,v.precio,
        v.precio-COALESCE((SELECT SUM(p.importe) FROM pagos p
        WHERE p.venta_id=v.id AND p.estado='convalidado'),0) AS saldo
        FROM ventas v WHERE v.cliente_id=%s ORDER BY v.id DESC''', (cliente_id,))
    return pagos, cursor.fetchall()


@conexiones_libres
@traducir_mysql
@requiere_permiso(VER_FINANCIERA)
def seguimiento(contrato_id=None, pendientes=False):
    conexion = obtener_conexion()
    cursor = conexion.cursor(dictionary=True)
    consulta = '''SELECT s.*, c.numero, c.moneda,
        CONCAT(cl.nombre,' ',cl.apellido) AS cliente FROM seguimiento_cobranza s
        JOIN contratos c ON c.id=s.contrato_id JOIN clientes cl ON cl.id=c.cliente_id WHERE 1=1'''
    valores = []
    if contrato_id is not None:
        consulta += ' AND s.contrato_id=%s'
        valores.append(contrato_id)
    if pendientes:
        consulta += ' AND s.completado=0'
    consulta += ' ORDER BY s.completado,COALESCE(s.proximo_contacto, s.promesa_fecha, DATE(s.fecha)),s.id DESC'
    cursor.execute(consulta, valores)
    return cursor.fetchall()


@conexiones_libres
@traducir_mysql
@requiere_permiso(GESTIONAR_FINANCIERA)
def registrar_seguimiento(contrato_id, canal, notas, proximo=None, promesa_fecha=None, promesa_importe=None):
    if canal not in ('llamada', 'whatsapp', 'presencial', 'otro') or not notas.strip() or len(notas) > 10000:
        raise ErrorValidacion('Selecciona un canal y escribe una nota de hasta 10.000 caracteres.')
    importe = None
    if promesa_fecha is not None or promesa_importe is not None:
        try:
            importe = Decimal(str(promesa_importe))
        except Exception as error:
            raise ErrorValidacion('Completa la fecha y el importe de la promesa.') from error
        if promesa_fecha is None or not importe.is_finite() or importe <= 0 or importe > Decimal('9999999999999.99') or importe != importe.quantize(Decimal('.01')):
            raise ErrorValidacion('Completa una promesa con fecha e importe positivo válido.')
    for fecha in (proximo, promesa_fecha):
        if fecha is not None and not isinstance(fecha, date):
            raise ErrorValidacion('La fecha no es válida.')
    conexion = obtener_conexion()
    cursor = conexion.cursor()
    cursor.execute('SELECT estado,moneda FROM contratos WHERE id=%s', (contrato_id,))
    contrato = cursor.fetchone()
    if not contrato or contrato[0] == 'cancelado':
        raise ErrorValidacion('Selecciona un contrato vigente.')
    if importe and contrato[1] == 'PYG' and importe != importe.to_integral_value():
        raise ErrorValidacion('Los guaraníes se registran sin decimales.')
    usuario = sesion.obtener_sesion()
    cursor.execute('''INSERT INTO seguimiento_cobranza
        (contrato_id,usuario_id,usuario_nombre,canal,notas,proximo_contacto,promesa_fecha,promesa_importe)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s)''',
        (contrato_id, usuario.id_usuario, usuario.nombre_usuario, canal, notas.strip(), proximo, promesa_fecha, importe))
    conexion.commit()
    registrar_accion('contratos', 'MODIFICAR', f'Seguimiento de cobranza del contrato {contrato_id}')
    return cursor.lastrowid


@conexiones_libres
@traducir_mysql
@requiere_permiso(GESTIONAR_FINANCIERA)
def completar_seguimiento(seguimiento_id):
    conexion = obtener_conexion()
    cursor = conexion.cursor()
    cursor.execute('UPDATE seguimiento_cobranza SET completado=1 WHERE id=%s', (seguimiento_id,))
    conexion.commit()
    registrar_accion('contratos', 'MODIFICAR', f'Seguimiento {seguimiento_id} completado')


@conexiones_libres
@traducir_mysql
@requiere_permiso(VER_FINANCIERA)
def resumen_inicio():
    filas = cuentas_por_cobrar()
    conexion = obtener_conexion()
    cursor = conexion.cursor()
    cursor.execute('SELECT id,moneda FROM contratos')
    monedas = dict(cursor.fetchall())
    resumen = {}
    for fila in filas:
        codigo = monedas[fila['contrato_id']]
        grupo = resumen.setdefault(codigo, {'saldo':Decimal('0'),'vencido':Decimal('0'),'contratos':0})
        grupo['saldo'] += fila['saldo']
        grupo['vencido'] += fila['importe_vencido']
        grupo['contratos'] += 1
    return resumen
