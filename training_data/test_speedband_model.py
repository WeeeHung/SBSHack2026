"""
Test suite for speedband prediction model.

Tests model loading, prediction functionality, and edge cases.
"""
import os
import pytest
import tempfile
import shutil
from pathlib import Path
from typing import List

# Import the model class
from speedband_model import SpeedbandPredictor


# Fixture for model path
@pytest.fixture
def model_path():
    """Return the path to the model file."""
    return os.path.join(os.path.dirname(__file__), "models", "speedband_model.joblib")


@pytest.fixture
def feature_names_path():
    """Return the path to the feature names file."""
    return os.path.join(os.path.dirname(__file__), "models", "feature_names.txt")


@pytest.fixture
def predictor(model_path, feature_names_path):
    """Create a SpeedbandPredictor instance for testing."""
    return SpeedbandPredictor(model_path=model_path)


# ============================================================================
# Model Loading Tests
# ============================================================================

def test_model_loading_success(model_path, feature_names_path):
    """Test that SpeedbandPredictor can be initialized with default model path."""
    predictor = SpeedbandPredictor(model_path=model_path)
    assert predictor is not None
    assert predictor.model is not None
    assert predictor.feature_names is not None
    assert len(predictor.feature_names) > 0


def test_model_loading_file_not_found():
    """Test that FileNotFoundError is raised when model file doesn't exist."""
    with pytest.raises(FileNotFoundError, match="Model file not found"):
        SpeedbandPredictor(model_path="/nonexistent/path/model.joblib")


def test_model_loading_feature_names_not_found(feature_names_path):
    """Test that FileNotFoundError is raised when feature_names.txt doesn't exist."""
    # Temporarily rename feature_names.txt to test error handling
    backup_path = feature_names_path + ".backup"
    
    try:
        # Rename the file temporarily
        if os.path.exists(feature_names_path):
            shutil.move(feature_names_path, backup_path)
        
        # Try to load - should fail because feature_names.txt doesn't exist
        with pytest.raises(FileNotFoundError, match="Feature names file not found"):
            SpeedbandPredictor()
    finally:
        # Restore the file
        if os.path.exists(backup_path):
            shutil.move(backup_path, feature_names_path)


# ============================================================================
# Basic Prediction Tests
# ============================================================================

def test_predict_basic(predictor):
    """Test basic prediction with valid input data."""
    link_id = "test_link_123"
    speedband_history = [3, 4, 3, 5, 4]
    rainfall_history = [0.0, 0.5, 1.2, 0.0, 0.0]
    incident_history = [False, False, True, False, False]
    
    prediction = predictor.predict(
        link_id=link_id,
        speedband_history=speedband_history,
        rainfall_history=rainfall_history,
        incident_history=incident_history,
        current_hour=14,
        current_minute=30
    )
    
    # Verify prediction is a float
    assert isinstance(prediction, float)
    
    # Verify prediction is in valid range [0, 8]
    assert 0 <= prediction <= 8


def test_predict_output_type(predictor):
    """Test that prediction returns a float."""
    prediction = predictor.predict(
        link_id="test_link",
        speedband_history=[3, 4, 3, 5, 4],
        current_hour=10,
        current_minute=0
    )
    assert isinstance(prediction, float)


def test_predict_output_range(predictor):
    """Test that predictions are always in valid range [0, 8]."""
    test_cases = [
        ([1, 1, 1, 1, 1], "low_speedband"),
        ([8, 8, 8, 8, 8], "high_speedband"),
        ([0, 0, 0, 0, 0], "zero_speedband"),
        ([4, 5, 3, 6, 4], "varied_speedband"),
    ]
    
    for speedband_history, test_name in test_cases:
        prediction = predictor.predict(
            link_id=f"test_{test_name}",
            speedband_history=speedband_history,
            current_hour=12,
            current_minute=0
        )
        assert 0 <= prediction <= 8, f"Prediction {prediction} out of range for {test_name}"


# ============================================================================
# Edge Case Tests
# ============================================================================

def test_predict_minimal_history(predictor):
    """Test prediction with minimal history (1-2 values)."""
    # Test with 1 value
    prediction_1 = predictor.predict(
        link_id="test_link",
        speedband_history=[3],
        current_hour=10,
        current_minute=0
    )
    assert isinstance(prediction_1, float)
    assert 0 <= prediction_1 <= 8
    
    # Test with 2 values
    prediction_2 = predictor.predict(
        link_id="test_link",
        speedband_history=[3, 4],
        current_hour=10,
        current_minute=0
    )
    assert isinstance(prediction_2, float)
    assert 0 <= prediction_2 <= 8


def test_predict_none_rainfall_history(predictor):
    """Test prediction with None rainfall_history (should default to zeros)."""
    prediction = predictor.predict(
        link_id="test_link",
        speedband_history=[3, 4, 3, 5, 4],
        rainfall_history=None,
        current_hour=10,
        current_minute=0
    )
    assert isinstance(prediction, float)
    assert 0 <= prediction <= 8


def test_predict_none_incident_history(predictor):
    """Test prediction with None incident_history (should default to False)."""
    prediction = predictor.predict(
        link_id="test_link",
        speedband_history=[3, 4, 3, 5, 4],
        incident_history=None,
        current_hour=10,
        current_minute=0
    )
    assert isinstance(prediction, float)
    assert 0 <= prediction <= 8


def test_predict_none_time_parameters(predictor):
    """Test prediction with None time parameters (should use current time)."""
    prediction = predictor.predict(
        link_id="test_link",
        speedband_history=[3, 4, 3, 5, 4],
        current_hour=None,
        current_minute=None
    )
    assert isinstance(prediction, float)
    assert 0 <= prediction <= 8


def test_predict_different_time_values(predictor):
    """Test prediction with different time values."""
    test_times = [
        (0, 0),   # midnight
        (12, 0),  # noon
        (18, 30), # evening
        (23, 59), # late night
    ]
    
    for hour, minute in test_times:
        prediction = predictor.predict(
            link_id="test_link",
            speedband_history=[3, 4, 3, 5, 4],
            current_hour=hour,
            current_minute=minute
        )
        assert isinstance(prediction, float)
        assert 0 <= prediction <= 8


def test_predict_batch(predictor):
    """Test batch prediction with multiple links."""
    link_data = [
        {
            'link_id': 'link_1',
            'speedband_history': [3, 4, 3, 5, 4],
            'rainfall_history': [0.0, 0.5, 1.2, 0.0, 0.0],
            'incident_history': [False, False, True, False, False],
            'current_hour': 10,
            'current_minute': 0
        },
        {
            'link_id': 'link_2',
            'speedband_history': [5, 6, 5, 4, 5],
            'rainfall_history': [0.0, 0.0, 0.0, 0.0, 0.0],
            'incident_history': [False, False, False, False, False],
            'current_hour': 14,
            'current_minute': 30
        },
        {
            'link_id': 'link_3',
            'speedband_history': [2, 2, 3, 2, 2],
            'rainfall_history': [1.5, 2.0, 1.8, 1.2, 0.5],
            'incident_history': [True, True, False, False, False],
            'current_hour': 8,
            'current_minute': 15
        }
    ]
    
    predictions = predictor.predict_batch(link_data)
    
    # Verify we got predictions for all links
    assert len(predictions) == len(link_data)
    
    # Verify all predictions are valid
    for i, prediction in enumerate(predictions):
        assert isinstance(prediction, float), f"Prediction {i} is not a float"
        assert 0 <= prediction <= 8, f"Prediction {i} ({prediction}) out of range"


def test_predict_batch_with_optional_params(predictor):
    """Test batch prediction with optional parameters omitted."""
    link_data = [
        {
            'link_id': 'link_1',
            'speedband_history': [3, 4, 3, 5, 4],
            # rainfall_history and incident_history omitted
        },
        {
            'link_id': 'link_2',
            'speedband_history': [5, 6, 5, 4, 5],
            'rainfall_history': [0.0, 0.0, 0.0, 0.0, 0.0],
            # incident_history omitted
        }
    ]
    
    predictions = predictor.predict_batch(link_data)
    
    assert len(predictions) == len(link_data)
    for prediction in predictions:
        assert isinstance(prediction, float)
        assert 0 <= prediction <= 8


# ============================================================================
# Additional Validation Tests
# ============================================================================

def test_predict_no_exceptions(predictor):
    """Test that prediction doesn't raise exceptions with various inputs."""
    test_inputs = [
        {
            'link_id': 'test_1',
            'speedband_history': [1],
        },
        {
            'link_id': 'test_2',
            'speedband_history': [8, 8, 8],
        },
        {
            'link_id': 'test_3',
            'speedband_history': [3, 4, 3, 5, 4, 6, 5, 7, 6, 8],
            'rainfall_history': [0.0] * 10,
            'incident_history': [False] * 10,
        },
        {
            'link_id': 'test_4',
            'speedband_history': [0, 1, 2, 3, 4],
            'rainfall_history': [10.0, 20.0, 15.0, 5.0, 0.0],
            'incident_history': [True, True, True, False, False],
        }
    ]
    
    for test_input in test_inputs:
        try:
            prediction = predictor.predict(**test_input, current_hour=12, current_minute=0)
            assert isinstance(prediction, float)
            assert 0 <= prediction <= 8
        except Exception as e:
            pytest.fail(f"Prediction raised exception for input {test_input}: {e}")


def test_predict_deterministic_inputs(predictor):
    """Test that same inputs produce consistent predictions (within floating point precision)."""
    link_id = "test_deterministic"
    speedband_history = [3, 4, 3, 5, 4]
    rainfall_history = [0.0, 0.5, 1.2, 0.0, 0.0]
    incident_history = [False, False, True, False, False]
    
    prediction1 = predictor.predict(
        link_id=link_id,
        speedband_history=speedband_history,
        rainfall_history=rainfall_history,
        incident_history=incident_history,
        current_hour=14,
        current_minute=30
    )
    
    prediction2 = predictor.predict(
        link_id=link_id,
        speedband_history=speedband_history,
        rainfall_history=rainfall_history,
        incident_history=incident_history,
        current_hour=14,
        current_minute=30
    )
    
    # Predictions should be the same (model is deterministic)
    assert prediction1 == prediction2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
