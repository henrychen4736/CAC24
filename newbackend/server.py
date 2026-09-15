# server.py
import io
import json
import logging
import os
import tempfile
import traceback

import cv2
import mediapipe as mp
import numpy as np
from flask import Flask, jsonify, request, send_file
from flask_cors import CORS
from tensorflow import keras

# Set up logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)

class VideoProcessor:
    def __init__(self):
        """Initialize the video processor for single video analysis"""
        # Initialize MediaPipe pose detection with improved configuration
        mp_pose = mp.solutions.pose
        self.pose = mp_pose.Pose(
            model_complexity=2,  # Use the most accurate model
            min_detection_confidence=0.5,
            min_tracking_confidence=0.5,
            enable_segmentation=False,
            static_image_mode=False
        )
        
    def process_video(self, video_path):
        """
        Process a single video file and extract pose landmarks
        
        Args:
            video_path (str): Path to the video file
            
        Returns:
            list: List of processed sequences
        """
        cap = cv2.VideoCapture(str(video_path))
        
        if not cap.isOpened():
            raise ValueError("Failed to open video file")
        
        # Get video dimensions
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        
        landmarks_sequence = []
        frames = []
        
        while cap.isOpened():
            success, frame = cap.read()
            if not success:
                break
                
            # Convert the BGR image to RGB
            image_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            
            # Process the frame
            results = self.pose.process(image_rgb)
            
            if results.pose_landmarks:
                # Normalize landmarks based on image dimensions
                normalized_landmarks = self._normalize_landmarks(
                    results.pose_landmarks.landmark,
                    width,
                    height
                )
                
                frame_data = self._extract_frame_data(normalized_landmarks)
                landmarks_sequence.append(frame_data)
                frames.append(frame)
        
        cap.release()
        
        if not landmarks_sequence:
            return []
        
        # Convert to numpy array and extract sequences
        landmarks_array = np.array(landmarks_sequence)
        return self._extract_sequences(landmarks_array)
    
    def _normalize_landmarks(self, landmarks, width, height):
        """Normalize landmarks based on image dimensions"""
        normalized = []
        for landmark in landmarks:
            normalized.append([
                landmark.x * width,
                landmark.y * height,
                landmark.z * width  # Use width for z to maintain aspect ratio
            ])
        return normalized
    
    def _extract_frame_data(self, landmarks):
        """Extract relevant joint data and angles from landmarks"""
        # Map MediaPipe indices to joint names
        joint_indices = {
            'right_shoulder': 12,
            'right_elbow': 14,
            'right_wrist': 16,
            'left_shoulder': 11,
            'left_elbow': 13,
            'left_wrist': 15,
            'right_hip': 24,
            'right_knee': 26,
            'right_ankle': 28,
            'left_hip': 23,
            'left_knee': 25,
            'left_ankle': 27
        }
        
        frame_data = []
        
        # Extract joint coordinates
        for joint in joint_indices.values():
            frame_data.extend([
                landmarks[joint][0],  # x
                landmarks[joint][1]   # y
            ])
        
        # Calculate angles
        angles = self._calculate_angles(landmarks, joint_indices)
        frame_data.extend(angles)
        
        return frame_data
    
    def _calculate_angles(self, landmarks, joint_indices):
        """Calculate joint angles"""
        angles = []
        
        # Define angle calculations for joints
        angle_definitions = [
            ('right_elbow', ['right_shoulder', 'right_elbow', 'right_wrist']),
            ('left_elbow', ['left_shoulder', 'left_elbow', 'left_wrist']),
            ('right_shoulder', ['right_hip', 'right_shoulder', 'right_elbow']),
            ('left_shoulder', ['left_hip', 'left_shoulder', 'left_elbow']),
            ('right_knee', ['right_hip', 'right_knee', 'right_ankle']),
            ('left_knee', ['left_hip', 'left_knee', 'left_ankle']),
            ('right_hip', ['right_knee', 'right_hip', 'right_shoulder']),
            ('left_hip', ['left_knee', 'left_hip', 'left_shoulder'])
        ]
        
        for _, (joint1, joint2, joint3) in angle_definitions:
            p1 = np.array(landmarks[joint_indices[joint1]])
            p2 = np.array(landmarks[joint_indices[joint2]])
            p3 = np.array(landmarks[joint_indices[joint3]])
            
            angle = self._calculate_angle(p1, p2, p3)
            angles.append(angle)
        
        return angles
    
    def _calculate_angle(self, p1, p2, p3):
        """Calculate the angle between three points"""
        v1 = p1 - p2
        v2 = p3 - p2
        
        cos_angle = np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2))
        angle = np.arccos(np.clip(cos_angle, -1.0, 1.0))
        
        return np.degrees(angle)
    
    def _extract_sequences(self, landmarks_sequence, sequence_length=30):
        """Extract fixed-length sequences from landmarks"""
        sequences = []
        
        if len(landmarks_sequence) < sequence_length:
            # Pad if sequence is too short
            pad_amount = sequence_length - len(landmarks_sequence)
            padded_sequence = np.pad(
                landmarks_sequence,
                ((0, pad_amount), (0, 0)),
                mode='edge'
            )
            sequences.append(padded_sequence)
        else:
            # Extract overlapping sequences
            stride = sequence_length // 2
            for i in range(0, len(landmarks_sequence) - sequence_length + 1, stride):
                sequence = landmarks_sequence[i:i + sequence_length]
                sequences.append(sequence)
        
        return sequences

# Load the trained model
try:
    model = keras.models.load_model('tennis_model.keras')
    logger.info("Model loaded successfully!")
except Exception as e:
    logger.error(f"Error loading model: {str(e)}")
    model = None

@app.route('/test', methods=['GET'])
def test():
    """Test endpoint"""
    return jsonify({
        'status': 'ok',
        'message': 'Server is running',
        'model_loaded': model is not None
    })

@app.route('/analyze_shot_forehand', methods=['POST'])
def analyze_forehand():
    """Endpoint to analyze forehand shots"""
    try:
        logger.info("Received forehand analysis request")
        
        # Check if file is present
        if 'file' not in request.files:
            logger.error("No file in request")
            return jsonify({'error': 'No video file provided'}), 400
        
        video_file = request.files['file']
        logger.info(f"Received file: {video_file.filename}")
        
        # Create temp directory
        temp_dir = tempfile.mkdtemp()
        video_path = os.path.join(temp_dir, 'temp_video.mp4')
        logger.info(f"Saving to temporary path: {video_path}")
        
        # Save file
        video_file.save(video_path)
        logger.info("File saved successfully")
        
        # Process video
        try:
            processor = VideoProcessor()
            logger.info("Processing video...")
            sequences = processor.process_video(video_path)
            logger.info(f"Extracted {len(sequences)} sequences")
            
            if not sequences:
                return jsonify({'error': 'No valid poses detected in video'}), 400
                
        except Exception as e:
            logger.error(f"Video processing error: {str(e)}\n{traceback.format_exc()}")
            return jsonify({'error': 'Video processing failed'}), 500
        
        # Make predictions
        try:
            predictions = []
            for i, seq in enumerate(sequences):
                logger.debug(f"Processing sequence {i+1}/{len(sequences)}")
                seq = np.expand_dims(seq, 0)
                pred = float(model.predict(seq, verbose=0)[0][0])
                predictions.append(pred)
            logger.info("Predictions completed")
        except Exception as e:
            logger.error(f"Prediction error: {str(e)}\n{traceback.format_exc()}")
            return jsonify({'error': 'Prediction failed'}), 500
        
        # Calculate overall similarity and joint-specific metrics
        overall_similarity = float(np.mean(predictions)) if predictions else 0
        
        # Calculate joint-specific similarities from the landmark data
        joint_similarities = {
            "right_shoulder": np.mean([seq[12:14].mean() for seq in sequences]),
            "right_elbow": np.mean([seq[14:16].mean() for seq in sequences]),
            "right_wrist": np.mean([seq[16:18].mean() for seq in sequences]),
            "right_hip": np.mean([seq[24:26].mean() for seq in sequences]),
            "right_knee": np.mean([seq[26:28].mean() for seq in sequences])
        }
        
        analysis_stats = {
            "overall_similarity": overall_similarity,
            "joint_similarities": joint_similarities
        }
        
        logger.info("Preparing response")
        try:
            # Create response with headers
            response = send_file(
                video_path,
                mimetype='video/mp4'
            )
            response.headers['X-Analysis-Stats'] = json.dumps(analysis_stats)
            response.headers['Access-Control-Expose-Headers'] = 'X-Analysis-Stats'
            
            logger.info("Response prepared successfully")
            return response
            
        except Exception as e:
            logger.error(f"Response creation error: {str(e)}\n{traceback.format_exc()}")
            return jsonify({'error': 'Failed to create response'}), 500
            
        finally:
            # Cleanup
            try:
                os.remove(video_path)
                os.rmdir(temp_dir)
                logger.info("Cleanup completed")
            except Exception as e:
                logger.error(f"Cleanup error: {str(e)}")
        
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}\n{traceback.format_exc()}")
        return jsonify({
            'error': 'Server error',
            'details': str(e),
            'traceback': traceback.format_exc()
        }), 500

@app.route('/analyze_shot_backhand', methods=['POST'])
def analyze_backhand():
    """Endpoint to analyze backhand shots"""
    try:
        logger.info("Received backhand analysis request")
        
        # Check if file is present
        if 'file' not in request.files:
            logger.error("No file in request")
            return jsonify({'error': 'No video file provided'}), 400
        
        video_file = request.files['file']
        logger.info(f"Received file: {video_file.filename}")
        
        # Create temp directory
        temp_dir = tempfile.mkdtemp()
        video_path = os.path.join(temp_dir, 'temp_video.mp4')
        logger.info(f"Saving to temporary path: {video_path}")
        
        # Save file
        video_file.save(video_path)
        logger.info("File saved successfully")
        
        # Process video
        try:
            processor = VideoProcessor()
            logger.info("Processing video...")
            sequences = processor.process_video(video_path)
            logger.info(f"Extracted {len(sequences)} sequences")
            
            if not sequences:
                return jsonify({'error': 'No valid poses detected in video'}), 400
                
        except Exception as e:
            logger.error(f"Video processing error: {str(e)}\n{traceback.format_exc()}")
            return jsonify({'error': 'Video processing failed'}), 500
        
        # Make predictions using backhand model
        try:
            predictions = []
            backhand_model = keras.models.load_model('tennis_backhand_model.keras')
            for i, seq in enumerate(sequences):
                logger.debug(f"Processing sequence {i+1}/{len(sequences)}")
                seq = np.expand_dims(seq, 0)
                pred = float(backhand_model.predict(seq, verbose=0)[0][0])
                predictions.append(pred)
            logger.info("Predictions completed")
        except Exception as e:
            logger.error(f"Prediction error: {str(e)}\n{traceback.format_exc()}")
            return jsonify({'error': 'Prediction failed'}), 500
        
        # Calculate overall similarity and joint-specific metrics
        overall_similarity = float(np.mean(predictions)) if predictions else 0
        
        # Calculate joint-specific similarities from the landmark data
        joint_similarities = {
            "left_shoulder": np.mean([seq[11:13].mean() for seq in sequences]),
            "left_elbow": np.mean([seq[13:15].mean() for seq in sequences]),
            "left_wrist": np.mean([seq[15:17].mean() for seq in sequences]),
            "left_hip": np.mean([seq[23:25].mean() for seq in sequences]),
            "left_knee": np.mean([seq[25:27].mean() for seq in sequences])
        }
        
        analysis_stats = {
            "overall_similarity": overall_similarity,
            "joint_similarities": joint_similarities
        }
        
        logger.info("Preparing response")
        try:
            # Create response with headers
            response = send_file(
                video_path,
                mimetype='video/mp4'
            )
            response.headers['X-Analysis-Stats'] = json.dumps(analysis_stats)
            response.headers['Access-Control-Expose-Headers'] = 'X-Analysis-Stats'
            
            logger.info("Response prepared successfully")
            return response
            
        except Exception as e:
            logger.error(f"Response creation error: {str(e)}\n{traceback.format_exc()}")
            return jsonify({'error': 'Failed to create response'}), 500
            
        finally:
            # Cleanup
            try:
                os.remove(video_path)
                os.rmdir(temp_dir)
                logger.info("Cleanup completed")
            except Exception as e:
                logger.error(f"Cleanup error: {str(e)}")
                
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}\n{traceback.format_exc()}")
        return jsonify({
            'error': 'Server error',
            'details': str(e),
            'traceback': traceback.format_exc()
        }), 500

@app.route('/analyze_shot_serve', methods=['POST'])
def analyze_serve():
    """Endpoint to analyze serve shots"""
    try:
        logger.info("Received serve analysis request")
        
        # Check if file is present
        if 'file' not in request.files:
            logger.error("No file in request")
            return jsonify({'error': 'No video file provided'}), 400
        
        video_file = request.files['file']
        logger.info(f"Received file: {video_file.filename}")
        
        # Create temp directory
        temp_dir = tempfile.mkdtemp()
        video_path = os.path.join(temp_dir, 'temp_video.mp4')
        logger.info(f"Saving to temporary path: {video_path}")
        
        # Save file
        video_file.save(video_path)
        logger.info("File saved successfully")
        
        # Process video
        try:
            processor = VideoProcessor()
            logger.info("Processing video...")
            sequences = processor.process_video(video_path)
            logger.info(f"Extracted {len(sequences)} sequences")
            
            if not sequences:
                return jsonify({'error': 'No valid poses detected in video'}), 400
                
        except Exception as e:
            logger.error(f"Video processing error: {str(e)}\n{traceback.format_exc()}")
            return jsonify({'error': 'Video processing failed'}), 500
        
        # Make predictions using serve model
        try:
            predictions = []
            serve_model = keras.models.load_model('tennis_serve_model.keras')
            for i, seq in enumerate(sequences):
                logger.debug(f"Processing sequence {i+1}/{len(sequences)}")
                seq = np.expand_dims(seq, 0)
                pred = float(serve_model.predict(seq, verbose=0)[0][0])
                predictions.append(pred)
            logger.info("Predictions completed")
        except Exception as e:
            logger.error(f"Prediction error: {str(e)}\n{traceback.format_exc()}")
            return jsonify({'error': 'Prediction failed'}), 500
        
        # Calculate overall similarity and joint-specific metrics
        overall_similarity = float(np.mean(predictions)) if predictions else 0
        
        # Calculate joint-specific similarities focusing on serve-specific joints
        joint_similarities = {
            "right_shoulder": np.mean([seq[12:14].mean() for seq in sequences]),
            "right_elbow": np.mean([seq[14:16].mean() for seq in sequences]),
            "right_wrist": np.mean([seq[16:18].mean() for seq in sequences]),
            "right_hip": np.mean([seq[24:26].mean() for seq in sequences]),
            "right_knee": np.mean([seq[26:28].mean() for seq in sequences]),
            "left_shoulder": np.mean([seq[11:13].mean() for seq in sequences])  # Important for serve motion
        }
        
        analysis_stats = {
            "overall_similarity": overall_similarity,
            "joint_similarities": joint_similarities
        }
        
        logger.info("Preparing response")
        try:
            # Create response with headers
            response = send_file(
                video_path,
                mimetype='video/mp4'
            )
            response.headers['X-Analysis-Stats'] = json.dumps(analysis_stats)
            response.headers['Access-Control-Expose-Headers'] = 'X-Analysis-Stats'
            
            logger.info("Response prepared successfully")
            return response
            
        except Exception as e:
            logger.error(f"Response creation error: {str(e)}\n{traceback.format_exc()}")
            return jsonify({'error': 'Failed to create response'}), 500
            
        finally:
            # Cleanup
            try:
                os.remove(video_path)
                os.rmdir(temp_dir)
                logger.info("Cleanup completed")
            except Exception as e:
                logger.error(f"Cleanup error: {str(e)}")
                
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}\n{traceback.format_exc()}")
        return jsonify({
            'error': 'Server error',
            'details': str(e),
            'traceback': traceback.format_exc()
        }), 500
        


if __name__ == '__main__':
    app.run(debug=True, port=5000)