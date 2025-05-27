import sqlite3
import os

def create_connection():
    try:
        db_path = os.path.join(os.path.dirname(__file__), 'myctgreport.db')
        connection = sqlite3.connect(db_path)
        connection.row_factory = sqlite3.Row  # permite acceder a columnas por nombre
        print("Conexión exitosa a SQLite")
        return connection
    except sqlite3.Error as e:
        print(f"Error al conectar a SQLite: {e}")
        return None

def close_connection(connection):
    if connection:
        connection.close()
        print("Conexión a SQLite cerrada")
