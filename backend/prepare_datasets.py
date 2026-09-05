import os
import numpy as np
import pandas as pd

def process_datasets():
    print("[*] Processing Raw IMD/IIG Datasets into Hybrid ML-Ready Datasets...")
    
    # Point directly to the processed folder where your files currently are
    processed_dir = os.path.join(os.path.dirname(__file__), "..", "data", "processed")
    os.makedirs(processed_dir, exist_ok=True)

    # ==========================================
    # 1. PROCESS BHARATI (IIG Data)
    # ==========================================
    bharati_path = os.path.join(processed_dir, "iig_bhariti.csv")
    if os.path.exists(bharati_path):
        print(" -> Processing Bharati...")
        df_b = pd.read_csv(bharati_path)
        
        df_b.rename(columns={
            'obstime': 'timestamp',
            'tempr': 'temperature',
            'ap': 'pressure',
            'ws': 'wind_speed'
        }, inplace=True)
        
        df_b = generate_energy_features(df_b, base_load=120, max_solar=120, max_wind=60)
        df_b.to_csv(os.path.join(processed_dir, "bharati_processed.csv"), index=False)
        print("    [SUCCESS] Saved bharati_processed.csv")
    else:
        print(f"    [ERROR] Could not find {bharati_path}")

    # ==========================================
    # 2. PROCESS MAITRI (IMD Data)
    # ==========================================
    maitri_path = os.path.join(processed_dir, "imd_maitri.csv")
    if os.path.exists(maitri_path):
        print(" -> Processing Maitri...")
        df_m = pd.read_csv(maitri_path, header=None, names=['timestamp', 'temperature', 'pressure', 'wind_speed', 'wd', 'rh'])
        
        df_m.replace(-999.0, np.nan, inplace=True)
        df_m['temperature'] = df_m['temperature'].ffill()
        df_m['wind_speed'] = df_m['wind_speed'].ffill()
        df_m['pressure'] = df_m['pressure'].ffill()
        
        df_m = generate_energy_features(df_m, base_load=150, max_solar=80, max_wind=40)
        df_m.to_csv(os.path.join(processed_dir, "maitri_processed.csv"), index=False)
        print("    [SUCCESS] Saved maitri_processed.csv")
    else:
        print(f"    [ERROR] Could not find {maitri_path}")

def generate_energy_features(df: pd.DataFrame, base_load: float, max_solar: float, max_wind: float) -> pd.DataFrame:
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    
    hour = df['timestamp'].dt.hour
    doy = df['timestamp'].dt.dayofyear
    
    polar_summer = np.where((doy < 80) | (doy > 280), 1.0, 0.0)
    daily_curve = np.maximum(0, np.sin(np.pi * (hour - 6) / 12))
    df['solar_irradiance'] = polar_summer * daily_curve * 1000.0
    
    df['solar_generation_kw'] = (df['solar_irradiance'] / 1000.0) * max_solar
    
    wind_power = np.where(df['wind_speed'] > 25, 0, 
                 np.where(df['wind_speed'] < 3, 0,
                 max_wind * np.minimum(1.0, (df['wind_speed']/12.0)**3)))
    df['wind_generation_kw'] = wind_power

    heating_factor = np.maximum(0, 18.0 - df['temperature']) * 3.5
    df['total_demand_kw'] = base_load + heating_factor + np.random.normal(0, 5, len(df))
    
    # Generate the target column required for the Blizzard Classifier
    df['blizzard_warning_12h'] = (df['wind_speed'].shift(-12) > 20).astype(int)
    
    # Fill any NaNs created by shifting using Pandas 2.0+ compliant methods
    df.ffill(inplace=True)
    df.bfill(inplace=True)
    
    return df

if __name__ == "__main__":
    process_datasets()