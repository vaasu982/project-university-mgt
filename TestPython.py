# coding: utf-8
from flask import Flask, request, jsonify
import os

app = Flask(__name__)

UPLOAD_FOLDER = 'uploads'
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

@app.route('/')
def index():
    return "Welcome to Python 2.7 Flask REST API!"

@app.route('/api/hello', methods=['GET'])
def hello():
    return jsonify({"message": "Hello from Python 2.7 API"})

@app.route('/api/upload', methods=['POST'])
def upload_files():
    if 'files' not in request.files:
        return jsonify({'error': 'No files part in the request'}), 400

    files = request.files.getlist('files')
    saved_files = []

    for file in files:
        if file.filename == '':
            continue
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
        file.save(filepath)
        saved_files.append(file.filename)

    return jsonify({'uploaded': saved_files}), 200

if __name__ == '__main__':
    app.run(debug=True)
-------------------
virtualenv -p python2.7 venv
source venv/bin/activate
--
pip install -r requirements.txt
--
Flask==1.1.2
