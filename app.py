import logging
import os
import secrets
import uuid
from logging.handlers import RotatingFileHandler

from flask import Flask, render_template, request, send_from_directory
from flask_socketio import SocketIO, emit


# Configure logging
def setup_logging():
    log_dir = 'logs'
    os.makedirs(log_dir, exist_ok=True)
    log_file = os.path.join(log_dir, 'chat_app.log')

    # Create a logger
    logger = logging.getLogger('ChatApp')
    logger.setLevel(logging.INFO)

    # Create a file handler with log rotation
    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=1024 * 1024,  # 1 MB
        backupCount=3
    )
    file_handler.setLevel(logging.INFO)

    # Create a console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)

    # Create a formatter
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)

    # Add the handlers to the logger
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    return logger


# Initialize app and logger
app = Flask(__name__)
app.config['SECRET_KEY'] = secrets.token_hex(16)
socketio = SocketIO(app)
logger = setup_logging()

# Create upload directory
UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Global variables
messages = []
user_data = {}  # In-memory username tracking


@app.route('/')
def chat():
    logger.info(f"Chat page accessed from IP: {request.remote_addr}")
    print(user_data)
    return render_template("index.html", messages=messages)


@app.route('/uploads/<filename>')
def uploaded_file(filename):
    logger.info(f"File download requested: {filename}")
    return send_from_directory(UPLOAD_FOLDER, filename)


@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        logger.warning(f"File upload failed from IP: {request.remote_addr} - No file uploaded")
        return {"success": False, "error": "No file uploaded"}, 400

    file = request.files['file']
    username = request.form.get("username", "Unknown")

    # Generate a unique filename to prevent overwriting
    filename = f"{uuid.uuid4()}_{file.filename}"
    file_path = os.path.join(UPLOAD_FOLDER, filename)

    try:
        file.save(file_path)
        logger.info(f"File uploaded by {username}: {filename}")

        file_url = f"/uploads/{filename}"
        return {"success": True, "filename": file.filename, "url": file_url}
    except Exception as e:
        logger.error(f"File upload error: {e}")
        return {"success": False, "error": "File upload failed"}, 500


@socketio.on('validate_username')
def validate_username(data):
    username = data.get('username', '').strip()

    # Validate username
    if not username:
        emit('username_validation', {
            'is_valid': False,
            'message': "Username cannot be empty."
        })
        return

    # Get client IP
    user_ip = request.remote_addr

    # If this IP already has a username, don't change it
    if user_ip in user_data:
        existing_username = user_data[user_ip]

        # If the provided username is different from the existing one
        if username != existing_username:
            # Check if the new username is already taken
            if username in user_data.values():
                emit('username_validation', {
                    'is_valid': False,
                    'message': "Username is already taken. Please choose another."
                })
                return

        # Keep the existing username or update it if it's the same user
        username = existing_username

    # Add or update username for this IP
    user_data[user_ip] = username

    logger.info(f"Username validated: {username} from IP: {user_ip}")

    # Confirm username is valid
    emit('username_validation', {
        'is_valid': True,
        'username': username
    })


@socketio.on('send_message')
def handle_message(data):
    user_ip = request.remote_addr
    username = user_data.get(user_ip, "Unknown")

    message_text = data.get("message", "").strip()
    # Truncate long messages
    if len(message_text) > 16383:
        message_text = message_text[:16,383] + "... {Truncated}"

    message_data = {"username": username, "text": message_text, "type": "text"}
    messages.append(message_data)

    logger.info(f"Message from {username}: {message_text}")

    emit('new_message', message_data, broadcast=True)


@socketio.on('send_file')
def handle_file(data):
    user_ip = request.remote_addr
    username = user_data.get(user_ip, "Unknown")

    message_data = {
        "username": username,
        "filename": data["filename"],
        "url": data["url"],
        "type": "file"
    }
    messages.append(message_data)

    logger.info(f"File sent by {username}: {data['filename']}")

    emit('new_message', message_data, broadcast=True)


if __name__ == '__main__':
    logger.info("Starting Chat Application")
    socketio.run(app, host='0.0.0.0', port=10000, debug=True, allow_unsafe_werkzeug=True)
