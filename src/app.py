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
                    return redirect(url_for("registro"))
                
            if not re.match(r'^[0-9]{10}$', telefono):
                flash("El número de celular debe tener solo 10 dígitos.")
                return redirect(url_for("registro"))
            
            conn = create_connection()
            cursor = conn.cursor()

            # Comprueba si el correo ya existe
            cursor.execute("SELECT * FROM usuarios WHERE correo= %s" , (correo,))
            user_by_email = cursor.fetchone()

            if user_by_email:
                flash("el correo electrouco ya existe")
                return redirect(url_for("registro"))
            else:
                # comprueba si nickname ya existe
                cursor.execute("SELECT * FROM usuarios WHERE nickname = %s", (nickname,))
                user_by_nickname = cursor.fetchone()

            if user_by_nickname:
                flash("el nickname ya existe")
                return redirect(url_for("registro"))
            
            #guarda el usuario en la base de datos
            cursor.execute("INSERT INTO usuarios (nombre, apellido, nickname, correo, contrasena, telefono, residencia) VALUES (%s, %s, %s, %s, %s, %s, %s)", (nombre, apellido, nickname, correo, contraseña, telefono, residencia))
            conn.commit()
            flash("Usuario registrado con éxito")
            return redirect(url_for("login"))
        else:
            flash("Por favor, completa todos los campos")
            return redirect(url_for("registro"))
    return render_template("register.html")

#Ruta para recuperar contraseña
@app.route('/olvide-contrasena', methods=['GET', 'POST'])
def olvido():
    if request.method == 'POST':
        correo = request.form['correo']
        codigo = request.form['codigo']
        nueva_contra = request.form['nueva_contrasena']

        conn = create_connection()
        cursor = conn.cursor(dictionary=True)

        # Validar correo
        cursor.execute("SELECT id_usuario FROM Usuarios WHERE correo = %s", (correo,))
        usuario = cursor.fetchone()

        if usuario:
            id_usuario = usuario['id_usuario']

            # Validar código
            cursor.execute("""
                SELECT * FROM CodigosSeguridad 
                WHERE id_usuario = %s AND codigo = %s AND usado = FALSE AND (expiracion IS NULL OR expiracion > NOW())
            """, (id_usuario, codigo))
            codigo_valido = cursor.fetchone()

            if codigo_valido:
                # Actualizar la contraseña sin hash
                cursor.execute("""
                    UPDATE Usuarios SET contrasena = %s WHERE id_usuario = %s
                """, (nueva_contra, id_usuario))

                # Eliminar el código
                cursor.execute("DELETE FROM CodigosSeguridad WHERE id_codigo = %s", (codigo_valido['id_codigo'],))

                conn.commit()
                flash("Contraseña actualizada correctamente. Inicia sesión.", "success")
                close_connection(conn)
                return redirect(url_for('login'))

            else:
                flash("Código inválido o vencido.", "danger")
        else:
            flash("Correo no registrado.", "danger")

        close_connection(conn)

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

    # Filtro para ordenar publicaciones
    filtro = request.args.get("filtro")
    orden = "p.fecha_publicacion DESC"
    if filtro == "populares":
        orden = "total_likes DESC"
    elif filtro == "comentados":
        orden = "total_comentarios DESC"

    # Obtiene las publicaciones con conteo de likes y comentarios
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

    # Agrega los comentarios a cada publicación
    for pub in publicaciones:
        cursor.execute("""
            SELECT c.*, u.nickname 
            FROM Comentarios c 
            JOIN Usuarios u ON c.id_usuario = u.id_usuario 
            WHERE c.id_publicacion = %s 
            ORDER BY c.fecha_comentario DESC
        """, (pub["id_publicacion"],))
        pub["comentarios"] = cursor.fetchall()

    # Obtiene las 4 publicaciones más likeadas (tendencias)
    cursor.execute("""
        SELECT p.id_publicacion, p.descripcion, COUNT(m.id_megusta) AS total_megusta
        FROM Publicaciones p
        LEFT JOIN MeGusta m ON p.id_publicacion = m.id_publicacion
        GROUP BY p.id_publicacion
        ORDER BY total_megusta DESC
        LIMIT 4
    """)
    tendencias = cursor.fetchall()

    close_connection(conn)

    return render_template("dashboard.html", user=user, publicaciones=publicaciones, tendencias=tendencias)

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

    cursor.execute("""
        SELECT * FROM MeGusta WHERE id_usuario = %s AND id_publicacion = %s
    """, (user_id, post_id))
    existing_like = cursor.fetchone()

    if existing_like:
        cursor.execute("DELETE FROM MeGusta WHERE id_megusta = %s", (existing_like["id_megusta"],))
    else:
        cursor.execute("INSERT INTO MeGusta (id_usuario, id_publicacion) VALUES (%s, %s)", (user_id, post_id))

        # Obtener autor y nickname
        cursor.execute("SELECT id_usuario FROM Publicaciones WHERE id_publicacion = %s", (post_id,))
        autor = cursor.fetchone()

        cursor.execute("SELECT nickname FROM Usuarios WHERE id_usuario = %s", (user_id,))
        nick = cursor.fetchone()

        if autor and nick and autor["id_usuario"] != user_id:
            # Verificar preferencias
            cursor.execute("""
                SELECT not_reacciones FROM PreferenciasNotificaciones WHERE id_usuario = %s
            """, (autor["id_usuario"],))
            pref = cursor.fetchone()

            if pref and pref["not_reacciones"]:
                cursor.execute("""
                    INSERT INTO Notificaciones (id_usuario, tipo_evento, id_referencia, mensaje)
                    VALUES (%s, 'reaccion', %s, %s)
                """, (
                    autor["id_usuario"],
                    post_id,
                    f"{nick['nickname']} le dio like a tu publicación."
                ))

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

    if request.method == "POST":
        comentario = request.form.get("comentario")
        if comentario:
            cursor.execute("""
                INSERT INTO Comentarios (id_usuario, id_publicacion, contenido)
                VALUES (%s, %s, %s)
            """, (user_id, post_id, comentario))

            cursor.execute("SELECT id_usuario FROM Publicaciones WHERE id_publicacion = %s", (post_id,))
            autor = cursor.fetchone()

            cursor.execute("SELECT nickname FROM Usuarios WHERE id_usuario = %s", (user_id,))
            nick = cursor.fetchone()

            if autor and nick and autor["id_usuario"] != user_id:
                cursor.execute("""
                    SELECT not_reacciones FROM PreferenciasNotificaciones WHERE id_usuario = %s
                """, (autor["id_usuario"],))
                pref = cursor.fetchone()

                if pref and pref["not_reacciones"]:
                    cursor.execute("""
                        INSERT INTO Notificaciones (id_usuario, tipo_evento, id_referencia, mensaje)
                        VALUES (%s, 'comentario', %s, %s)
                    """, (
                        autor["id_usuario"],
                        post_id,
                        f"{nick['nickname']} comentó en tu publicación."
                    ))

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
    cursor = conn.cursor(dictionary=True)

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

        cursor.execute("SELECT nickname FROM Usuarios WHERE id_usuario = %s", (id_seguidor,))
        nick = cursor.fetchone()

        if nick:
            cursor.execute("""
                SELECT not_seguidos FROM PreferenciasNotificaciones WHERE id_usuario = %s
            """, (id_seguido,))
            pref = cursor.fetchone()

            if pref and pref["not_seguidos"]:
                cursor.execute("""
                    INSERT INTO Notificaciones (id_usuario, tipo_evento, id_referencia, mensaje)
                    VALUES (%s, 'seguido', %s, %s)
                """, (
                    id_seguido,
                    id_seguidor,
                    f"{nick['nickname']} comenzó a seguirte."
                ))

    conn.commit()
    close_connection(conn)

    return redirect(url_for('perfil_usuario', id_usuario=id_seguido, filtro=filtro))


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

@app.route('/ajustes/<seccion>', methods=['GET', 'POST'])
def ajustes(seccion):
    if 'user' not in session:
        return redirect(url_for('login'))
    
    filtro = request.args.get("filtro")
    conn = create_connection()
    cursor = conn.cursor(dictionary=True)

    # Obtiene datos del usuario
    cursor.execute("SELECT * FROM Usuarios WHERE id_usuario = %s", (session['user'],))
    usuario = cursor.fetchone()

    # Variables comunes
    ultimo_inicio_sesion = None
    ip_inicio_sesion = None
    ultimo_cambio_contrasena = None
    ip_cambio_contrasena = None
    codigos = []
    preferencias = {
        'not_seguidos': True,
        'not_reportes': True,
        'not_reacciones': True,
        'not_personalizadas': True
    }

    # --- INFORMACIÓN ---
    if request.method == 'POST' and seccion == 'informacion':
        nombres = request.form['nombres']
        apellidos = request.form['apellidos']
        nickname = request.form['nickname']
        correo = request.form['correo']
        telefono = request.form['telefono']
        residencia = request.form['residencia']
        foto = request.files.get('nueva_foto')

        if not all([nombres.strip(), apellidos.strip(), nickname.strip(), correo.strip(), telefono.strip(), residencia.strip()]):
            flash('Todos los campos son obligatorios.', 'danger')
            close_connection(conn)
            return redirect(url_for('ajustes', seccion='informacion'))

        cursor.execute("SELECT id_usuario FROM Usuarios WHERE correo = %s AND id_usuario != %s", (correo, session['user']))
        if cursor.fetchone():
            flash('El correo ya está en uso por otro usuario.', 'danger')
            close_connection(conn)
            return redirect(url_for('ajustes', seccion='informacion'))

        cursor.execute("SELECT id_usuario FROM Usuarios WHERE nickname = %s AND id_usuario != %s", (nickname, session['user']))
        if cursor.fetchone():
            flash('El nickname ya está en uso por otro usuario.', 'danger')
            close_connection(conn)
            return redirect(url_for('ajustes', seccion='informacion'))

        if foto and allowed_file(foto.filename):
            original_filename = secure_filename(foto.filename)
            unique_filename = f"{uuid.uuid4().hex}_{original_filename}"
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)

            if usuario['foto_perfil'] != 'default.jpg':
                foto_actual_path = os.path.join(app.config['UPLOAD_FOLDER'], usuario['foto_perfil'])
                if os.path.exists(foto_actual_path):
                    os.remove(foto_actual_path)

            foto.save(filepath)
            foto_final = unique_filename
        else:
            foto_final = usuario['foto_perfil']

        cursor.execute("""
            UPDATE Usuarios
            SET nombre = %s, apellido = %s, nickname = %s, correo = %s, telefono = %s,
                residencia = %s, foto_perfil = %s
            WHERE id_usuario = %s
        """, (nombres, apellidos, nickname, correo, telefono, residencia, foto_final, session['user']))
        conn.commit()
        flash('Información actualizada correctamente.', 'success')

        # Recarga los datos actualizados
        cursor.execute("SELECT * FROM Usuarios WHERE id_usuario = %s", (session['user'],))
        usuario = cursor.fetchone()

    # --- SEGURIDAD ---
    elif seccion == 'seguridad':
        cursor.execute("""
            SELECT tipo_evento, fecha_evento, ip_dispositivo
            FROM RegistroActividad
            WHERE id_usuario = %s
            AND tipo_evento IN ('inicio de sesión', 'cambio de contraseña')
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

        if request.method == 'POST':
            accion = request.form.get('accion')

            if accion == 'generar':
                cursor.execute("DELETE FROM CodigosSeguridad WHERE id_usuario = %s", (session['user'],))
                for _ in range(4):
                    codigo = uuid.uuid4().hex[:10]
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

            elif accion == 'cambiar_contrasena':
                contrasena_actual = request.form['contrasena_actual']
                nueva_contrasena = request.form['nueva_contrasena']
                confirmar_contrasena = request.form['confirmar_contrasena']

                if nueva_contrasena != confirmar_contrasena:
                    flash('Las nuevas contraseñas no coinciden.', 'warning')
                else:
                    cursor.execute("SELECT contrasena FROM Usuarios WHERE id_usuario = %s", (session['user'],))
                    resultado = cursor.fetchone()

                    if not resultado or resultado['contrasena'] != contrasena_actual:
                        flash('La contraseña actual no es correcta.', 'danger')
                    else:
                        cursor.execute("UPDATE Usuarios SET contrasena = %s WHERE id_usuario = %s", (nueva_contrasena, session['user']))
                        cursor.execute("""
                            INSERT INTO RegistroActividad (id_usuario, tipo_evento, ip_dispositivo)
                            VALUES (%s, 'cambio de contraseña', %s)
                        """, (session['user'], request.remote_addr))
                        conn.commit()
                        flash('Contraseña actualizada correctamente.', 'success')

            elif accion == 'eliminar_cuenta':
                contrasena_confirmacion = request.form['contrasena_confirmacion']

                cursor.execute("SELECT contrasena FROM Usuarios WHERE id_usuario = %s", (session['user'],))
                resultado = cursor.fetchone()

                if not resultado or resultado['contrasena'] != contrasena_confirmacion:
                    flash('La contraseña ingresada es incorrecta.', 'danger')
                else:
                    # Elimina foto perfil
                    if usuario['foto_perfil'] != 'default.jpg':
                        ruta_foto = os.path.join(app.config['UPLOAD_FOLDER'], usuario['foto_perfil'])
                        if os.path.exists(ruta_foto):
                            os.remove(ruta_foto)

                    # Elimina fotos de publicaciones
                    cursor.execute("SELECT imagen FROM Publicaciones WHERE id_usuario = %s", (session['user'],))
                    for pub in cursor.fetchall():
                        if pub['imagen']:
                            ruta = os.path.join(app.config['UPLOAD_FOLDER'], pub['imagen'])
                            if os.path.exists(ruta):
                                os.remove(ruta)

                    # Elimina registros relacionados
                    cursor.execute("DELETE FROM CodigosSeguridad WHERE id_usuario = %s", (session['user'],))
                    cursor.execute("DELETE FROM RegistroActividad WHERE id_usuario = %s", (session['user'],))
                    cursor.execute("DELETE FROM Comentarios WHERE id_usuario = %s", (session['user'],))
                    cursor.execute("DELETE FROM Publicaciones WHERE id_usuario = %s", (session['user'],))
                    cursor.execute("DELETE FROM Usuarios WHERE id_usuario = %s", (session['user'],))
                    conn.commit()

                    session.clear()
                    flash('Tu cuenta ha sido eliminada permanentemente.', 'success')
                    return redirect(url_for('login'))

        # Obteniene los códigos actuales
        cursor.execute("SELECT codigo FROM CodigosSeguridad WHERE id_usuario = %s", (session['user'],))
        codigos = [row['codigo'] for row in cursor.fetchall()]

    # --- NOTIFICACIONES ---
    elif seccion == 'notificaciones':
        if request.method == 'POST':
            not_seguidos = 'seguido' in request.form
            not_reportes = 'reporte' in request.form
            not_reacciones = 'reaccion' in request.form
            not_personalizadas = 'personalizada' in request.form

            cursor.execute("""
                INSERT INTO PreferenciasNotificaciones (id_usuario, not_seguidos, not_reportes, not_reacciones, not_personalizadas)
                VALUES (%s, %s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE
                    not_seguidos = VALUES(not_seguidos),
                    not_reportes = VALUES(not_reportes),
                    not_reacciones = VALUES(not_reacciones),
                    not_personalizadas = VALUES(not_personalizadas)
            """, (session['user'], not_seguidos, not_reportes, not_reacciones, not_personalizadas))
            conn.commit()
            flash('Preferencias actualizadas correctamente.', 'success')

        cursor.execute("""
            SELECT not_seguidos, not_reportes, not_reacciones, not_personalizadas
            FROM PreferenciasNotificaciones
            WHERE id_usuario = %s
        """, (session['user'],))
        resultado = cursor.fetchone()
        if resultado:
            preferencias = resultado

    close_connection(conn)

    return render_template(
        'settings.html',
        usuario=usuario,
        seccion_activa=seccion,
        ultimo_inicio_sesion=ultimo_inicio_sesion,
        ip_inicio_sesion=ip_inicio_sesion,
        ultimo_cambio_contrasena=ultimo_cambio_contrasena,
        ip_cambio_contrasena=ip_cambio_contrasena,
        codigos=codigos,
        preferencias=preferencias,
        filtro=filtro
    )

#Ruta para historial de reportes
@app.route('/mis_reportes')
def mis_reportes():
    if 'user' not in session:
        return redirect(url_for('login'))
    
    filtro = request.args.get("filtro")
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

    return render_template('reports.html', reportes=reportes, filtro=filtro)

#Ruta de las notificaciones
@app.route('/mis_notificaciones')
def mis_notificaciones():
    user_id = session.get("user")
    if not user_id:
        flash("Debes iniciar sesión para ver tus notificaciones.", "warning")
        return redirect(url_for("login"))

    filtro = request.args.get("filtro")
    conn = create_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
        SELECT id_notificacion, tipo_evento, mensaje, id_referencia, fecha_notificacion
        FROM Notificaciones
        WHERE id_usuario = %s
        ORDER BY fecha_notificacion DESC
    """, (user_id,))
    
    notificaciones = cursor.fetchall()

    # Formatear fecha para evitar errores en Jinja
    for notif in notificaciones:
        notif["fecha_formateada"] = notif["fecha_notificacion"].strftime("%d/%m/%Y %H:%M")

    close_connection(conn)

    return render_template('notifications.html', notificaciones=notificaciones , filtro=filtro)

@app.route('/eliminar_notificacion/<int:id_notificacion>', methods=['POST'])
def eliminar_notificacion(id_notificacion):
    user_id = session.get("user")
    if not user_id:
        flash("Debes iniciar sesión.", "warning")
        return redirect(url_for("login"))

    filtro = request.args.get("filtro")
    conn = create_connection()
    cursor = conn.cursor()
    
    # Elimina la notificación solo si pertenece al usuario
    cursor.execute("""
        DELETE FROM Notificaciones
        WHERE id_notificacion = %s AND id_usuario = %s
    """, (id_notificacion, user_id))
    conn.commit()
    close_connection(conn)

    flash("Notificación eliminada correctamente.", "success")
    return redirect(url_for("mis_notificaciones" , filtro=filtro))


if __name__ == '__main__':
    app.run(debug=True)