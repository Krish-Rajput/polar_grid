"""
AI Load Forecasting Engine for Polar Stations
Implements multiple ML models: XGBoost, Random Forest, and Gradient Boosting
Includes specialized forecasters for Renewable Energy and Blizzard Risk Classification.
"""
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor, RandomForestClassifier
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score, mean_absolute_percentage_error, accuracy_score, precision_score, recall_score, f1_score
import pickle
import os
from typing import Dict, List, Tuple, Optional
import warnings
warnings.filterwarnings('ignore')


def engineer_polar_features(df: pd.DataFrame) -> pd.DataFrame:
    """Create rich ML-ready features from raw polar station time series"""
    features = df.copy()

    # Time Cyclical Features
    features['hour'] = features.index.hour
    features['day_of_week'] = features.index.dayofweek
    features['day_of_year'] = features.index.dayofyear
    features['month'] = features.index.month
    features['is_weekend'] = (features['day_of_week'] >= 5).astype(int)

    features['hour_sin'] = np.sin(2 * np.pi * features['hour'] / 24.0)
    features['hour_cos'] = np.cos(2 * np.pi * features['hour'] / 24.0)
    features['doy_sin'] = np.sin(2 * np.pi * features['day_of_year'] / 365.25)
    features['doy_cos'] = np.cos(2 * np.pi * features['day_of_year'] / 365.25)

    # Polar Climate Derived Physics
    if 'heating_degree_hours' not in features.columns:
        features['heating_degree_hours'] = np.maximum(0.0, 18.0 - features['temperature'])
    if 'cooling_degree_hours' not in features.columns:
        features['cooling_degree_hours'] = np.maximum(0.0, features['temperature'] - (-5.0))
        
    features['wind_power_potential'] = np.where(
        (features['wind_speed'] >= 3.0) & (features['wind_speed'] < 25.0),
        0.5 * 1.225 * np.pi * 400.0 * (features['wind_speed'] ** 3) / 1000.0,
        0.0
    )

    if 'wind_chill' not in features.columns:
        features['wind_chill'] = np.where(
            (features['temperature'] < 10.0) & (features['wind_speed'] > 1.3),
            13.12 + 0.6215 * features['temperature'] - 11.37 * (features['wind_speed'] ** 0.16) + 0.3965 * features['temperature'] * (features['wind_speed'] ** 0.16),
            features['temperature']
        )

    if 'pressure_drop_3h' not in features.columns:
        if 'pressure' in features.columns:
            features['pressure_drop_3h'] = features['pressure'].diff(3).bfill()
        else:
            features['pressure_drop_3h'] = 0.0

    # Demand Lag Features (Autoregressive dependencies)
    if 'total_demand_kw' in features.columns:
        for lag in [1, 2, 3, 6, 12, 24]:
            features[f'load_lag_{lag}h'] = features['total_demand_kw'].shift(lag)

        features['load_rolling_mean_6h'] = features['total_demand_kw'].rolling(6, min_periods=1).mean()
        features['load_rolling_std_6h'] = features['total_demand_kw'].rolling(6, min_periods=1).std()
        features['load_rolling_mean_24h'] = features['total_demand_kw'].rolling(24, min_periods=1).mean()

    # Solar Day / Night Markers
    if 'is_polar_night' not in features.columns:
        features['is_polar_night'] = (features['solar_irradiance'] <= 0.05).astype(int)
    if 'is_midnight_sun' not in features.columns:
        features['is_midnight_sun'] = (features['solar_irradiance'] > 100.0).astype(int)

    features.dropna(inplace=True)
    return features


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
        self.feature_importances = None

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
        """Train ensemble of ML models on polar station data"""
        feature_cols = self.get_feature_columns()
        available_features = [col for col in feature_cols if col in features_df.columns]
        self.feature_columns = available_features

        X = features_df[available_features].copy()
        y = features_df[target_col].values

        split_idx = int(len(X) * (1 - test_size))
        X_train, X_test = X.iloc[:split_idx], X.iloc[split_idx:]
        y_train, y_test = y[:split_idx], y[split_idx:]

        X_train_scaled = self.scaler.fit_transform(X_train)
        X_test_scaled = self.scaler.transform(X_test)

        # Train XGBoost (fallback to GradientBoosting if needed)
        try:
            import xgboost as xgb
            self.xgb_model = xgb.XGBRegressor(
                n_estimators=180,
                max_depth=6,
                learning_rate=0.06,
                subsample=0.85,
                colsample_bytree=0.85,
                random_state=42,
                objective='reg:squarederror'
            )
            self.xgb_model.fit(X_train_scaled, y_train)
        except Exception:
            self.xgb_model = GradientBoostingRegressor(
                n_estimators=180, max_depth=6, learning_rate=0.06, random_state=42
            )
            self.xgb_model.fit(X_train_scaled, y_train)

        # Train Random Forest
        self.rf_model = RandomForestRegressor(
            n_estimators=120,
            max_depth=10,
            min_samples_split=4,
            random_state=42,
            n_jobs=-1
        )
        self.rf_model.fit(X_train_scaled, y_train)

        # Train Gradient Boosting
        self.gb_model = GradientBoostingRegressor(
            n_estimators=120,
            max_depth=5,
            learning_rate=0.06,
            random_state=42
        )
        self.gb_model.fit(X_train_scaled, y_train)

        self.is_trained = True

        preds_xgb = self.xgb_model.predict(X_test_scaled)
        preds_rf = self.rf_model.predict(X_test_scaled)
        preds_gb = self.gb_model.predict(X_test_scaled)

        preds_ensemble = (self.weights['xgb'] * preds_xgb +
                          self.weights['rf'] * preds_rf +
                          self.weights['gb'] * preds_gb)

        metrics = self._calculate_metrics(y_test, preds_ensemble, preds_xgb, preds_rf, preds_gb)
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

    def predict_with_uncertainty(self, features_df: pd.DataFrame) -> Tuple[np.ndarray, Tuple[np.ndarray, np.ndarray]]:
        """Prediction with 95% confidence intervals from ensemble model disagreement"""
        X = features_df[self.feature_columns]
        X_scaled = self.scaler.transform(X)

        preds_xgb = self.xgb_model.predict(X_scaled)
        preds_rf = self.rf_model.predict(X_scaled)
        preds_gb = self.gb_model.predict(X_scaled)

        ensemble = (self.weights['xgb'] * preds_xgb +
                    self.weights['rf'] * preds_rf +
                    self.weights['gb'] * preds_gb)

        std = np.std([preds_xgb, preds_rf, preds_gb], axis=0)
        ci_lower = ensemble - 1.96 * std
        ci_upper = ensemble + 1.96 * std

        return ensemble, (ci_lower, ci_upper)

    def _calculate_metrics(self, y_true, y_ensemble, y_xgb, y_rf, y_gb) -> Dict:
        """Calculate comprehensive model performance metrics"""
        def calc_metrics(y_pred):
            return {
                'mae': float(mean_absolute_error(y_true, y_pred)),
                'rmse': float(np.sqrt(mean_squared_error(y_true, y_pred))),
                'r2': float(r2_score(y_true, y_pred)),
                'mape': float(mean_absolute_percentage_error(y_true, y_pred) * 100),
                'max_error': float(np.max(np.abs(y_true - y_pred)))
            }

        return {
            'ensemble': calc_metrics(y_ensemble),
            'xgboost': calc_metrics(y_xgb),
            'random_forest': calc_metrics(y_rf),
            'gradient_boosting': calc_metrics(y_gb),
            'sample_size': len(y_true),
            'test_period_hours': len(y_true)
        }

    def get_feature_importance(self, top_n: int = 10) -> List[Dict]:
        """Get top N most important features"""
        if self.feature_importances is None or self.feature_columns is None:
            return []

        importance_df = pd.DataFrame({
            'feature': self.feature_columns,
            'importance': self.feature_importances
        }).sort_values('importance', ascending=False)

        return importance_df.head(top_n).to_dict('records')

    def save_models(self, path: str, filename: str = 'forecaster.pkl'):
        """Save trained models to disk"""
        os.makedirs(path, exist_ok=True)
        model_data = {
            'xgb_model': self.xgb_model,
            'rf_model': self.rf_model,
            'gb_model': self.gb_model,
            'scaler': self.scaler,
            'feature_columns': self.feature_columns,
            'weights': self.weights,
            'is_trained': self.is_trained,
            'feature_importances': self.feature_importances
        }
        with open(os.path.join(path, filename), 'wb') as f:
            pickle.dump(model_data, f)

    def load_models(self, path: str, filename: str = 'forecaster.pkl'):
        """Load trained models from disk"""
        target = os.path.join(path, filename) if not os.path.isfile(path) else path
        with open(target, 'rb') as f:
            model_data = pickle.load(f)

        self.xgb_model = model_data['xgb_model']
        self.rf_model = model_data['rf_model']
        self.gb_model = model_data['gb_model']
        self.scaler = model_data['scaler']
        self.feature_columns = model_data['feature_columns']
        self.weights = model_data['weights']
        self.is_trained = model_data['is_trained']
        self.feature_importances = model_data.get('feature_importances')


class RenewableForecaster:
    """Specialized forecaster for solar PV and katabatic wind generation"""

    def __init__(self):
        self.solar_model = None
        self.wind_model = None
        self.solar_scaler = StandardScaler()
        self.wind_scaler = StandardScaler()
        self.is_trained = False
        self.solar_features = None
        self.wind_features = None

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

        # Train solar model
        self.solar_scaler = StandardScaler()
        self.solar_model = GradientBoostingRegressor(
            n_estimators=100, max_depth=5, learning_rate=0.08, random_state=42
        )
        X_solar_scaled = self.solar_scaler.fit_transform(X_solar)
        self.solar_model.fit(X_solar_scaled, y_solar)

        # Train wind model
        self.wind_scaler = StandardScaler()
        self.wind_model = GradientBoostingRegressor(
            n_estimators=100, max_depth=5, learning_rate=0.08, random_state=42
        )
        X_wind_scaled = self.wind_scaler.fit_transform(X_wind)
        self.wind_model.fit(X_wind_scaled, y_wind)

        self.is_trained = True
        self.solar_features = available_solar
        self.wind_features = available_wind

    def predict_solar(self, features_df: pd.DataFrame) -> np.ndarray:
        X = features_df[self.solar_features].values
        return np.maximum(0.0, self.solar_model.predict(self.solar_scaler.transform(X)))

    def predict_wind(self, features_df: pd.DataFrame) -> np.ndarray:
        X = features_df[self.wind_features].values
        return np.maximum(0.0, self.wind_model.predict(self.wind_scaler.transform(X)))

    def save_models(self, path: str, filename: str = 'renewable.pkl'):
        os.makedirs(path, exist_ok=True)
        data = {
            'solar_model': self.solar_model,
            'wind_model': self.wind_model,
            'solar_scaler': self.solar_scaler,
            'wind_scaler': self.wind_scaler,
            'solar_features': self.solar_features,
            'wind_features': self.wind_features,
            'is_trained': self.is_trained
        }
        with open(os.path.join(path, filename), 'wb') as f:
            pickle.dump(data, f)

    def load_models(self, path: str, filename: str = 'renewable.pkl'):
        target = os.path.join(path, filename) if not os.path.isfile(path) else path
        with open(target, 'rb') as f:
            data = pickle.load(f)
        self.solar_model = data['solar_model']
        self.wind_model = data['wind_model']
        self.solar_scaler = data['solar_scaler']
        self.wind_scaler = data['wind_scaler']
        self.solar_features = data['solar_features']
        self.wind_features = data['wind_features']
        self.is_trained = data['is_trained']


class BlizzardRiskClassifier:
    """
    ML Classifier for 12-24h Early Blizzard & Katabatic Storm Warning.
    Detects severe incoming storms using barometric pressure drop rate and wind acceleration.
    """

    def __init__(self):
        self.model = None
        self.scaler = StandardScaler()
        self.features = [
            'temperature', 'wind_speed', 'pressure', 'pressure_drop_3h',
            'wind_chill', 'heating_degree_hours', 'hour', 'month'
        ]
        self.is_trained = False

    def train(self, df: pd.DataFrame, target_col: str = 'blizzard_warning_12h', test_size: float = 0.2) -> Dict:
        available = [c for c in self.features if c in df.columns]
        self.features = available
        X = df[available].copy()
        y = df[target_col].values

        split = int(len(X) * (1 - test_size))
        X_train, X_test = X.iloc[:split], X.iloc[split:]
        y_train, y_test = y[:split], y[split:]

        X_train_s = self.scaler.fit_transform(X_train)
        X_test_s = self.scaler.transform(X_test)

        self.model = RandomForestClassifier(
            n_estimators=100,
            max_depth=8,
            class_weight='balanced',
            random_state=42,
            n_jobs=-1
        )
        self.model.fit(X_train_s, y_train)
        self.is_trained = True

        preds = self.model.predict(X_test_s)
        acc = accuracy_score(y_test, preds)
        prec = precision_score(y_test, preds, zero_division=0)
        rec = recall_score(y_test, preds, zero_division=0)
        f1 = f1_score(y_test, preds, zero_division=0)

        return {
            'accuracy': float(acc),
            'precision': float(prec),
            'recall': float(rec),
            'f1': float(f1)
        }

    def predict_risk_probability(self, df: pd.DataFrame) -> np.ndarray:
        if not self.is_trained:
            return np.zeros(len(df))
        X = df[self.features].copy()
        Xs = self.scaler.transform(X)
        probs = self.model.predict_proba(Xs)
        # return probability of positive class (blizzard)
        return probs[:, 1] if probs.shape[1] > 1 else np.zeros(len(df))

    def save_models(self, path: str, filename: str = 'blizzard.pkl'):
        os.makedirs(path, exist_ok=True)
        data = {
            'model': self.model,
            'scaler': self.scaler,
            'features': self.features,
            'is_trained': self.is_trained
        }
        with open(os.path.join(path, filename), 'wb') as f:
            pickle.dump(data, f)

    def load_models(self, path: str, filename: str = 'blizzard.pkl'):
        target = os.path.join(path, filename) if not os.path.isfile(path) else path
        with open(target, 'rb') as f:
            data = pickle.load(f)
        self.model = data['model']
        self.scaler = data['scaler']
        self.features = data['features']
        self.is_trained = data['is_trained']


class StationModelRegistry:
    """
    Manages dedicated ML models for each polar research station:
    - Bharati (Antarctica)
    - Maitri (Antarctica)
    - Himadri (Arctic)
    """

    def __init__(self, models_dir: str = "models"):
        self.models_dir = models_dir
        self.registry = {}
        self.load_all_stations()

    def get_slug(self, station_name: str) -> str:
        s = station_name.lower()
        if "bharati" in s:
            return "bharati"
        elif "maitri" in s:
            return "maitri"
        elif "himadri" in s:
            return "himadri"
        return "maitri"

    def load_all_stations(self):
        for slug in ["bharati", "maitri", "himadri"]:
            station_dir = os.path.join(self.models_dir, slug)
            if not os.path.exists(station_dir):
                continue

            try:
                forecaster = PolarLoadForecaster()
                f_path = os.path.join(station_dir, "forecaster.pkl")
                if os.path.exists(f_path):
                    forecaster.load_models(f_path)

                renewable = RenewableForecaster()
                r_path = os.path.join(station_dir, "renewable.pkl")
                if os.path.exists(r_path):
                    renewable.load_models(r_path)

                blizzard = BlizzardRiskClassifier()
                b_path = os.path.join(station_dir, "blizzard.pkl")
                if os.path.exists(b_path):
                    blizzard.load_models(b_path)

                metrics = {}
                m_path = os.path.join(station_dir, "metrics.pkl")
                if os.path.exists(m_path):
                    with open(m_path, "rb") as f:
                        metrics = pickle.load(f)

                self.registry[slug] = {
                    'forecaster': forecaster,
                    'renewable': renewable,
                    'blizzard': blizzard,
                    'metrics': metrics
                }
            except Exception as e:
                print(f"[WARN] Error loading models for {slug}: {e}")

    def get_bundle(self, station_name: str) -> Dict:
        slug = self.get_slug(station_name)
        if slug in self.registry:
            return self.registry[slug]
        # fallback to any available station
        if len(self.registry) > 0:
            return next(iter(self.registry.values()))
        return {
            'forecaster': PolarLoadForecaster(),
            'renewable': RenewableForecaster(),
            'blizzard': BlizzardRiskClassifier(),
            'metrics': {}
        }
