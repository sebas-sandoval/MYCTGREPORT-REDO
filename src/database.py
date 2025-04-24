from mysql.connector import Error

import mysql.connector

def create_connection():
    try:
        connection = mysql.connector.connect(
            host='localhost',  
            user='root',  
            password='',  
            database='myctgreport'
        )
        if connection.is_connected():
            print("Conexión exitosa a la base de datos")
            return connection
    except Error as e:
        print(f"Error al conectar a la base de datos: {e}")
        return None

def close_connection(connection):
    if connection and connection.is_connected():
        connection.close()
        print("Conexión cerrada")

