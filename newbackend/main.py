# main.py
import os

import numpy as np
from cnn import TennisModelTrainer


def create_directories():
    """Create necessary directories if they don't exist"""
    directories = [
        'data/forehand',
        'data/backhand',
        'data/serve',
        'extractions/processed/forehand',
        'extractions/processed/backhand',
        'extractions/processed/serve',
        'processed',
        'uploads'
    ]
    
    for directory in directories:
        if not os.path.exists(directory):
            os.makedirs(directory)
            print(f"Created directory: {directory}")

def train_model():
    """Train the model on processed sequences"""
    print("\nStep 2: Training model...")
    
    # Initialize trainer with correct parameters
    trainer = TennisModelTrainer(
        processed_dir='extractions/processed',
        sequence_length=30,
        num_features=32
    )
    
    # Train the model
    model, history = trainer.train_model()
    
    # Save the model
    model.save('tennis_model.keras')
    print("Model saved as tennis_model.keras")
    
    return model, history

def main():
    print("Tennis Analysis Pipeline")
    print("=======================")
    
    # Create necessary directories
    create_directories()
    
    # Check if we have existing processed sequences
    if os.path.exists('extractions/processed/forehand') and \
       len(os.listdir('extractions/processed/forehand')) > 0:
        print("\nStep 1: Using existing processed videos")
    else:
        print("No processed sequences found. Please run data_processor.py first.")
        return
    
    # Train the model
    train_model()

if __name__ == "__main__":
    main()