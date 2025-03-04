from flask import Flask, send_from_directory, jsonify
import os
import logging

# Get the absolute path to the project root
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
static_folder = os.path.join(project_root, 'frontend', 'build')

# Verify that the path exists
if not os.path.exists(static_folder):
    print(f"WARNING: Static folder not found at {static_folder}")
    # Create the directory to avoid errors, even if empty
    os.makedirs(static_folder, exist_ok=True)

    # Create a basic index.html file if it doesn't exist
    index_path = os.path.join(static_folder, 'index.html')
    if not os.path.exists(index_path):
        print(f"Creating index.html at {index_path}")
        with open(index_path, 'w') as f:
            f.write("""<!DOCTYPE html>
<html>
<head>
    <title>Fincode API Server</title>
    <style>
        body { font-family: Arial, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px; }
        h1 { color: #333; }
        .status { padding: 15px; background-color: #f0f8ff; border-radius: 5px; }
    </style>
</head>
<body>
    <h1>Fincode API Server</h1>
    <div class="status">
        <p>API server is running successfully.</p>
        <p>This is a temporary frontend page. The actual frontend will be added in future deployments.</p>
    </div>
</body>
</html>""")

# Create Flask app with the correct static folder path
app = Flask(__name__, 
           static_folder=static_folder,
           static_url_path='')

# Set secret key for session management
app.secret_key = os.environ.get('SECRET_KEY', os.urandom(24))

# Configure the application
# app.config.from_object('config.Config')

# Add debug logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# DO NOT define a root route here - it's defined in app.py
# This code is now used only for serving static files for paths that don't match any route

# Serve frontend files for paths that don't match API routes
@app.route('/<path:path>')
def serve_frontend(path):
    logger.debug(f"Request for path: {path}")
    logger.debug(f"Static folder is: {app.static_folder}")
    
    # Check if static folder exists
    if not os.path.exists(app.static_folder):
        logger.error(f"Static folder {app.static_folder} does not exist!")
        # Create it on the fly
        os.makedirs(app.static_folder, exist_ok=True)
    
    print(f"Serving path: {path}")  # Add debug logging
    if path != "" and os.path.exists(os.path.join(app.static_folder, path)):
        return send_from_directory(app.static_folder, path)
    else:
        # Check if index.html exists
        index_path = os.path.join(app.static_folder, 'index.html')
        if os.path.exists(index_path):
            return send_from_directory(app.static_folder, 'index.html')
        else:
            print(f"WARNING: index.html not found at {index_path}")
            # Return a fallback response if index.html is missing
            return """
            <!DOCTYPE html>
            <html>
            <head>
                <title>Fincode API Server</title>
                <style>
                    body { font-family: Arial, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px; }
                    h1 { color: #333; }
                    .status { padding: 15px; background-color: #f0f8ff; border-radius: 5px; }
                </style>
            </head>
            <body>
                <h1>Fincode API Server</h1>
                <div class="status">
                    <p>API server is running successfully.</p>
                    <p>Frontend application is not yet built or not found at the expected location.</p>
                </div>
            </body>
            </html>
            """, 200, {'Content-Type': 'text/html'}

# Import and register blueprints
from app.routes.scheduler import scheduler_bp
from app.routes.main import main_bp

app.register_blueprint(scheduler_bp, url_prefix='/api')
app.register_blueprint(main_bp, url_prefix='/main')  # Add a prefix for the main blueprint to avoid conflicts 