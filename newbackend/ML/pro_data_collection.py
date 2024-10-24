import cv2
import os
import random
import pandas as pd
from utils import extract_angles_from_frame, crop_and_normalize_frame

def process_video_frames(video_path, output_dir, num_frames_to_process):
    cap = cv2.VideoCapture(video_path)

    if not cap.isOpened():
        print(f"Error: Couldn't open video {video_path}")
        return

    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

    if num_frames_to_process > total_frames:
        print(f"Requested number of frames ({num_frames_to_process}) exceeds total frames ({total_frames}). Processing all frames.")
        num_frames_to_process = total_frames

    selected_frames = sorted(random.sample(range(total_frames), num_frames_to_process))

    frame_count = 0
    selected_frame_count = 0

    while selected_frame_count < num_frames_to_process:
        ret, frame = cap.read()

        if not ret:
            print("End of video or no frame received.")
            break

        if frame_count == selected_frames[selected_frame_count]:
            normalized_frame, _, _, _, _ = crop_and_normalize_frame(frame)
            output_image_path = os.path.join(output_dir, f"frame_{frame_count}.jpg")
            cv2.imwrite(output_image_path, normalized_frame)
            selected_frame_count += 1

        frame_count += 1

    cap.release()
    print(f"Video processing complete. {num_frames_to_process} frames processed.")

def process_image_directory(directory_path):
    data = []
    for filename in os.listdir(directory_path):
        if filename.endswith(('.png', '.jpg', '.jpeg')):
            image_path = os.path.join(directory_path, filename)
            
            frame = cv2.imread(image_path)

            _, angles = extract_angles_from_frame(frame)
            if angles:
                angles['filename'] = filename
                data.append(angles)

    return pd.DataFrame(data)

if __name__ == '__main__':
    video_path = 'kickserve.mp4'
    output_dir = 'data/kickserve'
    num_frames_to_process = 300

    # if not os.path.exists(output_dir):
    #     print(f"Creating output directory at {output_dir}")
    #     os.makedirs(output_dir, exist_ok=True)

    # process_video_frames(video_path, output_dir, num_frames_to_process)

    results_df = process_image_directory(output_dir)
    
    results_df.to_csv('pro_kickserve_angles.csv', index=False)
    print("Analysis complete. Results saved to pro_kickserve_angles.csv")
