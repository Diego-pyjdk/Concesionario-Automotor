from datetime import date
from decimal import Decimal
from pathlib import Path
import io
import uuid
import pytest
from PIL import Image
import mysql.connector
from database import fichas
from database.autos import obtener_autos, actualizar_auto
from database.ventas import registrar_venta, eliminar_venta
from database.contratos import crear_contrato, obtener_contrato
from database.pagos import registrar_pago, eliminar_pago
from database.conexion import obtener_conexion, configuracion
from errores import ErrorValidacion, ErrorSistema, PermisoDenegado
from utils.respaldo import crear_respaldo, verificar_respaldo, restaurar_respaldo


def test_unidad_vendida_no_se_duplica_y_anulacion_la_libera(como_administrador,datos_base):
    _, auto_id, cliente_id = datos_base
    unidad_id = fichas.guardar_unidad(auto_id,'VIN-001','ABC123',12000,'disponible','')
    venta,_ = registrar_venta(cliente_id,auto_id,date.today(),1000,unidad_id=unidad_id)
    assert venta
    segunda,mensaje = registrar_venta(cliente_id,auto_id,date.today(),1000,unidad_id=unidad_id)
    assert not segunda
    assert 'disponible' in mensaje
    assert fichas.unidades_auto(auto_id)[0]['situacion'] == 'vendido'
    with pytest.raises(ErrorValidacion):
        fichas.guardar_unidad(auto_id,'CAMBIO','',0,'disponible','',unidad_id)
    assert eliminar_venta(venta)
    assert fichas.unidades_auto(auto_id)[0]['situacion'] == 'disponible'
    assert obtener_autos()[0][6] == 3


def test_no_identifica_mas_unidades_que_stock(como_administrador,datos_base):
    _, auto_id, _ = datos_base
    for i in range(3):
        fichas.guardar_unidad(auto_id,f'VIN-{i}','',0,'disponible','')
    with pytest.raises(ErrorValidacion):
        fichas.guardar_unidad(auto_id,'VIN-EXTRA','',0,'disponible','')
    auto = obtener_autos()[0]
    with pytest.raises(ErrorValidacion):
        actualizar_auto(auto_id,datos_base[0],auto[2],auto[3],auto[4],auto[5],2)


def test_reservadas_no_se_venden_como_stock_generico(como_administrador,datos_base):
    _, auto_id, cliente = datos_base
    for i in range(3):
        fichas.guardar_unidad(auto_id,f'VIN-{i}','',0,'reservado','')
    venta,_ = registrar_venta(cliente,auto_id,date.today(),1000)
    assert not venta
    venta,_ = registrar_venta(cliente,auto_id,date.today(),1000,unidad_id=fichas.unidades_auto(auto_id)[0]['id'])
    assert not venta
    assert obtener_autos()[0][6] == 3


def test_stock_legacy_sigue_vendiendose(como_administrador,datos_base):
    _, auto_id, cliente = datos_base
    fichas.guardar_unidad(auto_id,'VIN-RESERVADO','',0,'reservado','')
    venta,_ = registrar_venta(cliente,auto_id,date.today(),1000)
    assert venta
    assert fichas.unidades_auto(auto_id)[0]['situacion'] == 'reservado'


def test_ficha_foto_y_chasis_en_contrato(como_administrador,datos_base):
    _, auto_id, cliente = datos_base
    fichas.guardar_ficha(auto_id,'Nafta','Manual','Prueba')
    imagen = Image.new('RGB',(10,10),'blue')
    contenido = io.BytesIO();imagen.save(contenido,format='PNG')
    foto = fichas.agregar_foto(auto_id,contenido.getvalue(),'auto.png')
    assert fichas.fotos_auto(auto_id)[0]['contenido'] == contenido.getvalue()
    assert fichas.ficha_auto(auto_id)['combustible'] == 'Nafta'
    unidad = fichas.guardar_unidad(auto_id,'VIN-CONTRATO','ABC123',100,'disponible','')
    venta,_ = registrar_venta(cliente,auto_id,date.today(),1000,unidad_id=unidad)
    contrato,_ = crear_contrato(venta,'Contado')
    assert obtener_contrato(contrato)['vin'] == 'VIN-CONTRATO'
    fichas.eliminar_foto(foto)
    assert not fichas.fotos_auto(auto_id)


def test_historial_cliente_no_cuenta_pago_anulado(como_administrador,datos_base):
    _, auto_id, cliente = datos_base
    venta,_ = registrar_venta(cliente,auto_id,date.today(),1000,moneda='USD')
    pago,_ = registrar_pago(venta,Decimal('100'),date.today(),'Efectivo')
    assert pago
    pagos,saldos = fichas.pagos_cliente(cliente)
    assert saldos[0]['saldo'] == Decimal('900')
    eliminar_pago(pago)
    pagos,saldos = fichas.pagos_cliente(cliente)
    assert saldos[0]['saldo'] == Decimal('1000')
    assert len(fichas.ficha_cliente(cliente)[1]) == 1


def test_promesa_no_modifica_saldo(como_administrador,datos_base):
    _, auto_id, cliente = datos_base
    venta,_ = registrar_venta(cliente,auto_id,date.today(),1000,moneda='USD')
    contrato,_ = crear_contrato(venta,'Contado')
    contacto = fichas.registrar_seguimiento(contrato,'llamada','Prometió acercarse',date.today(),date.today(),Decimal('50'))
    assert len(fichas.seguimiento(contrato,True)) == 1
    assert fichas.pagos_cliente(cliente)[1][0]['saldo'] == Decimal('1000')
    fichas.completar_seguimiento(contacto)
    assert not fichas.seguimiento(contrato,True)
    assert len(fichas.seguimiento(contrato)) == 1


def test_fotos_invalidas_se_rechazan(como_administrador,datos_base):
    with pytest.raises(ErrorValidacion):
        fichas.agregar_foto(datos_base[1],b'no es una foto','falso.png')


def test_respaldo_recupera_datos_fotos_y_decimal(como_administrador,datos_base,tmp_path):
    ruta = tmp_path/'respaldo.zip'
    imagen=Image.new('RGB',(8,8));archivo=io.BytesIO();imagen.save(archivo,format='PNG')
    fichas.agregar_foto(datos_base[1],archivo.getvalue(),'prueba.png')
    conteos = crear_respaldo(ruta)
    datos = verificar_respaldo(ruta)
    assert len(datos['tablas']) == 17
    nombre='pruebas_recuperacion_'+uuid.uuid4().hex[:12]
    try:
        recuperadas = restaurar_respaldo(ruta,nombre)
        assert recuperadas == conteos
        config=configuracion();config['database']=nombre
        conexion=mysql.connector.connect(**config)
        cursor=conexion.cursor()
        cursor.execute('SELECT contenido FROM auto_fotos')
        assert cursor.fetchone()[0] == archivo.getvalue()
        cursor.execute('SELECT precio FROM autos WHERE id=%s',(datos_base[1],))
        assert isinstance(cursor.fetchone()[0],Decimal)
        cursor.close();conexion.close()
        with pytest.raises(ErrorSistema):
            restaurar_respaldo(ruta,nombre)
    finally:
        config=configuracion();config.pop('database')
        conexion=mysql.connector.connect(**config);cursor=conexion.cursor()
        cursor.execute('DROP DATABASE IF EXISTS `'+nombre+'`')
        cursor.close();conexion.close()
    with pytest.raises(ErrorSistema):
        restaurar_respaldo(ruta,configuracion()['database'])


def test_migracion_aditiva_repetible_preserva_datos(como_administrador,datos_base):
    conexion=obtener_conexion();cursor=conexion.cursor()
    cursor.execute('SELECT COUNT(*) FROM autos');antes=cursor.fetchone()[0]
    sql=(Path(__file__).resolve().parents[1]/'sql/actualizar_mejoras.sql').read_text()
    sql='\n'.join(l for l in sql.splitlines() if not l.strip().startswith('--'))
    for repeticion in range(2):
        for sentencia in sql.split(';'):
            sentencia=sentencia.strip()
            if sentencia and not sentencia.upper().startswith('USE '):
                cursor.execute(sentencia)
    cursor.execute('SELECT COUNT(*) FROM autos');assert cursor.fetchone()[0] == antes
    cursor.close();conexion.close()
