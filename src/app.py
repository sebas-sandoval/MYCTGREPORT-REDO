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

# Ruta del login
@app.route("/", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]

        conn = create_connection()
        cursor = conn.cursor(dictionary=True)

        # Verifica si el correo y la contraseña coinciden
        cursor.execute("SELECT * FROM usuarios WHERE correo = %s AND contrasena = %s", (email, password))
        user = cursor.fetchone()

        if user:
            # Guarda la sesión
            session["user"] = user["id_usuario"]

            # Registra el inicio de sesión
            ip = request.remote_addr
            cursor.execute("""
                INSERT INTO RegistroActividad (id_usuario, tipo_evento, ip_dispositivo)
                VALUES (%s, 'inicio de sesión', %s)
            """, (user["id_usuario"], ip))
            conn.commit()

            close_connection(conn)
            return redirect(url_for("dashboard"))
        else:
            close_connection(conn)
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

        #valida los datos
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

            # Comprueba si el correo ya existe
            cursor.execute("SELECT * FROM usuarios WHERE correo= %s" , (correo,))
            user_by_email = cursor.fetchone()

            if user_by_email:
                flash("el correo electrouco ya existe")
                return redirect(url_for("register"))
            else:
                # comprueba si nickname ya existe
                cursor.execute("SELECT * FROM usuarios WHERE nickname = %s", (nickname,))
                user_by_nickname = cursor.fetchone()

            if user_by_nickname:
                flash("el nickname ya existe")
                return redirect(url_for("register"))
            
            #guarda el usuario en la base de datos
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

    # Obtiene los datos del usuario
    cursor.execute("SELECT * FROM usuarios WHERE id_usuario = %s", (user_id,))
    user = cursor.fetchone()

    
    filtro = request.args.get("filtro")

    orden = "p.fecha_publicacion DESC" 
    if filtro == "populares":
        orden = "total_likes DESC"
    elif filtro == "comentados":
        orden = "total_comentarios DESC"

    # Obtiene las publicaciones
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

    #Agrega los comentarios a cada publicación
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

    # Elimina la publicación
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

    # Verifica si ya le dio like
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

    # Procesa eñ comentario
    if request.method == "POST":
        comentario = request.form.get("comentario")
        if comentario:
            # Inserta el comentario en la base de datos
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

    # Obteniene datos del usuario
    cursor.execute("SELECT * FROM Usuarios WHERE id_usuario = %s", (id_usuario,))
    usuario = cursor.fetchone()
    if not usuario:
        flash("El usuario no fue encontrado", "warning")
        cursor.close()
        close_connection(conn)
        return redirect(url_for("dashboard"))

    # Contador de las publicaciones
    cursor.execute("SELECT COUNT(*) AS total FROM Publicaciones WHERE id_usuario = %s", (id_usuario,))
    publicaciones_count = cursor.fetchone()['total']

    # Contador de los seguidores
    cursor.execute("SELECT COUNT(*) AS total FROM Seguidores WHERE id_seguido = %s", (id_usuario,))
    seguidores_count = cursor.fetchone()['total']

    # Contar de los seguidos
    cursor.execute("SELECT COUNT(*) AS total FROM Seguidores WHERE id_seguidor = %s", (id_usuario,))
    seguidos_count = cursor.fetchone()['total']

    # Obtiene lista de seguidores 
    cursor.execute("""
        SELECT u.* FROM Seguidores s
        JOIN Usuarios u ON s.id_seguidor = u.id_usuario
        WHERE s.id_seguido = %s
    """, (id_usuario,))
    seguidores = cursor.fetchall()

    # Obtiene lista de seguidos
    cursor.execute("""
        SELECT u.* FROM Seguidores s
        JOIN Usuarios u ON s.id_seguido = u.id_usuario
        WHERE s.id_seguidor = %s
    """, (id_usuario,))
    seguidos = cursor.fetchall()

    # Verifica si el usuario actual ya sigue al usuario del perfil
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
@app.route('/ajustes/<seccion>', methods=['GET', 'POST'])
def ajustes(seccion):
    if 'user' not in session:
        return redirect(url_for('login'))

    conn = create_connection()
    cursor = conn.cursor(dictionary=True)

    # Obtiene los datos del usuario
    cursor.execute("SELECT * FROM Usuarios WHERE id_usuario = %s", (session['user'],))
    usuario = cursor.fetchone()

    # Variables por defecto para seguridad
    ultimo_inicio_sesion = None
    ip_inicio_sesion = None
    ultimo_cambio_contrasena = None
    ip_cambio_contrasena = None
    codigos = []

    if request.method == 'POST' and seccion == 'informacion':

        nombres = request.form['nombres']
        apellidos = request.form['apellidos']
        nickname = request.form['nickname']
        correo = request.form['correo']
        telefono = request.form['telefono']
        residencia = request.form['residencia']
        foto = request.files.get('nueva_foto')

        # Valida que ningún campo requerido esté vacío
        if not all([nombres.strip(), apellidos.strip(), nickname.strip(), correo.strip(), telefono.strip(), residencia.strip()]):
            flash('Todos los campos son obligatorios. Por favor, completa todos los campos.', 'danger')
            close_connection(conn)
            return redirect(url_for('ajustes', seccion='informacion'))

        # Valida si el correo ya existe en otro usuario
        cursor.execute("SELECT id_usuario FROM Usuarios WHERE correo = %s AND id_usuario != %s", (correo, session['user']))
        if cursor.fetchone():
            flash('El correo ya está en uso por otro usuario.', 'danger')
            close_connection(conn)
            return redirect(url_for('ajustes', seccion='informacion'))

        # Valida si el nickname ya existe en otro usuario
        cursor.execute("SELECT id_usuario FROM Usuarios WHERE nickname = %s AND id_usuario != %s", (nickname, session['user']))
        if cursor.fetchone():
            flash('El nickname ya está en uso por otro usuario.', 'danger')
            close_connection(conn)
            return redirect(url_for('ajustes', seccion='informacion'))

        # Maneja foto de perfil si es que se sube una nueva
        if foto and allowed_file(foto.filename):
            original_filename = secure_filename(foto.filename)
            unique_filename = f"{uuid.uuid4().hex}_{original_filename}"
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)

            # Elimina la foto actual si no es la predeterminada
            foto_actual = usuario['foto_perfil']
            if foto_actual != 'default.jpg':
                foto_actual_path = os.path.join(app.config['UPLOAD_FOLDER'], foto_actual)
                if os.path.exists(foto_actual_path):
                    os.remove(foto_actual_path)

            foto.save(filepath)

            # Actualiza con nueva foto
            cursor.execute("""
                UPDATE Usuarios
                SET nombre = %s, apellido = %s, nickname = %s, correo = %s, telefono = %s,
                    residencia = %s, foto_perfil = %s
                WHERE id_usuario = %s
            """, (nombres, apellidos, nickname, correo, telefono, residencia, unique_filename, session['user']))
            flash('Información y foto de perfil actualizadas correctamente.', 'success')
        else:
            cursor.execute("""
                UPDATE Usuarios
                SET nombre = %s, apellido = %s, nickname = %s, correo = %s, telefono = %s,
                    residencia = %s
                WHERE id_usuario = %s
            """, (nombres, apellidos, nickname, correo, telefono, residencia, session['user']))
            flash('Información actualizada correctamente.', 'success')

        conn.commit()

        # Recarga datos del usuario
        cursor.execute("SELECT * FROM Usuarios WHERE id_usuario = %s", (session['user'],))
        usuario = cursor.fetchone()

    elif seccion == 'seguridad':
        # Obtiene eventos recientes de seguridad
        cursor.execute("""
            SELECT tipo_evento, fecha_evento, ip_dispositivo
            FROM RegistroActividad
            WHERE id_usuario = %s
            AND tipo_evento IN ('inicio de sesi\u00f3n', 'cambio de contrase\u00f1a')
            ORDER BY fecha_evento DESC
        """, (session['user'],))
        eventos = cursor.fetchall()

        for evento in eventos:
            if evento['tipo_evento'] == 'inicio de sesión' and not ultimo_inicio_sesion:
                ultimo_inicio_sesion = evento['fecha_evento']
                ip_inicio_sesion = evento['ip_dispositivo']
            elif evento['tipo_evento'] == 'cambio de contraseña' and not ultimo_cambio_contrasena:
                ultimo_cambio_contrasena = evento['fecha_evento']
                ip_cambio_contrasena = evento['ip_dispositivo']
            if ultimo_inicio_sesion and ultimo_cambio_contrasena:
                break

        # Procesa acciones para códigos de seguridad
        if request.method == 'POST':
            accion = request.form.get('accion')
            if accion == 'generar':
                cursor.execute("DELETE FROM CodigosSeguridad WHERE id_usuario = %s", (session['user'],))
                # Genera 4 códigos de seguridad únicos
                for _ in range(4):
                    codigo = ''.join(uuid.uuid4().hex[:10])  # Genera un código único de 10 caracteres
                    cursor.execute("""
                        INSERT INTO CodigosSeguridad (id_usuario, codigo, expiracion)
                        VALUES (%s, %s, NOW() + INTERVAL 1 YEAR)
                    """, (session['user'], codigo))
                conn.commit()
                flash('Se generaron nuevos códigos de seguridad.', 'success')
            elif accion == 'eliminar':
                cursor.execute("DELETE FROM CodigosSeguridad WHERE id_usuario = %s", (session['user'],))
                conn.commit()
                flash('Códigos de seguridad eliminados.', 'warning')

        cursor.execute("SELECT codigo FROM CodigosSeguridad WHERE id_usuario = %s", (session['user'],))
        codigos = [row['codigo'] for row in cursor.fetchall()]

    close_connection(conn)

    return render_template(
        'settings.html',
        usuario=usuario,
        seccion_activa=seccion,
        ultimo_inicio_sesion=ultimo_inicio_sesion,
        ip_inicio_sesion=ip_inicio_sesion,
        ultimo_cambio_contrasena=ultimo_cambio_contrasena,
        ip_cambio_contrasena=ip_cambio_contrasena,
        codigos=codigos
    )

#Ruta para historial de reportes
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