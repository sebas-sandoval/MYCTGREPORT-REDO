from flask import Flask, render_template, request, redirect, url_for, session, flash
import os
from database import create_connection, close_connection
import re
from werkzeug.utils import secure_filename
import uuid

# Ruta base del proyecto
base_dir = os.path.dirname(os.path.abspath(__file__))

# Configuración de Flask y rutas de plantillas
template_dir = os.path.join(base_dir, 'templates')
app = Flask(__name__, template_folder=template_dir)

# Configuración de la carpeta de subida de imágenes
UPLOAD_FOLDER = os.path.join(base_dir, 'static', 'imgs')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)  # Crea la carpeta si no existe
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16 MB
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

def allowed_file(filename):
    return '.' in filename and \
        filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

app.secret_key = 'panaderia' # Clave secreta para sesiones y mensajes flash

# Ruta para la página login
@app.route("/", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]

        conn = create_connection()
        cursor = conn.cursor(dictionary=True)

        # Comprobar si correo y contraseña son correctos
        cursor.execute("SELECT * FROM usuarios WHERE correo = %s AND contrasena = %s", (email, password))

        user = cursor.fetchone()
        close_connection(conn)

        if user:
            session["user"] = user["id_usuario"] 
            return redirect(url_for("dashboard"))  # Redirige a la página de dashboard
        else:
            flash("Correo o contraseña incorrectos", "error") 
            return render_template("login.html")
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.pop("user", None)
    return redirect(url_for("login"))

# Ruta para registrar un nuevo usuario
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
                # comprobar nickname ya existe
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

#Ruta para recuperar contraseña
@app.route("/forgot_password", methods=["GET", "POST"])
def forgot_password():
    return render_template("forgot_password.html")

# Ruta de ventana principal
@app.route("/dashboard", methods=["GET", "POST"])
def dashboard():
    user_id = session.get("user")
    if not user_id:
        return redirect(url_for("login"))

    conn = create_connection()
    cursor = conn.cursor(dictionary=True)

    # Obtener los datos del usuario
    cursor.execute("SELECT * FROM usuarios WHERE id_usuario = %s", (user_id,))
    user = cursor.fetchone()
    session["user"] = user["id_usuario"] 

    # Obtener los reportes de la base de datos
    cursor.execute("SELECT * FROM publicaciones")
    reportes = cursor.fetchall()

    close_connection(conn)

    return render_template("dashboard.html", user=user, reportes=reportes)


@app.route("/reportes", methods=["GET", "POST"])
def reportes():
    if "user" not in session:
        return redirect(url_for("login"))

    if request.method == "POST":
        text = request.form.get("texto")
        file = request.files.get("imagen")
        ubication = request.form.get("ubicacion")
        id_usuario = session["user"]

        if not text or not ubication or not file:
            flash("Faltan datos.")
            return redirect(url_for("dashboard"))

        if file and allowed_file(file.filename):
            # Nombre seguro y único para el archivo
            original_filename = secure_filename(file.filename)
            unique_filename = f"{uuid.uuid4().hex}_{original_filename}"
            save_path = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
            file.save(save_path)

            # Guardar en base de datos
            conn = create_connection()
            cursor = conn.cursor(dictionary=True)
            cursor.execute("""
                INSERT INTO publicaciones (id_usuario, descripcion, imagen, ubicacion)
                VALUES (%s, %s, %s, %s)
            """, (id_usuario, text, unique_filename, ubication))
            conn.commit()
            close_connection(conn)
            flash("Reporte publicado con éxito")
        else:
            flash("Tipo de archivo no permitido. Solo se permiten imágenes.")
    return redirect(url_for("dashboard"))






if __name__ == '__main__':
    app.run(debug=True)