import os

import numpy as np
from tensorflow import keras


class TennisModelTester:
    def __init__(self, model_path='tennis_model.keras'):
        self.model = keras.models.load_model(model_path)
        self.sequence_length = 30
        self.num_features = 32
        
    def predict_single_sequence(self, sequence_path):
        """Predict a single sequence from a .npy file"""
        try:
            sequence = np.load(sequence_path)
            if sequence.shape != (self.sequence_length, self.num_features):
                print(f"Warning: Sequence shape {sequence.shape} doesn't match expected shape {(self.sequence_length, self.num_features)}")
                return None
                
            # Add batch dimension
            sequence = np.expand_dims(sequence, 0)
            
            # Get prediction
            prediction = self.model.predict(sequence, verbose=0)[0][0]
            
            # Convert to probability
            probability = float(prediction)
            return probability
            
        except Exception as e:
            print(f"Error processing sequence: {str(e)}")
            return None
    
    def test_directory(self, test_dir):
        """Test all sequences in a directory"""
        print(f"\nTesting sequences in {test_dir}")
        print("=" * 50)
        
        results = []
        for file in os.listdir(test_dir):
            if file.endswith('.npy'):
                sequence_path = os.path.join(test_dir, file)
                prob = self.predict_single_sequence(sequence_path)
                if prob is not None:
                    results.append((file, prob))
                    print(f"Sequence: {file}")
                    print(f"Probability of being a forehand: {prob:.2%}")
                    print("-" * 30)
        
        return results

def main():
    # Initialize tester
    tester = TennisModelTester('tennis_model.keras')
    
    # Test forehand sequences
    forehand_dir = 'extractions/processed/forehand'
    if os.path.exists(forehand_dir):
        results = tester.test_directory(forehand_dir)
        
        # Calculate average probability for forehand sequences
        if results:
            avg_prob = sum(prob for _, prob in results) / len(results)
            print(f"\nAverage probability for forehand sequences: {avg_prob:.2%}")
    else:
        print("Forehand directory not found!")

if __name__ == "__main__":
    main()