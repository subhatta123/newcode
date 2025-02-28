from flask import Flask, render_template_string, redirect, url_for, request, jsonify, send_from_directory, session, flash
import os
import json
from pathlib import Path
from datetime import datetime
import sqlite3
from user_management import UserManagement
from report_manager_new import ReportManager
from data_analyzer import DataAnalyzer
from report_formatter_new import ReportFormatter
from tableau_utils import authenticate, get_workbooks, download_and_save_data, generate_table_name
import pytz
from functools import wraps
from werkzeug.security import generate_password_hash, check_password_hash
import pandas as pd
from dotenv import load_dotenv
import numpy as np

# Load environment variables from .env file
load_dotenv()

app = Flask(__name__)
app.secret_key = os.urandom(24)  # For session management

# Initialize managers
user_manager = UserManagement()
report_manager = ReportManager()
report_manager.base_url = os.getenv('BASE_URL', 'http://localhost:8501')
data_analyzer = DataAnalyzer()
report_formatter = ReportFormatter()

# Login required decorator
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user' not in session:
            flash('Please log in first')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# Role required decorator
def role_required(roles):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if 'user' not in session or session['user'].get('role') not in roles:
                flash('Access denied')
                return redirect(url_for('home'))
            return f(*args, **kwargs)
        return decorated_function
    return decorator

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = user_manager.verify_user(username, password)
        if user:
            session['user'] = {
                'id': user[0],
                'username': user[1],
                'role': user[2],
                'permission_type': user[3],
                'organization_id': user[4],
                'organization_name': user[5]
            }
            flash('Login successful!')
            return redirect(url_for('home'))
        flash('Invalid credentials')
    return render_template_string('''
        <!DOCTYPE html>
        <html>
        <head>
            <title>Login - Tableau Data Reporter</title>
            <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
            <style>
                body { padding-top: 40px; }
                .form-signin {
                    width: 100%;
                    max-width: 330px;
                    padding: 15px;
                    margin: auto;
                }
            </style>
        </head>
        <body>
            <div class="container">
                <div class="form-signin text-center">
                    <h1 class="h3 mb-3">Tableau Data Reporter</h1>
                    {% with messages = get_flashed_messages() %}
                        {% if messages %}
                            {% for message in messages %}
                                <div class="alert alert-info">{{ message }}</div>
                            {% endfor %}
                        {% endif %}
                    {% endwith %}
                    <form method="post">
                        <div class="form-floating mb-3">
                            <input type="text" class="form-control" name="username" placeholder="Username" required>
                            <label>Username</label>
                        </div>
                        <div class="form-floating mb-3">
                            <input type="password" class="form-control" name="password" placeholder="Password" required>
                            <label>Password</label>
                        </div>
                        <button class="w-100 btn btn-lg btn-primary" type="submit">Login</button>
                        <p class="mt-3">
                            <a href="{{ url_for('register') }}">Register new account</a>
                        </p>
                    </form>
                </div>
            </div>
        </body>
        </html>
    ''')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        
        if not all([username, email, password, confirm_password]):
            flash('All fields are required')
        elif password != confirm_password:
            flash('Passwords do not match')
        else:
            try:
                if user_manager.add_user_to_org(
                    username=username,
                    password=password,
                    org_id=None,
                    permission_type='normal',
                    email=email
                ):
                    flash('Registration successful! Please login.')
                    return redirect(url_for('login'))
            except ValueError as e:
                flash(str(e))
    
    return render_template_string('''
        <!DOCTYPE html>
        <html>
        <head>
            <title>Register - Tableau Data Reporter</title>
            <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
            <style>
                body { padding-top: 40px; }
                .form-signin {
                    width: 100%;
                    max-width: 330px;
                    padding: 15px;
                    margin: auto;
                }
            </style>
        </head>
        <body>
            <div class="container">
                <div class="form-signin text-center">
                    <h1 class="h3 mb-3">Register New Account</h1>
                    {% with messages = get_flashed_messages() %}
                        {% if messages %}
                            {% for message in messages %}
                                <div class="alert alert-info">{{ message }}</div>
                            {% endfor %}
                        {% endif %}
                    {% endwith %}
                    <form method="post">
                        <div class="form-floating mb-3">
                            <input type="text" class="form-control" name="username" placeholder="Username" required>
                            <label>Username</label>
                        </div>
                        <div class="form-floating mb-3">
                            <input type="email" class="form-control" name="email" placeholder="Email" required>
                            <label>Email</label>
                        </div>
                        <div class="form-floating mb-3">
                            <input type="password" class="form-control" name="password" placeholder="Password" required>
                            <label>Password</label>
                        </div>
                        <div class="form-floating mb-3">
                            <input type="password" class="form-control" name="confirm_password" placeholder="Confirm Password" required>
                            <label>Confirm Password</label>
                        </div>
                        <button class="w-100 btn btn-lg btn-primary" type="submit">Register</button>
                        <p class="mt-3">
                            <a href="{{ url_for('login') }}">Back to login</a>
                        </p>
                    </form>
                </div>
            </div>
        </body>
        </html>
    ''')

@app.route('/')
def home():
    if 'user' not in session:
        return redirect(url_for('login'))
    
    user_role = session['user'].get('role')
    if user_role == 'superadmin':
        return redirect(url_for('admin_dashboard'))
    elif user_role == 'power':
        return redirect(url_for('power_user_dashboard'))
    else:
        return redirect(url_for('normal_user_dashboard'))

@app.route('/logout')
def logout():
    session.clear()
    flash('Logged out successfully')
    return redirect(url_for('login'))

@app.route('/normal-user')
@login_required
@role_required(['normal'])
def normal_user_dashboard():
    datasets = get_saved_datasets()
    return render_template_string('''
        <!DOCTYPE html>
        <html>
        <head>
            <title>Dashboard - Tableau Data Reporter</title>
            <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
            <link href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.7.2/font/bootstrap-icons.css" rel="stylesheet">
            <style>
                .sidebar {
                    position: fixed;
                    top: 0;
                    bottom: 0;
                    left: 0;
                    z-index: 100;
                    padding: 48px 0 0;
                    box-shadow: inset -1px 0 0 rgba(0, 0, 0, .1);
                }
                .main {
                    margin-left: 240px;
                    padding: 20px;
                }
                .nav-link {
                    padding: 0.5rem 1rem;
                    font-size: 0.9rem;
                }
                .nav-link i {
                    margin-right: 8px;
                    width: 20px;
                    text-align: center;
                }
                .nav-link.active {
                    font-weight: bold;
                    background-color: rgba(0, 123, 255, 0.1);
                }
            </style>
        </head>
        <body>
            <nav class="col-md-3 col-lg-2 d-md-block bg-light sidebar">
                <div class="position-sticky pt-3">
                    <div class="px-3">
                        <h5>👤 User Profile</h5>
                        <p><strong>Username:</strong> {{ session.user.username }}</p>
                        <p><strong>Role:</strong> {{ session.user.role }}</p>
                    </div>
                    <hr>
                    <ul class="nav flex-column">
                        <li class="nav-item">
                            <a class="nav-link active" href="{{ url_for('normal_user_dashboard') }}">
                                <i class="bi bi-house"></i> Dashboard
                            </a>
                        </li>
                        <li class="nav-item">
                            <a class="nav-link" href="{{ url_for('tableau_connect') }}">
                                <i class="bi bi-box-arrow-in-right"></i> Connect to Tableau
                            </a>
                        </li>
                        <li class="nav-item">
                            <a class="nav-link" href="{{ url_for('schedule_reports') }}">
                                <i class="bi bi-calendar-plus"></i> Create Schedule
                            </a>
                        </li>
                        <li class="nav-item">
                            <a class="nav-link" href="{{ url_for('manage_schedules') }}">
                                <i class="bi bi-calendar-check"></i> Manage Schedules
                            </a>
                        </li>
                        <li class="nav-item">
                            <a class="nav-link" href="{{ url_for('logout') }}">
                                <i class="bi bi-box-arrow-right"></i> Logout
                            </a>
                        </li>
                    </ul>
                </div>
            </nav>

            <main class="main">
                <div class="container">
                    {% with messages = get_flashed_messages() %}
                        {% if messages %}
                            {% for message in messages %}
                                <div class="alert alert-info">{{ message }}</div>
                            {% endfor %}
                        {% endif %}
                    {% endwith %}

                    <h1 class="mb-4">Your Datasets</h1>
                    
                    {% if datasets %}
                        <div class="row">
                            {% for dataset in datasets %}
                                <div class="col-md-4 mb-4">
                                    <div class="card">
                                        <div class="card-body">
                                            <h5 class="card-title">{{ dataset }}</h5>
                                            <h6 class="card-subtitle mb-2 text-muted">
                                                <small>{{ get_dataset_row_count(dataset) }} rows</small>
                                            </h6>
                                            <a href="#" class="card-link" 
                                               onclick="viewDatasetPreview('{{ dataset }}')">View Preview</a>
                                            <a href="{{ url_for('schedule_dataset', dataset=dataset) }}" 
                                               class="card-link">Create Schedule</a>
                                        </div>
                                    </div>
                                </div>
                            {% endfor %}
                        </div>
                    {% else %}
                        <div class="alert alert-info">
                            <p>No datasets available. Please connect to Tableau and download data first.</p>
                            <a href="{{ url_for('tableau_connect') }}" class="btn btn-primary">
                                <i class="bi bi-box-arrow-in-right"></i> Connect to Tableau
                            </a>
                        </div>
                    {% endif %}
                    
                    <!-- Dataset Preview Modal -->
                    <div class="modal fade" id="datasetPreviewModal" tabindex="-1">
                        <div class="modal-dialog modal-xl">
                            <div class="modal-content">
                                <div class="modal-header">
                                    <h5 class="modal-title">Dataset Preview: <span id="datasetName"></span></h5>
                                    <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
                                </div>
                                <div class="modal-body">
                                    <div id="datasetPreview"></div>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </main>
            
            <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/js/bootstrap.bundle.min.js"></script>
            <script>
                function viewDatasetPreview(dataset) {
                    document.getElementById('datasetName').textContent = dataset;
                    const previewDiv = document.getElementById('datasetPreview');
                    previewDiv.innerHTML = '<div class="text-center"><div class="spinner-border" role="status"></div><p>Loading preview...</p></div>';
                    
                    // Show modal
                    const modal = new bootstrap.Modal(document.getElementById('datasetPreviewModal'));
                    modal.show();
                    
                    // Fetch preview
                    fetch(`/api/datasets/${dataset}/preview`)
                        .then(response => response.text())
                        .then(html => {
                            previewDiv.innerHTML = html;
                        })
                        .catch(error => {
                            previewDiv.innerHTML = `<div class="alert alert-danger">Failed to load preview: ${error}</div>`;
                        });
                }
            </script>
        </body>
        </html>
    ''', datasets=datasets)

@app.route('/power-user')
@login_required
@role_required(['power'])
def power_user_dashboard():
    datasets = get_saved_datasets()
    return render_template_string('''
        <!DOCTYPE html>
        <html>
        <head>
            <title>Power User Dashboard - Tableau Data Reporter</title>
            <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
            <link href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.7.2/font/bootstrap-icons.css" rel="stylesheet">
            <style>
                .sidebar {
                    position: fixed;
                    top: 0;
                    bottom: 0;
                    left: 0;
                    z-index: 100;
                    padding: 48px 0 0;
                    box-shadow: inset -1px 0 0 rgba(0, 0, 0, .1);
                }
                .main {
                    margin-left: 240px;
                    padding: 20px;
                }
                .nav-link {
                    padding: 0.5rem 1rem;
                    font-size: 0.9rem;
                }
                .nav-link i {
                    margin-right: 8px;
                    width: 20px;
                    text-align: center;
                }
                .nav-link.active {
                    font-weight: bold;
                    background-color: rgba(0, 123, 255, 0.1);
                }
            </style>
        </head>
        <body>
            <nav class="col-md-3 col-lg-2 d-md-block bg-light sidebar">
                <div class="position-sticky pt-3">
                    <div class="px-3">
                        <h5>👤 User Profile</h5>
                        <p><strong>Username:</strong> {{ session.user.username }}</p>
                        <p><strong>Role:</strong> {{ session.user.role }}</p>
                    </div>
                    <hr>
                    <ul class="nav flex-column">
                        <li class="nav-item">
                            <a class="nav-link active" href="{{ url_for('power_user_dashboard') }}">
                                <i class="bi bi-house"></i> Dashboard
                            </a>
                        </li>
                        <li class="nav-item">
                            <a class="nav-link" href="{{ url_for('tableau_connect') }}">
                                <i class="bi bi-box-arrow-in-right"></i> Connect to Tableau
                            </a>
                        </li>
                        <li class="nav-item">
                            <a class="nav-link" href="{{ url_for('qa_page') }}">
                                <i class="bi bi-question-circle"></i> Ask Questions
                            </a>
                        </li>
                        <li class="nav-item">
                            <a class="nav-link" href="{{ url_for('schedule_reports') }}">
                                <i class="bi bi-calendar-plus"></i> Create Schedule
                            </a>
                        </li>
                        <li class="nav-item">
                            <a class="nav-link" href="{{ url_for('manage_schedules') }}">
                                <i class="bi bi-calendar-check"></i> Manage Schedules
                            </a>
                        </li>
                        <li class="nav-item">
                            <a class="nav-link" href="{{ url_for('logout') }}">
                                <i class="bi bi-box-arrow-right"></i> Logout
                            </a>
                        </li>
                    </ul>
                </div>
            </nav>

            <main class="main">
                <div class="container">
                    {% with messages = get_flashed_messages() %}
                        {% if messages %}
                            {% for message in messages %}
                                <div class="alert alert-info">{{ message }}</div>
                            {% endfor %}
                        {% endif %}
                    {% endwith %}

                    <h1 class="mb-4">Your Datasets</h1>
                    
                    {% if datasets %}
                        <div class="row">
                            {% for dataset in datasets %}
                                <div class="col-md-4 mb-4">
                                    <div class="card">
                                        <div class="card-body">
                                            <h5 class="card-title">{{ dataset }}</h5>
                                            <h6 class="card-subtitle mb-2 text-muted">
                                                <small>{{ get_dataset_row_count(dataset) }} rows</small>
                                            </h6>
                                            <div class="btn-group">
                                                <a href="#" class="btn btn-sm btn-outline-primary" 
                                                onclick="viewDatasetPreview('{{ dataset }}')">
                                                    <i class="bi bi-table"></i> View Preview
                                                </a>
                                                <a href="{{ url_for('qa_page') }}?dataset={{ dataset }}" 
                                                class="btn btn-sm btn-outline-success">
                                                    <i class="bi bi-question-circle"></i> Ask Questions
                                                </a>
                                                <a href="{{ url_for('schedule_dataset', dataset=dataset) }}" 
                                                class="btn btn-sm btn-outline-info">
                                                    <i class="bi bi-calendar-plus"></i> Schedule
                                                </a>
                                            </div>
                                        </div>
                                    </div>
                                </div>
                            {% endfor %}
                        </div>
                    {% else %}
                        <div class="alert alert-info">
                            <p>No datasets available. Please connect to Tableau and download data first.</p>
                            <a href="{{ url_for('tableau_connect') }}" class="btn btn-primary">
                                <i class="bi bi-box-arrow-in-right"></i> Connect to Tableau
                            </a>
                        </div>
                    {% endif %}
                    
                    <!-- Dataset Preview Modal -->
                    <div class="modal fade" id="datasetPreviewModal" tabindex="-1">
                        <div class="modal-dialog modal-xl">
                            <div class="modal-content">
                                <div class="modal-header">
                                    <h5 class="modal-title">Dataset Preview: <span id="datasetName"></span></h5>
                                    <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
                                </div>
                                <div class="modal-body">
                                    <div id="datasetPreview"></div>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </main>
            
            <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/js/bootstrap.bundle.min.js"></script>
            <script>
                function viewDatasetPreview(dataset) {
                    document.getElementById('datasetName').textContent = dataset;
                    const previewDiv = document.getElementById('datasetPreview');
                    previewDiv.innerHTML = '<div class="text-center"><div class="spinner-border" role="status"></div><p>Loading preview...</p></div>';
                    
                    // Show modal
                    const modal = new bootstrap.Modal(document.getElementById('datasetPreviewModal'));
                    modal.show();
                    
                    // Fetch preview
                    fetch(`/api/datasets/${dataset}/preview`)
                        .then(response => response.text())
                        .then(html => {
                            previewDiv.innerHTML = html;
                        })
                        .catch(error => {
                            previewDiv.innerHTML = `<div class="alert alert-danger">Failed to load preview: ${error}</div>`;
                        });
                }
            </script>
        </body>
        </html>
    ''', datasets=datasets, get_dataset_row_count=get_dataset_row_count)

@app.route('/qa-page')
@login_required
@role_required(['power', 'superadmin'])
def qa_page():
    dataset = request.args.get('dataset')
    datasets = get_saved_datasets()
    
    return render_template_string('''
        <!DOCTYPE html>
        <html>
        <head>
            <title>Ask Questions - Tableau Data Reporter</title>
            <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
            <style>
                body { padding: 20px; }
                .chat-container {
                    height: 400px;
                    overflow-y: auto;
                    border: 1px solid #dee2e6;
                    border-radius: 0.25rem;
                    padding: 1rem;
                    margin-bottom: 1rem;
                }
                .chat-message {
                    margin-bottom: 1rem;
                    padding: 0.5rem;
                    border-radius: 0.25rem;
                }
                .user-message {
                    background-color: #e9ecef;
                    margin-left: 20%;
                }
                .assistant-message {
                    background-color: #f8f9fa;
                    margin-right: 20%;
                }
                #visualization {
                    width: 100%;
                    height: 400px;
                    margin-top: 1rem;
                    border: 1px solid #dee2e6;
                    border-radius: 0.25rem;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                }
                .vis-placeholder {
                    color: #6c757d;
                    text-align: center;
                    font-style: italic;
                }
            </style>
        </head>
        <body>
            <div class="container">
                <div class="row justify-content-center">
                    <div class="col-md-10">
                        <div class="d-flex justify-content-between align-items-center mb-4">
                            <h1>❓ Ask Questions About Your Data</h1>
                            <a href="{{ url_for('home') }}" class="btn btn-outline-primary">← Back</a>
                        </div>
                        
                        <div class="card mb-4">
                            <div class="card-body">
                                <form id="questionForm">
                                    <div class="mb-3">
                                        <label class="form-label">Select Dataset</label>
                                        <select class="form-select" name="dataset" required>
                                            <option value="">Choose a dataset...</option>
                                            {% for ds in datasets %}
                                                <option value="{{ ds }}"
                                                        {% if ds == dataset %}selected{% endif %}>
                                                    {{ ds }}
                                                </option>
                                            {% endfor %}
                                        </select>
                                    </div>
                                    
                                    <div class="mb-3">
                                        <label class="form-label">Your Question</label>
                                        <div class="input-group">
                                            <input type="text" class="form-control" name="question"
                                                   placeholder="Ask a question about your data..."
                                                   required>
                                            <button type="submit" class="btn btn-primary">
                                                Ask Question
                                            </button>
                                        </div>
                                    </div>
                                </form>
                            </div>
                        </div>
                        
                        <div class="row">
                            <div class="col-md-6">
                                <div class="card">
                                    <div class="card-body">
                                        <h5 class="card-title">Conversation</h5>
                                        <div id="chatContainer" class="chat-container"></div>
                                    </div>
                                </div>
                            </div>
                            <div class="col-md-6">
                                <div class="card">
                                    <div class="card-body">
                                        <h5 class="card-title">Visualization</h5>
                                        <div id="visualization">
                                            <div class="vis-placeholder">Ask a question to see visualization</div>
                                        </div>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
            
            <script src="https://cdn.plot.ly/plotly-2.20.0.min.js"></script>
            <script>
                const questionForm = document.getElementById('questionForm');
                const chatContainer = document.getElementById('chatContainer');
                const visualizationDiv = document.getElementById('visualization');
                
                // Initialize visualization area
                visualizationDiv.innerHTML = '<div class="vis-placeholder">Ask a question to see visualization</div>';
                
                questionForm.addEventListener('submit', async (e) => {
                    e.preventDefault();
                    
                    const formData = new FormData(questionForm);
                    const dataset = formData.get('dataset');
                    const question = formData.get('question');
                    
                    // Clear previous visualization
                    visualizationDiv.innerHTML = '<div class="spinner-border text-primary" role="status"><span class="visually-hidden">Loading...</span></div>';
                    
                    // Add user message to chat
                    addMessage(question, 'user');
                    
                    try {
                        // Show loading message in assistant chat
                        const loadingMsgId = 'loading-' + Date.now();
                        addMessage('Analyzing data...', 'assistant', loadingMsgId);
                        
                        const response = await fetch('/api/ask-question', {
                            method: 'POST',
                            headers: {
                                'Content-Type': 'application/json'
                            },
                            body: JSON.stringify({
                                dataset: dataset,
                                question: question
                            })
                        });
                        
                        const data = await response.json();
                        
                        // Remove loading message
                        const loadingMsg = document.getElementById(loadingMsgId);
                        if (loadingMsg) loadingMsg.remove();
                        
                        if (data.success) {
                            // Add assistant's response to chat
                            addMessage(data.answer, 'assistant');
                            
                            // Update visualization if provided
                            if (data.visualization) {
                                console.log('Received visualization data:', data.visualization);
                                try {
                                    // Clear the visualization div
                                    visualizationDiv.innerHTML = '';
                                    
                                    // Create new Plotly chart
                                    Plotly.newPlot(visualizationDiv, data.visualization.data, data.visualization.layout);
                                } catch (visError) {
                                    console.error('Error displaying visualization:', visError);
                                    visualizationDiv.innerHTML = '<div class="alert alert-warning">Failed to display visualization: ' + visError.message + '</div>';
                                }
                            } else {
                                visualizationDiv.innerHTML = '<div class="vis-placeholder">No visualization available for this query</div>';
                            }
                        } else {
                            addMessage('Error: ' + data.error, 'assistant');
                            visualizationDiv.innerHTML = '<div class="alert alert-danger">Error: ' + data.error + '</div>';
                        }
                    } catch (error) {
                        console.error('API request error:', error);
                        addMessage('Error: Failed to get response. Check console for details.', 'assistant');
                        visualizationDiv.innerHTML = '<div class="alert alert-danger">Request failed: ' + error.message + '</div>';
                    }
                    
                    // Clear question input
                    questionForm.querySelector('input[name="question"]').value = '';
                });
                
                function addMessage(message, type, id = null) {
                    const messageDiv = document.createElement('div');
                    messageDiv.className = `chat-message ${type}-message`;
                    if (id) messageDiv.id = id;
                    messageDiv.textContent = message;
                    chatContainer.appendChild(messageDiv);
                    chatContainer.scrollTop = chatContainer.scrollHeight;
                }
                
                // If dataset is provided in URL, simulate click on Ask Questions button
                const urlParams = new URLSearchParams(window.location.search);
                const datasetParam = urlParams.get('dataset');
                if (datasetParam) {
                    const datasetSelect = questionForm.querySelector('select[name="dataset"]');
                    if (datasetSelect) {
                        datasetSelect.value = datasetParam;
                    }
                }
            </script>
        </body>
        </html>
    ''', datasets=datasets, dataset=dataset)

@app.route('/api/ask-question', methods=['POST'])
@login_required
@role_required(['power', 'superadmin'])
def ask_question_api():
    try:
        data = request.json
        dataset = data.get('dataset')
        question = data.get('question')
        
        if not dataset or not question:
            return jsonify({
                'success': False,
                'error': 'Dataset and question are required'
            })
        
        # Load dataset
        with sqlite3.connect('data/tableau_data.db') as conn:
            df = pd.read_sql_query(f"SELECT * FROM '{dataset}'", conn)
        
        # Get answer and visualization
        answer, visualization = data_analyzer.ask_question(df, question)
        
        # Debug: Log the visualization type and structure
        print(f"Visualization type: {type(visualization)}")
        
        # Convert visualization to a format the frontend can use
        vis_data = None
        
        # If we have a Plotly figure, convert it to JSON directly
        if visualization is not None:
            try:
                # Check if it's a Plotly figure by looking for common attributes
                if hasattr(visualization, 'data') and hasattr(visualization, 'layout'):
                    print("Using Plotly figure conversion")
                    # Create a clean dictionary structure for the frontend
                    vis_data = {
                        'data': [
                            # Convert each trace to a basic dict and handle numpy types
                            {k: convert_numpy_types(v) for k, v in trace.items() if k not in ['_legend', '_meta']}
                            for trace in visualization.data
                        ],
                        'layout': {
                            # Include only the essential layout properties
                            k: convert_numpy_types(v)
                            for k, v in visualization.layout.items()
                            if k not in ['_grid_ref', '_meta', '_subplot_refs']
                        }
                    }
                # Try to get JSON representation from to_json if available
                elif hasattr(visualization, 'to_json'):
                    print("Using to_json method")
                    vis_json = visualization.to_json()
                    vis_data = json.loads(vis_json)
                # Last resort - use the figure's dict representation if available
                elif hasattr(visualization, 'to_dict'):
                    print("Using to_dict method")
                    vis_dict = visualization.to_dict()
                    vis_data = convert_numpy_types(vis_dict)
                else:
                    print("Visualization format not recognized - sending as None")
                    vis_data = None
                    
                # Verify that visualization data is JSON serializable
                json.dumps(vis_data)  # This will raise an error if not serializable
                
            except Exception as e:
                print(f"Error converting visualization to JSON: {str(e)}")
                import traceback
                traceback.print_exc()
                vis_data = None
                
        return jsonify({
            'success': True,
            'answer': answer,
            'visualization': vis_data
        })
        
    except Exception as e:
        print(f"Error in ask_question_api: {str(e)}")
        import traceback
        traceback.print_exc()  # Print full stack trace for debugging
        return jsonify({
            'success': False,
            'error': str(e)
        })

# Helper function to convert numpy types to Python standard types
def convert_numpy_types(obj):
    import numpy as np
    
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    elif isinstance(obj, np.integer):
        return int(obj)
    elif isinstance(obj, np.floating):
        return float(obj)
    elif isinstance(obj, np.bool_):
        return bool(obj)
    elif isinstance(obj, dict):
        return {key: convert_numpy_types(value) for key, value in obj.items()}
    elif isinstance(obj, list) or isinstance(obj, tuple):
        return [convert_numpy_types(item) for item in obj]
    else:
        return obj

def get_dataset_preview_html(dataset_name):
    """Get HTML preview of dataset"""
    try:
        with sqlite3.connect('data/tableau_data.db') as conn:
            df = pd.read_sql_query(f"SELECT * FROM '{dataset_name}' LIMIT 5", conn)
            return df.to_html(classes='table table-sm', index=False)
    except Exception as e:
        print(f"Error getting dataset preview: {str(e)}")
        return "<div class='alert alert-danger'>Error loading preview</div>"

def get_dataset_row_count(dataset_name):
    """Get row count for dataset"""
    try:
        with sqlite3.connect('data/tableau_data.db') as conn:
            cursor = conn.cursor()
            cursor.execute(f"SELECT COUNT(*) FROM '{dataset_name}'")
            return cursor.fetchone()[0]
    except Exception as e:
        print(f"Error getting row count: {str(e)}")
        return 0

def get_saved_datasets():
    """Get list of saved datasets"""
    try:
        with sqlite3.connect('data/tableau_data.db') as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT name FROM sqlite_master 
                WHERE type='table' 
                AND name NOT IN (
                    'users', 
                    'organizations', 
                    'schedules', 
                    'sqlite_sequence', 
                    'schedule_runs',
                    '_internal_tableau_connections'
                )
                AND name NOT LIKE 'sqlite_%'
            """)
            return [row[0] for row in cursor.fetchall()]
    except Exception as e:
        print(f"Error getting datasets: {str(e)}")
        return []

# API endpoints for AJAX calls
@app.route('/api/datasets/<dataset>', methods=['DELETE'])
@login_required
def delete_dataset_api(dataset):
    try:
        with sqlite3.connect('data/tableau_data.db') as conn:
            cursor = conn.cursor()
            cursor.execute(f"DROP TABLE IF EXISTS '{dataset}'")
            conn.commit()
        return jsonify({'success': True})
    except Exception as e:
        print(f"Error deleting dataset: {str(e)}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/datasets/<dataset>/preview')
@login_required
def dataset_preview_api(dataset):
    try:
        preview_html = get_dataset_preview_html(dataset)
        return preview_html
    except Exception as e:
        print(f"Error generating preview for {dataset}: {str(e)}")
        return f"<div class='alert alert-danger'>Error: {str(e)}</div>"

@app.route('/admin')
@login_required
@role_required(['superadmin'])
def admin_dashboard():
    # Get users list
    try:
        # Get users from database
        with sqlite3.connect('data/tableau_data.db') as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT u.rowid, u.username, u.email, u.role, u.organization_id, o.name
                FROM users u
                LEFT JOIN organizations o ON u.organization_id = o.rowid
            """)
            users = []
            for row in cursor.fetchall():
                users.append({
                    'id': row[0],
                    'username': row[1],
                    'email': row[2],
                    'role': row[3],
                    'organization_id': row[4],
                    'organization_name': row[5]
                })
                
        # Get organizations
        with sqlite3.connect('data/tableau_data.db') as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT rowid, name FROM organizations")
            organizations = []
            for row in cursor.fetchall():
                organizations.append({
                    'id': row[0],
                    'name': row[1]
                })
                
        return render_template_string('''
            <!DOCTYPE html>
            <html>
            <head>
                <title>Admin Dashboard - Tableau Data Reporter</title>
                <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
                <style>
                    .sidebar {
                        position: fixed;
                        top: 0;
                        bottom: 0;
                        left: 0;
                        z-index: 100;
                        padding: 48px 0 0;
                        box-shadow: inset -1px 0 0 rgba(0, 0, 0, .1);
                    }
                    .main {
                        margin-left: 240px;
                        padding: 20px;
                    }
                </style>
            </head>
            <body>
                <nav class="col-md-3 col-lg-2 d-md-block bg-light sidebar">
                    <div class="position-sticky pt-3">
                        <div class="px-3">
                            <h5>👤 Admin Profile</h5>
                            <p><strong>Username:</strong> {{ session.user.username }}</p>
                            <p><strong>Role:</strong> {{ session.user.role }}</p>
                        </div>
                        <hr>
                        <div class="px-3">
                            <a href="{{ url_for('admin_users') }}" class="btn btn-primary w-100 mb-2">👥 Users</a>
                            <a href="{{ url_for('admin_organizations') }}" class="btn btn-primary w-100 mb-2">🏢 Organizations</a>
                            <a href="{{ url_for('admin_system') }}" class="btn btn-primary w-100 mb-2">⚙️ System</a>
                            <hr>
                            <a href="{{ url_for('logout') }}" class="btn btn-secondary w-100">🚪 Logout</a>
                        </div>
                    </div>
                </nav>
                
                <main class="main">
                    <h1>👥 User Management</h1>
                    
                    <div class="card mb-4">
                        <div class="card-body">
                            <h5>Add New User</h5>
                            <form id="addUserForm" onsubmit="return addUser(event)">
                                <div class="row">
                                    <div class="col-md-4">
                                        <div class="mb-3">
                                            <label class="form-label">Username</label>
                                            <input type="text" class="form-control" name="username" required>
                                        </div>
                                    </div>
                                    <div class="col-md-4">
                                        <div class="mb-3">
                                            <label class="form-label">Email</label>
                                            <input type="email" class="form-control" name="email" required>
                                        </div>
                                    </div>
                                    <div class="col-md-4">
                                        <div class="mb-3">
                                            <label class="form-label">Password</label>
                                            <input type="password" class="form-control" name="password" required>
                                        </div>
                                    </div>
                                </div>
                                <div class="row">
                                    <div class="col-md-4">
                                        <div class="mb-3">
                                            <label class="form-label">Permission Type</label>
                                            <select class="form-select" name="permission_type" required>
                                                <option value="normal">Normal</option>
                                                <option value="power">Power</option>
                                                <option value="superadmin">Superadmin</option>
                                            </select>
                                        </div>
                                    </div>
                                    <div class="col-md-4">
                                        <div class="mb-3">
                                            <label class="form-label">Organization</label>
                                            <select class="form-select" name="organization_id">
                                                <option value="">No Organization</option>
                                                {% for org in organizations %}
                                                    <option value="{{ org.id }}">{{ org.name }}</option>
                                                {% endfor %}
                                            </select>
                                        </div>
                                    </div>
                                    <div class="col-md-4">
                                        <div class="mb-3">
                                            <label class="form-label">&nbsp;</label>
                                            <button type="submit" class="btn btn-primary w-100">Create User</button>
                                        </div>
                                    </div>
                                </div>
                            </form>
                        </div>
                    </div>
                    
                    <div class="card">
                        <div class="card-body">
                            <div class="d-flex justify-content-between align-items-center mb-3">
                                <h5 class="mb-0">Existing Users</h5>
                                <div class="d-flex gap-2">
                                    <input type="text" class="form-control" id="searchUser" 
                                        placeholder="Search users..." onkeyup="filterUsers()">
                                    <select class="form-select" id="filterPermission" onchange="filterUsers()">
                                        <option value="">All Permissions</option>
                                        <option value="normal">Normal</option>
                                        <option value="power">Power</option>
                                        <option value="superadmin">Superadmin</option>
                                    </select>
                                </div>
                            </div>
                            
                            <div class="table-responsive">
                                <table class="table table-hover">
                                    <thead>
                                        <tr>
                                            <th>Username</th>
                                            <th>Email</th>
                                            <th>Role</th>
                                            <th>Organization</th>
                                            <th>Actions</th>
                                        </tr>
                                    </thead>
                                    <tbody id="userTableBody">
                                        {% for user in users %}
                                            <tr>
                                                <td>{{ user.username }}</td>
                                                <td>{{ user.email }}</td>
                                                <td>{{ user.role }}</td>
                                                <td>{{ user.organization_name or 'None' }}</td>
                                                <td>
                                                    <div class="btn-group btn-group-sm">
                                                        <button class="btn btn-outline-primary"
                                                                onclick="editUser('{{ user.id }}')">
                                                            ✏️ Edit
                                                        </button>
                                                        <button class="btn btn-outline-danger"
                                                                onclick="deleteUser('{{ user.id }}')">
                                                            🗑️ Delete
                                                        </button>
                                                    </div>
                                                </td>
                                            </tr>
                                        {% endfor %}
                                    </tbody>
                                </table>
                            </div>
                        </div>
                    </div>
                </main>
                
                <!-- Edit User Modal -->
                <div class="modal fade" id="editUserModal" tabindex="-1" aria-hidden="true">
                    <div class="modal-dialog">
                        <div class="modal-content">
                            <div class="modal-header">
                                <h5 class="modal-title">Edit User</h5>
                                <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
                            </div>
                            <div class="modal-body">
                                <form id="editUserForm">
                                    <input type="hidden" id="edit-user-id" name="id">
                                    <div class="mb-3">
                                        <label class="form-label">Username</label>
                                        <input type="text" class="form-control" id="edit-username" name="username" required>
                                    </div>
                                    <div class="mb-3">
                                        <label class="form-label">Email</label>
                                        <input type="email" class="form-control" id="edit-email" name="email" required>
                                    </div>
                                    <div class="mb-3">
                                        <label class="form-label">Password</label>
                                        <input type="password" class="form-control" id="edit-password" name="password" 
                                            placeholder="Leave blank to keep current password">
                                        <div class="form-text">Leave blank to keep the current password</div>
                                    </div>
                                    <div class="mb-3">
                                        <label class="form-label">Permission Type</label>
                                        <select class="form-select" id="edit-permission-type" name="permission_type" required>
                                            <option value="normal">Normal</option>
                                            <option value="power">Power</option>
                                            <option value="superadmin">Superadmin</option>
                                        </select>
                                    </div>
                                    <div class="mb-3">
                                        <label class="form-label">Organization</label>
                                        <select class="form-select" id="edit-organization-id" name="organization_id">
                                            <option value="">No Organization</option>
                                            {% for org in organizations %}
                                                <option value="{{ org.id }}">{{ org.name }}</option>
                                            {% endfor %}
                                        </select>
                                    </div>
                                </form>
                            </div>
                            <div class="modal-footer">
                                <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Cancel</button>
                                <button type="button" class="btn btn-primary" onclick="updateUser()">Save Changes</button>
                            </div>
                        </div>
                    </div>
                </div>
                
                <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/js/bootstrap.bundle.min.js"></script>
                <script>
                    function addUser(event) {
                        event.preventDefault();
                        const form = event.target;
                        const formData = new FormData(form);
                        
                        fetch('/api/users', {
                            method: 'POST',
                            headers: {
                                'Content-Type': 'application/json',
                            },
                            body: JSON.stringify(Object.fromEntries(formData))
                        })
                        .then(response => response.json())
                        .then(data => {
                            if (data.success) {
                                location.reload();
                            } else {
                                alert(data.error || 'Failed to create user');
                            }
                        });
                        
                        return false;
                    }
                    
                    function editUser(userId) {
                        console.log('editUser function called with userId:', userId);
                        
                        // Fetch user data
                        fetch(`/api/users/${userId}`)
                            .then(response => response.json())
                            .then(data => {
                                if (data.success) {
                                    // Populate the form
                                    const user = data.user;
                                    document.getElementById('edit-user-id').value = user.id;
                                    document.getElementById('edit-username').value = user.username;
                                    document.getElementById('edit-email').value = user.email;
                                    document.getElementById('edit-permission-type').value = user.role;
                                    document.getElementById('edit-organization-id').value = user.organization_id;
                                    
                                    // Clear password field
                                    document.getElementById('edit-password').value = '';
                                    
                                    // Try to show the modal using Bootstrap
                                    try {
                                        // Try using Bootstrap 5 approach
                                        const modalElement = document.getElementById('editUserModal');
                                        if (typeof bootstrap !== 'undefined') {
                                            const modal = new bootstrap.Modal(modalElement);
                                            modal.show();
                                        } else {
                                            // Fallback if Bootstrap JS is not loaded
                                            console.log('Bootstrap not loaded, using fallback to show modal');
                                            modalElement.style.display = 'block';
                                            modalElement.classList.add('show');
                                            modalElement.setAttribute('aria-modal', 'true');
                                            document.body.classList.add('modal-open');
                                            
                                            // Add backdrop
                                            const backdrop = document.createElement('div');
                                            backdrop.className = 'modal-backdrop fade show';
                                            document.body.appendChild(backdrop);
                                        }
                                    } catch (e) {
                                        console.error('Error showing modal:', e);
                                        alert('Error showing modal. Try refreshing the page.');
                                    }
                                } else {
                                    alert(data.error || 'Failed to get user data');
                                }
                            })
                            .catch(error => {
                                alert('Error fetching user data: ' + error);
                            });
                    }
                    
                    function updateUser() {
                        console.log('updateUser function called');
                        const userId = document.getElementById('edit-user-id').value;
                        const formData = new FormData(document.getElementById('editUserForm'));
                        
                        fetch(`/api/users/${userId}`, {
                            method: 'PUT',
                            headers: {
                                'Content-Type': 'application/json',
                            },
                            body: JSON.stringify(Object.fromEntries(formData))
                        })
                        .then(response => response.json())
                        .then(data => {
                            if (data.success) {
                                // Try to close the modal
                                try {
                                    const modalElement = document.getElementById('editUserModal');
                                    
                                    if (typeof bootstrap !== 'undefined') {
                                        // Bootstrap 5 approach
                                        const modalInstance = bootstrap.Modal.getInstance(modalElement);
                                        if (modalInstance) {
                                            modalInstance.hide();
                                        }
                                    } else {
                                        // Fallback if Bootstrap JS is not loaded
                                        modalElement.style.display = 'none';
                                        modalElement.classList.remove('show');
                                        modalElement.setAttribute('aria-modal', 'false');
                                        document.body.classList.remove('modal-open');
                                        
                                        // Remove backdrop if it exists
                                        const backdrop = document.querySelector('.modal-backdrop');
                                        if (backdrop) {
                                            backdrop.remove();
                                        }
                                    }
                                } catch (e) {
                                    console.error('Error closing modal:', e);
                                }
                                
                                // Reload the page to show updated data
                                location.reload();
                            } else {
                                alert(data.error || 'Failed to update user');
                            }
                        })
                        .catch(error => {
                            console.error('Error updating user:', error);
                            alert('Error updating user: ' + error);
                        });
                    }
                </script>
            </body>
            </html>
        ''', users=users, organizations=organizations)
        
    except Exception as e:
        print(f"Error in admin_dashboard function: {str(e)}")
        print(f"Exception type: {type(e).__name__}")
        flash(f'Error loading admin dashboard: {str(e)}')
        return redirect(url_for('home'))

@app.route('/create_schedule', methods=['POST'])
def process_schedule_form():
    try:
        # Get form data
        dataset_name = request.form.get('dataset_name')
        if not dataset_name:
            flash('Dataset name is required', 'error')
            return redirect(url_for('manage_schedules'))
        
        # Debug: Print all form data to see what's being submitted
        print("Form data received:")
        for key, value in request.form.items():
            print(f"  {key}: {value}")
            
        # Get timezone from form or default to UTC
        timezone_str = request.form.get('timezone', 'UTC')
        print(f"Selected timezone: {timezone_str}")
            
        # Schedule type and time - explicitly convert to int with proper error handling
        schedule_type = request.form.get('schedule_type')
        
        # For hour and minute, check raw form values first
        try:
            raw_hour = request.form.get('hour')
            raw_minute = request.form.get('minute')
            print(f"Raw hour value from form: '{raw_hour}'")
            print(f"Raw minute value from form: '{raw_minute}'")
            
            # Try to convert to integer
            hour = int(raw_hour) if raw_hour else 0
            minute = int(raw_minute) if raw_minute else 0
        except (ValueError, TypeError) as e:
            print(f"Error parsing hour/minute: {str(e)}")
            # Fallback to default
            hour = 0
            minute = 0
            
        print(f"Submitted time: {hour:02d}:{minute:02d}")
        print(f"Parsed hour: {hour}, minute: {minute}")
        
        # Create schedule configuration
        schedule_config = {
            'type': schedule_type,
            'hour': hour,
            'minute': minute,
            'timezone': timezone_str,
            'time_str': f"{hour:02d}:{minute:02d} ({timezone_str})" # For display
        }
        
        # Add schedule-specific parameters
        if schedule_type == 'one-time':
            date = request.form.get('date')
            print(f"Date from form: '{date}'")
            if not date:
                flash('Date is required for one-time schedules', 'error')
                return redirect(url_for('manage_schedules'))
            schedule_config['date'] = date
            
            # Add local and UTC datetimes for reference
            try:
                # Use pytz to create timezone-aware datetime
                dt_str = f"{date} {hour:02d}:{minute:02d}:00"
                print(f"Creating datetime from: '{dt_str}'")
                timezone = pytz.timezone(timezone_str)
                local_dt = timezone.localize(datetime.strptime(dt_str, '%Y-%m-%d %H:%M:%S'))
                utc_dt = local_dt.astimezone(pytz.UTC)
                schedule_config['local_datetime'] = local_dt.isoformat()
                schedule_config['utc_datetime'] = utc_dt.isoformat()
                print(f"Parsed datetime: {local_dt.isoformat()} (local), {utc_dt.isoformat()} (UTC)")
            except Exception as e:
                print(f"Error parsing datetime: {str(e)}")
                # Continue without the parsed datetime - not critical
        
        elif schedule_type == 'weekly':
            days = request.form.getlist('days')
            if not days:
                flash('At least one day must be selected for weekly schedules', 'error')
                return redirect(url_for('manage_schedules'))
            schedule_config['days'] = days
            
        elif schedule_type == 'monthly':
            day_option = request.form.get('day_option', 'Specific Day')
            schedule_config['day_option'] = day_option
            
            if day_option == 'Specific Day':
                day = request.form.get('day')
                if not day:
                    flash('Day is required for monthly schedules with specific day', 'error')
                    return redirect(url_for('manage_schedules'))
                schedule_config['day'] = int(day)
                
        # Email configuration
        email_config = {
            'recipients': request.form.getlist('recipients'),
            'cc': request.form.getlist('cc'),
            'subject': request.form.get('subject', f'Report for {dataset_name}'),
            'body': request.form.get('body', 'Please find the attached report.')
        }
        
        # Format configuration
        format_type = request.form.get('format_type')
        format_config = {'type': format_type}
        
        if format_type == 'csv':
            format_config['delimiter'] = request.form.get('delimiter', ',')
            format_config['quotechar'] = request.form.get('quotechar', '"')
            
        elif format_type == 'excel':
            format_config['sheet_name'] = request.form.get('sheet_name', 'Sheet1')
            
        elif format_type == 'json':
            format_config['indent'] = int(request.form.get('indent', 4))
            format_config['orient'] = request.form.get('orient', 'records')
            
        # Schedule the report
        job_id = report_manager.schedule_report(dataset_name, schedule_config, email_config, format_config)
        
        if job_id:
            flash(f"Schedule created successfully. Next run at: {report_manager.get_next_run_time(job_id)}", 'success')
        else:
            flash("Failed to create schedule. Check logs for details.", 'error')
            
        return redirect(url_for('manage_schedules'))
        
    except Exception as e:
        print(f"Error in process_schedule_form: {str(e)}")
        flash(f"Error creating schedule: {str(e)}", 'error')
        return redirect(url_for('manage_schedules'))

# Fix the admin routes to match endpoint names
@app.route('/admin_users')
@login_required
@role_required(['superadmin'])
def admin_users():
    # Redirect to admin dashboard since it already has the user management UI
    return redirect(url_for('admin_dashboard'))

@app.route('/admin_organizations')
@login_required
@role_required(['superadmin'])
def admin_organizations():
    # Get organizations from database
    try:
        with sqlite3.connect('data/tableau_data.db') as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT rowid, name FROM organizations")
            organizations = []
            for row in cursor.fetchall():
                organizations.append({
                    'id': row[0],
                    'name': row[1]
                })
        
        # Organizations management page
        return render_template_string('''
            <!DOCTYPE html>
            <html>
            <head>
                <title>Organizations - Tableau Data Reporter</title>
                <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
                <style>
                    .sidebar {
                        position: fixed;
                        top: 0;
                        bottom: 0;
                        left: 0;
                        z-index: 100;
                        padding: 48px 0 0;
                        box-shadow: inset -1px 0 0 rgba(0, 0, 0, .1);
                    }
                    .main {
                        margin-left: 240px;
                        padding: 20px;
                    }
                </style>
            </head>
            <body>
                <nav class="col-md-3 col-lg-2 d-md-block bg-light sidebar">
                    <div class="position-sticky pt-3">
                        <div class="px-3">
                            <h5>👤 Admin Profile</h5>
                            <p><strong>Username:</strong> {{ session.user.username }}</p>
                            <p><strong>Role:</strong> {{ session.user.role }}</p>
                        </div>
                        <hr>
                        <div class="px-3">
                            <a href="{{ url_for('admin_users') }}" class="btn btn-primary w-100 mb-2">👥 Users</a>
                            <a href="{{ url_for('admin_organizations') }}" class="btn btn-primary w-100 mb-2">🏢 Organizations</a>
                            <a href="{{ url_for('admin_system') }}" class="btn btn-primary w-100 mb-2">⚙️ System</a>
                            <hr>
                            <a href="{{ url_for('logout') }}" class="btn btn-secondary w-100">🚪 Logout</a>
                        </div>
                    </div>
                </nav>
                
                <main class="main">
                    <h1>🏢 Organizations Management</h1>
                    
                    <div class="card mb-4">
                        <div class="card-body">
                            <h5>Add New Organization</h5>
                            <form id="addOrgForm" onsubmit="return addOrganization(event)">
                                <div class="row">
                                    <div class="col-md-6">
                                        <div class="mb-3">
                                            <label class="form-label">Organization Name</label>
                                            <input type="text" class="form-control" name="name" required>
                                        </div>
                                    </div>
                                    <div class="col-md-6">
                                        <div class="mb-3">
                                            <label class="form-label">&nbsp;</label>
                                            <button type="submit" class="btn btn-primary w-100">Create Organization</button>
                                        </div>
                                    </div>
                                </div>
                            </form>
                        </div>
                    </div>
                    
                    <div class="card">
                        <div class="card-body">
                            <h5>Existing Organizations</h5>
                            <div class="table-responsive">
                                <table class="table table-hover">
                                    <thead>
                                        <tr>
                                            <th>ID</th>
                                            <th>Name</th>
                                            <th>Actions</th>
                                        </tr>
                                    </thead>
                                    <tbody>
                                        {% for org in organizations %}
                                            <tr>
                                                <td>{{ org.id }}</td>
                                                <td>{{ org.name }}</td>
                                                <td>
                                                    <div class="btn-group btn-group-sm">
                                                        <button class="btn btn-outline-primary"
                                                                onclick="editOrg('{{ org.id }}')">
                                                            ✏️ Edit
                                                        </button>
                                                        <button class="btn btn-outline-danger"
                                                                onclick="deleteOrg('{{ org.id }}')">
                                                            🗑️ Delete
                                                        </button>
                                                    </div>
                                                </td>
                                            </tr>
                                        {% endfor %}
                                    </tbody>
                                </table>
                            </div>
                        </div>
                    </div>
                </main>
                
                <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/js/bootstrap.bundle.min.js"></script>
                <script>
                    function addOrganization(event) {
                        event.preventDefault();
                        // Implement add organization functionality
                        alert('Add organization functionality not implemented yet');
                        return false;
                    }
                    
                    function editOrg(orgId) {
                        // Implement edit organization functionality
                        alert('Edit organization functionality not implemented yet');
                    }
                    
                    function deleteOrg(orgId) {
                        // Implement delete organization functionality
                        alert('Delete organization functionality not implemented yet');
                    }
                </script>
            </body>
            </html>
        ''', organizations=organizations)
    except Exception as e:
        print(f"Error in admin_organizations function: {str(e)}")
        print(f"Exception type: {type(e).__name__}")
        flash(f'Error loading organizations page: {str(e)}')
        return redirect(url_for('admin_dashboard'))

@app.route('/admin_system')
@login_required
@role_required(['superadmin'])
def admin_system():
    # System settings page
    try:
        import sys
        import flask
        import time
        from datetime import datetime
        
        return render_template_string('''
            <!DOCTYPE html>
            <html>
            <head>
                <title>System Settings - Tableau Data Reporter</title>
                <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
                <style>
                    .sidebar {
                        position: fixed;
                        top: 0;
                        bottom: 0;
                        left: 0;
                        z-index: 100;
                        padding: 48px 0 0;
                        box-shadow: inset -1px 0 0 rgba(0, 0, 0, .1);
                    }
                    .main {
                        margin-left: 240px;
                        padding: 20px;
                    }
                </style>
            </head>
            <body>
                <nav class="col-md-3 col-lg-2 d-md-block bg-light sidebar">
                    <div class="position-sticky pt-3">
                        <div class="px-3">
                            <h5>👤 Admin Profile</h5>
                            <p><strong>Username:</strong> {{ session.user.username }}</p>
                            <p><strong>Role:</strong> {{ session.user.role }}</p>
                        </div>
                        <hr>
                        <div class="px-3">
                            <a href="{{ url_for('admin_users') }}" class="btn btn-primary w-100 mb-2">👥 Users</a>
                            <a href="{{ url_for('admin_organizations') }}" class="btn btn-primary w-100 mb-2">🏢 Organizations</a>
                            <a href="{{ url_for('admin_system') }}" class="btn btn-primary w-100 mb-2">⚙️ System</a>
                            <hr>
                            <a href="{{ url_for('logout') }}" class="btn btn-secondary w-100">🚪 Logout</a>
                        </div>
                    </div>
                </nav>
                
                <main class="main">
                    <h1>⚙️ System Settings</h1>
                    
                    <div class="card mb-4">
                        <div class="card-body">
                            <h5>Email Configuration</h5>
                            <form id="emailConfigForm">
                                <div class="mb-3">
                                    <label class="form-label">SMTP Server</label>
                                    <input type="text" class="form-control" name="smtp_server" 
                                          value="{{ os.getenv('SMTP_SERVER', '') }}">
                                </div>
                                <div class="mb-3">
                                    <label class="form-label">SMTP Port</label>
                                    <input type="number" class="form-control" name="smtp_port" 
                                          value="{{ os.getenv('SMTP_PORT', '587') }}">
                                </div>
                                <div class="mb-3">
                                    <label class="form-label">Sender Email</label>
                                    <input type="email" class="form-control" name="sender_email" 
                                          value="{{ os.getenv('SENDER_EMAIL', '') }}">
                                </div>
                                <div class="mb-3">
                                    <label class="form-label">Sender Password</label>
                                    <input type="password" class="form-control" name="sender_password" 
                                          value="{{ os.getenv('SENDER_PASSWORD', '') }}">
                                </div>
                                <button type="submit" class="btn btn-primary">Save Settings</button>
                            </form>
                        </div>
                    </div>
                    
                    <div class="card mb-4">
                        <div class="card-body">
                            <h5>Database Management</h5>
                            <div class="row">
                                <div class="col-md-6">
                                    <div class="mb-3">
                                        <label class="form-label">Backup Database</label>
                                        <button class="btn btn-primary w-100" onclick="backupDatabase()">
                                            Create Backup
                                        </button>
                                    </div>
                                </div>
                                <div class="col-md-6">
                                    <div class="mb-3">
                                        <label class="form-label">Restore Database</label>
                                        <input type="file" class="form-control" id="restoreFile" accept=".db">
                                        <button class="btn btn-warning w-100 mt-2" onclick="restoreDatabase()">
                                            Restore from Backup
                                        </button>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                    
                    <div class="card">
                        <div class="card-body">
                            <h5>System Information</h5>
                            <div class="table-responsive">
                                <table class="table">
                                    <tbody>
                                        <tr>
                                            <th>Python Version</th>
                                            <td>{{ sys.version.split()[0] }}</td>
                                        </tr>
                                        <tr>
                                            <th>Flask Version</th>
                                            <td>{{ flask.__version__ }}</td>
                                        </tr>
                                        <tr>
                                            <th>Server Time</th>
                                            <td>{{ datetime.now().strftime('%Y-%m-%d %H:%M:%S') }}</td>
                                        </tr>
                                        <tr>
                                            <th>Server Timezone</th>
                                            <td>{{ time.tzname[0] }}</td>
                                        </tr>
                                    </tbody>
                                </table>
                            </div>
                        </div>
                    </div>
                </main>
                
                <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/js/bootstrap.bundle.min.js"></script>
                <script>
                    document.getElementById('emailConfigForm').addEventListener('submit', function(e) {
                        e.preventDefault();
                        // Implement save email settings functionality
                        alert('Save email settings functionality not implemented yet');
                    });
                    
                    function backupDatabase() {
                        // Implement backup database functionality
                        alert('Backup database functionality not implemented yet');
                    }
                    
                    function restoreDatabase() {
                        // Implement restore database functionality
                        alert('Restore database functionality not implemented yet');
                    }
                </script>
            </body>
            </html>
        ''', os=os, sys=sys, flask=flask, time=time, datetime=datetime)
    except Exception as e:
        print(f"Error in admin_system function: {str(e)}")
        print(f"Exception type: {type(e).__name__}")
        flash(f'Error loading system settings page: {str(e)}')
        return redirect(url_for('admin_dashboard'))

@app.route('/api/users/<user_id>', methods=['GET'])
@login_required
@role_required(['superadmin'])
def get_user_api(user_id):
    try:
        with sqlite3.connect('data/tableau_data.db') as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT u.rowid, u.username, u.email, u.role, u.organization_id
                FROM users u
                WHERE u.rowid = ?
            """, (user_id,))
            user_data = cursor.fetchone()
            
            if not user_data:
                return jsonify({'success': False, 'error': 'User not found'})
                
            user = {
                'id': user_data[0],
                'username': user_data[1],
                'email': user_data[2],
                'role': user_data[3],
                'organization_id': user_data[4] or ''
            }
            
            return jsonify({'success': True, 'user': user})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/users/<user_id>', methods=['PUT'])
@login_required
@role_required(['superadmin'])
def update_user_api(user_id):
    try:
        data = request.json
        
        # Prepare the update data
        update_data = {
            'username': data.get('username'),
            'email': data.get('email'),
            'role': data.get('permission_type'),  # Map permission_type to role
            'organization_id': data.get('organization_id') or None
        }
        
        # Only include password if it was provided and not empty
        if data.get('password') and data.get('password').strip():
            update_data['password_hash'] = generate_password_hash(data['password'])
        
        # Update the user in the database
        with sqlite3.connect('data/tableau_data.db') as conn:
            cursor = conn.cursor()
            
            # Construct the SET clause dynamically based on what fields are provided
            set_clause = ", ".join([f"{key} = ?" for key in update_data.keys()])
            values = list(update_data.values())
            values.append(user_id)  # For the WHERE clause
            
            query = f"UPDATE users SET {set_clause} WHERE rowid = ?"
            cursor.execute(query, values)
            conn.commit()
            
            if cursor.rowcount == 0:
                return jsonify({'success': False, 'error': 'User not found or no changes made'})
            
            return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/tableau-connect', endpoint='tableau_connect')
@login_required
def tableau_connect():
    """Page to connect to Tableau Server and download data"""
    return render_template_string('''
        <!DOCTYPE html>
        <html>
        <head>
            <title>Connect to Tableau - Tableau Data Reporter</title>
            <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
            <style>
                body { padding: 20px; }
                .form-container {
                    max-width: 800px;
                    margin: 0 auto;
                }
                .card {
                    margin-bottom: 20px;
                }
                .loading {
                    display: none;
                    text-align: center;
                    padding: 20px;
                }
                .loading-spinner {
                    width: 3rem;
                    height: 3rem;
                }
            </style>
        </head>
        <body>
            <div class="container">
                <div class="form-container">
                    <div class="d-flex justify-content-between align-items-center mb-4">
                        <h1>Connect to Tableau Server</h1>
                        <a href="{{ url_for('home') }}" class="btn btn-outline-primary">← Back to Dashboard</a>
                    </div>
                    
                    {% with messages = get_flashed_messages() %}
                        {% if messages %}
                            {% for message in messages %}
                                <div class="alert alert-info">{{ message }}</div>
                            {% endfor %}
                        {% endif %}
                    {% endwith %}
                    
                    <div class="card">
                        <div class="card-body">
                            <h5 class="card-title">Connection Details</h5>
                            <form id="connectionForm" method="post" action="{{ url_for('process_tableau_connection') }}">
                                <div class="mb-3">
                                    <label class="form-label">Tableau Server URL</label>
                                    <input type="text" class="form-control" name="server_url" 
                                           placeholder="https://your-server.tableau.com" required>
                                    <div class="form-text">Include https:// and don't include a trailing slash</div>
                                </div>
                                
                                <div class="mb-3">
                                    <label class="form-label">Site Name (leave empty for Default)</label>
                                    <input type="text" class="form-control" name="site_name" 
                                           placeholder="Site name (not URL)">
                                    <div class="form-text">For default site, leave this blank</div>
                                </div>
                                
                                <div class="mb-3">
                                    <label class="form-label">Authentication Method</label>
                                    <select class="form-select" name="auth_method" id="authMethod" required>
                                        <option value="password">Username / Password</option>
                                        <option value="token">Personal Access Token</option>
                                    </select>
                                </div>
                                
                                <!-- Username/Password Auth Fields -->
                                <div id="userPassAuth">
                                    <div class="mb-3">
                                        <label class="form-label">Username</label>
                                        <input type="text" class="form-control" name="username">
                                    </div>
                                    
                                    <div class="mb-3">
                                        <label class="form-label">Password</label>
                                        <input type="password" class="form-control" name="password">
                                    </div>
                                </div>
                                
                                <!-- Token Auth Fields -->
                                <div id="tokenAuth" style="display: none;">
                                    <div class="mb-3">
                                        <label class="form-label">Personal Access Token Name</label>
                                        <input type="text" class="form-control" name="token_name">
                                    </div>
                                    
                                    <div class="mb-3">
                                        <label class="form-label">Personal Access Token Value</label>
                                        <input type="password" class="form-control" name="token_value">
                                    </div>
                                </div>
                                
                                <button type="submit" class="btn btn-primary" id="connectButton">
                                    Connect to Tableau
                                </button>
                            </form>
                            
                            <div id="loadingIndicator" class="loading">
                                <div class="spinner-border loading-spinner text-primary" role="status">
                                    <span class="visually-hidden">Loading...</span>
                                </div>
                                <p class="mt-3">Connecting to Tableau and retrieving workbooks... This may take a minute.</p>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
            
            <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/js/bootstrap.bundle.min.js"></script>
            <script>
                // Toggle auth method fields
                document.getElementById('authMethod').addEventListener('change', function() {
                    const authMethod = this.value;
                    if (authMethod === 'password') {
                        document.getElementById('userPassAuth').style.display = 'block';
                        document.getElementById('tokenAuth').style.display = 'none';
                    } else {
                        document.getElementById('userPassAuth').style.display = 'none';
                        document.getElementById('tokenAuth').style.display = 'block';
                    }
                });
                
                // Show loading indicator on form submit
                document.getElementById('connectionForm').addEventListener('submit', function() {
                    document.getElementById('connectButton').disabled = true;
                    document.getElementById('loadingIndicator').style.display = 'block';
                });
            </script>
        </body>
        </html>
    ''')

@app.route('/process-tableau-connection', methods=['POST'], endpoint='process_tableau_connection')
@login_required
def process_tableau_connection():
    """Process the Tableau Server connection form"""
    try:
        # Get form data
        server_url = request.form.get('server_url')
        site_name = request.form.get('site_name')
        auth_method = request.form.get('auth_method')
        
        if not server_url:
            flash('Server URL is required')
            return redirect(url_for('tableau_connect'))
        
        # Process auth credentials based on method
        credentials = {}
        if auth_method == 'password':
            username = request.form.get('username')
            password = request.form.get('password')
            if not username or not password:
                flash('Username and password are required for password authentication')
                return redirect(url_for('tableau_connect'))
            credentials = {'username': username, 'password': password}
        else:  # token auth
            token_name = request.form.get('token_name')
            token_value = request.form.get('token_value')
            if not token_name or not token_value:
                flash('Token name and value are required for token authentication')
                return redirect(url_for('tableau_connect'))
            credentials = {'token_name': token_name, 'token': token_value}
        
        # Authenticate with Tableau
        try:
            print(f"Connecting to Tableau Server: {server_url}")
            server = authenticate(server_url, auth_method, credentials, site_name)
            if not server:
                flash('Authentication failed. Please check your credentials and try again.')
                return redirect(url_for('tableau_connect'))
            
            # Get workbooks
            workbooks = get_workbooks(server)
            if not workbooks:
                flash('No workbooks found or failed to retrieve workbooks')
                return redirect(url_for('tableau_connect'))
            
            # Store in session for next step
            session['tableau_server'] = {
                'server_url': server_url,
                'site_name': site_name,
                'auth_method': auth_method,
                'credentials': credentials  # Note: In production, consider more secure storage
            }
            session['tableau_workbooks'] = workbooks
            
            # Redirect to select workbook page
            return redirect(url_for('select_tableau_workbook'))
            
        except Exception as e:
            flash(f'Error connecting to Tableau: {str(e)}')
            return redirect(url_for('tableau_connect'))
        
    except Exception as e:
        flash(f'Error processing form: {str(e)}')
        return redirect(url_for('tableau_connect'))

@app.route('/select-tableau-workbook', endpoint='select_tableau_workbook')
@login_required
def select_tableau_workbook():
    """Page to select a workbook and views to download"""
    # Check if we have workbooks in session
    if 'tableau_workbooks' not in session:
        flash('Please connect to Tableau first')
        return redirect(url_for('tableau_connect'))
    
    workbooks = session['tableau_workbooks']
    
    return render_template_string('''
        <!DOCTYPE html>
        <html>
        <head>
            <title>Select Workbook - Tableau Data Reporter</title>
            <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
            <style>
                body { padding: 20px; }
                .form-container {
                    max-width: 800px;
                    margin: 0 auto;
                }
                .card {
                    margin-bottom: 20px;
                }
                .loading {
                    display: none;
                    text-align: center;
                    padding: 20px;
                }
                .loading-spinner {
                    width: 3rem;
                    height: 3rem;
                }
                .workbook-card {
                    cursor: pointer;
                }
                .workbook-card:hover {
                    border-color: #0d6efd;
                }
                .workbook-card.selected {
                    border-color: #0d6efd;
                    background-color: rgba(13, 110, 253, 0.1);
                }
            </style>
        </head>
        <body>
            <div class="container">
                <div class="form-container">
                    <div class="d-flex justify-content-between align-items-center mb-4">
                        <h1>Select Tableau Workbook</h1>
                        <a href="{{ url_for('tableau_connect') }}" class="btn btn-outline-primary">← Back</a>
                    </div>
                    
                    {% with messages = get_flashed_messages() %}
                        {% if messages %}
                            {% for message in messages %}
                                <div class="alert alert-info">{{ message }}</div>
                            {% endfor %}
                        {% endif %}
                    {% endwith %}
                    
                    <div class="card mb-4">
                        <div class="card-body">
                            <h5 class="card-title">Available Workbooks</h5>
                            
                            {% if workbooks %}
                                <form id="workbookForm" method="post" action="{{ url_for('process_workbook_selection') }}">
                                    <div class="row">
                                        {% for workbook in workbooks %}
                                            <div class="col-md-6 mb-3">
                                                <div class="card workbook-card h-100" onclick="selectWorkbook('{{ workbook.id }}')">
                                                    <div class="card-body">
                                                        <h5 class="card-title">{{ workbook.name }}</h5>
                                                        <p class="card-text text-muted">Project: {{ workbook.project_name }}</p>
                                                        
                                                        {% if workbook.views %}
                                                            <div class="form-check form-switch mb-2">
                                                                <input class="form-check-input workbook-selector" 
                                                                       type="checkbox" 
                                                                       id="workbook-{{ workbook.id }}" 
                                                                       name="workbook" 
                                                                       value="{{ workbook.id }}"
                                                                       data-name="{{ workbook.name }}">
                                                                <label class="form-check-label" for="workbook-{{ workbook.id }}">
                                                                    Select this workbook
                                                                </label>
                                                            </div>
                                                            
                                                            <div class="views-container" style="display: none;" id="views-{{ workbook.id }}">
                                                                <hr>
                                                                <h6>Available Views:</h6>
                                                                <div class="mb-2">
                                                                    <button type="button" class="btn btn-sm btn-outline-secondary mb-2"
                                                                            onclick="selectAllViews('{{ workbook.id }}')">
                                                                        Select All
                                                                    </button>
                                                                    <button type="button" class="btn btn-sm btn-outline-secondary mb-2"
                                                                            onclick="deselectAllViews('{{ workbook.id }}')">
                                                                        Deselect All
                                                                    </button>
                                                                </div>
                                                                
                                                                {% for view in workbook.views %}
                                                                    <div class="form-check">
                                                                        <input class="form-check-input view-selector-{{ workbook.id }}" 
                                                                               type="checkbox" 
                                                                               id="view-{{ view.id }}" 
                                                                               name="views-{{ workbook.id }}" 
                                                                               value="{{ view.id }}"
                                                                               data-name="{{ view.name }}">
                                                                        <label class="form-check-label" for="view-{{ view.id }}">
                                                                            {{ view.name }}
                                                                        </label>
                                                                    </div>
                                                                {% endfor %}
                                                            </div>
                                                        {% else %}
                                                            <p class="text-muted">No views available</p>
                                                        {% endif %}
                                                    </div>
                                                </div>
                                            </div>
                                        {% endfor %}
                                    </div>
                                    
                                    <div class="mb-3">
                                        <label class="form-label">Dataset Name (will be used in the database)</label>
                                        <input type="text" class="form-control" name="dataset_name" id="datasetName" required>
                                        <div class="form-text">This name will be used to identify the dataset in the database</div>
                                    </div>
                                    
                                    <button type="submit" class="btn btn-primary" id="downloadButton">
                                        Download Selected Views
                                    </button>
                                </form>
                                
                                <div id="loadingIndicator" class="loading">
                                    <div class="spinner-border loading-spinner text-primary" role="status">
                                        <span class="visually-hidden">Loading...</span>
                                    </div>
                                    <p class="mt-3">Downloading data from Tableau... This may take a few minutes for large datasets.</p>
                                </div>
                            {% else %}
                                <div class="alert alert-info">
                                    No workbooks found. Please check your permissions or try a different site.
                                </div>
                            {% endif %}
                        </div>
                    </div>
                </div>
            </div>
            
            <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/js/bootstrap.bundle.min.js"></script>
            <script>
                // Select workbook and show views
                function selectWorkbook(workbookId) {
                    const checkbox = document.getElementById('workbook-' + workbookId);
                    checkbox.checked = !checkbox.checked;
                    
                    updateViewsVisibility(workbookId);
                    updateDatasetName();
                }
                
                // Show/hide views based on workbook selection
                function updateViewsVisibility(workbookId) {
                    const checkbox = document.getElementById('workbook-' + workbookId);
                    const viewsContainer = document.getElementById('views-' + workbookId);
                    const workbookCard = checkbox.closest('.workbook-card');
                    
                    if (checkbox.checked) {
                        viewsContainer.style.display = 'block';
                        workbookCard.classList.add('selected');
                    } else {
                        viewsContainer.style.display = 'none';
                        workbookCard.classList.remove('selected');
                        // Uncheck all views
                        document.querySelectorAll('.view-selector-' + workbookId).forEach(view => {
                            view.checked = false;
                        });
                    }
                }
                
                // Select all views for a workbook
                function selectAllViews(workbookId) {
                    document.querySelectorAll('.view-selector-' + workbookId).forEach(view => {
                        view.checked = true;
                    });
                }
                
                // Deselect all views for a workbook
                function deselectAllViews(workbookId) {
                    document.querySelectorAll('.view-selector-' + workbookId).forEach(view => {
                        view.checked = false;
                    });
                }
                
                // Auto-generate dataset name based on selections
                function updateDatasetName() {
                    const selectedWorkbooks = [];
                    document.querySelectorAll('.workbook-selector:checked').forEach(workbook => {
                        selectedWorkbooks.push(workbook.dataset.name);
                    });
                    
                    if (selectedWorkbooks.length > 0) {
                        document.getElementById('datasetName').value = selectedWorkbooks.join('_').replace(/[^a-zA-Z0-9]/g, '_');
                    } else {
                        document.getElementById('datasetName').value = '';
                    }
                }
                
                // Add event listeners to all workbook checkboxes
                document.querySelectorAll('.workbook-selector').forEach(checkbox => {
                    checkbox.addEventListener('change', function() {
                        const workbookId = this.value;
                        updateViewsVisibility(workbookId);
                        updateDatasetName();
                    });
                });
                
                // Show loading indicator on form submit
                document.getElementById('workbookForm').addEventListener('submit', function(e) {
                    // Validate that at least one view is selected
                    let hasSelectedView = false;
                    document.querySelectorAll('.workbook-selector:checked').forEach(workbook => {
                        const workbookId = workbook.value;
                        document.querySelectorAll('.view-selector-' + workbookId + ':checked').forEach(() => {
                            hasSelectedView = true;
                        });
                    });
                    
                    if (!hasSelectedView) {
                        e.preventDefault();
                        alert('Please select at least one view to download');
                        return;
                    }
                    
                    document.getElementById('downloadButton').disabled = true;
                    document.getElementById('loadingIndicator').style.display = 'block';
                });
            </script>
        </body>
        </html>
    ''', workbooks=workbooks)

@app.route('/process-workbook-selection', methods=['POST'], endpoint='process_workbook_selection')
@login_required
def process_workbook_selection():
    """Process the workbook and views selection and download data"""
    try:
        # Check if we have server info in session
        if 'tableau_server' not in session or 'tableau_workbooks' not in session:
            flash('Session expired. Please connect to Tableau again.')
            return redirect(url_for('tableau_connect'))
        
        # Get selected workbook and views
        workbook_id = request.form.get('workbook')
        views_key = f'views-{workbook_id}'
        view_ids = request.form.getlist(views_key)
        dataset_name = request.form.get('dataset_name')
        
        if not workbook_id or not view_ids or not dataset_name:
            flash('Please select a workbook, at least one view, and provide a dataset name')
            return redirect(url_for('select_tableau_workbook'))
        
        # Find workbook details in session
        workbooks = session['tableau_workbooks']
        selected_workbook = None
        for wb in workbooks:
            if wb['id'] == workbook_id:
                selected_workbook = wb
                break
        
        if not selected_workbook:
            flash('Selected workbook not found')
            return redirect(url_for('select_tableau_workbook'))
        
        # Get view names for the selected views
        view_names = []
        for view in selected_workbook['views']:
            if view['id'] in view_ids:
                view_names.append(view['name'])
        
        # Re-authenticate with Tableau
        server_info = session['tableau_server']
        try:
            server = authenticate(
                server_info['server_url'], 
                server_info['auth_method'], 
                server_info['credentials'], 
                server_info['site_name']
            )
            
            if not server:
                flash('Re-authentication failed. Please try connecting again.')
                return redirect(url_for('tableau_connect'))
                
            # Generate table name
            table_name = generate_table_name(selected_workbook['name'], view_names)
            if dataset_name:
                # Use dataset_name if provided, but sanitize it for SQLite
                table_name = ''.join(c if c.isalnum() else '_' for c in dataset_name)
                if not table_name[0].isalpha():
                    table_name = 'table_' + table_name
            
            # Download data
            success = download_and_save_data(
                server, 
                view_ids,
                selected_workbook['name'],
                view_names,
                table_name
            )
            
            if success:
                flash(f'Data downloaded successfully and saved as "{table_name}"')
                return redirect(url_for('home'))
            else:
                flash('Failed to download data from Tableau')
                return redirect(url_for('select_tableau_workbook'))
                
        except Exception as e:
            flash(f'Error downloading data: {str(e)}')
            return redirect(url_for('select_tableau_workbook'))
        
    except Exception as e:
        flash(f'Error processing selection: {str(e)}')
        return redirect(url_for('select_tableau_workbook'))

@app.route('/schedule-reports', endpoint='schedule_reports')
@login_required
def schedule_reports():
    """Page to schedule reports"""
    return render_template_string('''
        <!DOCTYPE html>
        <html>
        <head>
            <title>Schedule Reports - Tableau Data Reporter</title>
            <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
            <style>
                body { padding: 20px; }
            </style>
        </head>
        <body>
            <div class="container">
                <div class="d-flex justify-content-between align-items-center mb-4">
                    <h1>Schedule Reports</h1>
                    <a href="{{ url_for('home') }}" class="btn btn-outline-primary">← Back to Dashboard</a>
                </div>
                
                <div class="alert alert-info">
                    <p>Please select a dataset and configure your report schedule.</p>
                    <a href="{{ url_for('home') }}" class="btn btn-primary">
                        Go to Datasets
                    </a>
                </div>
            </div>
        </body>
        </html>
    ''')

@app.route('/manage-schedules', endpoint='manage_schedules')
@login_required
def manage_schedules():
    """Page to manage existing schedules"""
    return render_template_string('''
        <!DOCTYPE html>
        <html>
        <head>
            <title>Manage Schedules - Tableau Data Reporter</title>
            <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
            <style>
                body { padding: 20px; }
            </style>
        </head>
        <body>
            <div class="container">
                <div class="d-flex justify-content-between align-items-center mb-4">
                    <h1>Manage Schedules</h1>
                    <a href="{{ url_for('home') }}" class="btn btn-outline-primary">← Back to Dashboard</a>
                </div>
                
                <div class="alert alert-info">
                    <p>No schedules found. Create a schedule from your datasets page.</p>
                    <a href="{{ url_for('home') }}" class="btn btn-primary">
                        Go to Datasets
                    </a>
                </div>
            </div>
        </body>
        </html>
    ''')

@app.route('/schedule-dataset/<dataset>', endpoint='schedule_dataset')
@login_required
def schedule_dataset(dataset):
    """Page to schedule a specific dataset"""
    return render_template_string('''
        <!DOCTYPE html>
        <html>
        <head>
            <title>Schedule Dataset - Tableau Data Reporter</title>
            <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
            <style>
                body { padding: 20px; }
            </style>
        </head>
        <body>
            <div class="container">
                <div class="d-flex justify-content-between align-items-center mb-4">
                    <h1>Schedule Dataset: {{ dataset }}</h1>
                    <a href="{{ url_for('home') }}" class="btn btn-outline-primary">← Back to Dashboard</a>
                </div>
                
                <div class="alert alert-info">
                    <p>Scheduling functionality is under development.</p>
                    <a href="{{ url_for('home') }}" class="btn btn-primary">
                        Return to Dashboard
                    </a>
                </div>
            </div>
        </body>
        </html>
    ''', dataset=dataset)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8501))
    app.run(host='0.0.0.0', port=port) 