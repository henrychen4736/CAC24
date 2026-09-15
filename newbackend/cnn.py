# cnn.py
import os

import numpy as np
from keras.layers import LSTM, Dense, Dropout, Input
from keras.models import Sequential


class TennisModelTrainer:
    def __init__(self, processed_dir=None, sequence_length=30, num_features=32):
        self.processed_dir = processed_dir if processed_dir else 'extractions/processed'
        self.sequence_length = sequence_length
        self.num_features = num_features
        self.model = self._build_model()
        
    def _build_model(self):
        model = Sequential([
            Input(shape=(self.sequence_length, self.num_features)),
            LSTM(128, return_sequences=True),
            Dropout(0.2),
            LSTM(64),
            Dropout(0.2),
            Dense(32, activation='relu'),
            Dropout(0.2),
            Dense(16, activation='relu'),
            Dense(1, activation='sigmoid')
        ])
        
        model.compile(
            optimizer='adam',
            loss='binary_crossentropy',
            metrics=['accuracy']
        )
        
        return model
    
    def load_training_data(self):
        """Load the processed sequences for training"""
        X = []
        y = []
        
        print("Loading training data...")
        
        # Load forehand sequences
        forehand_dir = os.path.join(self.processed_dir, 'forehand')
        if os.path.exists(forehand_dir):
            files = [f for f in os.listdir(forehand_dir) if f.endswith('.npy')]
            print(f"Found {len(files)} sequence files")
            
            for file in files:
                try:
                    sequence = np.load(os.path.join(forehand_dir, file))
                    X.append(sequence)
                    y.append(1)  # 1 for forehand
                except Exception as e:
                    print(f"Error loading {file}: {str(e)}")
        
        # Convert to numpy arrays
        X = np.array(X)
        y = np.array(y)
        
        print(f"Final dataset shapes - X: {X.shape}, y: {y.shape}")
        
        if len(X) == 0:
            raise ValueError("No valid training sequences found!")
            
        return X, y
    
    def train_model(self):
        """Train the model with the loaded data"""
        X, y = self.load_training_data()
        print(f"Training with {len(X)} sequences")
        
        history = self.model.fit(
            X, y,
            epochs=50,
            batch_size=32,
            validation_split=0.2,
            verbose=1
        )
        
        return self.model, history