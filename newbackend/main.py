import json
import os

from analyze import tennis_analysis_pipeline
from flask import Flask, jsonify, make_response, request, send_from_directory
from flask_cors import CORS
from werkzeug.utils import secure_filename

app = Flask(__name__)
CORS(app)

UPLOAD_FOLDER = 'uploads'
PROCESSED_FOLDER = 'processed'
ALLOWED_EXTENSIONS = {'mp4'}

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['PROCESSED_FOLDER'] = PROCESSED_FOLDER

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(PROCESSED_FOLDER, exist_ok=True)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/')
def index():
    return jsonify({"message": "IT WORKS!"})

@app.route('/analyze_shot_forehand', methods=['POST'])
def analyze_forehand():
    return process_video('forehand')

@app.route('/analyze_shot_backhand', methods=['POST'])
def analyze_backhand():
    return process_video('backhand')

@app.route('/analyze_shot_kickserve', methods=['POST'])
def analyze_kickserve():
    return process_video('kickserve')

@app.route('/processed/<filename>')
def download_file(filename):
    return send_from_directory(app.config['PROCESSED_FOLDER'], filename, as_attachment=True)

def process_video(shot_type):
    if 'file' not in request.files:
        return jsonify({"error": "No file part"}), 400
    
    file = request.files['file']
    
    if file.filename == '':
        return jsonify({"error": "No selected file"}), 400
    
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(file_path)
        
        processed_filename = f"annotated_{filename}"
        processed_file_path = os.path.join(app.config['PROCESSED_FOLDER'], processed_filename)
        
        try:
            if shot_type == 'forehand' or shot_type == 'backhand' or shot_type == 'kickserve':
                annotated_video_path = tennis_analysis_pipeline(video_path=file_path, pro_data_path=f"ML/pro_{shot_type}_angles.csv", output_video_path=processed_file_path)

            if annotated_video_path:
                return send_from_directory(app.config['PROCESSED_FOLDER'], processed_filename, as_attachment=True)
            else:
                return jsonify({"error": "Failed to process video"}), 500

        except Exception as e:
            return jsonify({"error": str(e)}), 500
    
    return jsonify({"error": "Invalid file format, only MP4 allowed"}), 400

if __name__ == '__main__':
    app.run(debug=True, port=5001)