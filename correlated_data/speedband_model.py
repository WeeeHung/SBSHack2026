"""
Model wrapper for loading and using the trained speedband prediction model.
"""
import os
import pandas as pd
import numpy as np
import joblib
from typing import Dict, Any, List, Optional
import xgboost as xgb

ROOT_DIR = os.path.dirname(os.path.abspath(os.path.join(__file__, os.pardir)))
MODEL_DIR = os.path.join(os.path.dirname(__file__), "models")
MODEL_FILE = os.path.join(MODEL_DIR, "speedband_model.joblib")
FEATURE_NAMES_FILE = os.path.join(MODEL_DIR, "feature_names.txt")


class SpeedbandPredictor:
    """Wrapper class for the trained speedband prediction model."""
    
    def __init__(self, model_path: Optional[str] = None):
        """
        Initialize the predictor by loading the model and feature names.
        
        Args:
            model_path: Optional path to model file. If None, uses default path.
        """
        if model_path is None:
            model_path = MODEL_FILE
        
        if not os.path.exists(model_path):
            raise FileNotFoundError(f"Model file not found: {model_path}")
        
        if not os.path.exists(FEATURE_NAMES_FILE):
            raise FileNotFoundError(f"Feature names file not found: {FEATURE_NAMES_FILE}")
        
        # Load model
        print(f"Loading model from {model_path}...")
        self.model = joblib.load(model_path)
        
        # Load feature names
        with open(FEATURE_NAMES_FILE, 'r') as f:
            self.feature_names = [line.strip() for line in f.readlines()]
        
        print(f"Model loaded successfully with {len(self.feature_names)} features")
    
    def _create_features_from_history(self, 
                                      link_id: str,
                                      speedband_history: List[int],
                                      rainfall_history: List[float],
                                      incident_history: List[bool],
                                      current_hour: int,
                                      current_minute: int) -> pd.DataFrame:
        """
        Create feature vector from historical data.
        
        Args:
            link_id: Link identifier
            speedband_history: List of speedband values (most recent last)
            rainfall_history: List of rainfall values (most recent last)
            incident_history: List of incident flags (most recent last)
            current_hour: Current hour (0-23)
            current_minute: Current minute (0-59)
        
        Returns:
            DataFrame with single row containing features
        """
        # Reverse history to have oldest first (for proper lag calculation)
        speedband_history = list(reversed(speedband_history))
        rainfall_history = list(reversed(rainfall_history))
        incident_history = list(reversed(incident_history))
        
        n = len(speedband_history)
        
        # Initialize feature dictionary
        features = {}
        
        # Time features
        features['hour'] = current_hour
        features['minute'] = current_minute
        
        # Lag features
        features['speedband_lag1'] = speedband_history[-1] if n >= 1 else 3.0  # Default to mean
        features['speedband_lag2'] = speedband_history[-2] if n >= 2 else features['speedband_lag1']
        features['speedband_lag3'] = speedband_history[-3] if n >= 3 else features['speedband_lag2']
        features['speedband_lag5'] = speedband_history[-5] if n >= 5 else features['speedband_lag3']
        
        # Rolling statistics
        for window in [3, 5, 10]:
            window_data = speedband_history[-window:] if n >= window else speedband_history
            if window_data:
                features[f'speedband_rolling_mean_{window}'] = np.mean(window_data)
                features[f'speedband_rolling_std_{window}'] = np.std(window_data) if len(window_data) > 1 else 0.0
                features[f'speedband_rolling_min_{window}'] = np.min(window_data)
                features[f'speedband_rolling_max_{window}'] = np.max(window_data)
            else:
                features[f'speedband_rolling_mean_{window}'] = 3.0
                features[f'speedband_rolling_std_{window}'] = 0.0
                features[f'speedband_rolling_min_{window}'] = 3.0
                features[f'speedband_rolling_max_{window}'] = 3.0
        
        # Number of changes
        if n >= 3:
            changes_3 = sum(1 for i in range(1, min(3, n)) if speedband_history[-i] != speedband_history[-i-1])
            features['speedband_changes_3'] = changes_3
        else:
            features['speedband_changes_3'] = 0
        
        if n >= 5:
            changes_5 = sum(1 for i in range(1, min(5, n)) if speedband_history[-i] != speedband_history[-i-1])
            features['speedband_changes_5'] = changes_5
        else:
            features['speedband_changes_5'] = 0
        
        # Speedband difference
        if n >= 2:
            features['speedband_diff'] = speedband_history[-1] - speedband_history[-2]
        else:
            features['speedband_diff'] = 0.0
        
        # Link-specific features (using historical average)
        if speedband_history:
            features['link_avg_speedband'] = np.mean(speedband_history)
            features['link_std_speedband'] = np.std(speedband_history) if len(speedband_history) > 1 else 0.0
        else:
            features['link_avg_speedband'] = 3.0
            features['link_std_speedband'] = 0.0
        
        # Rainfall features
        if rainfall_history:
            features['rainfall_mm'] = rainfall_history[-1] if len(rainfall_history) > 0 else 0.0
            # Rolling averages
            for window in [3, 5]:
                window_rain = rainfall_history[-window:] if len(rainfall_history) >= window else rainfall_history
                features[f'rainfall_rolling_mean_{window}'] = np.mean(window_rain) if window_rain else 0.0
        else:
            features['rainfall_mm'] = 0.0
            features['rainfall_rolling_mean_3'] = 0.0
            features['rainfall_rolling_mean_5'] = 0.0
        
        # Incident feature
        features['has_incident'] = int(incident_history[-1]) if incident_history else 0
        
        # LinkID encoding (simple hash-based encoding for consistency)
        # In production, should use same encoding as training
        link_id_hash = hash(str(link_id)) % 1000000
        features['LinkID_encoded'] = link_id_hash
        
        # Create DataFrame with all features in correct order
        feature_df = pd.DataFrame([features])
        
        # Ensure all expected features are present
        for feat_name in self.feature_names:
            if feat_name not in feature_df.columns:
                # Fill missing features with default values
                if 'lag' in feat_name or 'rolling' in feat_name:
                    feature_df[feat_name] = 3.0
                elif 'std' in feat_name or 'diff' in feat_name:
                    feature_df[feat_name] = 0.0
                elif 'changes' in feat_name:
                    feature_df[feat_name] = 0
                else:
                    feature_df[feat_name] = 0.0
        
        # Reorder columns to match training order
        feature_df = feature_df[self.feature_names]
        
        return feature_df
    
    def predict(self,
                link_id: str,
                speedband_history: List[int],
                rainfall_history: Optional[List[float]] = None,
                incident_history: Optional[List[bool]] = None,
                current_hour: Optional[int] = None,
                current_minute: Optional[int] = None) -> float:
        """
        Predict next speedband value for a link.
        
        Args:
            link_id: Link identifier
            speedband_history: List of recent speedband values (most recent last)
            rainfall_history: Optional list of recent rainfall values
            incident_history: Optional list of recent incident flags
            current_hour: Current hour (0-23), defaults to current time
            current_minute: Current minute (0-59), defaults to current time
        
        Returns:
            Predicted speedband value (0-8)
        """
        from datetime import datetime
        
        if current_hour is None or current_minute is None:
            now = datetime.now()
            current_hour = now.hour
            current_minute = now.minute
        
        if rainfall_history is None:
            rainfall_history = [0.0] * len(speedband_history)
        
        if incident_history is None:
            incident_history = [False] * len(speedband_history)
        
        # Create features
        features = self._create_features_from_history(
            link_id, speedband_history, rainfall_history, incident_history,
            current_hour, current_minute
        )
        
        # Predict
        prediction = self.model.predict(features)[0]
        
        # Clip to valid range
        prediction = np.clip(prediction, 0, 8)
        
        return float(prediction)
    
    def predict_batch(self, 
                     link_data: List[Dict[str, Any]]) -> List[float]:
        """
        Predict for multiple links at once.
        
        Args:
            link_data: List of dictionaries, each containing:
                - link_id: str
                - speedband_history: List[int]
                - rainfall_history: Optional[List[float]]
                - incident_history: Optional[List[bool]]
                - current_hour: Optional[int]
                - current_minute: Optional[int]
        
        Returns:
            List of predicted speedband values
        """
        predictions = []
        for data in link_data:
            pred = self.predict(
                link_id=data['link_id'],
                speedband_history=data['speedband_history'],
                rainfall_history=data.get('rainfall_history'),
                incident_history=data.get('incident_history'),
                current_hour=data.get('current_hour'),
                current_minute=data.get('current_minute')
            )
            predictions.append(pred)
        
        return predictions


# Global model instance (lazy loading)
_model_instance = None


def get_predictor() -> SpeedbandPredictor:
    """Get or create the global model instance."""
    global _model_instance
    if _model_instance is None:
        _model_instance = SpeedbandPredictor()
    return _model_instance


def predict_speedband(link_id: str,
                     speedband_history: List[int],
                     rainfall_history: Optional[List[float]] = None,
                     incident_history: Optional[List[bool]] = None) -> float:
    """
    Convenience function to predict speedband.
    
    Args:
        link_id: Link identifier
        speedband_history: List of recent speedband values (most recent last)
        rainfall_history: Optional list of recent rainfall values
        incident_history: Optional list of recent incident flags
    
    Returns:
        Predicted speedband value (0-8)
    """
    predictor = get_predictor()
    return predictor.predict(link_id, speedband_history, rainfall_history, incident_history)
