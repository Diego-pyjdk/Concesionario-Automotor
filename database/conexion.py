import mysql.connector


def obtener_conexion():
    return mysql.connector.connect(
        host="localhost",
        user="root",
        password="224426",
        database="concesionario"
    )