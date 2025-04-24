from flask import Flask, render_template, request, redirect, url_for
import os
from database import create_connection, close_connection
from flask import flash
import re


# Configuración de Flask y rutas de plantillas
template_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'templates')
app = Flask(__name__, template_folder=template_dir)

app.secret_key = 'panaderia' # Clave secreta para sesiones y mensajes flash

# Ruta para la página login
@app.route("/", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]

        conn = create_connection()
        cursor = conn.cursor()

        # Comprobar si correo y contraseña son correctos
        cursor.execute("SELECT * FROM usuarios WHERE correo = %s AND contrasena = %s", (email, password))

        user = cursor.fetchone()
        close_connection(conn)

        if user:
            return redirect(url_for("dashboard"))  # Redirige a la página de dashboard
        else:
            flash("Correo o contraseña incorrectos", "error")  # Mensaje de error con flash
            return render_template("login.html")
    return render_template("login.html")

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form["nombre"]
        lastname = request.form["apellido"]
        nickname = request.form["nickname"]
        email = request.form["correo"]
        password = request.form["contraseña"]
        phone = request.form["telefono"]
        adress = request.form["residencia"]

        #validar datos
        if name and lastname and nickname and email and password and phone and adress:
            fields = {
                "nombre": (name, 3, "El nombre debe tener al menos 3 caracteres."),
                "apellido": (lastname, 3, "El apellido debe tener al menos 3 caracteres."),
                "nickname": (nickname, 3, "El nickname debe tener al menos 3 caracteres."),
                "contraseña": (password, 8, "La contraseña debe tener al menos 8 caracteres.")
            }

            for fields, (value, min_length, error_message) in fields.items():
                if len(value) < min_length:
                    flash(error_message)
                    return redirect(url_for("register"))
                
            if not re.match(r'^[0-9]{10}$', phone):
                flash("El número de celular debe tener solo 10 dígitos.")
                return redirect(url_for("register"))
            
            conn = create_connection()
            cursor = conn.cursor()

            # Comprobar si el correo ya existe
            cursor.execute("SELECT * FROM usuarios WHERE correo= %s" , (email,))
            user_by_email = cursor.fetchone()

            if user_by_email:
                flash("el correo electrouco ya existe")
                return redirect(url_for("register"))
            else:
                # comprobar nickname ya
                cursor.execute("SELECT * FROM usuarios WHERE nickname = %s", (nickname,))
                user_by_nickname = cursor.fetchone()

            if user_by_nickname:
                flash("el nickname ya existe")
                return redirect(url_for("register"))
            
            #guardar usuario en la base de datos
            cursor.execute("INSERT INTO usuarios (nombre, apellido, nickname, correo, contrasena, telefono, residencia) VALUES (%s, %s, %s, %s, %s, %s, %s)", (name, lastname, nickname, email, password, phone, adress))
            conn.commit()
            flash("Usuario registrado con éxito")
            return redirect(url_for("login"))
        else:
            flash("Por favor, completa todos los campos")
            return redirect(url_for("register"))
    return render_template("register.html")

@app.route("/forgot_password", methods=["GET", "POST"])
def forgot_password():
    return render_template("forgot_password.html")

@app.route("/dashboard", methods=["GET", "POST"])
def dashboard():
    return render_template("dashboard.html")





if __name__ == '__main__':
    app.run(debug=True)