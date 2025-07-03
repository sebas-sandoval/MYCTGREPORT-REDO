from typing import List
import random
import string


def generate_password(
    length: int = 12,
    use_uppercases: bool = True,
    use_numbers: bool = True,
    use_symbols: bool = True,
) -> str:
    characters: List[str] = list(string.ascii_lowercase)

    if use_uppercases:
        characters.extend(string.ascii_uppercase)

    if use_numbers:
        characters.extend(string.digits)

    if use_symbols:
        characters.extend("!@#$%^&*()-_=+[]{}|;:,.<>?/")

    if not characters:
        raise ValueError("Debes incluir al menos un tipo de carácter")

    password: str = "".join(random.choice(characters) for _ in range(length))

    return password


if __name__ == "__main__":
    print("Generador de Contraseñas Seguras")

    try:
        length: int = int(input("Longitud de la contraseña (mínimo 8): "))
    except ValueError:
        print("Debes ingresar un número válido.")
        exit()

    use_uppercases: bool = input("¿Incluir mayúsculas? (s/n): ").strip().lower() == "s"
    use_numbers: bool = input("¿Incluir números? (s/n): ").strip().lower() == "s"
    use_symbols: bool = input("¿Incluir símbolos? (s/n): ").strip().lower() == "s"

    if length < 8:
        print("La longitud mínima recomendada es 8 caracteres.")
    else:
        password: str = generate_password(
            length, use_uppercases, use_numbers, use_symbols
        )
        print("Contraseña generada:", password)
