import mysql.connector
from config import Config
import re

def check_backend():
    print("\n--- 1. Backend Verification ---")
    try:
        db = mysql.connector.connect(
            host=Config.DB_HOST,
            user=Config.DB_USER,
            password=Config.DB_PASSWORD,
            database=Config.DB_NAME
        )
        cursor = db.cursor()
        
        # Check subjects.staff_id exists
        cursor.execute("DESCRIBE subjects")
        cols = [row[0] for row in cursor.fetchall()]
        if 'staff_id' in cols:
            print("✅ 'subjects.staff_id' column exists.")
        else:
            print("❌ 'subjects.staff_id' column MISSING.")

        db.close()
    except Exception as e:
        print(f"❌ DB Error: {e}")

    # Check app.py for logic
    try:
        with open('app.py', 'r') as f:
            content = f.read()
            
        # Check manage_subjects fetches staff
        if 'SELECT * FROM staff' in content and 'manage_subjects' in content:
            print("✅ 'manage_subjects' appears to fetch staff list.")
        else:
            print("⚠️ Could not confirm 'manage_subjects' fetches staff (check manually).")
            
        # Check JOIN logic in manage_subjects query
        if 'LEFT JOIN staff s' in content and 'manage_subjects' in content:
             print("✅ 'manage_subjects' query includes JOIN with staff.")
        else:
             print("⚠️ 'manage_subjects' query might be missing JOIN (check manually).")

    except Exception as e:
        print(f"❌ File Error: {e}")

def check_templates():
    print("\n--- 2. & 3. Template & Button Verification ---")
    
    # admin_manage_subjects.html
    try:
        with open('templates/admin_manage_subjects.html', 'r') as f:
            content = f.read()
            
        if 'select name="staff_id"' in content or "select name='staff_id'" in content:
            print("✅ 'admin_manage_subjects.html' has 'staff_id' dropdown.")
        else:
             print("❌ 'admin_manage_subjects.html' MISSING 'staff_id' dropdown.")
             
        if 'staff.id' in content and 'staff.name' in content:
             print("✅ Dropdown populated with staff data.")
        
        if 'edit_subject' in content:
             print("✅ 'Edit' action exists in Subject row.")
             
    except Exception as e:
        print(f"❌ Template Error (manage_subjects): {e}")

    # admin_edit_subject.html
    try:
        with open('templates/admin_edit_subject.html', 'r') as f:
            content = f.read()
            
        if 'select name="staff_id"' in content:
            print("✅ 'admin_edit_subject.html' has 'staff_id' dropdown.")
        else:
             print("❌ 'admin_edit_subject.html' MISSING 'staff_id' dropdown.")
             
    except Exception as e:
        print(f"❌ Template Error (edit_subject): {e}")

def check_permissions():
    print("\n--- 4. Permission Verification ---")
    try:
        with open('app.py', 'r') as f:
            content = f.read()
            
        # Check manage_subjects decorators
        if "@app.route('/admin/subjects'" in content:
            # Simple check if @role_required('admin') is near the route def
            # This is a bit loose but good for quick check
            matches = re.findall(r"@app\.route\('/admin/subjects'.*?\n(.*?)\n(.*?)\n", content, re.DOTALL)
            if matches:
                decorators = matches[0]
                if "@role_required('admin')" in decorators or "@role_required('admin')" in str(matches):
                    print("✅ 'manage_subjects' protected by @role_required('admin').")
                else:
                    print("⚠️ 'manage_subjects' might be missing admin role check.")
    except Exception as e:
        print(f"❌ File Error: {e}")

if __name__ == "__main__":
    check_backend()
    check_templates()
    check_permissions()
