import csv
import io
import os
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, Response, flash, session, send_from_directory
import sqlite3

app = Flask(__name__)
app.secret_key = 'clave_secreta_colegio' 

UPLOAD_FOLDER = 'static/uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

def get_db_connection():
    conn = sqlite3.connect('aulanova.db')
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    conn.execute('''
        CREATE TABLE IF NOT EXISTS Roles (
            id_rol INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre_rol TEXT NOT NULL
        )
    ''')
    conn.execute('''
        CREATE TABLE IF NOT EXISTS Usuarios (
            id_usuario INTEGER PRIMARY KEY AUTOINCREMENT,
            nombres TEXT NOT NULL,
            apellidos TEXT NOT NULL,
            correo TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            dni TEXT,
            grado TEXT,
            seccion TEXT,
            id_rol INTEGER,
            estado INTEGER DEFAULT 1,
            FOREIGN KEY (id_rol) REFERENCES Roles (id_rol)
        )
    ''')
    conn.execute('''
        CREATE TABLE IF NOT EXISTS Cursos (
            id_curso INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre_curso TEXT NOT NULL,
            grado TEXT NOT NULL,
            id_docente INTEGER,
            FOREIGN KEY (id_docente) REFERENCES Usuarios (id_usuario),
            UNIQUE(nombre_curso, grado)
        )
    ''')
    conn.execute('''
        CREATE TABLE IF NOT EXISTS Asistencia (
            id_asistencia INTEGER PRIMARY KEY AUTOINCREMENT,
            id_alumno INTEGER,
            fecha TEXT NOT NULL,
            estado TEXT NOT NULL,
            FOREIGN KEY (id_alumno) REFERENCES Usuarios (id_usuario),
            UNIQUE(id_alumno, fecha)
        )
    ''')
    conn.execute('''
        CREATE TABLE IF NOT EXISTS Calificaciones (
            id_calificacion INTEGER PRIMARY KEY AUTOINCREMENT,
            id_alumno INTEGER,
            id_curso INTEGER,
            periodo TEXT NOT NULL,
            nota REAL,
            FOREIGN KEY (id_alumno) REFERENCES Usuarios (id_usuario),
            FOREIGN KEY (id_curso) REFERENCES Cursos (id_curso),
            UNIQUE(id_alumno, id_curso, periodo)
        )
    ''')
    conn.execute('''
        CREATE TABLE IF NOT EXISTS Comunicados (
            id_comunicado INTEGER PRIMARY KEY AUTOINCREMENT,
            titulo TEXT NOT NULL,
            mensaje TEXT NOT NULL,
            fecha TEXT NOT NULL,
            autor TEXT NOT NULL
        )
    ''')
    conn.execute('''
        CREATE TABLE IF NOT EXISTS Tareas (
            id_tarea INTEGER PRIMARY KEY AUTOINCREMENT,
            id_curso INTEGER,
            titulo TEXT NOT NULL,
            descripcion TEXT NOT NULL,
            fecha_entrega TEXT NOT NULL,
            archivo_adjunto TEXT,
            FOREIGN KEY (id_curso) REFERENCES Cursos (id_curso)
        )
    ''')
    conn.execute('''
        CREATE TABLE IF NOT EXISTS EntregasTareas (
            id_entrega INTEGER PRIMARY KEY AUTOINCREMENT,
            id_tarea INTEGER,
            id_alumno INTEGER,
            archivo_alumno TEXT NOT NULL,
            fecha_entrega TEXT NOT NULL,
            nota_tarea REAL,
            FOREIGN KEY (id_tarea) REFERENCES Tareas (id_tarea),
            FOREIGN KEY (id_alumno) REFERENCES Usuarios (id_usuario),
            UNIQUE(id_tarea, id_alumno)
        )
    ''')
    
    roles_existentes = conn.execute('SELECT COUNT(*) FROM Roles').fetchone()[0]
    if roles_existentes == 0:
        conn.execute("INSERT INTO Roles (nombre_rol) VALUES ('Administrador')")
        conn.execute("INSERT INTO Roles (nombre_rol) VALUES ('Docente')")
        conn.execute("INSERT INTO Roles (nombre_rol) VALUES ('Estudiante')")
    
    admin_existente = conn.execute("SELECT COUNT(*) FROM Usuarios WHERE correo = 'admin@guadalupe.edu.pe'").fetchone()[0]
    if admin_existente == 0:
        conn.execute('''
            INSERT INTO Usuarios (nombres, apellidos, correo, password, dni, id_rol, estado)
            VALUES ('Xavier Antonio', 'Tamara Atanacio', 'admin@guadalupe.edu.pe', '123456', '00000000', 1, 1)
        ''')
        
    conn.commit()
    conn.close()

init_db()

@app.route('/')
def index():
    if 'id_rol' in session:
        if session['id_rol'] == 1: return redirect(url_for('dashboard'))
        if session['id_rol'] == 2: return redirect(url_for('dashboard_docente'))
        if session['id_rol'] == 3: return redirect(url_for('dashboard_estudiante'))
    return render_template('login.html')

@app.route('/login', methods=['POST'])
def login():
    correo = request.form['correo']
    password = request.form['password']
    
    conn = get_db_connection()
    usuario = conn.execute('SELECT * FROM Usuarios WHERE correo = ? OR dni = ?', (correo, correo)).fetchone()
    conn.close()
    
    if usuario and usuario['password'] == password:
        session['id_usuario'] = usuario['id_usuario']
        session['id_rol'] = usuario['id_rol']
        
        if usuario['id_rol'] == 1:
            return redirect(url_for('dashboard'))
        elif usuario['id_rol'] == 2:
            return redirect(url_for('dashboard_docente'))
        elif usuario['id_rol'] == 3:
            return redirect(url_for('dashboard_estudiante'))
    else:
        return render_template('login.html', error="Correo o DNI / Contraseña incorrectos.")

@app.route('/logout')
def logout():
    session.clear() 
    return redirect(url_for('index'))

@app.route('/dashboard')
def dashboard():
    if 'id_rol' not in session or session['id_rol'] != 1: return redirect(url_for('index'))
    conn = get_db_connection()
    usuario = conn.execute('SELECT * FROM Usuarios WHERE id_usuario = ?', (session['id_usuario'],)).fetchone()
    
    total_alumnos = conn.execute('SELECT COUNT(*) FROM Usuarios WHERE id_rol = 3').fetchone()[0]
    total_docentes = conn.execute('SELECT COUNT(*) FROM Usuarios WHERE id_rol = 2').fetchone()[0]
    total_cursos = conn.execute('SELECT COUNT(*) FROM Cursos').fetchone()[0]
    
    conn.close()
    return render_template('dashboard.html', usuario=usuario, total_alumnos=total_alumnos, total_docentes=total_docentes, total_cursos=total_cursos)

@app.route('/dashboard_docente')
def dashboard_docente():
    if 'id_rol' not in session or session['id_rol'] != 2: 
        return redirect(url_for('index'))
    
    conn = get_db_connection()
    usuario = conn.execute('SELECT * FROM Usuarios WHERE id_usuario = ?', (session['id_usuario'],)).fetchone()
    cursos_docente = conn.execute('SELECT * FROM Cursos WHERE id_docente = ?', (session['id_usuario'],)).fetchall()
    conn.close()
    
    return render_template('dashboard_docente.html', usuario=usuario, cursos=cursos_docente)

# --- PORTAL DEL ESTUDIANTE Y PADRE ---
@app.route('/dashboard_estudiante')
def dashboard_estudiante():
    if 'id_rol' not in session or session['id_rol'] != 3: 
        return redirect(url_for('index'))
    
    conn = get_db_connection()
    usuario = conn.execute('SELECT * FROM Usuarios WHERE id_usuario = ?', (session['id_usuario'],)).fetchone()
    
    cursos = conn.execute('''
        SELECT c.*, u.nombres AS docente_nombres, u.apellidos AS docente_apellidos 
        FROM Cursos c
        LEFT JOIN Usuarios u ON c.id_docente = u.id_usuario
        WHERE c.grado = ?
    ''', (usuario['grado'],)).fetchall()
    
    tareas = []
    if cursos:
        cursos_ids = [c['id_curso'] for c in cursos]
        placeholders = ','.join(['?'] * len(cursos_ids))
        tareas = conn.execute(f'''
            SELECT t.*, c.nombre_curso 
            FROM Tareas t 
            JOIN Cursos c ON t.id_curso = c.id_curso
            WHERE t.id_curso IN ({placeholders}) 
            ORDER BY t.id_tarea DESC
        ''', cursos_ids).fetchall()
        
    raw_notas = conn.execute('SELECT id_curso, periodo, nota FROM Calificaciones WHERE id_alumno = ?', (usuario['id_usuario'],)).fetchall()
    notas_alumno = {(rn['id_curso'], rn['periodo']): rn['nota'] for rn in raw_notas}
    
    raw_entregas = conn.execute('SELECT id_tarea, archivo_alumno, fecha_entrega, nota_tarea FROM EntregasTareas WHERE id_alumno = ?', (usuario['id_usuario'],)).fetchall()
    entregas_dict = {e['id_tarea']: e for e in raw_entregas}
    
    conn.close()
    return render_template('dashboard_estudiante.html', usuario=usuario, cursos=cursos, tareas=tareas, notas_alumno=notas_alumno, entregas_dict=entregas_dict)

@app.route('/estudiante/entregar-tarea/<int:id_tarea>', methods=['POST'])
def entregar_tarea(id_tarea):
    if 'id_rol' not in session or session['id_rol'] != 3: 
        return redirect(url_for('index'))
    
    archivo = request.files.get('archivo_alumno')
    if archivo and archivo.filename != '':
        filename = archivo.filename
        archivo.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
        
        fecha_actual = datetime.now().strftime('%Y-%m-%d %H:%M')
        id_alumno = session['id_usuario']
        
        conn = get_db_connection()
        conn.execute('''
            INSERT INTO EntregasTareas (id_tarea, id_alumno, archivo_alumno, fecha_entrega)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(id_tarea, id_alumno) DO UPDATE SET archivo_alumno = ?, fecha_entrega = ?
        ''', (id_tarea, id_alumno, filename, fecha_actual, filename, fecha_actual))
        conn.commit()
        conn.close()
        
        flash('✅ ¡Tarea enviada y confirmada correctamente!')
    else:
        flash('⚠️ Debes seleccionar un archivo para enviar.')
        
    return redirect(url_for('dashboard_estudiante'))

# --- MÓDULO DE ALUMNOS ---
@app.route('/alumnos')
def gestionar_alumnos():
    if 'id_rol' not in session or session['id_rol'] != 1: return redirect(url_for('index'))
    
    grado_filtro = request.args.get('grado', '')
    seccion_filtro = request.args.get('seccion', '')
    busqueda = request.args.get('busqueda', '')
    
    query = '''
        SELECT u.*, r.nombre_rol 
        FROM Usuarios u 
        JOIN Roles r ON u.id_rol = r.id_rol
        WHERE u.id_rol = 3
    '''
    params = []
    
    if grado_filtro:
        query += ' AND u.grado = ?'
        params.append(grado_filtro)
    if seccion_filtro:
        query += ' AND u.seccion = ?'
        params.append(seccion_filtro)
    if busqueda:
        query += ' AND (u.nombres LIKE ? OR u.apellidos LIKE ? OR u.dni LIKE ?)'
        params.extend([f'%{busqueda}%', f'%{busqueda}%', f'%{busqueda}%'])
        
    conn = get_db_connection()
    alumnos = conn.execute(query, params).fetchall()
    admin_default = conn.execute('SELECT * FROM Usuarios WHERE id_usuario = ?', (session['id_usuario'],)).fetchone()
    conn.close()
    
    return render_template('alumnos.html', alumnos=alumnos, usuario=admin_default, grado_filtro=grado_filtro, seccion_filtro=seccion_filtro, busqueda=busqueda)

@app.route('/crear-alumno', methods=['POST'])
def crear_alumno():
    if 'id_rol' not in session or session['id_rol'] != 1: return redirect(url_for('index'))
    nombres = request.form['nombres']
    apellidos = request.form['apellidos']
    dni = request.form['dni']
    grado = request.form['grado']
    seccion = request.form['seccion']
    
    correo = f"{dni}@guadalupe.edu.pe"
    password = dni
    
    conn = get_db_connection()
    try:
        conn.execute('''
            INSERT INTO Usuarios (nombres, apellidos, correo, password, dni, grado, seccion, id_rol, estado)
            VALUES (?, ?, ?, ?, ?, ?, ?, 3, 1)
        ''', (nombres, apellidos, correo, password, dni, grado, seccion))
        conn.commit()
    except sqlite3.IntegrityError:
        pass
    finally:
        conn.close()
    return redirect(url_for('gestionar_alumnos'))

@app.route('/descargar-plantilla')
def descargar_plantilla():
    if 'id_rol' not in session or session['id_rol'] != 1: return redirect(url_for('index'))
    output = io.StringIO()
    output.write('\ufeff') 
    writer = csv.writer(output, delimiter=';')
    writer.writerow(['dni', 'nombres', 'apellidos', 'grado', 'seccion'])
    writer.writerow(['74839201', 'Carlos', 'Quispe', '3ro de Secundaria', 'A'])
    writer.writerow(['75920182', 'Ana', 'García', '4to de Secundaria', 'B'])
    
    output.seek(0)
    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment;filename=plantilla_alumnos.csv"}
    )

@app.route('/importar-alumnos', methods=['POST'])
def importar_alumnos():
    if 'id_rol' not in session or session['id_rol'] != 1: return redirect(url_for('index'))
    archivo = request.files.get('archivo')
    if not archivo or archivo.filename == '':
        return redirect(url_for('gestionar_alumnos'))

    stream = io.TextIOWrapper(archivo.stream, encoding="utf-8-sig")
    contenido = stream.read()
    delimitador = ';' if ';' in contenido.split('\n')[0] else ','
    stream.seek(0)
    
    reader = csv.DictReader(stream, delimiter=delimitador)
    conn = get_db_connection()
    
    exitosos = 0
    duplicados = 0
    
    for row in reader:
        dni = row.get('dni', '').strip() if row.get('dni') else None
        nombres = row.get('nombres', '').strip() if row.get('nombres') else ''
        apellidos = row.get('apellidos', '').strip() if row.get('apellidos') else ''
        grado = row.get('grado', '').strip() if row.get('grado') else ''
        seccion = row.get('seccion', '').strip() if row.get('seccion') else ''
        
        if dni:
            correo = f"{dni}@guadalupe.edu.pe"
            password = dni
            
            try:
                conn.execute('''
                    INSERT INTO Usuarios (nombres, apellidos, correo, password, dni, grado, seccion, id_rol, estado)
                    VALUES (?, ?, ?, ?, ?, ?, ?, 3, 1)
                ''', (nombres, apellidos, correo, password, dni, grado, seccion))
                exitosos += 1
            except sqlite3.IntegrityError:
                duplicados += 1
            
    conn.commit()
    conn.close()
    
    flash(f'✅ Importación completada: {exitosos} alumnos registrados correctamente. ⚠️ {duplicados} omitidos por DNI duplicado.')
    return redirect(url_for('gestionar_alumnos'))

# --- MÓDULO DE DOCENTES ---
@app.route('/docentes')
def gestionar_docentes():
    if 'id_rol' not in session or session['id_rol'] != 1: 
        return redirect(url_for('index'))
    
    conn = get_db_connection()
    docentes = conn.execute('''
        SELECT u.*, r.nombre_rol 
        FROM Usuarios u 
        JOIN Roles r ON u.id_rol = r.id_rol
        WHERE u.id_rol = 2
    ''').fetchall()
    
    admin_default = conn.execute('SELECT * FROM Usuarios WHERE id_usuario = ?', (session['id_usuario'],)).fetchone()
    conn.close()
    
    return render_template('docentes.html', docentes=docentes, usuario=admin_default)

@app.route('/crear-docente', methods=['POST'])
def crear_docente():
    if 'id_rol' not in session or session['id_rol'] != 1: 
        return redirect(url_for('index'))
        
    nombres = request.form['nombres']
    apellidos = request.form['apellidos']
    dni = request.form['dni']
    
    correo = f"{dni}@guadalupe.edu.pe"
    password = dni
    
    conn = get_db_connection()
    try:
        conn.execute('''
            INSERT INTO Usuarios (nombres, apellidos, correo, password, dni, id_rol, estado)
            VALUES (?, ?, ?, ?, ?, 2, 1)
        ''', (nombres, apellidos, correo, password, dni))
        conn.commit()
        flash('✅ Docente registrado correctamente.')
    except sqlite3.IntegrityError:
        flash('⚠️ El DNI ya se encuentra registrado.')
    finally:
        conn.close()
        
    return redirect(url_for('gestionar_docentes'))

@app.route('/descargar-plantilla-docentes')
def descargar_plantilla_docentes():
    if 'id_rol' not in session or session['id_rol'] != 1: return redirect(url_for('index'))
    output = io.StringIO()
    output.write('\ufeff') 
    writer = csv.writer(output, delimiter=';')
    writer.writerow(['dni', 'nombres', 'apellidos'])
    writer.writerow(['45829102', 'Roberto', 'Gómez'])
    writer.writerow(['46182938', 'María', 'Pérez'])
    
    output.seek(0)
    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment;filename=plantilla_docentes.csv"}
    )

@app.route('/importar-docentes', methods=['POST'])
def importar_docentes():
    if 'id_rol' not in session or session['id_rol'] != 1: return redirect(url_for('index'))
    archivo = request.files.get('archivo')
    if not archivo or archivo.filename == '':
        return redirect(url_for('gestionar_docentes'))

    stream = io.TextIOWrapper(archivo.stream, encoding="utf-8-sig")
    contenido = stream.read()
    delimitador = ';' if ';' in contenido.split('\n')[0] else ','
    stream.seek(0)
    
    reader = csv.DictReader(stream, delimiter=delimitador)
    conn = get_db_connection()
    
    exitosos = 0
    duplicados = 0
    
    for row in reader:
        dni = row.get('dni', '').strip() if row.get('dni') else None
        nombres = row.get('nombres', '').strip() if row.get('nombres') else ''
        apellidos = row.get('apellidos', '').strip() if row.get('apellidos') else ''
        
        if dni:
            correo = f"{dni}@guadalupe.edu.pe"
            password = dni
            
            try:
                conn.execute('''
                    INSERT INTO Usuarios (nombres, apellidos, correo, password, dni, id_rol, estado)
                    VALUES (?, ?, ?, ?, ?, 2, 1)
                ''', (nombres, apellidos, correo, password, dni))
                exitosos += 1
            except sqlite3.IntegrityError:
                duplicados += 1
            
    conn.commit()
    conn.close()
    
    flash(f'✅ Importación completada: {exitosos} docentes registrados correctamente. ⚠️ {duplicados} omitidos por DNI duplicado.')
    return redirect(url_for('gestionar_docentes'))

# --- MÓDULO DE CURSOS Y TAREAS ---
@app.route('/cursos')
def gestionar_cursos():
    if 'id_rol' not in session or session['id_rol'] != 1: return redirect(url_for('index'))
    
    conn = get_db_connection()
    cursos = conn.execute('''
        SELECT c.*, u.nombres AS docente_nombres, u.apellidos AS docente_apellidos 
        FROM Cursos c
        LEFT JOIN Usuarios u ON c.id_docente = u.id_usuario
    ''').fetchall()
    
    docentes = conn.execute('SELECT * FROM Usuarios WHERE id_rol = 2').fetchall()
    admin_default = conn.execute('SELECT * FROM Usuarios WHERE id_usuario = ?', (session['id_usuario'],)).fetchone()
    conn.close()
    
    return render_template('cursos.html', cursos=cursos, docentes=docentes, usuario=admin_default)

@app.route('/crear-curso', methods=['POST'])
def crear_curso():
    if 'id_rol' not in session or session['id_rol'] != 1: return redirect(url_for('index'))
    
    nombre_curso = request.form['nombre_curso'].strip().upper()
    grado = request.form['grado']
    id_docente = request.form['id_docente']
    
    if not id_docente:
        flash('⚠️ Es obligatorio seleccionar un docente a cargo para registrar el curso.')
        return redirect(url_for('gestionar_cursos'))
    
    conn = get_db_connection()
    try:
        conn.execute('''
            INSERT INTO Cursos (nombre_curso, grado, id_docente)
            VALUES (?, ?, ?)
        ''', (nombre_curso, grado, id_docente))
        conn.commit()
        flash('✅ Curso registrado y asignado correctamente.')
    except sqlite3.IntegrityError:
        flash(f'⚠️ El curso "{nombre_curso}" ya se encuentra registrado para el grado {grado}.')
    finally:
        conn.close()
        
    return redirect(url_for('gestionar_cursos'))

@app.route('/eliminar-curso/<int:id_curso>')
def eliminar_curso(id_curso):
    if 'id_rol' not in session or session['id_rol'] != 1: return redirect(url_for('index'))
    
    conn = get_db_connection()
    conn.execute('DELETE FROM Cursos WHERE id_curso = ?', (id_curso,))
    conn.commit()
    conn.close()
    
    flash('🗑️ Curso eliminado correctamente del sistema.')
    return redirect(url_for('gestionar_cursos'))

# --- MÓDULO DE CONTROL DE ASISTENCIA ---
@app.route('/asistencia', methods=['GET', 'POST'])
def gestionar_asistencia():
    if 'id_rol' not in session or session['id_rol'] != 1: return redirect(url_for('index'))
    
    conn = get_db_connection()
    admin_default = conn.execute('SELECT * FROM Usuarios WHERE id_usuario = ?', (session['id_usuario'],)).fetchone()
    
    grado = request.args.get('grado', '1ro de Secundaria')
    seccion = request.args.get('seccion', 'A')
    fecha = request.args.get('fecha', datetime.now().strftime('%Y-%m-%d'))
    
    alumnos = conn.execute('''
        SELECT u.id_usuario, u.dni, u.nombres, u.apellidos, 
        (SELECT estado FROM Asistencia WHERE id_alumno = u.id_usuario AND fecha = ?) AS estado_asistencia
        FROM Usuarios u
        WHERE u.id_rol = 3 AND u.grado = ? AND u.seccion = ?
    ''', (fecha, grado, seccion)).fetchall()
    
    conn.close()
    return render_template('asistencia.html', alumnos=alumnos, usuario=admin_default, grado=grado, seccion=seccion, fecha=fecha)

@app.route('/guardar-asistencia', methods=['POST'])
def guardar_asistencia():
    if 'id_rol' not in session or session['id_rol'] != 1: return redirect(url_for('index'))
    
    fecha = request.form['fecha']
    grado = request.form['grado']
    seccion = request.form['seccion']
    
    conn = get_db_connection()
    alumnos = conn.execute('SELECT id_usuario FROM Usuarios WHERE id_rol = 3 AND grado = ? AND seccion = ?', (grado, seccion)).fetchall()
    
    for a in alumnos:
        id_alumno = a['id_usuario']
        estado = request.form.get(f'estado_{id_alumno}', 'Presente')
        
        conn.execute('''
            INSERT INTO Asistencia (id_alumno, fecha, estado) 
            VALUES (?, ?, ?)
            ON CONFLICT(id_alumno, fecha) DO UPDATE SET estado = ?
        ''', (id_alumno, fecha, estado, estado))
        
    conn.commit()
    conn.close()
    
    flash('✅ Asistencia registrada y guardada correctamente.')
    return redirect(url_for('gestionar_asistencia', grado=grado, seccion=seccion, fecha=fecha))

@app.route('/reporte-asistencia')
def reporte_asistencia():
    if 'id_rol' not in session or session['id_rol'] != 1: return redirect(url_for('index'))
    
    conn = get_db_connection()
    admin_default = conn.execute('SELECT * FROM Usuarios WHERE id_usuario = ?', (session['id_usuario'],)).fetchone()
    
    grado = request.args.get('grado', '1ro de Secundaria')
    seccion = request.args.get('seccion', 'A')
    
    reporte = conn.execute('''
        SELECT u.dni, u.nombres, u.apellidos,
        SUM(CASE WHEN a.estado = 'Presente' THEN 1 ELSE 0 END) AS total_presente,
        SUM(CASE WHEN a.estado = 'Tardanza' THEN 1 ELSE 0 END) AS total_tardanza,
        SUM(CASE WHEN a.estado = 'Ausente' THEN 1 ELSE 0 END) AS total_ausente,
        SUM(CASE WHEN a.estado = 'Tardanza Justificada' THEN 1 ELSE 0 END) AS total_tj,
        SUM(CASE WHEN a.estado = 'Falta Justificada' THEN 1 ELSE 0 END) AS total_fj,
        COUNT(a.id_asistencia) AS total_registros
        FROM Usuarios u
        LEFT JOIN Asistencia a ON u.id_usuario = a.id_alumno
        WHERE u.id_rol = 3 AND u.grado = ? AND u.seccion = ?
        GROUP BY u.id_usuario
    ''', (grado, seccion)).fetchall()
    
    conn.close()
    return render_template('reporte_asistencia.html', reporte=reporte, usuario=admin_default, grado=grado, seccion=seccion)

# --- MÓDULO DE CALIFICACIONES (ADMIN) ---
@app.route('/calificaciones', methods=['GET', 'POST'])
def gestionar_calificaciones():
    if 'id_rol' not in session or session['id_rol'] != 1: return redirect(url_for('index'))
    
    conn = get_db_connection()
    admin_default = conn.execute('SELECT * FROM Usuarios WHERE id_usuario = ?', (session['id_usuario'],)).fetchone()
    
    grado = request.args.get('grado', '1ro de Secundaria')
    seccion = request.args.get('seccion', 'A')
    periodo = request.args.get('periodo', 'Bimestre 1')
    
    cursos = conn.execute('SELECT * FROM Cursos WHERE grado = ?', (grado,)).fetchall()
    alumnos = conn.execute('SELECT * FROM Usuarios WHERE id_rol = 3 AND grado = ? AND seccion = ?', (grado, seccion)).fetchall()
    
    notas_raw = conn.execute('SELECT id_alumno, id_curso, nota FROM Calificaciones WHERE periodo = ?', (periodo,)).fetchall()
    notas_dict = {(n['id_alumno'], n['id_curso']): n['nota'] for n in notas_raw}
    
    conn.close()
    return render_template('calificaciones.html', alumnos=alumnos, cursos=cursos, notas_dict=notas_dict, usuario=admin_default, grado=grado, seccion=seccion, periodo=periodo)

@app.route('/guardar-calificaciones', methods=['POST'])
def guardar_calificaciones():
    if 'id_rol' not in session or session['id_rol'] != 1: return redirect(url_for('index'))
    
    grado = request.form['grado']
    seccion = request.form['seccion']
    periodo = request.form['periodo']
    
    conn = get_db_connection()
    for key, value in request.form.items():
        if key.startswith('nota_'):
            partes = key.split('_')
            id_alumno = partes[1]
            id_curso = partes[2]
            nota = float(value) if value != '' else None
            
            conn.execute('''
                INSERT INTO Calificaciones (id_alumno, id_curso, periodo, nota)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(id_alumno, id_curso, periodo) DO UPDATE SET nota = ?
            ''', (id_alumno, id_curso, periodo, nota, nota))
            
    conn.commit()
    conn.close()
    
    flash('✅ Calificaciones actualizadas correctamente.')
    return redirect(url_for('gestionar_calificaciones', grado=grado, seccion=seccion, periodo=periodo))

# --- MÓDULO DE GESTIÓN DE NOTAS Y TAREAS DEL DOCENTE ---
@app.route('/docente/curso/<int:id_curso>', methods=['GET', 'POST'])
def docente_curso(id_curso):
    if 'id_rol' not in session or session['id_rol'] != 2: 
        return redirect(url_for('index'))
    
    conn = get_db_connection()
    usuario = conn.execute('SELECT * FROM Usuarios WHERE id_usuario = ?', (session['id_usuario'],)).fetchone()
    
    curso = conn.execute('SELECT * FROM Cursos WHERE id_curso = ? AND id_docente = ?', (id_curso, session['id_usuario'])).fetchone()
    if not curso:
        conn.close()
        flash('⚠️ No tienes permiso para acceder a este curso.')
        return redirect(url_for('dashboard_docente'))
        
    periodo = request.args.get('periodo', 'Bimestre 1')
    
    if request.method == 'POST':
        periodo = request.form['periodo']
        for key, value in request.form.items():
            if key.startswith('nota_'):
                id_alumno = key.split('_')[1]
                nota = float(value) if value != '' else None
                conn.execute('''
                    INSERT INTO Calificaciones (id_alumno, id_curso, periodo, nota)
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT(id_alumno, id_curso, periodo) DO UPDATE SET nota = ?
                ''', (id_alumno, id_curso, periodo, nota, nota))
        conn.commit()
        flash('✅ Notas actualizadas correctamente.')
        
    alumnos = conn.execute('SELECT * FROM Usuarios WHERE id_rol = 3 AND grado = ?', (curso['grado'],)).fetchall()
    
    notas_raw = conn.execute('SELECT id_alumno, nota FROM Calificaciones WHERE id_curso = ? AND periodo = ?', (id_curso, periodo)).fetchall()
    notas_dict = {n['id_alumno']: n['nota'] for n in notas_raw}
    
    conn.close()
    return render_template('docente_curso.html', usuario=usuario, curso=curso, alumnos=alumnos, notas_dict=notas_dict, periodo=periodo)

@app.route('/docente/curso/<int:id_curso>/tareas', methods=['GET', 'POST'])
def docente_tareas(id_curso):
    if 'id_rol' not in session or session['id_rol'] != 2: 
        return redirect(url_for('index'))
    
    conn = get_db_connection()
    usuario = conn.execute('SELECT * FROM Usuarios WHERE id_usuario = ?', (session['id_usuario'],)).fetchone()
    
    curso = conn.execute('SELECT * FROM Cursos WHERE id_curso = ? AND id_docente = ?', (id_curso, session['id_usuario'])).fetchone()
    if not curso:
        conn.close()
        flash('⚠️ No tienes permiso para acceder a este curso.')
        return redirect(url_for('dashboard_docente'))
        
    if request.method == 'POST':
        titulo = request.form['titulo']
        descripcion = request.form['descripcion']
        fecha_entrega = request.form['fecha_entrega']
        
        archivo_adjunto = None
        archivo = request.files.get('archivo')
        if archivo and archivo.filename != '':
            filename = archivo.filename
            archivo.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            archivo_adjunto = filename
        
        conn.execute('''
            INSERT INTO Tareas (id_curso, titulo, descripcion, fecha_entrega, archivo_adjunto)
            VALUES (?, ?, ?, ?, ?)
        ''', (id_curso, titulo, descripcion, fecha_entrega, archivo_adjunto))
        conn.commit()
        flash('✅ Tarea o material adjunto publicado correctamente.')
        return redirect(url_for('docente_tareas', id_curso=id_curso))
        
    tareas = conn.execute('SELECT * FROM Tareas WHERE id_curso = ? ORDER BY id_tarea DESC', (id_curso,)).fetchall()
    conn.close()
    return render_template('tareas_docente.html', usuario=usuario, curso=curso, tareas=tareas)

@app.route('/docente/tarea/<int:id_tarea>/entregas', methods=['GET', 'POST'])
def docente_ver_entregas(id_tarea):
    if 'id_rol' not in session or session['id_rol'] != 2: 
        return redirect(url_for('index'))
        
    conn = get_db_connection()
    usuario = conn.execute('SELECT * FROM Usuarios WHERE id_usuario = ?', (session['id_usuario'],)).fetchone()
    
    tarea = conn.execute('''
        SELECT t.*, c.nombre_curso, c.grado, c.id_curso 
        FROM Tareas t 
        JOIN Cursos c ON t.id_curso = c.id_curso 
        WHERE t.id_tarea = ? AND c.id_docente = ?
    ''', (id_tarea, session['id_usuario'])).fetchone()
    
    if not tarea:
        conn.close()
        flash('⚠️ No tienes permiso para ver esta tarea.')
        return redirect(url_for('dashboard_docente'))
        
    if request.method == 'POST':
        for key, value in request.form.items():
            if key.startswith('nota_entrega_'):
                id_entrega = key.split('_')[2]
                nota = float(value) if value != '' else None
                conn.execute('UPDATE EntregasTareas SET nota_tarea = ? WHERE id_entrega = ?', (nota, id_entrega))
        conn.commit()
        flash('✅ Calificaciones de tareas guardadas correctamente.')
        
    alumnos_entregas = conn.execute('''
        SELECT u.id_usuario, u.dni, u.nombres, u.apellidos, 
               e.id_entrega, e.archivo_alumno, e.fecha_entrega, e.nota_tarea
        FROM Usuarios u
        LEFT JOIN EntregasTareas e ON u.id_usuario = e.id_alumno AND e.id_tarea = ?
        WHERE u.id_rol = 3 AND u.grado = ?
    ''', (id_tarea, tarea['grado'])).fetchall()
    
    conn.close()
    return render_template('docente_entregas.html', usuario=usuario, tarea=tarea, alumnos_entregas=alumnos_entregas)

@app.route('/docente/tarea/eliminar/<int:id_tarea>')
def eliminar_tarea(id_tarea):
    if 'id_rol' not in session or session['id_rol'] != 2: 
        return redirect(url_for('index'))
        
    conn = get_db_connection()
    tarea = conn.execute('SELECT * FROM Tareas WHERE id_tarea = ?', (id_tarea,)).fetchone()
    if tarea:
        id_curso = tarea['id_curso']
        if tarea['archivo_adjunto']:
            path_archivo = os.path.join(app.config['UPLOAD_FOLDER'], tarea['archivo_adjunto'])
            if os.path.exists(path_archivo):
                os.remove(path_archivo)
        conn.execute('DELETE FROM Tareas WHERE id_tarea = ?', (id_tarea,))
        conn.commit()
        conn.close()
        flash('🗑️ Tarea eliminada correctamente.')
        return redirect(url_for('docente_tareas', id_curso=id_curso))
    
    conn.close()
    return redirect(url_for('dashboard_docente'))

# --- MÓDULO DE LIBRETA ACADÉMICA ---
@app.route('/libreta-academica')
def libreta_academica():
    if 'id_rol' not in session or session['id_rol'] != 1: return redirect(url_for('index'))
    
    conn = get_db_connection()
    admin_default = conn.execute('SELECT * FROM Usuarios WHERE id_usuario = ?', (session['id_usuario'],)).fetchone()
    
    grado = request.args.get('grado', '1ro de Secundaria')
    seccion = request.args.get('seccion', 'A')
    id_alumno = request.args.get('id_alumno', type=int)
    
    alumnos = conn.execute('SELECT * FROM Usuarios WHERE id_rol = 3 AND grado = ? AND seccion = ?', (grado, seccion)).fetchall()
    
    cursos = []
    notas_alumno = {}
    
    if id_alumno:
        cursos = conn.execute('SELECT * FROM Cursos WHERE grado = ?', (grado,)).fetchall()
        raw_notas = conn.execute('SELECT id_curso, periodo, nota FROM Calificaciones WHERE id_alumno = ?', (id_alumno,)).fetchall()
        for rn in raw_notas:
            notas_alumno[(rn['id_curso'], rn['periodo'])] = rn['nota']
            
    conn.close()
    return render_template('libreta_academica.html', alumnos=alumnos, cursos=cursos, notas_alumno=notas_alumno, usuario=admin_default, grado=grado, seccion=seccion, id_alumno=id_alumno)

# --- MÓDULO DE COMUNICADOS / MENSAJERÍA ---
@app.route('/comunicados', methods=['GET', 'POST'])
def gestionar_comunicados():
    if 'id_rol' not in session: return redirect(url_for('index'))
    
    conn = get_db_connection()
    usuario = conn.execute('SELECT * FROM Usuarios WHERE id_usuario = ?', (session['id_usuario'],)).fetchone()
    
    if request.method == 'POST' and session['id_rol'] in [1, 2]:
        titulo = request.form['titulo']
        mensaje = request.form['mensaje']
        fecha = datetime.now().strftime('%Y-%m-%d %H:%M')
        rol_txt = "Admin" if session['id_rol'] == 1 else "Docente"
        autor = f"{usuario['nombres']} {usuario['apellidos']} ({rol_txt})"
        
        conn.execute('INSERT INTO Comunicados (titulo, mensaje, fecha, autor) VALUES (?, ?, ?, ?)', (titulo, mensaje, fecha, autor))
        conn.commit()
        flash('✅ Comunicado publicado correctamente.')
        return redirect(url_for('gestionar_comunicados'))
        
    comunicados = conn.execute('SELECT * FROM Comunicados ORDER BY id_comunicado DESC').fetchall()
    conn.close()
    return render_template('comunicados.html', comunicados=comunicados, usuario=usuario)

if __name__ == '__main__':
    app.run(debug=True, port=5000)