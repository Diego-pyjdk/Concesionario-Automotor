import argparse
from utils.respaldo import restaurar_respaldo, verificar_respaldo
from errores import ErrorSistema


def main():
    parser = argparse.ArgumentParser(description='Verificar o recuperar un respaldo propio en una base NUEVA.')
    parser.add_argument('archivo')
    parser.add_argument('--base',help='Nombre de una base nueva, por ejemplo concesionario_recuperado')
    argumentos = parser.parse_args()
    try:
        if argumentos.base:
            filas = restaurar_respaldo(argumentos.archivo,argumentos.base)
            print('Base nueva recuperada:',argumentos.base)
            print('Tablas:',len(filas),'Filas:',sum(filas.values()))
            print('La base original sigue intacta. Verifica la recuperación antes de cambiar DB_NAME.')
        else:
            datos = verificar_respaldo(argumentos.archivo)
            print('Respaldo íntegro. Tablas:',len(datos['tablas']))
    except ErrorSistema as error:
        parser.exit(1,error.mensaje+'\n')


if __name__ == '__main__':
    main()
