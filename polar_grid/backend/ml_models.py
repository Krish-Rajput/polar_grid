"""
AI Load Forecasting Engine for Polar Stations
Implements multiple ML models: XGBoost, Random Forest, and statistical methods
Hybrid ensemble approach for robust predictions
"""
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score, mean_absolute_percentage_error
import pickle
import os
from typing import Dict, List, Tuple, Optional
import warnings
warnings.filterwarnings('ignore')

class PolarLoadForecaster:
    """
    Hybrid ensemble forecaster combining multiple ML approaches
    Optimized for polar station energy demand prediction
    """
    
    def __init__(self):
        self.xgb_model = None
        self.rf_model = None
        self.gb_model = None
        self.scaler = StandardScaler()
        self.feature_columns = None
        self.is_trained = False
        
        # Model weights (ensemble)
        self.weights = {
            'xgb': 0.45,
            'rf': 0.25,
            'gb': 0.30
        }
    
    def get_feature_columns(self) -> List[str]:
        """Returns the feature columns used for prediction"""
        return [
            'hour', 'day_of_week', 'day_of_year', 'month', 'is_weekend',
            'hour_sin', 'hour_cos', 'doy_sin', 'doy_cos',
            'temperature', 'wind_speed', 'solar_irradiance',
            'heating_degree_hours', 'wind_power_potential',
            'is_polar_night', 'is_midnight_sun',
            'load_lag_1h', 'load_lag_2h', 'load_lag_3h',
            'load_lag_6h', 'load_lag_12h', 'load_lag_24h',
            'load_rolling_mean_6h', 'load_rolling_std_6h',
            'load_rolling_mean_24h'
        ]
    
    def train(self, features_df: pd.DataFrame, target_col: str = 'total_demand_kw',
              test_size: float = 0.2) -> Dict:
        """
        Train ensemble of ML models on polar station data
        Returns training metrics and model performance
        """
        feature_cols = self.get_feature_columns()
        
        # Ensure all required features exist
        available_features = [col for col in feature_cols if col in features_df.columns]
        self.feature_columns = available_features
        
        # Prepare data (remove target from features if present)
        X = features_df[available_features].copy()
        y = features_df[target_col].values
        
        # Split data temporally (no random shuffle for time series)
        split_idx = int(len(X) * (1 - test_size))
        X_train, X_test = X.iloc[:split_idx], X.iloc[split_idx:]
        y_train, y_test = y[:split_idx], y[split_idx:]
        
        # Scale features
        X_train_scaled = self.scaler.fit_transform(X_train)
        X_test_scaled = self.scaler.transform(X_test)
        
        # Train XGBoost (using GradientBoosting as fallback if xgboost not available)
        try:
            import xgboost as xgb
            self.xgb_model = xgb.XGBRegressor(
                n_estimators=200,
                max_depth=6,
                learning_rate=0.05,
                subsample=0.8,
                colsample_bytree=0.8,
                random_state=42,
                objective='reg:squarederror'
            )
            self.xgb_model.fit(X_train_scaled, y_train)
        except ImportError:
            self.xgb_model = GradientBoostingRegressor(
                n_estimators=200, max_depth=6, learning_rate=0.05, random_state=42
            )
            self.xgb_model.fit(X_train_scaled, y_train)
        
        # Train Random Forest
        self.rf_model = RandomForestRegressor(
            n_estimators=150,
            max_depth=10,
            min_samples_split=5,
            random_state=42,
            n_jobs=-1
        )
        self.rf_model.fit(X_train_scaled, y_train)
        
        # Train Gradient Boosting
        self.gb_model = GradientBoostingRegressor(
            n_estimators=150,
            max_depth=5,
            learning_rate=0.05,
            random_state=42
        )
        self.gb_model.fit(X_train_scaled, y_train)
        
        self.is_trained = True
        
        # Generate predictions
        preds_xgb = self.xgb_model.predict(X_test_scaled)
        preds_rf = self.rf_model.predict(X_test_scaled)
        preds_gb = self.gb_model.predict(X_test_scaled)
        
        # Ensemble prediction
        preds_ensemble = (self.weights['xgb'] * preds_xgb + 
                         self.weights['rf'] * preds_rf + 
                         self.weights['gb'] * preds_gb)
        
        # Calculate metrics
        metrics = self._calculate_metrics(y_test, preds_ensemble, preds_xgb, preds_rf, preds_gb)
        
        # Store feature importances
        self.feature_importances = self.xgb_model.feature_importances_
        
        return metrics
    
    def predict(self, features_df: pd.DataFrame) -> np.ndarray:
        """Generate ensemble prediction"""
        if not self.is_trained:
            raise ValueError("Model not trained yet")
        
        X = features_df[self.feature_columns]
        X_scaled = self.scaler.transform(X)
        
        preds_xgb = self.xgb_model.predict(X_scaled)
        preds_rf = self.rf_model.predict(X_scaled)
        preds_gb = self.gb_model.predict(X_scaled)
        
        return (self.weights['xgb'] * preds_xgb + 
                self.weights['rf'] * preds_rf + 
                self.weights['gb'] * preds_gb)
    
    def predict_with_uncertainty(self, features_df: pd.DataFrame) -> Tuple[np.ndarray, np.ndarray]:
        """
        Prediction with confidence intervals
        Uses model disagreement as uncertainty estimate
        """
        X = features_df[self.feature_columns]
        X_scaled = self.scaler.transform(X)
        
        preds_xgb = self.xgb_model.predict(X_scaled)
        preds_rf = self.rf_model.predict(X_scaled)
        preds_gb = self.gb_model.predict(X_scaled)
        
        ensemble = (self.weights['xgb'] * preds_xgb + 
                   self.weights['rf'] * preds_rf + 
                   self.weights['gb'] * preds_gb)
        
        # Uncertainty from model disagreement
        std = np.std([preds_xgb, preds_rf, preds_gb], axis=0)
        
        # 95% confidence interval (approximately 2 std)
        ci_lower = ensemble - 1.96 * std
        ci_upper = ensemble + 1.96 * std
        
        return ensemble, (ci_lower, ci_upper)
    
    def _calculate_metrics(self, y_true, y_ensemble, y_xgb, y_rf, y_gb) -> Dict:
        """Calculate comprehensive model performance metrics"""
        
        def calc_metrics(y_pred):
            return {
                'mae': mean_absolute_error(y_true, y_pred),
                'rmse': np.sqrt(mean_squared_error(y_true, y_pred)),
                'r2': r2_score(y_true, y_pred),
                'mape': mean_absolute_percentage_error(y_true, y_pred) * 100,
                'max_error': np.max(np.abs(y_true - y_pred))
            }
        
        return {
            'ensemble': calc_metrics(y_ensemble),
            'xgboost': calc_metrics(y_xgb),
            'random_forest': calc_metrics(y_rf),
            'gradient_boosting': calc_metrics(y_gb),
            'sample_size': len(y_true),
            'test_period_hours': len(y_true)
        }
    
    def get_feature_importance(self, top_n: int = 10) -> Dict:
        """Get top N most important features"""
        if self.feature_importances is None or self.feature_columns is None:
            return {}
        
        importance_df = pd.DataFrame({
            'feature': self.feature_columns,
            'importance': self.feature_importances
        }).sort_values('importance', ascending=False)
        
        return importance_df.head(top_n).to_dict('records')
    
    def save_models(self, path: str):
        """Save trained models to disk"""
        os.makedirs(path, exist_ok=True)
        
        model_data = {
            'xgb_model': self.xgb_model,
            'rf_model': self.rf_model,
            'gb_model': self.gb_model,
            'scaler': self.scaler,
            'feature_columns': self.feature_columns,
            'weights': self.weights,
            'is_trained': self.is_trained
        }
        
        with open(os.path.join(path, 'forecaster.pkl'), 'wb') as f:
            pickle.dump(model_data, f)
    
    def load_models(self, path: str):
        """Load trained models from disk"""
        with open(os.path.join(path, 'forecaster.pkl'), 'rb') as f:
            model_data = pickle.load(f)
        
        self.xgb_model = model_data['xgb_model']
        self.rf_model = model_data['rf_model']
        self.gb_model = model_data['gb_model']
        self.scaler = model_data['scaler']
        self.feature_columns = model_data['feature_columns']
        self.weights = model_data['weights']
        self.is_trained = model_data['is_trained']


class RenewableForecaster:
    """
    Specialized forecaster for solar and wind energy generation
    Uses physical models + ML corrections
    """
    
    def __init__(self):
        self.solar_model = None
        self.wind_model = None
        self.scaler = StandardScaler()
        self.is_trained = False
    
    def train(self, features_df: pd.DataFrame):
        """Train solar and wind generation forecasters"""
        solar_features = ['hour_sin', 'hour_cos', 'doy_sin', 'doy_cos',
                         'temperature', 'solar_irradiance', 'is_polar_night']
        wind_features = ['wind_speed', 'wind_power_potential', 'temperature',
                        'hour', 'doy_sin', 'doy_cos']
        
        available_solar = [c for c in solar_features if c in features_df.columns]
        available_wind = [c for c in wind_features if c in features_df.columns]
        
        X_solar = features_df[available_solar].values
        y_solar = features_df['solar_generation_kw'].values
        
        X_wind = features_df[available_wind].values
        y_wind = features_df['wind_generation_kw'].values
        
        # Fit separate scalers for solar and wind
        self.solar_scaler = StandardScaler()
        self.wind_scaler = StandardScaler()
        
        # Train solar model
        self.solar_model = GradientBoostingRegressor(
            n_estimators=100, max_depth=5, learning_rate=0.1, random_state=42
        )
        X_solar_scaled = self.solar_scaler.fit_transform(X_solar)
        self.solar_model.fit(X_solar_scaled, y_solar)
        
        # Train wind model
        self.wind_model = GradientBoostingRegressor(
            n_estimators=100, max_depth=5, learning_rate=0.1, random_state=42
        )
        X_wind_scaled = self.wind_scaler.fit_transform(X_wind)
        self.wind_model.fit(X_wind_scaled, y_wind)
        
        self.is_trained = True
        self.solar_features = available_solar
        self.wind_features = available_wind
    
    def predict_solar(self, features_df: pd.DataFrame) -> np.ndarray:
        X = features_df[self.solar_features].values
        return self.solar_model.predict(self.solar_scaler.transform(X))
    
    def predict_wind(self, features_df: pd.DataFrame) -> np.ndarray:
        X = features_df[self.wind_features].values
        return self.wind_model.predict(self.wind_scaler.transform(X))


if __name__ == "__main__":
    from data_simulator import PolarDataSimulator
    
    # Test the forecaster
    simulator = PolarDataSimulator(station_type="antarctica", seed=42)
    df = simulator.generate_hourly_data(days=365)
    features = simulator.generate_features_for_ml(df)
    
    forecaster = PolarLoadForecaster()
    metrics = forecaster.train(features)
    
    print("\n=== Load Forecasting Model Performance ===")
    print(f"\nTest period: {metrics['test_period_hours']} hours")
    print("\nEnsemble Model:")
    for metric, value in metrics['ensemble'].items():
        if metric == 'mape':
            print(f"  {metric.upper()}: {value:.2f}%")
        else:
            print(f"  {metric.upper()}: {value:.2f}")
    
    print("\nIndividual Models:")
    for model_name in ['xgboost', 'random_forest', 'gradient_boosting']:
        print(f"  {model_name}: MAE={metrics[model_name]['mae']:.2f}, R²={metrics[model_name]['r2']:.4f}")
    
    print("\nTop 10 Feature Importances:")
    for feat in forecaster.get_feature_importance(10):
        print(f"  {feat['feature']}: {feat['importance']:.4f}")
