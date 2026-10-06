# Respaldo de tablas InnoDB con una instantánea consistente.
# Restauración exclusivamente en una base NUEVA, nunca sobre la base activa.
import base64
import hashlib
import json
import re
import zipfile
from datetime import datetime, date, time, timedelta
from decimal import Decimal
from pathlib import Path
import mysql.connector
from database.conexion import configuracion
from errores import ErrorSistema
from permisos import requiere_permiso, GESTIONAR_CONFIGURACION
from database.auditoria import registrar_accion


def codificar(valor):
    if isinstance(valor, Decimal):
        return {'tipo':'decimal','valor':str(valor)}
    if isinstance(valor, (bytes, bytearray)):
        return {'tipo':'bytes','valor':base64.b64encode(valor).decode('ascii')}
    if isinstance(valor, (datetime,date,time)):
        return {'tipo':type(valor).__name__,'valor':valor.isoformat()}
    if isinstance(valor, timedelta):
        return {'tipo':'timedelta','valor':valor.total_seconds()}
    raise TypeError(type(valor).__name__)


def decodificar(valor):
    if set(valor) != {'tipo','valor'}:
        return valor
    tipo, dato = valor['tipo'],valor['valor']
    if tipo == 'decimal':
        return Decimal(dato)
    if tipo == 'bytes':
        return base64.b64decode(dato,validate=True)
    if tipo == 'datetime':
        return datetime.fromisoformat(dato)
    if tipo == 'date':
        return date.fromisoformat(dato)
    if tipo == 'time':
        return time.fromisoformat(dato)
    if tipo == 'timedelta':
        return timedelta(seconds=dato)
    raise ErrorSistema('Tipo de dato desconocido en el respaldo.')


def identificador(nombre):
    if not re.fullmatch(r'[A-Za-z][A-Za-z0-9_]{0,63}',nombre):
        raise ErrorSistema('Nombre de tabla o base no válido.')
    return '`'+nombre+'`'


@requiere_permiso(GESTIONAR_CONFIGURACION)
def crear_respaldo(ruta):
    ruta = Path(ruta)
    if ruta.exists():
        raise ErrorSistema('Elige un nombre de archivo nuevo para el respaldo.')
    conexion = mysql.connector.connect(**configuracion())
    temporal = ruta.with_suffix(ruta.suffix+'.tmp')
    try:
        cursor = conexion.cursor()
        cursor.execute('SET SESSION TRANSACTION ISOLATION LEVEL REPEATABLE READ')
        cursor.execute('START TRANSACTION WITH CONSISTENT SNAPSHOT')
        cursor.execute('SHOW TABLE STATUS')
        tablas = cursor.fetchall()
        if any(t[1] != 'InnoDB' for t in tablas):
            raise ErrorSistema('El respaldo requiere que todas las tablas sean InnoDB.')
        datos = []
        for tabla in tablas:
            nombre = tabla[0]
            citado = identificador(nombre)
            cursor.execute('SHOW CREATE TABLE '+citado)
            ddl = cursor.fetchone()[1]
            cursor.execute('SELECT * FROM '+citado)
            columnas = list(cursor.column_names)
            filas = cursor.fetchall()
            datos.append({'tabla':nombre,'ddl':ddl,'columnas':columnas,'filas':filas})
        contenido = json.dumps({'version':1,'base':configuracion()['database'],
            'creado':datetime.now().isoformat(),'tablas':datos},default=codificar,ensure_ascii=False).encode('utf-8')
        manifiesto = {'version':1,'sha256':hashlib.sha256(contenido).hexdigest(),
                      'filas':{t['tabla']:len(t['filas']) for t in datos}}
        with zipfile.ZipFile(temporal,'w',zipfile.ZIP_DEFLATED) as archivo:
            archivo.writestr('datos.json',contenido)
            archivo.writestr('manifest.json',json.dumps(manifiesto))
        verificar_respaldo(temporal)
        temporal.replace(ruta)
        registrar_accion('configuracion','CREAR','Copia de seguridad verificada')
        return manifiesto['filas']
    except mysql.connector.Error as error:
        raise ErrorSistema('No se pudo crear el respaldo de MySQL.') from error
    finally:
        conexion.rollback()
        conexion.close()
        if temporal.exists():
            temporal.unlink()


def verificar_respaldo(ruta):
    try:
        with zipfile.ZipFile(ruta) as archivo:
            contenido = archivo.read('datos.json')
            manifiesto = json.loads(archivo.read('manifest.json'))
        if manifiesto.get('version') != 1 or hashlib.sha256(contenido).hexdigest() != manifiesto['sha256']:
            raise ErrorSistema('El respaldo está incompleto o dañado.')
        datos = json.loads(contenido,object_hook=decodificar)
        if datos.get('version') != 1 or {t['tabla']:len(t['filas']) for t in datos['tablas']} != manifiesto['filas']:
            raise ErrorSistema('Los conteos del respaldo no coinciden.')
        for t in datos['tablas']:
            identificador(t['tabla'])
            for columna in t['columnas']:
                identificador(columna)
        return datos
    except (OSError,ValueError,KeyError,zipfile.BadZipFile) as error:
        raise ErrorSistema('No se pudo verificar el archivo de respaldo.') from error


def restaurar_respaldo(ruta, base_nueva):
    citado = identificador(base_nueva)
    config = configuracion()
    if base_nueva.lower() in (config['database'].lower(),'mysql','information_schema','performance_schema','sys'):
        raise ErrorSistema('La restauración exige una base nueva diferente de la actual.')
    datos = verificar_respaldo(ruta)
    config.pop('database')
    conexion = mysql.connector.connect(**config)
    creada = False
    try:
        cursor = conexion.cursor()
        cursor.execute('SELECT SCHEMA_NAME FROM information_schema.SCHEMATA WHERE LOWER(SCHEMA_NAME)=LOWER(%s)',(base_nueva,))
        if cursor.fetchone():
            raise ErrorSistema('Esa base ya existe. No se sobrescribe; elige otro nombre.')
        cursor.execute('CREATE DATABASE '+citado+' CHARACTER SET utf8mb4')
        creada = True
        cursor.execute('USE '+citado)
        cursor.execute('SET FOREIGN_KEY_CHECKS=0')
        for tabla in datos['tablas']:
            ddl = tabla['ddl']
            # El archivo debe ser un respaldo propio; solo se acepta CREATE TABLE del nombre esperado.
            if not ddl.startswith('CREATE TABLE '+identificador(tabla['tabla'])+' ') or ';' in ddl:
                raise ErrorSistema('El respaldo contiene una definición de tabla no admitida.')
            cursor.execute(ddl)
        for tabla in datos['tablas']:
            if tabla['filas']:
                columnas = ','.join(identificador(c) for c in tabla['columnas'])
                placeholders = ','.join(['%s']*len(tabla['columnas']))
                consulta = 'INSERT INTO '+identificador(tabla['tabla'])+' ('+columnas+') VALUES ('+placeholders+')'
                for inicio in range(0,len(tabla['filas']),200):
                    cursor.executemany(consulta,tabla['filas'][inicio:inicio+200])
            cursor.execute('SELECT COUNT(*) FROM '+identificador(tabla['tabla']))
            if cursor.fetchone()[0] != len(tabla['filas']):
                raise ErrorSistema('La verificación de filas restauradas falló.')
        cursor.execute('SET FOREIGN_KEY_CHECKS=1')
        conexion.commit()
        return {t['tabla']:len(t['filas']) for t in datos['tablas']}
    except Exception as error:
        conexion.rollback()
        # Solo se elimina la base nueva creada por ESTA operación si no completó la recuperación.
        if creada:
            cursor.execute('DROP DATABASE '+citado)
        if isinstance(error,ErrorSistema):
            raise
        raise ErrorSistema('La restauración falló; la base original no se modificó.') from error
    finally:
        conexion.close()
