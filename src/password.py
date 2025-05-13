import random
import string

def generar_contrasena(longitud=12, usar_mayusculas=True, usar_numeros=True, usar_simbolos=True):
    caracteres = list(string.ascii_lowercase)

    if usar_mayusculas:
        caracteres.extend(string.ascii_uppercase)
    if usar_numeros:
        caracteres.extend(string.digits)
    if usar_simbolos:
        caracteres.extend("!@#$%^&*()-_=+[]{}|;:,.<>?/")

    if not caracteres:
        raise ValueError("Debes incluir al menos un tipo de carácter")

    contrasena = ''.join(random.choice(caracteres) for _ in range(longitud))
    return contrasena


if __name__ == "__main__":
    print("Generador de Contraseñas Seguras")
    
    try:
        longitud = int(input("Longitud de la contraseña (mínimo 8): "))
    except ValueError:
        print("Debes ingresar un número válido.")
        exit()

    usar_mayusculas = input("¿Incluir mayúsculas? (s/n): ").strip().lower() == 's'
    usar_numeros = input("¿Incluir números? (s/n): ").strip().lower() == 's'
    usar_simbolos = input("¿Incluir símbolos? (s/n): ").strip().lower() == 's'

    if longitud < 8:
        print("La longitud mínima recomendada es 8 caracteres.")
    else:
        contrasena = generar_contrasena(longitud, usar_mayusculas, usar_numeros, usar_simbolos)
        print("Contraseña generada:", contrasena)
