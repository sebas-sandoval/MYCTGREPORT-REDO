# 🏙️ MYCTGREPORT

Una aplicación web desarrollada con **Flask** que permite a los ciudadanos **reportar problemas en su ciudad**, recibir **retroalimentación**, e interactuar con otros usuarios mediante **likes y comentarios**. Además, los **administradores pueden gestionar y actualizar el estado de cada publicación**.

---

## 🚀 Características

### 👤 Usuarios
- Registro e inicio de sesión
- Edición del perfil (nombre, foto, descripción, etc.)
- Seguridad mediante sesiones y hash de contraseñas

### 📝 Publicaciones
- Crear publicaciones sobre problemas urbanos (baches, luminarias, basuras, etc.)
- Adjuntar imágenes o descripciones
- Dar like a otras publicaciones
- Comentar en publicaciones
- Las publicaciones pueden tener diferentes estados:
  - `Sin revisar`
  - `En proceso`
  - `Completado`

### 🔐 Administración
- Los administradores pueden:
  - Validar o rechazar publicaciones
  - Cambiar el estado de los reportes
  - Moderar comentarios si es necesario

---

## 🛠️ Tecnologías

- **Python 3**
- **Flask**
- **Flask-Login**
- **Flask-SQLAlchemy**
- **Jinja2**
- **SQLite**
- **Bootstrap 5**

---

## ⚙️ Instalación

1. Clona el repositorio:
   ```bash
   git clone https://github.com/sebas-sandoval/MYCTGREPORT-REDO.git
   cd MYCTGREPORT-REDO
   ```

2. Crea un entorno virtual e instala las dependencias:
   ```bash
   python -m venv venv
   source venv/Scripts/activate
   pip install -r requirements.txt
   ```

3. Ejecuta la aplicación:
   ```bash
   flask run
   ```

---

## 🛡️ Roles

- **Usuario común:** puede publicar, comentar, dar likes y editar su perfil.
- **Administrador:** además de todo lo anterior, puede cambiar el estado de las publicaciones y moderar la plataforma.