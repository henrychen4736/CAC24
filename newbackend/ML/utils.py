import cv2
import mediapipe as mp
import numpy as np

mp_pose = mp.solutions.pose
pose = mp_pose.Pose(static_image_mode=True, model_complexity=2, min_detection_confidence=0.5)

def calculate_angle(a, b, c):
    a = np.array(a)
    b = np.array(b)
    c = np.array(c)
    radians = np.arctan2(c[1] - b[1], c[0] - b[0]) - np.arctan2(a[1] - b[1], a[0] - b[0])
    angle = np.abs(radians * 180.0 / np.pi)
    if angle > 180.0:
        angle = 360 - angle
    return angle

def extract_keypoints(landmarks):
    return {
        'right_shoulder': (landmarks[mp_pose.PoseLandmark.RIGHT_SHOULDER].x, landmarks[mp_pose.PoseLandmark.RIGHT_SHOULDER].y),
        'right_elbow': (landmarks[mp_pose.PoseLandmark.RIGHT_ELBOW].x, landmarks[mp_pose.PoseLandmark.RIGHT_ELBOW].y),
        'right_wrist': (landmarks[mp_pose.PoseLandmark.RIGHT_WRIST].x, landmarks[mp_pose.PoseLandmark.RIGHT_WRIST].y),
        'right_hip': (landmarks[mp_pose.PoseLandmark.RIGHT_HIP].x, landmarks[mp_pose.PoseLandmark.RIGHT_HIP].y),
        'right_knee': (landmarks[mp_pose.PoseLandmark.RIGHT_KNEE].x, landmarks[mp_pose.PoseLandmark.RIGHT_KNEE].y),
        'right_ankle': (landmarks[mp_pose.PoseLandmark.RIGHT_ANKLE].x, landmarks[mp_pose.PoseLandmark.RIGHT_ANKLE].y),
        'left_shoulder': (landmarks[mp_pose.PoseLandmark.LEFT_SHOULDER].x, landmarks[mp_pose.PoseLandmark.LEFT_SHOULDER].y),
        'left_elbow': (landmarks[mp_pose.PoseLandmark.LEFT_ELBOW].x, landmarks[mp_pose.PoseLandmark.LEFT_ELBOW].y),
        'left_wrist': (landmarks[mp_pose.PoseLandmark.LEFT_WRIST].x, landmarks[mp_pose.PoseLandmark.LEFT_WRIST].y),
        'left_hip': (landmarks[mp_pose.PoseLandmark.LEFT_HIP].x, landmarks[mp_pose.PoseLandmark.LEFT_HIP].y),
        'left_knee': (landmarks[mp_pose.PoseLandmark.LEFT_KNEE].x, landmarks[mp_pose.PoseLandmark.LEFT_KNEE].y),
        'left_ankle': (landmarks[mp_pose.PoseLandmark.LEFT_ANKLE].x, landmarks[mp_pose.PoseLandmark.LEFT_ANKLE].y)
    }

def extract_angles_from_frame(frame): # please keep in mind that this returns both the keypoints and the angles
    image_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    results = pose.process(image_rgb)
    
    if not results.pose_landmarks:
        return None, None
    
    keypoints = extract_keypoints(results.pose_landmarks.landmark)

    angles = {
        'right_elbow': calculate_angle(keypoints['right_shoulder'],
                                       keypoints['right_elbow'],
                                       keypoints['right_wrist']),
        'left_elbow': calculate_angle(keypoints['left_shoulder'],
                                      keypoints['left_elbow'],
                                      keypoints['left_wrist']),
        'right_shoulder': calculate_angle(keypoints['right_hip'],
                                          keypoints['right_shoulder'],
                                          keypoints['right_elbow']),
        'left_shoulder': calculate_angle(keypoints['left_hip'],
                                         keypoints['left_shoulder'],
                                         keypoints['left_elbow']),
        'right_knee': calculate_angle(keypoints['right_hip'],
                                      keypoints['right_knee'],
                                      keypoints['right_ankle']),
        'left_knee': calculate_angle(keypoints['left_hip'],
                                     keypoints['left_knee'],
                                     keypoints['left_ankle']),
        'right_hip': calculate_angle(keypoints['right_shoulder'],
                                     keypoints['right_hip'],
                                     keypoints['right_knee']),
        'left_hip': calculate_angle(keypoints['left_shoulder'],
                                     keypoints['left_hip'],
                                     keypoints['left_knee'])
    }

    return keypoints, angles

def crop_and_normalize_frame(frame, width=500, height=800, padding=50): # need to return the min and max x and y for calculations in analyze.py
    image_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    results = pose.process(image_rgb)

    if not results.pose_landmarks:
        print(f"No person detected in frame")
        return frame, None, None, None, None

    landmarks = results.pose_landmarks.landmark

    x_coords = [int(landmark.x * frame.shape[1]) for landmark in landmarks]
    y_coords = [int(landmark.y * frame.shape[0]) for landmark in landmarks]

    min_x, max_x = min(x_coords), max(x_coords)
    min_y, max_y = min(y_coords), max(y_coords)

    min_x = max(min_x - padding, 0)
    max_x = min(max_x + padding, frame.shape[1])
    min_y = max(min_y - padding, 0)
    max_y = min(max_y + padding, frame.shape[0])

    cropped_image = frame[min_y:max_y, min_x:max_x]

    resized_image = cv2.resize(cropped_image, (width, height))

    return resized_image, min_x, max_x, min_y, max_y