import os

import cv2
import numpy as np
import pandas as pd
from ML.utils import crop_and_normalize_frame, extract_angles_from_frame


def load_video(video_path):
    cap = cv2.VideoCapture(video_path)
    return cap

def load_professional_data(file_path):
    pro_data = pd.read_csv(file_path)
    pro_data = pro_data.select_dtypes(include=[np.number])
    return pro_data

import numpy as np


def calculate_similarity(frame_angles, pro_angles):
    user_vector = []
    pro_vector = []

    for joint in frame_angles.keys():
        if joint in pro_angles:
            user_vector.append(frame_angles[joint])
            pro_vector.append(pro_angles[joint])

    if len(user_vector) == 0 or len(pro_vector) == 0:
        return 0, {}

    user_vector = np.array(user_vector)
    pro_vector = np.array(pro_vector)

    # mean absolute error
    mae = np.mean(np.abs(user_vector - pro_vector))

    normalized_similarity = max(0, 1 - mae / 180)  # normalize, max deviation is 180 deg

    # Per-joint similarity (for annotation)
    similarity_scores = {}
    for joint in frame_angles.keys():
        if joint in pro_angles:
            diff = np.abs(frame_angles[joint] - pro_angles[joint])
            similarity_scores[joint] = max(0, 1 - diff / 180)  # normed individual similarity score for each joint

    return normalized_similarity, similarity_scores

def find_most_similar_pose(frame_angles, pro_data):
    best_similarity = -np.inf
    best_similarity_scores = {}
    best_pro_row = None

    for idx, pro_row in pro_data.iterrows():
        pro_angles = pro_row.to_dict()
        overall_similarity, similarity_scores = calculate_similarity(frame_angles, pro_angles)

        if overall_similarity > best_similarity:
            best_similarity = overall_similarity
            best_similarity_scores = similarity_scores
            best_pro_row = pro_row

    return best_similarity, best_similarity_scores, best_pro_row

def annotate_frame(frame, keypoints, angles, similarity_scores, overall_similarity):
    for joint, angle in angles.items():
        if joint == 'right_elbow':
            a_name, b_name, c_name = 'right_shoulder', 'right_elbow', 'right_wrist'
        elif joint == 'left_elbow':
            a_name, b_name, c_name = 'left_shoulder', 'left_elbow', 'left_wrist'
        elif joint == 'right_shoulder':
            a_name, b_name, c_name = 'right_hip', 'right_shoulder', 'right_elbow'
        elif joint == 'left_shoulder':
            a_name, b_name, c_name = 'left_hip', 'left_shoulder', 'left_elbow'
        elif joint == 'right_knee':
            a_name, b_name, c_name = 'right_hip', 'right_knee', 'right_ankle'
        elif joint == 'left_knee':
            a_name, b_name, c_name = 'left_hip', 'left_knee', 'left_ankle'
        elif joint == 'right_hip':
            a_name, b_name, c_name = 'right_shoulder', 'right_hip', 'right_knee'
        elif joint == 'left_hip':
            a_name, b_name, c_name = 'left_shoulder', 'left_hip', 'left_knee'
        else:
            continue

        # Ensure all points exist
        if a_name in keypoints and b_name in keypoints and c_name in keypoints:
            a = (int(keypoints[a_name][0]), int(keypoints[a_name][1]))
            b = (int(keypoints[b_name][0]), int(keypoints[b_name][1]))
            c = (int(keypoints[c_name][0]), int(keypoints[c_name][1]))

            # Draw lines between the points a, b, c
            color = (0, 255, 0)  # green default color if good performance
            if similarity_scores.get(joint, 0) < 0.85:  # threshold to color as red
                color = (0, 0, 255)  # red

            cv2.line(frame, a, b, color, 2)
            cv2.line(frame, b, c, color, 2)
            cv2.circle(frame, a, 5, (0, 0, 255), -1)
            cv2.circle(frame, b, 5, (255, 0, 0), -1)
            cv2.circle(frame, c, 5, (0, 0, 255), -1)

            # Annotate angle and similarity score
            angle_text = f"{int(angle)}'"
            similarity_text = f"{similarity_scores.get(joint, 0):.2f}"

            # Place the text right next to the joint (point 'b')
            text_x, text_y = b[0] + 10, b[1] + 10
            cv2.putText(frame, angle_text, (text_x, text_y - 20),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 2, cv2.LINE_AA)
            cv2.putText(frame, similarity_text, (text_x, text_y),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 0), 2, cv2.LINE_AA)

    # Annotate overall similarity score on the frame (placed at top-left corner)
    cv2.putText(frame, f"Overall Similarity: {overall_similarity:.2f}", (10, 30),
                cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 255), 2, cv2.LINE_AA)

    return frame

def scale_keypoints_to_original_frame(keypoints, min_x, max_x, min_y, max_y):
    scaled_keypoints = {}
    for joint, (x, y) in keypoints.items():
        x_original = x * (max_x - min_x) + min_x
        y_original = y * (max_y - min_y) + min_y
        scaled_keypoints[joint] = (x_original, y_original)
    
    return scaled_keypoints

def generate_performance_report(similarity_tracker):
    feedback = {}
    total_similarity = 0
    total_joints = 0

    for joint, scores in similarity_tracker.items():
        if scores:
            average_similarity = sum(scores) / len(scores)
            feedback[joint] = average_similarity
            total_similarity += average_similarity
            total_joints += 1

    if total_joints > 0:
        overall_similarity = total_similarity / total_joints
    else:
        overall_similarity = 0

    report = {
        "overall_similarity": overall_similarity,
        "joint_feedback": {}
    }

    for joint, avg_similarity in feedback.items():
        if avg_similarity < 0.85:
            report["joint_feedback"][joint] = {
                "status": "Needs Improvement",
                "average_similarity": avg_similarity,
                "feedback": get_joint_feedback(joint)
            }
        else:
            report["joint_feedback"][joint] = {
                "status": "Good",
                "average_similarity": avg_similarity,
                "feedback": "Good performance on this joint."
            }

    return report

def get_joint_feedback(joint):
    if 'elbow' in joint:
        return "Focus on your elbow position to match the professional swing."
    elif 'knee' in joint:
        return "Pay attention to your knee bend. Proper knee bend helps with balance and generates more power during your shots."
    elif 'shoulder' in joint:
        return "Shoulder rotation is key for generating power. Ensure full shoulder rotation to create more force in your swings."
    elif 'hip' in joint:
        return "Hip rotation is essential to transferring energy from your legs to your racket. Rotate your hips with your shoulders for fluid motion."
    else:
        return "General advice: Focus on proper form and positioning to improve your technique."

def tennis_analysis_pipeline(video_path, pro_data_path, output_video_path):
    cap = load_video(video_path)
    if not cap.isOpened():
        print(f"Error: Could not open video file {video_path}")
        return None, None

    frame_rate = int(cap.get(cv2.CAP_PROP_FPS))
    pro_data = load_professional_data(pro_data_path)
    frame_count = 0
    annotated_frames = []
    
    # Track statistics
    overall_similarities = []
    all_joint_similarities = {}

    similarity_tracker = {}
    for joint in ['right_elbow', 'left_elbow', 'right_shoulder', 'left_shoulder', 'right_knee', 'left_knee', 'right_hip', 'left_hip']:
        similarity_tracker[joint] = []

    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            break
        
        normalized_frame, min_x, max_x, min_y, max_y = crop_and_normalize_frame(frame)
        if normalized_frame is None:
            print(f"Warning: Could not detect player for frame {frame_count}")
            annotated_frames.append(frame)
            frame_count += 1
            continue

        keypoints, frame_angles = extract_angles_from_frame(normalized_frame)
        if frame_angles and keypoints:
            best_similarity, best_similarity_scores, best_pro_row = find_most_similar_pose(frame_angles, pro_data)

            scaled_keypoints = scale_keypoints_to_original_frame(keypoints, min_x, max_x, min_y, max_y) # we need to draw on the original picture, not the normalized picture
            annotated_frame = annotate_frame(frame.copy(), scaled_keypoints, frame_angles, best_similarity_scores, best_similarity)
            annotated_frames.append(annotated_frame)
            print(f"Frame {frame_count}: Overall Similarity Score = {best_similarity:.2f}")
        else:
            print(f"Warning: Could not extract angles for frame {frame_count}")
            annotated_frames.append(frame)

        frame_count += 1

    cap.release()

    # Calculate final statistics
    stats = {
        'overall_similarity': float(np.mean(overall_similarities)) if overall_similarities else 0.0,
        'joint_similarities': {
            joint: float(np.mean(scores)) for joint, scores in all_joint_similarities.items()
        }
    }

    height, width, _ = annotated_frames[0].shape
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    out = cv2.VideoWriter(output_video_path, fourcc, frame_rate, (width, height))

    for frame in annotated_frames:
        out.write(frame)
    out.release()

    print(f"Annotated video saved as {output_video_path}")
    return output_video_path

if __name__ == "__main__":
    video_file = "New_Project.mp4"
    pro_data_file = "ML/pro_forehand_angles.csv"
    tennis_analysis_pipeline(video_file, pro_data_file, 'annotated.mp4')
