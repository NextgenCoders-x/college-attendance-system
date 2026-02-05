from flask import Flask, render_template, request, redirect, url_for, flash, session, g
import mysql.connector
from werkzeug.security import generate_password_hash, check_password_hash
import functools
from config import Config

app = Flask(__name__)
app.config.from_object(Config)

# Database Helper Functions
def get_db():
    if 'db' not in g:
        g.db = mysql.connector.connect(
            host=app.config['DB_HOST'],
            user=app.config['DB_USER'],
            password=app.config['DB_PASSWORD'],
            database=app.config['DB_NAME'],
            autocommit=True
        )
        g.cursor = g.db.cursor(dictionary=True) # Return rows as dictionaries
    return g.db, g.cursor

@app.teardown_appcontext
def close_db(error):
    db = g.pop('db', None)
    if db is not None:
        db.close()

# Auth Decorators
def login_required(view):
    @functools.wraps(view)
    def wrapped_view(**kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return view(**kwargs)
    return wrapped_view

def role_required(role):
    def decorator(view):
        @functools.wraps(view)
        def wrapped_view(**kwargs):
            if 'user_id' not in session:
                return redirect(url_for('login'))
            if session.get('role') != role and session.get('role') != 'admin': # Admin overrides? Or strict?
                # Let's keep it strict or allow Admin access
                if session.get('role') != role: 
                     flash("Access denied. Unauthorized role.", "danger")
                     return redirect(url_for('login'))
            return view(**kwargs)
        return wrapped_view
    return decorator

# --- Routes ---

@app.route('/')
def splash():
    return render_template('splash.html')

@app.route('/login', methods=('GET', 'POST'))
def login():
    if 'user_id' in session:
        role = session.get('role')
        # Redirect if already logged in
        if role == 'admin': return redirect(url_for('admin_dashboard'))
        elif role == 'staff': return redirect(url_for('staff_dashboard'))
        elif role == 'student': return redirect(url_for('student_dashboard'))

    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        try:
            db, cursor = get_db()
            cursor.execute("SELECT * FROM users WHERE username = %s", (username,))
            user = cursor.fetchone()
            
            if user:
                if check_password_hash(user['password_hash'], password):
                    session.clear()
                    session['user_id'] = user['id']
                    session['role'] = user['role']
                    session['username'] = user['username']
                    
                    if user['role'] == 'admin': return redirect(url_for('admin_dashboard'))
                    elif user['role'] == 'staff':
                        # Check if this is a Class Login
                        cursor.execute("SELECT * FROM class_logins WHERE user_id = %s", (user['id'],))
                        class_login = cursor.fetchone()
                        
                        if class_login:
                            session['is_class_login'] = True
                            session['class_id'] = class_login['id']
                            session['dept_id'] = class_login['department_id']
                            session['year'] = class_login['year']
                            session['batch'] = class_login['batch']
                            return redirect(url_for('class_dashboard'))
                        else:
                            return redirect(url_for('staff_dashboard'))
                            
                    elif user['role'] == 'student': return redirect(url_for('student_dashboard'))
                else:
                    flash('Incorrect password.', 'danger')
            else:
                flash('User not found.', 'danger')
        except mysql.connector.Error as err:
            flash(f"Database Error: {err}", "danger")

    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/developer-info')
@login_required
def developer_info():
    return render_template('developer_info.html')

# --- Placeholders for Dashboards ---

# --- Admin Routes ---

@app.route('/admin')
@login_required
@role_required('admin')
def admin_dashboard():
    db, cursor = get_db()
    
    # Fetch Stats
    cursor.execute("SELECT COUNT(*) as count FROM students")
    student_count = cursor.fetchone()['count']
    
    cursor.execute("SELECT COUNT(*) as count FROM class_logins")
    class_login_count = cursor.fetchone()['count']
    
    cursor.execute("SELECT COUNT(*) as count FROM departments")
    dept_count = cursor.fetchone()['count']

    return render_template('admin_dashboard.html', 
                           student_count=student_count, 
                           class_login_count=class_login_count, 
                           dept_count=dept_count)

# -- DEPARTMENTS --
@app.route('/admin/departments', methods=('GET', 'POST'))
@login_required
@role_required('admin')
def manage_departments():
    db, cursor = get_db()
    if request.method == 'POST':
        name = request.form['name']
        code = request.form['code']
        try:
            cursor.execute("INSERT INTO departments (name, code) VALUES (%s, %s)", (name, code))
            flash('Department added successfully.', 'success')
            return redirect(url_for('manage_departments'))
        except mysql.connector.Error as err:
            flash(f"Error: {err}", "danger")
    
    cursor.execute("SELECT * FROM departments")
    departments = cursor.fetchall()
    return render_template('admin_manage_departments.html', departments=departments)

@app.route('/admin/departments/edit/<int:dept_id>', methods=('GET', 'POST'))
@login_required
@role_required('admin')
def edit_department(dept_id):
    db, cursor = get_db()
    
    if request.method == 'POST':
        name = request.form['name']
        code = request.form['code']
        try:
            cursor.execute("UPDATE departments SET name = %s, code = %s WHERE id = %s", (name, code, dept_id))
            flash('Department updated successfully.', 'success')
            return redirect(url_for('manage_departments'))
        except mysql.connector.Error as err:
            flash(f"Error: {err}", "danger")
            
    cursor.execute("SELECT * FROM departments WHERE id = %s", (dept_id,))
    department = cursor.fetchone()
    if not department:
         flash('Department not found.', 'danger')
         return redirect(url_for('manage_departments'))
         
    return render_template('admin_edit_department.html', department=department)

@app.route('/admin/departments/delete/<int:dept_id>', methods=['POST'])
@login_required
@role_required('admin')
def delete_department(dept_id):
    db, cursor = get_db()
    
    # Check Dependencies
    # 1. Students
    cursor.execute("SELECT COUNT(*) as count FROM students WHERE department_id = %s", (dept_id,))
    if cursor.fetchone()['count'] > 0:
        flash('Cannot delete: Students are assigned to this department.', 'danger')
        return redirect(url_for('manage_departments'))
        
    # 2. Staff
    cursor.execute("SELECT COUNT(*) as count FROM staff WHERE department_id = %s", (dept_id,))
    if cursor.fetchone()['count'] > 0:
        flash('Cannot delete: Staff are assigned to this department.', 'danger')
        return redirect(url_for('manage_departments'))
        
    # 3. Subjects
    cursor.execute("SELECT COUNT(*) as count FROM subjects WHERE department_id = %s", (dept_id,))
    if cursor.fetchone()['count'] > 0:
        flash('Cannot delete: Subjects are assigned to this department.', 'danger')
        return redirect(url_for('manage_departments'))

    try:
        cursor.execute("DELETE FROM departments WHERE id = %s", (dept_id,))
        flash('Department deleted.', 'success')
    except mysql.connector.Error as err:
        flash(f"Error: {err}", "danger")
        
    return redirect(url_for('manage_departments'))

@app.route('/admin/staff', methods=('GET', 'POST'))
@login_required
@role_required('admin')
def manage_staff():
    db, cursor = get_db()
    
    # Get Departments for Dropdown
    cursor.execute("SELECT * FROM departments")
    departments = cursor.fetchall()
    
    if request.method == 'POST':
        name = request.form['name']
        dept_id = request.form['department']
        
        try:
             # Create Staff Profile (No User Account Created)
            cursor.execute("INSERT INTO staff (name, department_id) VALUES (%s, %s)", (name, dept_id))
            flash('Staff member added successfully.', 'success')
            return redirect(url_for('manage_staff'))
        except mysql.connector.Error as err:
            flash(f"Error: {err}", "danger")
            
    cursor.execute("""
        SELECT s.*, d.name as dept_name 
        FROM staff s 
        LEFT JOIN departments d ON s.department_id = d.id
    """)
    staff_list = cursor.fetchall()
    return render_template('admin_manage_staff.html', staff_list=staff_list, departments=departments)

@app.route('/admin/staff/edit/<int:staff_id>', methods=('GET', 'POST'))
@login_required
@role_required('admin')
def edit_staff(staff_id):
    db, cursor = get_db()
    
    if request.method == 'POST':
        name = request.form['name']
        dept_id = request.form['department']
        
        try:
            # Update Profile
            cursor.execute("UPDATE staff SET name = %s, department_id = %s WHERE id = %s", (name, dept_id, staff_id))
            flash('Staff profile updated successfully.', 'success')
            return redirect(url_for('manage_staff'))
            
        except mysql.connector.Error as err:
            flash(f"Error: {err}", "danger")
            
    cursor.execute("SELECT * FROM staff WHERE id = %s", (staff_id,))
    staff = cursor.fetchone()
    
    if not staff:
        flash('Staff not found.', 'danger')
        return redirect(url_for('manage_staff'))
        
    cursor.execute("SELECT * FROM departments")
    departments = cursor.fetchall()
    
    return render_template('admin_edit_staff.html', staff=staff, departments=departments)

@app.route('/admin/staff/delete/<int:staff_id>', methods=['POST'])
@login_required
@role_required('admin')
def delete_staff(staff_id):
    db, cursor = get_db()
    
    # Check Dependencies not needed for Subjects (SET NULL), but usually good to check?
    # Requirement: "When deleting a staff: do not delete subjects, just set subject.staff_id = NULL"
    # This is handled by DB Constraint ON DELETE SET NULL.
    
    try:
        # Just delete the staff record.
        # If there was a linked user, it becomes an orphan user unless we check.
        # But per new requirement, staff might NOT have a user.
        # If old staff (with user), we might want to delete user too?
        # Requirement says "Do NOT modify class_logins, login logic...".
        # But these act like "Academic staff allocation not like system login users."
        # If we delete a staff from here, we should probably delete the linked user ONLY IF it was a staff-role user.
        
        # 1. Check if linked to a user
        cursor.execute("SELECT user_id FROM staff WHERE id = %s", (staff_id,))
        res = cursor.fetchone()
        
        cursor.execute("DELETE FROM staff WHERE id = %s", (staff_id,))
        
        # Optional: Cleanup User if it exists and was a staff user
        if res and res['user_id']:
             user_id = res['user_id']
             # Double check role before deleting user to be safe
             cursor.execute("SELECT role FROM users WHERE id = %s", (user_id,))
             u_res = cursor.fetchone()
             if u_res and u_res['role'] == 'staff':
                 cursor.execute("DELETE FROM users WHERE id = %s", (user_id,))
        
        flash('Staff member deleted.', 'success')
            
    except mysql.connector.Error as err:
        flash(f"Error: {err}", "danger")
        
    return redirect(url_for('manage_staff'))

# -- STUDENTS --
@app.route('/admin/students', methods=('GET', 'POST'))
@login_required
@role_required('admin')
def manage_students():
    db, cursor = get_db()
    
    cursor.execute("SELECT * FROM departments")
    departments = cursor.fetchall()
    
    if request.method == 'POST':
        name = request.form['name']
        register_no = request.form['register_no']
        password = request.form['password'] # Or default to reg_no
        dept_id = request.form['department']
        year = request.form['year']
        section = request.form['section']
        
        # Username for student is register_no
        hashed = generate_password_hash(password)
        
        try:
            # Create User
            cursor.execute("INSERT INTO users (username, password_hash, role) VALUES (%s, %s, %s)", (register_no, hashed, 'student'))
            user_id = cursor.lastrowid
            
            # Create Student Profile
            cursor.execute("""
                INSERT INTO students (user_id, register_no, name, department_id, current_year, section) 
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (user_id, register_no, name, dept_id, year, section))
            
            flash('Student added successfully.', 'success')
            return redirect(url_for('manage_students'))
        except mysql.connector.Error as err:
             flash(f"Error: {err}", "danger")

    cursor.execute("""
        SELECT s.*, d.name as dept_name 
        FROM students s 
        LEFT JOIN departments d ON s.department_id = d.id
    """)
    students = cursor.fetchall()
    return render_template('admin_manage_students.html', students=students, departments=departments)

@app.route('/admin/students/edit/<int:student_id>', methods=('GET', 'POST'))
@login_required
@role_required('admin')
def edit_student(student_id):
    db, cursor = get_db()
    
    if request.method == 'POST':
        name = request.form['name']
        register_no = request.form['register_no']
        dept_id = request.form['department']
        year = request.form['year']
        section = request.form['section']
        password = request.form.get('password')
        
        try:
            # Update Profile
            cursor.execute("""
                UPDATE students 
                SET name=%s, register_no=%s, department_id=%s, current_year=%s, section=%s 
                WHERE id=%s
            """, (name, register_no, dept_id, year, section, student_id))
            
            # Update User/Password if needed (and username if reg_no changed)
            cursor.execute("SELECT user_id FROM students WHERE id = %s", (student_id,))
            user_id = cursor.fetchone()['user_id']
            
            # Update Username (Reg No) always to keep in sync
            cursor.execute("UPDATE users SET username = %s WHERE id = %s", (register_no, user_id))
            
            if password:
                hashed = generate_password_hash(password)
                cursor.execute("UPDATE users SET password_hash = %s WHERE id = %s", (hashed, user_id))
                
            flash('Student profile updated successfully.', 'success')
            return redirect(url_for('manage_students'))
            
        except mysql.connector.Error as err:
            flash(f"Error: {err}", "danger")
            
    cursor.execute("SELECT * FROM students WHERE id = %s", (student_id,))
    student = cursor.fetchone()
    
    if not student:
        flash('Student not found.', 'danger')
        return redirect(url_for('manage_students'))
        
    cursor.execute("SELECT * FROM departments")
    departments = cursor.fetchall()
    
    return render_template('admin_edit_student.html', student=student, departments=departments)

@app.route('/admin/students/delete/<int:student_id>', methods=['POST'])
@login_required
@role_required('admin')
def delete_student(student_id):
    db, cursor = get_db()
    
    # Check Attendance
    cursor.execute("SELECT COUNT(*) as count FROM attendance WHERE student_id = %s", (student_id,))
    if cursor.fetchone()['count'] > 0:
        flash('Cannot delete: This student has attendance records.', 'danger')
        return redirect(url_for('manage_students'))
        
    try:
        # Get User ID to delete the User account (Cascade will delete student)
        cursor.execute("SELECT user_id FROM students WHERE id = %s", (student_id,))
        res = cursor.fetchone()
        if res:
            user_id = res['user_id']
            cursor.execute("DELETE FROM users WHERE id = %s", (user_id,))
            flash('Student deleted.', 'success')
        else:
            flash('Student user mapping not found.', 'danger')
            
    except mysql.connector.Error as err:
        flash(f"Error: {err}", "danger")
        
    return redirect(url_for('manage_students'))

# -- SUBJECTS --
@app.route('/admin/subjects', methods=('GET', 'POST'))
@login_required
@role_required('admin')
def manage_subjects():
    db, cursor = get_db()
    
    cursor.execute("SELECT * FROM departments")
    departments = cursor.fetchall()
    
    cursor.execute("SELECT * FROM staff")
    staff_list = cursor.fetchall()
    
    if request.method == 'POST':
        name = request.form['name']
        code = request.form['code']
        dept_id = request.form['department']
        year = request.form['year']
        section = request.form['section']
        staff_id = request.form.get('staff_id') # Can be None/Empty
        
        if not staff_id or staff_id == "":
            staff_id = None
        
        try:
            cursor.execute("""
                INSERT INTO subjects (name, code, department_id, year, section, staff_id)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (name, code, dept_id, year, section, staff_id))
            flash('Subject added successfully.', 'success')
            return redirect(url_for('manage_subjects'))
        except mysql.connector.Error as err:
             flash(f"Error: {err}", "danger")

    cursor.execute("""
        SELECT sub.*, d.name as dept_name, s.name as staff_name
        FROM subjects sub
        LEFT JOIN departments d ON sub.department_id = d.id
        LEFT JOIN staff s ON sub.staff_id = s.id
    """)
    subjects = cursor.fetchall()
    return render_template('admin_manage_subjects.html', subjects=subjects, departments=departments, staff_list=staff_list)

@app.route('/admin/subjects/edit/<int:sub_id>', methods=('GET', 'POST'))
@login_required
@role_required('admin')
def edit_subject(sub_id):
    db, cursor = get_db()
    
    if request.method == 'POST':
        name = request.form['name']
        code = request.form['code']
        dept_id = request.form['department']
        year = request.form['year']
        section = request.form['section']
        staff_id = request.form.get('staff_id')
        
        if not staff_id or staff_id == "":
            staff_id = None
        
        try:
            cursor.execute("""
                UPDATE subjects SET name=%s, code=%s, department_id=%s, year=%s, section=%s, staff_id=%s
                WHERE id=%s
            """, (name, code, dept_id, year, section, staff_id, sub_id))
            flash('Subject updated successfully.', 'success')
            return redirect(url_for('manage_subjects'))
        except mysql.connector.Error as err:
            flash(f"Error: {err}", "danger")
            
    cursor.execute("SELECT * FROM subjects WHERE id = %s", (sub_id,))
    subject = cursor.fetchone()
    if not subject: return redirect(url_for('manage_subjects'))
    
    cursor.execute("SELECT * FROM departments")
    departments = cursor.fetchall()
    
    cursor.execute("SELECT * FROM staff")
    staff_list = cursor.fetchall()
    
    return render_template('admin_edit_subject.html', subject=subject, departments=departments, staff_list=staff_list)

@app.route('/admin/subjects/delete/<int:sub_id>', methods=['POST'])
@login_required
@role_required('admin')
def delete_subject(sub_id):
    db, cursor = get_db()
    
    # Check Dependencies: Attendance
    cursor.execute("SELECT COUNT(*) as count FROM attendance WHERE subject_id = %s", (sub_id,))
    if cursor.fetchone()['count'] > 0:
        flash('Cannot delete: Attendance records exist for this subject.', 'danger')
        return redirect(url_for('manage_subjects'))
        
    try:
        cursor.execute("DELETE FROM subjects WHERE id = %s", (sub_id,))
        flash('Subject deleted.', 'success')
    except mysql.connector.Error as err:
        flash(f"Error: {err}", "danger")
        
    return redirect(url_for('manage_subjects'))


# --- CLASS DASHBOARD (NEW) ---
@app.route('/class_dashboard')
@login_required
@role_required('staff')
def class_dashboard():
    # Verify if it is a class login
    if not session.get('is_class_login'):
        return redirect(url_for('staff_dashboard'))

    db, cursor = get_db()
    
    dept_id = session['dept_id']
    year = session['year']
    batch = session['batch']
    
    # Get Class Info for Display
    cursor.execute("SELECT name FROM departments WHERE id = %s", (dept_id,))
    dept_name = cursor.fetchone()['name']
    
    # Get All Subjects for this Class (Dept + Year + Batch)
    # Note: subjects table uses 'section' column to store batch info (I Batch, II Batch)
    cursor.execute("""
        SELECT s.*, d.name as dept_name, st.name as staff_name
        FROM subjects s 
        LEFT JOIN departments d ON s.department_id = d.id
        LEFT JOIN staff st ON s.staff_id = st.id
        WHERE s.department_id = %s AND s.year = %s AND s.section = %s
    """, (dept_id, year, batch))
    subjects = cursor.fetchall()
    
    return render_template('class_dashboard.html', 
                           subjects=subjects, 
                           dept_name=dept_name, 
                           year=year, 
                           batch=batch)

# --- STAFF ROUTES ---
@app.route('/staff')
@login_required
@role_required('staff')
def staff_dashboard():
    db, cursor = get_db()
    
    # Get Staff ID from User ID
    cursor.execute("SELECT id FROM staff WHERE user_id = %s", (session['user_id'],))
    staff = cursor.fetchone()
    
    if not staff:
        flash("Staff profile not found.", "danger")
        return redirect(url_for('logout'))
        
    staff_id = staff['id']
    
    # Get Assigned Subjects
    cursor.execute("""
        SELECT s.*, d.name as dept_name 
        FROM subjects s 
        LEFT JOIN departments d ON s.department_id = d.id
        WHERE s.staff_id = %s
    """, (staff_id,))
    subjects = cursor.fetchall()
    
    return render_template('staff_dashboard.html', subjects=subjects)

@app.route('/staff/mark/<int:subject_id>', methods=('GET', 'POST'))
@login_required
@role_required('staff')
def mark_attendance(subject_id):
    db, cursor = get_db()
    
    # Modified Authorization Logic for Class Login
    if session.get('is_class_login'):
        # Check if subject belongs to this class
        cursor.execute("SELECT * FROM subjects WHERE id = %s", (subject_id,))
        subject = cursor.fetchone()
        
        if not subject:
             flash("Subject not found.", "danger")
             return redirect(url_for('class_dashboard'))

        # Verify Subject Matches Class Login Credentials
        # Subject 'section' col stores Batch (I Batch, II Batch)
        if (subject['department_id'] != session['dept_id'] or 
            subject['year'] != session['year'] or 
            subject['section'] != session['batch']):
            flash("Access denied. This subject does not belong to your class login.", "danger")
            return redirect(url_for('class_dashboard'))
            
    else:
        # Standard Staff Login Check
        # Get Staff ID
        cursor.execute("SELECT id FROM staff WHERE user_id = %s", (session['user_id'],))
        staff = cursor.fetchone()
        if not staff:
             flash("Staff profile not found.", "danger")
             return redirect(url_for('logout'))
        staff_id = staff['id']
        
        # Verify Subject Assignment
        cursor.execute("SELECT * FROM subjects WHERE id = %s AND staff_id = %s", (subject_id, staff_id))
        subject = cursor.fetchone()
        
        if not subject:
            flash("Access denied. You are not assigned to this subject.", "danger")
            return redirect(url_for('staff_dashboard'))
        
    if request.method == 'POST':
        date = request.form['date']
        
        # FEATURE 2: Check limit - Prevent Duplicate Submission
        cursor.execute("SELECT COUNT(*) as count FROM attendance WHERE subject_id = %s AND date = %s", (subject_id, date))
        existing_records = cursor.fetchone()['count']
        
        if existing_records > 0:
             flash(f"Attendance already marked for this subject on {date}. Modification not allowed.", "danger")
             return redirect(url_for('class_dashboard') if session.get('is_class_login') else url_for('staff_dashboard'))

        # Get list of students for this subject's class again to be safe
        cursor.execute("""
            SELECT id FROM students 
            WHERE department_id = %s AND current_year = %s AND section = %s
        """, (subject['department_id'], subject['year'], subject['section']))
        students = cursor.fetchall()
        
        try:
            for student in students:
                sid = student['id']
                status_key = f"status_{sid}"
                status = request.form.get(status_key) # 'Present', 'Absent', 'On Duty'
                
                # Insert Only - No Update
                cursor.execute("""
                    INSERT INTO attendance (student_id, subject_id, date, status)
                    VALUES (%s, %s, %s, %s)
                """, (sid, subject_id, date, status))
            
            flash(f"Attendance marked for {date}.", "success")
            return redirect(url_for('class_dashboard') if session.get('is_class_login') else url_for('staff_dashboard'))
        except mysql.connector.Error as err:
            flash(f"Error marking attendance: {err}", "danger")

    # Get Students for this Subject (Dept, Year, Section)
    cursor.execute("""
        SELECT * FROM students 
        WHERE department_id = %s AND current_year = %s AND section = %s
        ORDER BY register_no
    """, (subject['department_id'], subject['year'], subject['section']))
    students = cursor.fetchall()
    
    return render_template('staff_mark_attendance.html', subject=subject, students=students)


@app.route('/class/view-student-percentage/<int:subject_id>')
@login_required
@role_required('staff')
def class_view_student_percentage(subject_id):
    # Strictly for Class Login
    if not session.get('is_class_login'):
        return redirect(url_for('staff_dashboard'))
        
    db, cursor = get_db()
    
    # Verify Subject (Match by Class Login Credentials)
    cursor.execute("""
        SELECT sub.*, s.name as staff_name 
        FROM subjects sub
        LEFT JOIN staff s ON sub.staff_id = s.id
        WHERE sub.id = %s
    """, (subject_id,))
    subject = cursor.fetchone()
    
    if not subject:
         flash("Subject not found.", "danger")
         return redirect(url_for('class_dashboard'))
         
    # Check if subject belongs to this class login (Dept + Year + Batch)
    if (subject['department_id'] != session['dept_id'] or 
        subject['year'] != session['year'] or 
        subject['section'] != session['batch']):
        flash("Access denied. Subject mismatch.", "danger")
        return redirect(url_for('class_dashboard'))
        
    # Get all students for this class
    cursor.execute("""
        SELECT * FROM students 
        WHERE department_id = %s AND current_year = %s AND section = %s
        ORDER BY register_no
    """, (subject['department_id'], subject['year'], subject['section']))
    students = cursor.fetchall()
    
    student_stats = []
    
    for student in students:
        percentage = calculate_student_percentage(cursor, student['id'])
        student_stats.append({
            'register_no': student['register_no'],
            'name': student['name'],
            'percentage': round(percentage, 1)
        })
        
    return render_template('class_student_percentage.html', subject=subject, stats=student_stats)


# --- HELPER: ATTENDANCE CALCULATION ---
def calculate_student_percentage(cursor, student_id):
    """
    Calculates overall attendance based on day-wise logic.
    - Start: 100%
    - All subjects Present/OD on a date: +1%
    - All subjects Absent on a date: -2%
    - Mixed: No change
    - Clamped 0-100%
    
    UPDATED: Checks for admin_override_percentage first.
    """
    # 0. Check Override
    cursor.execute("SELECT admin_override_percentage FROM students WHERE id = %s", (student_id,))
    res = cursor.fetchone()
    if res and res['admin_override_percentage'] is not None:
         return float(res['admin_override_percentage'])

    current_percentage = 100.0
    
    # 1. Fetch all attendance records for this student
    cursor.execute("""
        SELECT status 
        FROM attendance 
        WHERE student_id = %s
    """, (student_id,))
    all_records = cursor.fetchall()
    
    # 2. Period-Wise Calculation
    total_periods = len(all_records)
    attended_periods = 0
    
    if total_periods == 0:
        return 0.0 # Default to 0% if no records (Strict Rule)
        
    for record in all_records:
        if record['status'] in ['Present', 'On Duty']:
            attended_periods += 1
            
    # Calculate Percentage
    current_percentage = (attended_periods / total_periods) * 100.0
    
    # Round to 2 decimal places
    current_percentage = round(current_percentage, 2)
    
    # Cap between 0 and 100
    if current_percentage > 100: current_percentage = 100.0
    if current_percentage < 0: current_percentage = 0.0
    
    return current_percentage


@app.route('/staff/view-stats/<int:subject_id>')
@login_required
@role_required('staff')
def staff_view_attendance_stats(subject_id):
    db, cursor = get_db()
    
    # Get Staff ID
    cursor.execute("SELECT id FROM staff WHERE user_id = %s", (session['user_id'],))
    staff = cursor.fetchone()
    staff_id = staff['id']
    
    # Verify Subject
    cursor.execute("SELECT * FROM subjects WHERE id = %s AND staff_id = %s", (subject_id, staff_id))
    subject = cursor.fetchone()
    
    if not subject:
        flash("Access denied.", "danger")
        return redirect(url_for('staff_dashboard'))
        
    # Get all students for this class
    cursor.execute("""
        SELECT * FROM students 
        WHERE department_id = %s AND current_year = %s AND section = %s
        ORDER BY register_no
    """, (subject['department_id'], subject['year'], subject['section']))
    students = cursor.fetchall()
    
    # Calculate Stats for each student using GLOBAL logic
    student_stats = []
    
    for student in students:
        # Helper automatically handles override now
        percentage = calculate_student_percentage(cursor, student['id'])
            
        student_stats.append({
            'register_no': student['register_no'],
            'name': student['name'], 
            'percentage': round(percentage, 1)
        })
        
    return render_template('staff_view_stats.html', subject=subject, stats=student_stats)

@app.route('/staff/view-stats/<int:subject_id>/export')
@login_required
@role_required('staff')
def staff_export_attendance_stats(subject_id):
    db, cursor = get_db()
    import openpyxl
    from io import BytesIO
    from flask import send_file
    
    # Reuse exact logic from view stats
    # Get Staff ID
    cursor.execute("SELECT id FROM staff WHERE user_id = %s", (session['user_id'],))
    staff = cursor.fetchone()
    if not staff: return redirect(url_for('login'))
    
    staff_id = staff['id']
    
    # Verify Subject (Scope check)
    cursor.execute("SELECT * FROM subjects WHERE id = %s AND staff_id = %s", (subject_id, staff_id))
    subject = cursor.fetchone()
    
    if not subject:
        flash("Access denied.", "danger")
        return redirect(url_for('staff_dashboard'))
        
    # Get all students for this class
    cursor.execute("""
        SELECT * FROM students 
        WHERE department_id = %s AND current_year = %s AND section = %s
        ORDER BY register_no
    """, (subject['department_id'], subject['year'], subject['section']))
    students = cursor.fetchall()
    
    # Create Excel
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Attendance Stats"
    
    # Header
    ws.append(["Register No", "Attendance Percentage"])
    
    # Data
    for student in students:
        # STRICTLY REUSE CALCULATE FUNCTION
        percentage = calculate_student_percentage(cursor, student['id'])
        ws.append([student['register_no'], f"{round(percentage, 1)}%"])
        
    # Save to buffer
    buffer = BytesIO()
    wb.save(buffer)
    buffer.seek(0)
    
    filename = f"Attendance_{subject['code']}_{subject['year']}{subject['section']}.xlsx"
    return send_file(buffer, as_attachment=True, download_name=filename, mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')


# --- ADMIN ATTENDANCE CORRECTION ---
@app.route('/admin/attendance', methods=('GET', 'POST'))
@login_required
@role_required('admin')
def admin_attendance_correction():
    db, cursor = get_db()
    
    # 1. Fetch Departments for Dropdown
    cursor.execute("SELECT * FROM departments ORDER BY name")
    departments = cursor.fetchall()

    selected_dept_id = None
    selected_subject = None
    selected_date = None
    subjects = []
    attendance_records = []
    
    # Check for parameters in POST or GET (to handle reload persistence)
    # Priority: POST form > GET args
    if request.method == 'POST':
        selected_dept_id = request.form.get('department_id')
        subject_id = request.form.get('subject_id')
        date = request.form.get('date')
    else:
        selected_dept_id = request.args.get('department_id')
        subject_id = request.args.get('subject_id')
        date = request.args.get('date')

    # 2. If Department Selected, Fetch Subjects for that Department
    if selected_dept_id:
        cursor.execute("SELECT * FROM subjects WHERE department_id = %s ORDER BY name", (selected_dept_id,))
        subjects = cursor.fetchall()
        
    # 3. If Subject & Date Selected (and Subject belongs to the filtered list logic, though UI enforces it), fetch records
    if subject_id and date:
        selected_date = date
        
        # Verify subject (and fetch details)
        cursor.execute("SELECT * FROM subjects WHERE id = %s", (subject_id,))
        selected_subject = cursor.fetchone()
        
        if selected_subject:
             # Query: Get students for the subject class, and join attendance for that date
            cursor.execute("""
                SELECT st.id as student_id, st.register_no, st.name as student_name, 
                       a.id as attendance_id, a.status
                FROM students st
                LEFT JOIN attendance a ON st.id = a.student_id AND a.subject_id = %s AND a.date = %s
                WHERE st.department_id = %s AND st.current_year = %s AND st.section = %s
                ORDER BY st.register_no
            """, (subject_id, date, selected_subject['department_id'], selected_subject['year'], selected_subject['section']))
            
            attendance_records = cursor.fetchall()

    return render_template('admin_attendance_correction.html', 
                           departments=departments,
                           subjects=subjects, 
                           selected_dept_id=selected_dept_id,
                           selected_subject=selected_subject, 
                           selected_date=selected_date, 
                           attendance_records=attendance_records)

@app.route('/admin/attendance/update', methods=['POST'])
@login_required
@role_required('admin')
def admin_update_attendance():
    db, cursor = get_db()
    
    subject_id = request.form.get('subject_id')
    date = request.form.get('date')
    
    if not subject_id or not date:
        flash("Missing subject or date information.", "danger")
        return redirect(url_for('admin_attendance_correction'))
        
    try:
        # Loop through form data to find status updates
        # Form keys: status_{student_id}
        # Iterate over all keys in request.form
        for key in request.form:
            if key.startswith('status_'):
                student_id = key.split('_')[1]
                new_status = request.form[key]
                
                # Upsert (Insert or Update)
                # If record exists, update. If not, insert (Admin might mark missing attendance)
                cursor.execute("""
                    INSERT INTO attendance (student_id, subject_id, date, status)
                    VALUES (%s, %s, %s, %s)
                    ON DUPLICATE KEY UPDATE status = VALUES(status)
                """, (student_id, subject_id, date, new_status))
                
        flash("Attendance updated successfully.", "success")
    except mysql.connector.Error as err:
        flash(f"Error updating attendance: {err}", "danger")
        
    return redirect(url_for('admin_attendance_correction'))


# --- ADMIN: STUDENT ATTENDANCE PERCENTAGE OVERRIDE ---
@app.route('/admin/student-percentage', methods=('GET', 'POST'))
@login_required
@role_required('admin')
def admin_student_percentage():
    db, cursor = get_db()
    
    # Fetch Departments for Filter
    cursor.execute("SELECT * FROM departments")
    departments = cursor.fetchall()
    
    students_data = []
    
    # Filter Logic
    dept_id = request.args.get('department_id')
    year = request.args.get('year')
    
    # If filtered, fetch students
    if dept_id and year:
         cursor.execute("""
            SELECT s.id, s.register_no, s.name, s.admin_override_percentage 
            FROM students s
            WHERE s.department_id = %s AND s.current_year = %s
            ORDER BY s.register_no
         """, (dept_id, year))
         students = cursor.fetchall()
         
         # Calculate current calculated vs override
         for s in students:
             calculated = calculate_student_percentage(cursor, s['id'])
             # Note: calculate_student_percentage uses override if set. 
             # We want to show "System Calculated" vs "Override".
             # So we need to Bypass the override check manually for display?
             # Or we just show "Current Effective Percentage" and "Override Value".
             
             # Re-calculating RAW system percentage (ignoring override for display purposes)
             # Duplicate logic or modify helper?
             # Let's modify helper to take 'ignore_override' arg? NO, simplest is just copy-paste logic OR
             # Since calculate_student_percentage returns FINAL, if we want RAW, we need to manually doing it or
             # temporarily set override to None. That's messy.
             
             # Let's DRY. Modify helper slightly to accept optional flag? 
             # Or just trust the admin knows that if Override is set, it IS the percentage.
             # User prompt: "Calculated Attendance Percentage (read-only)" AND "Editable Field: Admin Override Percentage".
             # Implies showing what system *thinks* it is vs what Admin sets.
             
             # Let's inline the RAW calculation for this specific Admin view so we show the true calculated value.
             
             current_system_percentage = 100.0
             cursor.execute("""SELECT status FROM attendance WHERE student_id = %s""", (s['id'],))
             recs = cursor.fetchall()
             
             total_periods = len(recs)
             attended_periods = 0
             
             if total_periods > 0:
                 for r in recs:
                     if r['status'] in ['Present', 'On Duty']: 
                        attended_periods += 1
                 current_system_percentage = (attended_periods / total_periods) * 100.0
                 current_system_percentage = round(current_system_percentage, 2)
             else:
                 current_system_percentage = 0.0
                 
             if current_system_percentage > 100: current_system_percentage = 100.0
             if current_system_percentage < 0: current_system_percentage = 0.0
             
             students_data.append({
                 'id': s['id'],
                 'register_no': s['register_no'],
                 'name': s['name'],
                 'calculated': round(current_system_percentage, 1),
                 'override': s['admin_override_percentage']
             })

    return render_template('admin_student_percentage.html', 
                           departments=departments, 
                           students=students_data,
                           selected_dept=dept_id,
                           selected_year=year)

@app.route('/admin/student-percentage/update', methods=['POST'])
@login_required
@role_required('admin')
def admin_student_percentage_update():
    db, cursor = get_db()
    
    dept_id = request.form.get('department_id')
    year = request.form.get('year')
    
    # Process updates
    # Form: override_{student_id}
    try:
        for key in request.form:
             if key.startswith('override_'):
                 student_id = key.split('_')[1]
                 val = request.form[key].strip()
                 
                 final_val = None
                 if val:
                     try:
                         final_val = float(val)
                         if final_val < 0: final_val = 0
                         if final_val > 100: final_val = 100
                     except ValueError:
                         pass # Ignore invalid inputs -> None
                 
                 # Update DB
                 # If None, it NULLs the column, restoring system calc
                 cursor.execute("UPDATE students SET admin_override_percentage = %s WHERE id = %s", (final_val, student_id))
                 
        flash("Percentages updated successfully.", "success")
    except mysql.connector.Error as err:
        flash(f"Error: {err}", "danger")
        
    return redirect(url_for('admin_student_percentage', department_id=dept_id, year=year))

# --- ADMIN: RESET ATTENDANCE DATA ---
@app.route('/admin/reset-attendance', methods=['GET'])
@login_required
@role_required('admin')
def admin_reset_attendance():
    db, cursor = get_db()
    
    # 1. Fetch Students
    cursor.execute("""
        SELECT s.id, s.register_no, s.name, d.code as dept_name 
        FROM students s
        LEFT JOIN departments d ON s.department_id = d.id
        ORDER BY s.register_no
    """)
    students = cursor.fetchall()

    # 2. Fetch Departments
    cursor.execute("SELECT * FROM departments ORDER BY name")
    departments = cursor.fetchall()

    # 3. Fetch Subjects
    cursor.execute("""
        SELECT s.*, d.code as dept_name 
        FROM subjects s
        LEFT JOIN departments d ON s.department_id = d.id 
        ORDER BY s.code
    """)
    subjects = cursor.fetchall()

    # 4. Fetch Staff
    cursor.execute("SELECT * FROM staff ORDER BY name")
    staff_list = cursor.fetchall()
    
    return render_template('admin_reset_attendance.html', 
                           students=students,
                           departments=departments,
                           subjects=subjects,
                           staff_list=staff_list)

@app.route('/admin/reset-attendance/action', methods=['POST'])
@login_required
@role_required('admin')
def admin_reset_attendance_action():
    db, cursor = get_db()
    action = request.form.get('action')
    
    try:
        # --- SECTION 1: Clear ALL Attendance ---
        if action == 'clear_all':
            cursor.execute("DELETE FROM attendance")
            flash("All attendance records have been permanently deleted.", "success")
            print(f"ADMIN ACTION: All attendance records deleted by user {session.get('username')}")
            
        # --- SECTION 2: Clear ONE Student Attendance ---
        elif action == 'clear_student':
            student_id = request.form.get('student_id')
            if student_id:
                cursor.execute("DELETE FROM attendance WHERE student_id = %s", (student_id,))
                flash("Attendance records for the selected student have been deleted.", "success")
            else:
                flash("No student selected.", "warning")

        # --- SECTION 3: Clear Department Attendance ---
        elif action == 'delete_department_attendance':
            dept_id = request.form.get('department_id')
            if dept_id:
                # Delete attendance for students belonging to this department
                cursor.execute("""
                    DELETE a FROM attendance a 
                    JOIN students s ON a.student_id = s.id 
                    WHERE s.department_id = %s
                """, (dept_id,))
                flash("Department attendance cleared successfully.", "success")
            else:
                flash("No department selected.", "warning")

        # --- SECTION 4: Clear Subject Attendance ---
        elif action == 'delete_subject_attendance':
            subject_id = request.form.get('subject_id')
            if subject_id:
                cursor.execute("DELETE FROM attendance WHERE subject_id = %s", (subject_id,))
                flash("Subject attendance cleared successfully.", "success")
            else:
                flash("No subject selected.", "warning")

        # --- SECTION 5: Clear Staff Attendance handled by Staff ---
        elif action == 'delete_staff_attendance':
            staff_id = request.form.get('staff_id')
            if staff_id:
                # 1. Find subjects assigned to this staff
                cursor.execute("SELECT id FROM subjects WHERE staff_id = %s", (staff_id,))
                subjects = cursor.fetchall()
                
                if subjects:
                    subject_ids = [s['id'] for s in subjects]
                    # Mysql connector formatting for IN clause requires manual handling or executemany? 
                    # Simpler to loop or format string for this destructive action?
                    # Safer: string formatting with tuples.
                    format_strings = ','.join(['%s'] * len(subject_ids))
                    query = "DELETE FROM attendance WHERE subject_id IN (%s)" % format_strings
                    cursor.execute(query, tuple(subject_ids))
                    flash("Staff attendance records cleared successfully.", "success")
                else:
                    flash("No subjects found for this staff.", "info")
            else:
                flash("No staff selected.", "warning")

        # --- SECTION 6: Delete Student (Full Data) ---
        elif action == 'delete_student_full':
            student_id = request.form.get('student_id')
            if student_id:
                # Attendance cascades on delete, but we can be explicit if needed. 
                # ON DELETE CASCADE is defined in schema.
                cursor.execute("DELETE FROM students WHERE id = %s", (student_id,))
                flash("Student and their attendance deleted successfully.", "success")
            else:
                flash("No student selected.", "warning")

        # --- SECTION 7: Delete Department (Full Data) ---
        elif action == 'delete_department_full':
            dept_id = request.form.get('department_id')
            if dept_id:
                try:
                    # Transactional Order:
                    # 1. Delete Attendance of students in Dept
                    cursor.execute("""
                        DELETE a FROM attendance a 
                        JOIN students s ON a.student_id = s.id 
                        WHERE s.department_id = %s
                    """, (dept_id,))
                    
                    # 2. Delete Students
                    cursor.execute("DELETE FROM students WHERE department_id = %s", (dept_id,))
                    
                    # 3. Delete Subjects
                    cursor.execute("DELETE FROM subjects WHERE department_id = %s", (dept_id,))
                    
                    # 4. Set Staff Department to NULL
                    cursor.execute("UPDATE staff SET department_id = NULL WHERE department_id = %s", (dept_id,))
                    
                    # 5. Delete Department
                    cursor.execute("DELETE FROM departments WHERE id = %s", (dept_id,))
                    
                    db.commit() # Commit Explicitly
                    flash("Department and all related data deleted successfully.", "success")
                    
                except Exception as e:
                    db.rollback()
                    raise e # Re-raise to be caught by outer except
            else:
                flash("No department selected.", "warning")

        # --- SECTION 8: Delete Staff (Academic Staff Only) ---
        elif action == 'delete_staff':
            staff_id = request.form.get('staff_id')
            if staff_id:
                # Subjects.staff_id will set to NULL via CASCADE/SET NULL in schema
                cursor.execute("DELETE FROM staff WHERE id = %s", (staff_id,))
                flash("Staff record deleted successfully (User login remains).", "success")
            else:
                flash("No staff selected.", "warning")

        # --- SECTION 9: Delete Subject (Full) ---
        elif action == 'delete_subject':
            subject_id = request.form.get('subject_id')
            if subject_id:
                cursor.execute("DELETE FROM subjects WHERE id = %s", (subject_id,))
                flash("Subject deleted successfully.", "success")
            else:
                flash("No subject selected.", "warning")

        else:
             flash("Invalid action.", "danger")
        
        # Global Commit for non-explicit commits (if autocommit is off, but typically Flask-MySQL connector might auto-commit or we need to ensure)
        # The 'get_db' doesn't seem to imply auto-commit based on other code using db.commit() in some places.
        # But 'DELETE' without transaction block might auto-commit in some configs. 
        # Safest is to commit for all modifying actions.
        db.commit()

    except mysql.connector.Error as err:
        db.rollback()
        flash(f"Database Error: {err}", "danger")
    except Exception as e:
        db.rollback()
        flash(f"Error: {e}", "danger")
        
    return redirect(url_for('admin_reset_attendance'))



    return redirect(url_for('admin_reset_attendance'))

# --- ADMIN: CLASS LOGINS ---
@app.route('/admin/manage_class_logins', methods=('GET', 'POST'))
@login_required
@role_required('admin')
def manage_class_logins():
    db, cursor = get_db()
    
    if request.method == 'POST':
        # Create New Class Login
        username = request.form['username']
        password = request.form['password']
        dept_id = request.form['department_id']
        year = request.form['year']
        batch = request.form['batch']
        
        try:
            # 1. Create User
            password_hash = generate_password_hash(password)
            cursor.execute("INSERT INTO users (username, password_hash, role) VALUES (%s, %s, 'staff')", (username, password_hash))
            user_id = cursor.lastrowid
            
            # 2. Create Class Login Entry
            cursor.execute("""
                INSERT INTO class_logins (user_id, department_id, year, batch)
                VALUES (%s, %s, %s, %s)
            """, (user_id, dept_id, year, batch))
            
            db.commit()
            flash("Class Login created successfully.", "success")
            
        except mysql.connector.Error as err:
            db.rollback()
            flash(f"Error creating class login: {err}", "danger")
            
    # Fetch Existing Class Logins
    cursor.execute("""
        SELECT cl.*, u.username, d.name as dept_name 
        FROM class_logins cl
        JOIN users u ON cl.user_id = u.id
        JOIN departments d ON cl.department_id = d.id
        ORDER BY d.name, cl.year, cl.batch
    """)
    class_logins = cursor.fetchall()
    
    # Fetch Departments for Dropdown
    cursor.execute("SELECT * FROM departments ORDER BY name")
    departments = cursor.fetchall()
    
    return render_template('admin_manage_class_logins.html', class_logins=class_logins, departments=departments)

@app.route('/admin/delete_class_login/<int:class_login_id>', methods=['POST'])
@login_required
@role_required('admin')
def delete_class_login(class_login_id):
    db, cursor = get_db()
    try:
        # Get User ID to delete from users table (Cascade will handle class_logins)
        cursor.execute("SELECT user_id FROM class_logins WHERE id = %s", (class_login_id,))
        record = cursor.fetchone()
        
        if record:
            user_id = record['user_id']
            cursor.execute("DELETE FROM users WHERE id = %s", (user_id,))
            db.commit()
            flash("Class Login deleted successfully.", "success")
        else:
            flash("Class Login not found.", "danger")
            
    except mysql.connector.Error as err:
        flash(f"Error deleting class login: {err}", "danger")
        
    return redirect(url_for('manage_class_logins'))

# --- ADMIN: DEPARTMENT-WISE ATTENDANCE OVERVIEW ---
@app.route('/admin/attendance-overview', methods=['GET'])
@login_required
@role_required('admin')
def admin_attendance_overview():
    db, cursor = get_db()
    
    # 1. Fetch Departments for Filter
    cursor.execute("SELECT * FROM departments ORDER BY name")
    departments = cursor.fetchall()
    
    # 2. Get Filter Params
    dept_id = request.args.get('department_id')
    year = request.args.get('year')
    
    students_data = []
    
    # 3. If Filter Applied, Fetch Students
    if dept_id:
        query = """
            SELECT s.*, d.name as dept_name, d.code as dept_code 
            FROM students s
            LEFT JOIN departments d ON s.department_id = d.id
            WHERE s.department_id = %s
        """
        params = [dept_id]
        
        if year:
            query += " AND s.current_year = %s"
            params.append(year)
            
        query += " ORDER BY s.register_no"
        
        cursor.execute(query, tuple(params))
        students = cursor.fetchall()
        
        # 4. Calculate Percentage loop
        for student in students:
            percentage = calculate_student_percentage(cursor, student['id'])
            # We convert row to dict to append percentage
            s_dict = dict(student) 
            s_dict['percentage'] = percentage
            students_data.append(s_dict)
            
    return render_template('admin_attendance_overview.html', 
                           departments=departments,
                           students=students_data,
                           selected_dept=dept_id,
                           selected_year=year)


# --- STUDENT ROUTES ---
@app.route('/student')
@login_required
@role_required('student')
def student_dashboard():
    db, cursor = get_db()
    
    # Get Student ID
    cursor.execute("SELECT * FROM students WHERE user_id = %s", (session['user_id'],))
    student = cursor.fetchone()
    
    if not student:
        flash("Student profile not found.", "danger")
        return redirect(url_for('logout'))
        
    # Use Global Calculation Helper
    current_percentage = calculate_student_percentage(cursor, student['id'])
    
    return render_template('student_dashboard.html', 
                           student=student, 
                           overall_percentage=current_percentage)

@app.route('/student/attendance-history')
@login_required
@role_required('student')
def student_attendance_history():
    db, cursor = get_db()
    
    # Get Student ID
    cursor.execute("SELECT * FROM students WHERE user_id = %s", (session['user_id'],))
    student = cursor.fetchone()
    
    if not student:
        flash("Student profile not found.", "danger")
        return redirect(url_for('logout'))

    # Fetch Detailed History (Date Descending)
    cursor.execute("""
        SELECT a.date, a.status, s.name as subject_name, s.code as subject_code
        FROM attendance a
        JOIN subjects s ON a.subject_id = s.id
        WHERE a.student_id = %s
        ORDER BY a.date DESC
    """, (student['id'],))
    history = cursor.fetchall()
    
    return render_template('student_attendance_history.html', student=student, history=history)

# --- CLI Command to Seed Admin ---
# Helper to create an admin user manually if DB is empty
@app.cli.command('init-db')
def init_db_command():
    """Initializes the database with an Admin user."""
    try:
        db, cursor = get_db()
        # Check if admin exists
        cursor.execute("SELECT * FROM users WHERE role = 'admin'")
        if not cursor.fetchone():
            print("Creating default admin user...")
            username = 'admin'
            password = 'admin123'
            hashed = generate_password_hash(password)
            cursor.execute("INSERT INTO users (username, password_hash, role) VALUES (%s, %s, %s)", (username, hashed, 'admin'))
            print(f"Admin created. User: {username}, Pass: {password}")
        else:
            print("Admin already exists.")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == '__main__':
    app.run(debug=True)
