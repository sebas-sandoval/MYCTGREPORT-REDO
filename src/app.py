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
@app.route("/registro", methods=["GET", "POST"])
def registro():
    if request.method == "POST":
        nombre = request.form["nombre"]
        apellido = request.form["apellido"]
        nickname = request.form["nickname"]
        correo = request.form["correo"]
        contraseña = request.form["contraseña"]
        telefono = request.form["telefono"]
        residencia = request.form["residencia"]

        #validar datos
        if nombre and apellido and nickname and correo and contraseña and telefono and residencia:
            fields = {
                "nombre": (nombre, 3, "El nombre debe tener al menos 3 caracteres."),
                "apellido": (apellido, 3, "El apellido debe tener al menos 3 caracteres."),
                "nickname": (nickname, 3, "El nickname debe tener al menos 3 caracteres."),
                "contraseña": (contraseña, 8, "La contraseña debe tener al menos 8 caracteres.")
            }

            for fields, (value, min_length, error_message) in fields.items():
                if len(value) < min_length:
                    flash(error_message)
                    return redirect(url_for("register"))
                
            if not re.match(r'^[0-9]{10}$', telefono):
                flash("El número de celular debe tener solo 10 dígitos.")
                return redirect(url_for("register"))
            
            conn = create_connection()
            cursor = conn.cursor()

            # Comprobar si el correo ya existe
            cursor.execute("SELECT * FROM usuarios WHERE correo= %s" , (correo,))
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
            cursor.execute("INSERT INTO usuarios (nombre, apellido, nickname, correo, contrasena, telefono, residencia) VALUES (%s, %s, %s, %s, %s, %s, %s)", (nombre, apellido, nickname, correo, contraseña, telefono, residencia))
            conn.commit()
            flash("Usuario registrado con éxito")
            return redirect(url_for("login"))
        else:
            flash("Por favor, completa todos los campos")
            return redirect(url_for("register"))
    return render_template("register.html")

#Ruta para recuperar contraseña
@app.route("/olvido_contraseña", methods=["GET", "POST"])
def olvido():
    return render_template("forgot_password.html")

@app.route("/dashboard", methods=["GET", "POST"])
def dashboard():
    user_id = session.get("user")
    if not user_id:
        return redirect(url_for("login"))

    conn = create_connection()
    cursor = conn.cursor(dictionary=True)

    # Obtener datos del usuario
    cursor.execute("SELECT * FROM usuarios WHERE id_usuario = %s", (user_id,))
    user = cursor.fetchone()

    
    filtro = request.args.get("filtro")

    orden = "p.fecha_publicacion DESC" 
    if filtro == "populares":
        orden = "total_likes DESC"
    elif filtro == "comentados":
        orden = "total_comentarios DESC"

    # Obtener publicaciones
    query = f"""
        SELECT p.*, u.nickname, u.foto_perfil,
            (SELECT COUNT(*) FROM MeGusta WHERE id_publicacion = p.id_publicacion) AS total_likes,
            (SELECT COUNT(*) FROM Comentarios WHERE id_publicacion = p.id_publicacion) AS total_comentarios,
            EXISTS(
                SELECT 1 FROM MeGusta 
                WHERE id_usuario = %s AND id_publicacion = p.id_publicacion
            ) AS dio_like
        FROM Publicaciones p
        JOIN Usuarios u ON p.id_usuario = u.id_usuario
        ORDER BY {orden}
    """
    cursor.execute(query, (user_id,))
    publicaciones = cursor.fetchall()

    #Agregar comentarios a cada publicación
    for pub in publicaciones:
        cursor.execute("""
            SELECT c.*, u.nickname 
            FROM Comentarios c 
            JOIN Usuarios u ON c.id_usuario = u.id_usuario 
            WHERE c.id_publicacion = %s 
            ORDER BY c.fecha_comentario DESC
        """, (pub["id_publicacion"],))
        pub["comentarios"] = cursor.fetchall()

    close_connection(conn)

    return render_template("dashboard.html", user=user, publicaciones=publicaciones)

# Ruta para subir reportes
@app.route("/reportes", methods=["GET", "POST"])
def reportes():
    if "user" not in session:
        return redirect(url_for("login"))

    if request.method == "POST":
        texto = request.form.get("texto")
        imagen = request.files.get("imagen")
        ubicacion = request.form.get("ubicacion")
        id_usuario = session["user"]
        filtro = request.form.get("filtro", "")

        if not texto or not ubicacion or not imagen:
            flash("Faltan datos.")
            return redirect(url_for("dashboard"))

        if imagen and allowed_file(imagen.filename):
            # Nombre seguro y único para el archivo
            original_filename = secure_filename(imagen.filename)
            unique_filename = f"{uuid.uuid4().hex}_{original_filename}"
            save_path = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
            imagen.save(save_path)

            # Guardar en base de datos
            conn = create_connection()
            cursor = conn.cursor(dictionary=True)
            cursor.execute("""
                INSERT INTO publicaciones (id_usuario, descripcion, imagen, ubicacion)
                VALUES (%s, %s, %s, %s)
            """, (id_usuario, texto, unique_filename, ubicacion))
            conn.commit()
            close_connection(conn)
            flash("Reporte publicado con éxito")
        else:
            flash("Tipo de archivo no permitido. Solo se permiten imágenes.")
    return redirect(url_for("dashboard", filtro=filtro))

# Ruta para editar reportes
@app.route('/editar/<int:post_id>', methods=['POST'])
def editar_publicacion(post_id):
    user_id = session.get("user")
    if not user_id:
        return redirect(url_for("login"))

    descripcion = request.form['descripcion']
    ubicacion = request.form['ubicacion']
    filtro = request.form.get("filtro", "")

    conn = create_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id_usuario FROM Publicaciones WHERE id_publicacion = %s", (post_id,))
    resultado = cursor.fetchone()

    if not resultado or resultado[0] != user_id:
        flash("No tienes permiso para editar esta publicación.", "danger")
        return redirect(url_for("dashboard"))

    cursor.execute("""
        UPDATE Publicaciones 
        SET descripcion = %s, ubicacion = %s 
        WHERE id_publicacion = %s
    """, (descripcion, ubicacion, post_id))
    conn.commit()
    close_connection(conn)

    flash("Publicación actualizada correctamente.", "success")
    return redirect(url_for("dashboard", filtro=filtro))

# Ruta para eliminar reportes
@app.route('/eliminar/<int:post_id>', methods=['POST'])
def eliminar_publicacion(post_id):
    user_id = session.get("user")
    if not user_id:
        return redirect(url_for("login"))
    
    filtro = request.form.get("filtro", "")

    conn = create_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id_usuario, imagen FROM Publicaciones WHERE id_publicacion = %s", (post_id,))
    resultado = cursor.fetchone()

    if not resultado or resultado[0] != user_id:
        flash("No tienes permiso para eliminar esta publicación.", "danger")
        return redirect(url_for("dashboard" , filtro=filtro))

    nombre_imagen = resultado[1]
    ruta_imagen = os.path.join(app.config['UPLOAD_FOLDER'], nombre_imagen)
    if os.path.exists(ruta_imagen):
        os.remove(ruta_imagen)

    # Eliminar la publicación
    cursor.execute("DELETE FROM Publicaciones WHERE id_publicacion = %s", (post_id,))
    conn.commit()
    close_connection(conn)

    flash("Publicación eliminada correctamente.", "success")
    return redirect(url_for("dashboard" , filtro=filtro))


# Ruta de los likes
@app.route('/like/<int:post_id>', methods=['POST'])
def like_post(post_id):
    user_id = session.get("user")
    if not user_id:
        return redirect(url_for("login"))

    conn = create_connection()
    cursor = conn.cursor(dictionary=True)

    # Verificar si ya le dio like
    cursor.execute("""
        SELECT * FROM MeGusta WHERE id_usuario = %s AND id_publicacion = %s
    """, (user_id, post_id))
    existing_like = cursor.fetchone()

    if existing_like:
        cursor.execute("DELETE FROM MeGusta WHERE id_megusta = %s", (existing_like["id_megusta"],))
    else:
        cursor.execute("INSERT INTO MeGusta (id_usuario, id_publicacion) VALUES (%s, %s)", (user_id, post_id))

    conn.commit()
    close_connection(conn)

    filtro = request.args.get("filtro", "")
    return redirect(url_for('dashboard', filtro=filtro))

#Ruta para ingresar comentarios
@app.route('/comentarios/<int:post_id>', methods=['GET', 'POST'])
def comentarios(post_id):
    user_id = session.get("user")
    if not user_id:
        return redirect(url_for("login"))
    
    filtro = request.form.get("filtro", "")

    conn = create_connection()
    cursor = conn.cursor(dictionary=True)

    # Procesar comentario
    if request.method == "POST":
        comentario = request.form.get("comentario")
        if comentario:
            # Insertar el comentario en la base de datos
            cursor.execute("""
                INSERT INTO Comentarios (id_usuario, id_publicacion, contenido)
                VALUES (%s, %s, %s)
            """, (user_id, post_id, comentario))
            conn.commit()

    close_connection(conn)

    return redirect(url_for('dashboard', filtro=filtro))

#Ruta para editar comentarios
@app.route('/comentario/editar/<int:comentario_id>', methods=['POST'])
def editar_comentario(comentario_id):
    user_id = session.get("user")
    if not user_id:
        return redirect(url_for("login"))

    nuevo_texto = request.form.get("comentario")
    filtro = request.form.get("filtro", "")


    conn = create_connection()
    cursor = conn.cursor()

    # Solo permite editar si el comentario es del usuario
    cursor.execute("""
        UPDATE Comentarios 
        SET contenido = %s 
        WHERE id_comentario = %s AND id_usuario = %s
    """, (nuevo_texto, comentario_id, user_id))
    conn.commit()

    close_connection(conn)
    return redirect(url_for("dashboard", filtro=filtro))  

#Ruta para eliminar comentarios
@app.route('/comentario/eliminar/<int:comentario_id>', methods=['POST'])
def eliminar_comentario(comentario_id):
    user_id = session.get("user")
    if not user_id:
        return redirect(url_for("login"))

    filtro = request.form.get("filtro", "")

    conn = create_connection()
    cursor = conn.cursor()
    cursor.execute("""
        DELETE FROM Comentarios 
        WHERE id_comentario = %s AND id_usuario = %s
    """, (comentario_id, user_id))
    conn.commit()

    close_connection(conn)
    return redirect(url_for("dashboard", filtro=filtro))

#Ruta para seguir y dejar de seguir usuarios
@app.route('/seguir/<int:id_seguido>', methods=['POST'])
def toggle_seguir(id_seguido):
    id_seguidor = session.get('user')
    filtro = request.args.get('filtro')

    if not id_seguidor:
        flash("Debes iniciar sesión para seguir a otros usuarios.", "warning")
        return redirect(url_for('login'))

    if id_seguidor == id_seguido:
        flash("No puedes seguirte a ti mismo.", "danger")
        return redirect(url_for('perfil_usuario', id_usuario=id_seguido))

    conn = create_connection()
    if not conn:
        flash("No se pudo conectar a la base de datos.", "danger")
        return redirect(url_for('perfil_usuario', id_usuario=id_seguido))

    cursor = conn.cursor()

    cursor.execute("""
        SELECT 1 FROM Seguidores 
        WHERE id_seguidor = %s AND id_seguido = %s
    """, (id_seguidor, id_seguido))
    ya_sigue = cursor.fetchone()

    if ya_sigue:
        cursor.execute("""
            DELETE FROM Seguidores 
            WHERE id_seguidor = %s AND id_seguido = %s
        """, (id_seguidor, id_seguido))
        flash("Has dejado de seguir al usuario.", "info")
    else:
        cursor.execute("""
            INSERT IGNORE INTO Seguidores (id_seguidor, id_seguido)
            VALUES (%s, %s)
        """, (id_seguidor, id_seguido))
        flash("Ahora sigues a este usuario.", "success")

    conn.commit()
    cursor.close()
    close_connection(conn)

    return redirect(url_for('perfil_usuario', id_usuario=id_seguido, filtro=filtro ))

#Ruta para ver el perfil del usuario
@app.route('/perfil/<int:id_usuario>')
def perfil_usuario(id_usuario):
    id_actual = session.get('user')  
    filtro = request.args.get('filtro')

    conn = create_connection()
    if not conn:
        flash("Error al conectar con la base de datos", "danger")
        return redirect(url_for("dashboard"))

    cursor = conn.cursor(dictionary=True)

    # Obtener datos del usuario
    cursor.execute("SELECT * FROM Usuarios WHERE id_usuario = %s", (id_usuario,))
    usuario = cursor.fetchone()
    if not usuario:
        flash("El usuario no fue encontrado", "warning")
        cursor.close()
        close_connection(conn)
        return redirect(url_for("dashboard"))

    # Contar publicaciones
    cursor.execute("SELECT COUNT(*) AS total FROM Publicaciones WHERE id_usuario = %s", (id_usuario,))
    publicaciones_count = cursor.fetchone()['total']

    # Contar seguidores
    cursor.execute("SELECT COUNT(*) AS total FROM Seguidores WHERE id_seguido = %s", (id_usuario,))
    seguidores_count = cursor.fetchone()['total']

    # Contar seguidos
    cursor.execute("SELECT COUNT(*) AS total FROM Seguidores WHERE id_seguidor = %s", (id_usuario,))
    seguidos_count = cursor.fetchone()['total']

    # Obtener lista de seguidores 
    cursor.execute("""
        SELECT u.* FROM Seguidores s
        JOIN Usuarios u ON s.id_seguidor = u.id_usuario
        WHERE s.id_seguido = %s
    """, (id_usuario,))
    seguidores = cursor.fetchall()

    # Obtener lista de seguidos
    cursor.execute("""
        SELECT u.* FROM Seguidores s
        JOIN Usuarios u ON s.id_seguido = u.id_usuario
        WHERE s.id_seguidor = %s
    """, (id_usuario,))
    seguidos = cursor.fetchall()

    # Verificar si el usuario actual ya sigue al usuario del perfil
    ya_sigue = False
    if id_actual and id_actual != id_usuario:
        cursor.execute("""
            SELECT 1 FROM Seguidores
            WHERE id_seguidor = %s AND id_seguido = %s
        """, (id_actual, id_usuario))
        ya_sigue = cursor.fetchone() is not None

    cursor.close()
    close_connection(conn)

    return render_template('profile.html',
                        usuario_perfil=usuario,
                        publicaciones_count=publicaciones_count,
                        seguidores_count=seguidores_count,
                        seguidos_count=seguidos_count,
                        seguidores=seguidores,
                        seguidos=seguidos,
                        ya_sigue=ya_sigue,
                        filtro=filtro)

# Ruta para los ajustes
@app.route('/ajustes/informacion', methods=['GET', 'POST'])
def ajustes_informacion():
    if 'user' not in session:
        return redirect(url_for('login'))

    conn = create_connection()
    cursor = conn.cursor(dictionary=True)

    if request.method == 'POST':
        nombres = request.form['nombres']
        apellidos = request.form['apellidos']
        nickname = request.form['nickname']
        correo = request.form['correo']
        telefono = request.form['telefono']
        residencia = request.form['residencia']

        # Manejar foto de perfil
        foto = request.files.get('nueva_foto')
        if foto and allowed_file(foto.filename):
            # Generar nombre seguro y único
            original_filename = secure_filename(foto.filename)
            unique_filename = f"{uuid.uuid4().hex}_{original_filename}"
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)

            # Obtener foto actual del usuario
            cursor.execute("SELECT foto_perfil FROM Usuarios WHERE id_usuario = %s", (session['user'],))
            usuario = cursor.fetchone()
            foto_actual = usuario['foto_perfil']

            # Eliminar la foto anterior si no es la predeterminada
            if foto_actual != 'default.jpg':
                foto_actual_path = os.path.join(app.config['UPLOAD_FOLDER'], foto_actual)
                if os.path.exists(foto_actual_path):
                    os.remove(foto_actual_path)

            # Guardar la nueva foto
            foto.save(filepath)

            # Actualizar datos incluyendo nueva foto
            cursor.execute(""" 
                UPDATE Usuarios 
                SET nombre = %s, apellido = %s, nickname = %s, correo = %s, telefono = %s,
                    residencia = %s, foto_perfil = %s
                WHERE id_usuario = %s
            """, (nombres, apellidos, nickname, correo, telefono, residencia, unique_filename, session['user']))
            flash('Información y foto de perfil actualizadas correctamente.', 'success')
        else:
            # Actualizar solo los datos personales si no hay foto nueva
            cursor.execute("""
                UPDATE Usuarios 
                SET nombre = %s, apellido = %s, nickname = %s, correo = %s, telefono = %s,
                    residencia = %s
                WHERE id_usuario = %s
            """, (nombres, apellidos, nickname, correo, telefono, residencia, session['user']))
            flash('Información actualizada correctamente.', 'success')

        conn.commit()

    cursor.execute("SELECT * FROM Usuarios WHERE id_usuario = %s", (session['user'],))
    usuario = cursor.fetchone()
    close_connection(conn)

    return render_template('settings.html', usuario=usuario)


#Ruta para actualizar la información del usuario
@app.route('/actualizar_usuario', methods=['POST'])
def actualizar_usuario():
    if 'user' not in session:
        return redirect(url_for('login'))

    id_usuario = session['user']
    conn = create_connection()
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE Usuarios SET nombre = %s, apellido = %s, nickname = %s, correo = %s, telefono = %s, residencia = %s
        WHERE id_usuario = %s
    """, (
        request.form['nombres'],
        request.form['apellidos'],
        request.form['nickname'],
        request.form['correo'],
        request.form['telefono'],
        request.form['residencia'],
        id_usuario
    ))

    conn.commit()
    close_connection(conn)

    flash('Datos actualizados exitosamente.', 'success')
    return redirect(url_for('ajustes_informacion'))


@app.route('/mis_reportes')
def mis_reportes():
    if 'user' not in session:
        return redirect(url_for('login'))

    conn = create_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
        SELECT descripcion, fecha_publicacion, estado 
        FROM Publicaciones 
        WHERE id_usuario = %s 
        ORDER BY fecha_publicacion DESC
    """, (session['user'],))

    reportes = cursor.fetchall()
    close_connection(conn)

    return render_template('reports.html', reportes=reportes)


if __name__ == '__main__':
    app.run(debug=True)