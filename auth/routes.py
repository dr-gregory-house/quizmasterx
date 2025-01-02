from flask import Blueprint, render_template, request, redirect, url_for, session, flash, abort
from werkzeug.security import generate_password_hash, check_password_hash
from utils import get_db_connection
from datetime import datetime, timedelta
import uuid
import json

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        if not username or not password:
            flash('Username and password are required.', 'error')
            return render_template('auth/register.html')
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT id FROM users WHERE username = ?', (username,))
        if cursor.fetchone():
            conn.close()
            flash('Username already exists.', 'error')
            return render_template('auth/register.html')
        hashed_password = generate_password_hash(password)
        try:
            cursor.execute('INSERT INTO users (username, password_hash) VALUES (?, ?)', (username, hashed_password))
            conn.commit()
            conn.close()
            flash('Registration successful! Please log in.', 'success')
            return redirect(url_for('auth.login'))
        except Exception as e:
            conn.close()
            flash(f'Database error during registration: {e}', 'error')
            return render_template('auth/register.html')
    return render_template('auth/register.html')

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        conn = get_db_connection()
        cursor = conn.cursor()
        user = cursor.execute('SELECT * FROM users WHERE username = ?', (username,)).fetchone()
        conn.close()
        if user and check_password_hash(user['password_hash'], password):
            if user['is_active'] == 1:
                session['user_id'] = user['id']
                session['username'] = user['username']
                flash('Logged in successfully!', 'success')
                return redirect(url_for('main.hello'))
            else:
                flash('Your account is inactive. Please contact the administrator.', 'warning')
                return render_template('auth/login.html')  # Correct redirect here
        else:
            flash('Login failed. Check your credentials.', 'error')
    return render_template('auth/login.html')

@auth_bp.route('/logout')
def logout():
    # Clear all session data
    session.clear()
    flash('You have been logged out.', 'info')
    return redirect(url_for('main.hello'))

@auth_bp.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        conn = get_db_connection()
        cursor = conn.cursor()
        user = cursor.execute('SELECT * FROM users WHERE username = ? AND role = "admin"', (username,)).fetchone()
        conn.close()
        
        if user and check_password_hash(user['password_hash'], password):
            session['user_id'] = user['id']
            session['username'] = user['username']
            session['user_role'] = 'admin'
            flash('Welcome back, Admin!', 'success')
            return redirect(url_for('admin.dashboard'))
        flash('Invalid admin credentials.', 'error')
    return render_template('auth/admin_login.html')

@auth_bp.route('/guest_login', methods=['GET', 'POST'])
def guest_login():
    if request.method == 'POST':
        guest_name = request.form.get('guest_name', '').strip()
        if not guest_name:
            flash('Please enter a display name to continue as guest.', 'error')
            return render_template('auth/guest_login.html')
        
        # Create a unique guest ID
        guest_id = f'guest_{uuid.uuid4().hex[:8]}'
        
        # Get client IP and user agent
        ip_address = request.remote_addr
        user_agent = request.user_agent.string
        
        # Set up guest session
        session['user_id'] = guest_id
        session['username'] = f'{guest_name} (Guest)'
        session['user_role'] = 'guest'
        session['is_guest'] = True
        session['guest_start_time'] = datetime.now().timestamp()
        
        # Record guest activity in database
        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('''
                INSERT INTO guest_sessions (
                    guest_id, display_name, ip_address, user_agent, 
                    start_time, last_activity, session_data
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                guest_id, guest_name, ip_address, user_agent,
                datetime.now(), datetime.now(),
                json.dumps({'created': datetime.now().isoformat()})
            ))
            conn.commit()
        except Exception as e:
            print(f"Error recording guest session: {e}")
        finally:
            conn.close()
        
        flash(f'Welcome {guest_name}! You are now in guest mode.', 'success')
        return redirect(url_for('main.hello'))
    
    return render_template('auth/guest_login.html')

@auth_bp.before_request
def check_guest_session():
    if session.get('is_guest'):
        start_time = session.get('guest_start_time')
        if start_time:
            # Check if 30 minutes have passed
            if datetime.now().timestamp() - start_time > 1800:  # 1800 seconds = 30 minutes
                # Record session end in database
                guest_id = session.get('user_id')
                if guest_id:
                    conn = get_db_connection()
                    cursor = conn.cursor()
                    try:
                        cursor.execute('''
                            UPDATE guest_sessions 
                            SET end_time = ?, session_data = json_set(
                                COALESCE(session_data, '{}'),
                                '$.ended', ?
                            )
                            WHERE guest_id = ? AND end_time IS NULL
                        ''', (datetime.now(), datetime.now().isoformat(), guest_id))
                        conn.commit()
                    except Exception as e:
                        print(f"Error updating guest session end: {e}")
                    finally:
                        conn.close()
                
                session.clear()
                flash('Guest session has expired. Please login again.', 'info')
                return redirect(url_for('main.hello'))
            
            # Update last activity
            guest_id = session.get('user_id')
            if guest_id:
                conn = get_db_connection()
                cursor = conn.cursor()
                try:
                    cursor.execute('''
                        UPDATE guest_sessions 
                        SET last_activity = ?
                        WHERE guest_id = ? AND end_time IS NULL
                    ''', (datetime.now(), guest_id))
                    conn.commit()
                except Exception as e:
                    print(f"Error updating guest last activity: {e}")
                finally:
                    conn.close()