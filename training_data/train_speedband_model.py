"""
Train XGBoost model to predict next speedband value for each link.

This script implements:
1. Data preprocessing and feature engineering
2. Train/validation/test split
3. Model training with XGBoost
4. Model evaluation
5. Model persistence
"""
import os
import pandas as pd
import numpy as np
from datetime import datetime
from typing import Tuple, Dict, Any
import joblib
from sklearn.metrics import mean_absolute_error, mean_squared_error
import xgboost as xgb

ROOT_DIR = os.path.dirname(os.path.abspath(os.path.join(__file__, os.pardir)))
PARQUET_FILE = os.path.join(ROOT_DIR, "correlated_data", "correlated_traffic_data.parquet")
MODEL_DIR = os.path.join(os.path.dirname(__file__), "models")
MODEL_FILE = os.path.join(MODEL_DIR, "speedband_model.joblib")
FEATURE_NAMES_FILE = os.path.join(MODEL_DIR, "feature_names.txt")

# Create models directory if it doesn't exist
os.makedirs(MODEL_DIR, exist_ok=True)


def load_data() -> pd.DataFrame:
    """Load the parquet file."""
    print("Loading data...")
    df = pd.read_parquet(PARQUET_FILE)
    print(f"Loaded {len(df):,} rows")
    return df


def preprocess_data(df: pd.DataFrame) -> pd.DataFrame:
    """
    Preprocess data: convert timestamps, sort, and prepare for feature engineering.
    """
    print("\n" + "=" * 80)
    print("Step 1: Data Preprocessing")
    print("=" * 80)
    
    # Convert generated_at to datetime
    print("Converting timestamps...")
    df['generated_at'] = pd.to_datetime(df['generated_at'])
    
    # Sort by LinkID and timestamp to ensure proper ordering
    print("Sorting by LinkID and timestamp...")
    df = df.sort_values(['LinkID', 'generated_at']).reset_index(drop=True)
    
    print(f"Data shape: {df.shape}")
    print(f"Date range: {df['generated_at'].min()} to {df['generated_at'].max()}")
    
    return df


def create_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Create features for the model:
    - Time-based features
    - Lag features (most important)
    - Rolling statistics
    - Link-specific features
    - External features (rainfall, incidents)
    - Target variable (next speedband)
    """
    print("\n" + "=" * 80)
    print("Step 2: Feature Engineering")
    print("=" * 80)
    
    df = df.copy()
    
    # Time-based features
    print("Creating time-based features...")
    df['hour'] = df['generated_at'].dt.hour
    df['minute'] = df['generated_at'].dt.minute
    
    # Group by LinkID to create link-specific and lag features
    print("Creating lag features and link-specific features...")
    
    def create_link_features(group):
        """Create features for a single link."""
        group = group.sort_values('generated_at').reset_index(drop=True)
        
        # Lag features (PRIMARY FEATURES)
        group['speedband_lag1'] = group['speedband'].shift(1)
        group['speedband_lag2'] = group['speedband'].shift(2)
        group['speedband_lag3'] = group['speedband'].shift(3)
        group['speedband_lag5'] = group['speedband'].shift(5)
        
        # Rolling statistics over windows
        for window in [3, 5, 10]:
            group[f'speedband_rolling_mean_{window}'] = group['speedband'].shift(1).rolling(window=window, min_periods=1).mean()
            group[f'speedband_rolling_std_{window}'] = group['speedband'].shift(1).rolling(window=window, min_periods=1).std().fillna(0)
            group[f'speedband_rolling_min_{window}'] = group['speedband'].shift(1).rolling(window=window, min_periods=1).min()
            group[f'speedband_rolling_max_{window}'] = group['speedband'].shift(1).rolling(window=window, min_periods=1).max()
        
        # Number of changes in rolling window
        group['speedband_changes_3'] = (group['speedband'].shift(1).diff() != 0).rolling(window=3, min_periods=1).sum()
        group['speedband_changes_5'] = (group['speedband'].shift(1).diff() != 0).rolling(window=5, min_periods=1).sum()
        
        # Speedband change rate
        group['speedband_diff'] = group['speedband'].shift(1).diff().fillna(0)
        
        # Link-specific features
        # Historical average (using all previous data)
        group['link_avg_speedband'] = group['speedband'].shift(1).expanding().mean()
        group['link_std_speedband'] = group['speedband'].shift(1).expanding().std().fillna(0)
        
        # Rolling average of rainfall
        group['rainfall_rolling_mean_3'] = group['rainfall_mm'].shift(1).rolling(window=3, min_periods=1).mean()
        group['rainfall_rolling_mean_5'] = group['rainfall_mm'].shift(1).rolling(window=5, min_periods=1).mean()
        
        # Target variable: next speedband value
        group['target'] = group['speedband'].shift(-1)
        
        return group
    
    print("Processing links (this may take a while)...")
    df = df.groupby('LinkID', group_keys=False).apply(create_link_features).reset_index(drop=True)
    
    # Fill NaN values in lag features (first few rows per link)
    lag_cols = [col for col in df.columns if 'lag' in col or 'rolling' in col or 'link_' in col]
    for col in lag_cols:
        if col in df.columns:
            df[col] = df[col].fillna(df[col].median() if df[col].dtype in [np.float64, np.int64] else 0)
    
    # Encode LinkID as categorical (using numeric encoding for XGBoost)
    print("Encoding LinkID...")
    df['LinkID_encoded'] = pd.Categorical(df['LinkID']).codes
    
    # Convert boolean to int
    df['has_incident'] = df['has_incident'].astype(int)
    
    # Drop rows where target is NaN (last row of each link)
    print("Dropping rows with missing target...")
    initial_rows = len(df)
    df = df.dropna(subset=['target']).reset_index(drop=True)
    print(f"Dropped {initial_rows - len(df):,} rows with missing target")
    
    print(f"Final feature matrix shape: {df.shape}")
    print(f"Features created: {len([c for c in df.columns if c not in ['LinkID', 'generated_at', 'speedband', 'target']])}")
    
    return df


def split_data(df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """
    Split data into train/validation/test sets using time-based split.
    For each link: 70% train, 15% validation, 15% test.
    """
    print("\n" + "=" * 80)
    print("Step 3: Train/Validation/Test Split")
    print("=" * 80)
    
    train_dfs = []
    val_dfs = []
    test_dfs = []
    
    print("Splitting by link (time-based split)...")
    for link_id, group in df.groupby('LinkID'):
        group = group.sort_values('generated_at').reset_index(drop=True)
        n = len(group)
        
        # Split indices: 70% train, 15% val, 15% test
        train_end = int(n * 0.70)
        val_end = int(n * 0.85)
        
        train_dfs.append(group.iloc[:train_end])
        val_dfs.append(group.iloc[train_end:val_end])
        test_dfs.append(group.iloc[val_end:])
    
    train_df = pd.concat(train_dfs, ignore_index=True)
    val_df = pd.concat(val_dfs, ignore_index=True)
    test_df = pd.concat(test_dfs, ignore_index=True)
    
    print(f"Training set: {len(train_df):,} rows ({len(train_df)/len(df)*100:.1f}%)")
    print(f"Validation set: {len(val_df):,} rows ({len(val_df)/len(df)*100:.1f}%)")
    print(f"Test set: {len(test_df):,} rows ({len(test_df)/len(df)*100:.1f}%)")
    
    return train_df, val_df, test_df


def prepare_features(df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.Series]:
    """
    Prepare feature matrix X and target y from dataframe.
    """
    # Exclude non-feature columns
    exclude_cols = ['LinkID', 'generated_at', 'speedband', 'target']
    feature_cols = [col for col in df.columns if col not in exclude_cols]
    
    X = df[feature_cols]
    y = df['target']
    
    return X, y


def train_model(X_train: pd.DataFrame, y_train: pd.Series, 
                X_val: pd.DataFrame, y_val: pd.Series) -> xgb.XGBRegressor:
    """
    Train XGBoost regression model.
    """
    print("\n" + "=" * 80)
    print("Step 4: Model Training")
    print("=" * 80)
    
    print("Training XGBoost regressor...")
    
    # XGBoost parameters
    params = {
        'objective': 'reg:squarederror',
        'max_depth': 6,
        'learning_rate': 0.1,
        'n_estimators': 500,
        'subsample': 0.8,
        'colsample_bytree': 0.8,
        'min_child_weight': 3,
        'gamma': 0.1,
        'random_state': 42,
        'n_jobs': -1,
    }
    
    model = xgb.XGBRegressor(**params)
    
    # Train with early stopping
    print("Training with early stopping on validation set...")
    model.fit(
        X_train, y_train,
        eval_set=[(X_val, y_val)],
        early_stopping_rounds=20,
        verbose=100
    )
    
    print(f"Best iteration: {model.best_iteration}")
    print(f"Best score: {model.best_score:.4f}")
    
    return model


def evaluate_model(model: xgb.XGBRegressor, X: pd.DataFrame, y: pd.Series, 
                   dataset_name: str) -> Dict[str, float]:
    """
    Evaluate model and return metrics.
    """
    print(f"\nEvaluating on {dataset_name} set...")
    
    # Predict
    y_pred = model.predict(X)
    
    # Clip predictions to valid range [0, 8]
    y_pred = np.clip(y_pred, 0, 8)
    
    # Calculate metrics
    mae = mean_absolute_error(y, y_pred)
    rmse = np.sqrt(mean_squared_error(y, y_pred))
    
    # MAPE (handle division by zero)
    mape = np.mean(np.abs((y - y_pred) / (y + 1e-8))) * 100
    
    # Accuracy (exact match)
    y_pred_rounded = np.round(y_pred).astype(int)
    accuracy = (y_pred_rounded == y).mean() * 100
    
    metrics = {
        'MAE': mae,
        'RMSE': rmse,
        'MAPE': mape,
        'Accuracy': accuracy
    }
    
    print(f"  MAE: {mae:.4f}")
    print(f"  RMSE: {rmse:.4f}")
    print(f"  MAPE: {mape:.2f}%")
    print(f"  Accuracy (exact match): {accuracy:.2f}%")
    
    return metrics


def print_feature_importance(model: xgb.XGBRegressor, feature_names: list, top_n: int = 20):
    """Print top N most important features."""
    print(f"\nTop {top_n} Most Important Features:")
    print("-" * 60)
    
    importance = model.feature_importances_
    indices = np.argsort(importance)[::-1][:top_n]
    
    for i, idx in enumerate(indices, 1):
        print(f"{i:2d}. {feature_names[idx]:40s} {importance[idx]:.4f}")


def save_model(model: xgb.XGBRegressor, feature_names: list):
    """Save model and feature names."""
    print("\n" + "=" * 80)
    print("Step 5: Saving Model")
    print("=" * 80)
    
    print(f"Saving model to {MODEL_FILE}...")
    joblib.dump(model, MODEL_FILE)
    
    print(f"Saving feature names to {FEATURE_NAMES_FILE}...")
    with open(FEATURE_NAMES_FILE, 'w') as f:
        for name in feature_names:
            f.write(f"{name}\n")
    
    print("Model saved successfully!")


def main():
    """Main training pipeline."""
    print("=" * 80)
    print("Speedband Prediction Model Training")
    print("=" * 80)
    print(f"Start time: {datetime.now()}")
    
    # Load data
    df = load_data()
    
    # Preprocess
    df = preprocess_data(df)
    
    # Create features
    df = create_features(df)
    
    # Split data
    train_df, val_df, test_df = split_data(df)
    
    # Prepare features
    X_train, y_train = prepare_features(train_df)
    X_val, y_val = prepare_features(val_df)
    X_test, y_test = prepare_features(test_df)
    
    print(f"\nFeature matrix shape: {X_train.shape}")
    print(f"Feature columns: {list(X_train.columns)}")
    
    # Train model
    model = train_model(X_train, y_train, X_val, y_val)
    
    # Evaluate on all sets
    print("\n" + "=" * 80)
    print("Step 6: Model Evaluation")
    print("=" * 80)
    
    train_metrics = evaluate_model(model, X_train, y_train, "Training")
    val_metrics = evaluate_model(model, X_val, y_val, "Validation")
    test_metrics = evaluate_model(model, X_test, y_test, "Test")
    
    # Feature importance
    print_feature_importance(model, list(X_train.columns), top_n=20)
    
    # Save model
    save_model(model, list(X_train.columns))
    
    # Print summary
    print("\n" + "=" * 80)
    print("Training Summary")
    print("=" * 80)
    print(f"Training MAE: {train_metrics['MAE']:.4f}, Accuracy: {train_metrics['Accuracy']:.2f}%")
    print(f"Validation MAE: {val_metrics['MAE']:.4f}, Accuracy: {val_metrics['Accuracy']:.2f}%")
    print(f"Test MAE: {test_metrics['MAE']:.4f}, Accuracy: {test_metrics['Accuracy']:.2f}%")
    print(f"\nModel saved to: {MODEL_FILE}")
    print(f"End time: {datetime.now()}")
    print("=" * 80)


if __name__ == "__main__":
    main()
