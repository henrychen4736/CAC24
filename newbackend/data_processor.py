# data_processor.py
import os
from pathlib import Path

import cv2
import mediapipe as mp
import numpy as np
from ML.utils import crop_and_normalize_frame, extract_angles_from_frame


class VideoProcessor:
    def __init__(self):
        """Initialize the video processor for single video analysis"""
        pass
        
    def process_video(self, video_path):
        """
        Process a single video file and extract pose landmarks
        
        Args:
            video_path (str): Path to the video file
            
        Returns:
            tuple: (frames, landmarks_sequence)
        """
        cap = cv2.VideoCapture(str(video_path))
        landmarks_sequence = []
        frames = []
        
        while cap.isOpened():
            success, frame = cap.read()
            if not success:
                break
                
            normalized_frame, min_x, max_x, min_y, max_y = crop_and_normalize_frame(frame)
            if normalized_frame is None:
                continue
                
            keypoints, angles = extract_angles_from_frame(normalized_frame)
            
            if keypoints:
                frame_data = []
                for joint in ['right_shoulder', 'right_elbow', 'right_wrist',
                            'left_shoulder', 'left_elbow', 'left_wrist',
                            'right_hip', 'right_knee', 'right_ankle',
                            'left_hip', 'left_knee', 'left_ankle']:
                    coords = keypoints[joint]
                    frame_data.extend([coords[0], coords[1]])
                
                for joint in ['right_elbow', 'left_elbow', 'right_shoulder', 'left_shoulder',
                            'right_knee', 'left_knee', 'right_hip', 'left_hip']:
                    frame_data.append(angles[joint])
                
                landmarks_sequence.append(frame_data)
                frames.append(frame)
        
        cap.release()
        return frames, np.array(landmarks_sequence)
    
    def extract_sequence(self, landmarks_sequence, sequence_length=30):
        """
        Extract a fixed-length sequence from landmarks
        
        Args:
            landmarks_sequence (np.array): Array of landmarks
            sequence_length (int): Desired sequence length
            
        Returns:
            np.array: Processed sequence
        """
        if len(landmarks_sequence) < sequence_length:
            pad_amount = sequence_length - len(landmarks_sequence)
            return np.pad(landmarks_sequence, 
                         ((0, pad_amount), (0, 0)), 
                         mode='edge')
        else:
            # Take the middle portion of the sequence
            start = (len(landmarks_sequence) - sequence_length) // 2
            return landmarks_sequence[start:start + sequence_length]

class TennisDataProcessor:
    def __init__(self, video_dir, output_dir, sequence_length=30):
        """
        Initialize the data processor
        
        Args:
            video_dir (str): Directory containing pose folders (forehand, backhand, serve)
            output_dir (str): Base directory for processed output
            sequence_length (int): Length of sequences to extract
        """
        self.video_dir = Path(video_dir)
        self.output_dir = Path(output_dir)
        self.sequence_length = sequence_length
        self.poses = ["backhand", "forehand", "serve"]
        
        # Create output directories for each pose
        for pose in self.poses:
            pose_dir = self.output_dir / "processed_landmarks" / pose
            pose_dir.mkdir(parents=True, exist_ok=True)
    
    def process_all_videos(self):
        """Process videos for all poses"""
        total_sequences = 0
        
        for pose in self.poses:
            pose_input_dir = self.video_dir / pose
            pose_output_dir = self.output_dir / "processed_landmarks" / pose
            
            if not pose_input_dir.exists():
                print(f"Warning: No directory found for {pose} at {pose_input_dir}")
                continue
                
            video_files = list(pose_input_dir.glob('*.mp4'))
            print(f"\nProcessing {len(video_files)} {pose} videos...")
            
            for idx, video_path in enumerate(video_files):
                print(f"Processing {pose} video {idx + 1}/{len(video_files)}: {video_path.name}")
                
                # Process video
                processor = VideoProcessor()
                _, landmarks_sequence = processor.process_video(video_path)
                
                if len(landmarks_sequence) > 0:
                    sequences = self.extract_sequences(landmarks_sequence)
                    
                    # Save sequences
                    for seq_idx, sequence in enumerate(sequences):
                        output_path = pose_output_dir / f"{video_path.stem}_seq_{seq_idx}.npy"
                        np.save(output_path, sequence)
                        total_sequences += 1
                    
                    print(f"Extracted {len(sequences)} sequences from {video_path.name}")
                else:
                    print(f"Warning: No valid frames extracted from {video_path.name}")
        
        print(f"\nProcessing complete. Total sequences extracted: {total_sequences}")
        return total_sequences
    
    def extract_sequences(self, landmarks_sequence):
        """Extract fixed-length sequences with sliding window"""
        sequences = []
        
        if len(landmarks_sequence) < self.sequence_length:
            pad_amount = self.sequence_length - len(landmarks_sequence)
            landmarks_sequence = np.pad(landmarks_sequence, 
                                     ((0, pad_amount), (0, 0)), 
                                     mode='edge')
            sequences.append(landmarks_sequence)
        else:
            stride = self.sequence_length // 2
            for i in range(0, len(landmarks_sequence) - self.sequence_length + 1, stride):
                sequence = landmarks_sequence[i:i + self.sequence_length]
                sequences.append(sequence)
                
        return sequences

def main():
    # Test the processor
    processor = TennisDataProcessor(
        video_dir="data",           # Contains forehand/, backhand/, serve/ folders
        output_dir="extractions",   # Will create processed_landmarks/{pose}/ folders
        sequence_length=30
    )
    
    num_sequences = processor.process_all_videos()
    print(f"Successfully created {num_sequences} training sequences")

if __name__ == "__main__":
    main()