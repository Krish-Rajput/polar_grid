"""
PolarGrid AI - Multi-Station ML Training Engine
Trains dedicated machine learning models for:
- Bharati Station (Antarctica - IIG Observational Data)
- Maitri Station (Antarctica - IMD Observational Data)
- Himadri Station (Arctic - ERA5 Observational Reanalysis)
"""
import os
import sys

# Ensure UTF-8 output on Windows consoles
if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

import pickle
import numpy as np
import pandas as pd
from typing import Dict

# Add backend directory to sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ml_models import PolarLoadForecaster, RenewableForecaster, BlizzardRiskClassifier, engineer_polar_features

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROCESSED_DIR = os.path.join(PROJECT_ROOT, "data", "processed")
MODELS_DIR = os.path.join(PROJECT_ROOT, "models")
STATIONS = [
    {
        "name": "Bharati (Antarctica)",
        "slug": "bharati",
        "csv": "bharati_processed.csv",  # Changed from iig_bhariti.csv
        "recent_hours": 17520 
    },
    {
        "name": "Maitri (Antarctica)",
        "slug": "maitri",
        "csv": "maitri_processed.csv",   # Changed from imd_maitri.csv
        "recent_hours": 17520 
    }
]


def train_station(station_info: Dict) -> Dict:
    name = station_info["name"]
    slug = station_info["slug"]
    csv_file = os.path.join(PROCESSED_DIR, station_info["csv"])
    station_model_dir = os.path.join(MODELS_DIR, slug)
    os.makedirs(station_model_dir, exist_ok=True)
    
    print("\n" + "=" * 65)
    print(f"[*] Training Dedicated Models for: {name}")
    print(f"    Source Data: {csv_file}")
    print(f"    Target Directory: {station_model_dir}")
    print("=" * 65)
    
    # Load processed data
    df = pd.read_csv(csv_file)
    if 'timestamp' in df.columns:
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        df.set_index('timestamp', inplace=True)
    elif 'Unnamed: 0' in df.columns:
        df['timestamp'] = pd.to_datetime(df['Unnamed: 0'])
        df.set_index('timestamp', inplace=True)
        df.drop(columns=['Unnamed: 0'], inplace=True, errors='ignore')
    elif 'obstime' in df.columns:
        df['timestamp'] = pd.to_datetime(df['obstime'])
        df.set_index('timestamp', inplace=True)
    
    # Use recent contiguous hours for optimal seasonal training
    if len(df) > station_info["recent_hours"]:
        df = df.tail(station_info["recent_hours"])
    print(f"  Training dataset: {len(df)} hourly records ({len(df)/24:.1f} days)")
    
    # Engineer Polar Features
    features_df = engineer_polar_features(df)
    print(f"  Engineered features shape: {features_df.shape}")
    
    # 1. Train PolarLoadForecaster
    print("\n  [1/3] Training PolarLoadForecaster (Ensemble XGBoost + RF + GB)...")
    forecaster = PolarLoadForecaster()
    load_metrics = forecaster.train(features_df, target_col='total_demand_kw', test_size=0.2)
    forecaster.save_models(station_model_dir, filename="forecaster.pkl")
    
    ens_r2 = load_metrics['ensemble']['r2']
    ens_mae = load_metrics['ensemble']['mae']
    ens_mape = load_metrics['ensemble']['mape']
    print(f"        Ensemble Test Metrics -> R2: {ens_r2:.4f} | MAE: {ens_mae:.2f} kW | MAPE: {ens_mape:.2f}%")
    for model_key in ['xgboost', 'random_forest', 'gradient_boosting']:
        m = load_metrics[model_key]
        print(f"        - {model_key.upper()}: R2 = {m['r2']:.4f}, MAE = {m['mae']:.2f} kW")
    
    # 2. Train RenewableForecaster
    print("\n  [2/3] Training RenewableForecaster (Solar PV + Katabatic Wind)...")
    renewable_fc = RenewableForecaster()
    renewable_fc.train(features_df)
    renewable_fc.save_models(station_model_dir, filename="renewable.pkl")
    print("        Renewable models (Solar & Wind) trained and saved.")
    
    # 3. Train BlizzardRiskClassifier
    print("\n  [3/3] Training BlizzardRiskClassifier (12-24h Early Warning System)...")
    blizzard_clf = BlizzardRiskClassifier()
    clf_metrics = blizzard_clf.train(features_df, target_col='blizzard_warning_12h', test_size=0.2)
    blizzard_clf.save_models(station_model_dir, filename="blizzard.pkl")
    print(f"        Blizzard Classifier Test Accuracy: {clf_metrics['accuracy']*100:.2f}% | Precision: {clf_metrics['precision']:.3f} | Recall: {clf_metrics['recall']:.3f}")
    
    summary = {
        'station_name': name,
        'slug': slug,
        'training_hours': len(features_df),
        'load_metrics': load_metrics,
        'blizzard_metrics': clf_metrics,
        'top_features': forecaster.get_feature_importance(10)
    }
    with open(os.path.join(station_model_dir, "metrics.pkl"), "wb") as f:
        pickle.dump(summary, f)
        
    return summary


def train_all():
    print("[*] PolarGrid AI - Starting Comprehensive Model Training for All Stations...")
    results = {}
    for st in STATIONS:
        results[st["name"]] = train_station(st)
        
    # Save a default root forecaster.pkl in models/ for backwards compatibility
    root_forecaster_src = os.path.join(MODELS_DIR, "maitri", "forecaster.pkl")
    root_forecaster_dst = os.path.join(MODELS_DIR, "forecaster.pkl")
    if os.path.exists(root_forecaster_src):
        import shutil
        shutil.copy2(root_forecaster_src, root_forecaster_dst)
        
    print("\n" + "=" * 65)
    print("[SUCCESS] All dedicated models successfully trained and persisted!")
    print("=" * 65)
    for name, res in results.items():
        lm = res['load_metrics']['ensemble']
        bm = res['blizzard_metrics']
        print(f"\n>> {name}:")
        print(f"   * Load Demand Forecast:  R2 = {lm['r2']:.4f} | MAE = {lm['mae']:.2f} kW | MAPE = {lm['mape']:.2f}%")
        print(f"   * Blizzard Early Warning: Accuracy = {bm['accuracy']*100:.1f}% | Recall = {bm['recall']*100:.1f}%")
        print("   * Top 3 Drivers: " + ", ".join([f"{feat['feature']} ({feat['importance']:.3f})" for feat in res['top_features'][:3]]))


if __name__ == "__main__":
    train_all()
