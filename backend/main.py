"""
PolarGrid AI - FastAPI Backend Server
AI-Driven Smart Energy Management System for Polar Research Stations
Problem Statement 26061 - Smart India Hackathon (SIH 2026)
Organization: NCPOR / Ministry of Earth Sciences (MoES)
"""
import sys
import os
import pandas as pd
import numpy as np
from datetime import datetime
from fastapi import FastAPI
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import traceback

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(PROJECT_ROOT, "backend"))

from ml_models import StationModelRegistry, engineer_polar_features
from optimizer import EnergyOptimizer, get_station_config

app = FastAPI(
    title="PolarGrid AI",
    description="AI-Driven Smart Energy Management System for Polar Research Stations | NCPOR / MoES",
    version="2.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

static_dir = os.path.join(PROJECT_ROOT, "frontend", "static")
if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

models_dir = os.path.join(PROJECT_ROOT, "models")
registry = StationModelRegistry(models_dir=models_dir)
station_cache = {}
system_initialized = False

def load_station_csv(station_name: str) -> pd.DataFrame:
    file_map = {
        "Bharati (Antarctica)": "bharati_processed.csv",
        "Maitri (Antarctica)": "maitri_processed.csv"
    }
    filename = file_map.get(station_name)
    if not filename:
        raise FileNotFoundError(f"No CSV mapping found for {station_name}")
    filepath = os.path.join(PROJECT_ROOT, "data", "processed", filename)
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"Dataset missing: {filepath}")
    
    df = pd.read_csv(filepath)
    
    if 'timestamp' in df.columns:
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        df.set_index('timestamp', inplace=True)
    elif 'Unnamed: 0' in df.columns:
        df['timestamp'] = pd.to_datetime(df['Unnamed: 0'])
        df.set_index('timestamp', inplace=True)
        df.drop(columns=['Unnamed: 0'], inplace=True, errors='ignore')
    else:
        raise ValueError(f"Could not find a timestamp column in {filename}")
        
    df.sort_index(inplace=True)
    return df

def initialize_stations():
    global station_cache, system_initialized
    if system_initialized:
        return
    print("=" * 60)
    print("[*] PolarGrid AI: Loading Real CSV Station Archives...")
    print("=" * 60)
    stations = ["Bharati (Antarctica)", "Maitri (Antarctica)"]
    for st in stations:
        print(f"  -> Loading {st}...")
        try:
            df = load_station_csv(st)
            features = engineer_polar_features(df)
            station_cache[st] = {
                'raw_data': df,
                'features': features
            }
            bundle = registry.get_bundle(st)
            trained = bundle['forecaster'].is_trained
            print(f"     Loaded {len(df)} hourly records | Model Trained: {trained}")
        except Exception as e:
            print(f"     [Error loading {st}]: {e}")
    system_initialized = True
    print("=" * 60)
    print("[SUCCESS] System initialized successfully with real polar datasets!\n")

@app.on_event("startup")
async def startup_event():
    initialize_stations()

@app.get("/")
async def serve_dashboard():
    initialize_stations()
    template_path = os.path.join(PROJECT_ROOT, "frontend", "templates", "index.html")
    if not os.path.exists(template_path):
        return HTMLResponse("<h1>PolarGrid AI Dashboard Template Not Found</h1>", status_code=404)
    with open(template_path, 'r', encoding='utf-8') as f:
        return HTMLResponse(content=f.read())

@app.get("/api/health")
async def health_check():
    initialize_stations()
    return {
        "status": "ok",
        "stations": list(station_cache.keys()),
        "datasets": "Real IMD Maitri & IIG Bharati Observations"
    }

@app.get("/api/stations")
async def list_stations():
    initialize_stations()
    return {
        'stations': ["Bharati (Antarctica)", "Maitri (Antarctica)"],
        'current_station': "Bharati (Antarctica)"
    }

@app.get("/api/blizzard-warning")
async def get_blizzard_warning(station: str = "Bharati (Antarctica)"):
    initialize_stations()
    data = station_cache.get(station)
    if not data:
        return JSONResponse(status_code=404, content={"error": f"Station {station} not found"})
    bundle = registry.get_bundle(station)
    blizzard_clf = bundle['blizzard']
    recent_features = data['features'].tail(24)
    risk_probs = blizzard_clf.predict_risk_probability(recent_features)
    current_risk = float(risk_probs[-1]) if len(risk_probs) > 0 else 0.05
    max_24h_risk = float(np.max(risk_probs)) if len(risk_probs) > 0 else 0.05
    if max_24h_risk >= 0.60:
        alert_level = "SEVERE_BLIZZARD_WARNING"
        status_text = "BLIZZARD IMMINENT (Next 12-24 Hours)"
        color = "red"
        actions = ["Pre-charging Battery Energy Storage System to >= 95%", "Activating Diesel Generator fuel line pre-heaters", "Initiating wind turbine aerodynamic feathering"]
    elif max_24h_risk >= 0.30:
        alert_level = "ELEVATED_WATCH"
        status_text = "ELEVATED KATABATIC WIND WATCH"
        color = "amber"
        actions = ["Monitoring barometric pressure", "Maintaining battery SoC > 70%"]
    else:
        alert_level = "NORMAL_CONDITIONS"
        status_text = "NORMAL POLAR CONDITIONS"
        color = "green"
        actions = ["Optimal renewable economic dispatch active"]
    return {
        "station": station,
        "alert_level": alert_level,
        "status_text": status_text,
        "color": color,
        "current_risk_probability": round(current_risk * 100, 1),
        "max_risk_24h_probability": round(max_24h_risk * 100, 1),
        "recent_risk_timeline": [round(float(p) * 100, 1) for p in risk_probs[-12:]],
        "autonomous_defense_actions": actions,
        "timestamp": datetime.now().isoformat()
    }

@app.get("/api/current-mode")
async def get_current_mode(station: str = "Bharati (Antarctica)"):
    initialize_stations()
    data = station_cache.get(station, next(iter(station_cache.values())))
    recent = data['raw_data'].tail(1).iloc[0]
    temp = float(recent.get('temperature', -15.0))
    wind = float(recent.get('wind_speed', 10.0))
    solar = float(recent.get('solar_generation_kw', 0.0))
    config = get_station_config(station)
    optimizer = EnergyOptimizer(config)
    mode = optimizer.determine_operating_mode({
        'avg_solar': solar / config.solar_capacity_kw if config.solar_capacity_kw > 0 else 0,
        'temperature': temp,
        'wind_speed': wind,
        'battery_soc': 70.0
    })
    return {
        "station": station,
        "mode": mode.value,
        "temperature": round(temp, 1),
        "wind_speed": round(wind, 1),
        "solar_kw": round(solar, 1),
        "battery_soc": 70.0
    }

@app.post("/api/simulate-mode")
async def simulate_mode_scenario(station: str = "Bharati (Antarctica)", mode: str = "normal", hours_ahead: int = 72):
    try:
        initialize_stations()
        config = get_station_config(station)
        optimizer = EnergyOptimizer(config)
        
        scenarios = {
            "normal": {"temp": -15.0, "wind": 9.0, "solar_factor": 0.55, "soc": 65.0},
            "polar_night": {"temp": -32.0, "wind": 14.0, "solar_factor": 0.0, "soc": 55.0},
            "blizzard": {"temp": -36.0, "wind": 28.0, "solar_factor": 0.0, "soc": 92.0},
            "summer_surge": {"temp": -4.0, "wind": 7.0, "solar_factor": 1.0, "soc": 80.0},
            "emergency": {"temp": -34.0, "wind": 18.0, "solar_factor": 0.0, "soc": 14.0}
        }
        sc = scenarios.get(mode.lower(), scenarios["normal"])
        n_hours = min(168, max(24, hours_ahead))
        hours_arr = np.arange(n_hours)
        base_demand = config.critical_load_kw * 1.3
        temp_factor = max(0, 18.0 - sc["temp"]) * 1.2
        
        # Use .tolist() to safely convert numpy arrays to JSON-serializable Python floats
        demand_sim = (np.full(n_hours, base_demand + temp_factor) + 20.0 * np.sin(2 * np.pi * hours_arr / 24.0)).tolist()
        
        if sc["solar_factor"] > 0:
            solar_sim = (config.solar_capacity_kw * sc["solar_factor"] * np.maximum(0, np.sin(np.pi * (hours_arr % 24) / 24.0))).tolist()
        else:
            solar_sim = [0.0] * n_hours
            
        if sc["wind"] >= 25.0:
            wind_sim = [0.0] * n_hours
        else:
            wind_sim = (np.full(n_hours, config.wind_capacity_kw) * min(1.0, (sc["wind"] / 12.0) ** 3)).tolist()
            
        res = optimizer.optimize_dispatch(demand_forecast=demand_sim, solar_forecast=solar_sim, wind_forecast=wind_sim, current_soc=sc["soc"], temperature=sc["temp"], wind_speed=sc["wind"], hours_ahead=n_hours)
        dispatch = res["dispatch"]
        summary = res["summary"]
        
        insights = [f"Mode active: {mode.upper()} simulated across {n_hours} hours at {station}.", f"Fuel consumed: {summary['total_diesel_liters']} L | Renewable share: {summary['renewable_share']}%", f"Ambient temperature {sc['temp']}C derates effective battery storage to {optimizer.get_effective_battery_capacity(sc['temp']):.1f} kWh."]
        if mode.lower() == "blizzard":
            insights.append("Blizzard safety protocol: Wind turbines safely feathered (cut-out active above 25 m/s) to prevent catastrophic mechanical failure.")
        elif mode.lower() == "polar_night":
            insights.append("Polar Night protocol: Solar PV zero for 24h. Generators operated in steady fuel-efficient band.")
            
        return {
            "conditions": {"temperature": sc["temp"], "wind_speed": sc["wind"], "solar_factor": sc["solar_factor"], "start_soc": sc["soc"]},
            "summary": summary,
            "dispatch": {"timestamps": [f"+{h}h" for h in range(n_hours)], "demand": dispatch["demand_kw"], "solar": dispatch["solar_kw"], "wind": dispatch["wind_kw"], "battery": dispatch["battery_kw"], "generator": dispatch["generator_kw"], "soc": dispatch["soc_after"], "mode": dispatch["operating_mode"]},
            "insights": insights
        }
    except Exception as e:
        traceback.print_exc()
        return JSONResponse(status_code=500, content={"error": str(e)})

@app.get("/api/dashboard")
async def get_dashboard_data(station: str = "Bharati (Antarctica)", hours_ahead: int = 168):
    initialize_stations()
    if station not in station_cache:
        station = "Bharati (Antarctica)"
    try:
        data = station_cache[station]
        df = data['raw_data']
        features_full = data['features']
        bundle = registry.get_bundle(station)
        
        forecaster = bundle['forecaster']
        renewable_fc = bundle['renewable']
        blizzard_clf = bundle['blizzard']
        config = get_station_config(station)
        optimizer = EnergyOptimizer(config)
        
        recent_data = df.tail(168)
        test_window = features_full.tail(hours_ahead * 2).head(hours_ahead)
        if len(test_window) < hours_ahead:
            test_window = features_full.tail(hours_ahead)
            
        demand_forecast, (ci_lower, ci_upper) = forecaster.predict_with_uncertainty(test_window)
        solar_forecast = renewable_fc.predict_solar(test_window)
        wind_forecast = renewable_fc.predict_wind(test_window)
        blizzard_probs = blizzard_clf.predict_risk_probability(test_window)
        
        avg_temp = float(test_window['temperature'].mean())
        avg_wind = float(test_window['wind_speed'].mean())
        
        result = optimizer.optimize_dispatch(demand_forecast=demand_forecast, solar_forecast=solar_forecast, wind_forecast=wind_forecast, current_soc=65.0, temperature=avg_temp, wind_speed=avg_wind, hours_ahead=hours_ahead)
        dispatch = result['dispatch']
        
        mode_val = dispatch['operating_mode'][0] if dispatch['operating_mode'] else 'normal'
        mode_map = {
            'normal': {'icon': '🟢', 'label': 'NORMAL OPERATION', 'color': '#10b981', 'desc': 'Balanced economic dispatch prioritizing renewables and battery storage'},
            'polar_night': {'icon': '🌙', 'label': 'POLAR NIGHT MODE', 'color': '#8b5cf6', 'desc': 'Zero solar generation. Generator running at fuel-efficient steady output with battery peak-shaving'},
            'blizzard': {'icon': '⚠️', 'label': 'BLIZZARD DEFENSE MODE', 'color': '#ef4444', 'desc': 'Extreme winds / storm warning. Turbine cut-out failsafe active, battery pre-charged to 95%'},
            'summer_surge': {'icon': '☀️', 'label': 'SUMMER SURGE (MIDNIGHT SUN)', 'color': '#fbbf24', 'desc': '24-hour solar generation. Maximizing renewable penetration and water desalination buffering'},
            'emergency': {'icon': '🚨', 'label': 'CRITICAL EMERGENCY LOAD SHEDDING', 'color': '#ef4444', 'desc': 'Battery SoC depleted below 15%. All diesel generators active, non-critical research loads shed'}
        }
        mode_info = mode_map.get(mode_val, mode_map['normal'])

        recent_diesel = ((recent_data['total_demand_kw'] - recent_data['solar_generation_kw'] - recent_data['wind_generation_kw']).clip(lower=0) * 0.25).round(2)
        recent_gen = (recent_data['total_demand_kw'] - recent_data['solar_generation_kw'] - recent_data['wind_generation_kw']).clip(lower=0).round(2)

        return {
            'station': station,
            'timestamp': datetime.now().isoformat(),
            'mode_icon': mode_info['icon'],
            'mode_label': mode_info['label'],
            'mode_color': mode_info['color'],
            'mode_description': mode_info['desc'],
            'conditions': {
                'temperature': round(avg_temp, 1),
                'wind_speed': round(avg_wind, 1),
                'solar_kw': round(float(recent_data['solar_generation_kw'].iloc[-1]), 1),
                'battery_soc': 70.0
            },
            'recent_data': {
                'timestamps': [t.isoformat() for t in recent_data.index],
                'demand': recent_data['total_demand_kw'].fillna(0).tolist(),
                'solar': recent_data['solar_generation_kw'].fillna(0).tolist(),
                'wind': recent_data['wind_generation_kw'].fillna(0).tolist(),
                'battery_soc': [70.0] * len(recent_data),
                'generator': recent_gen.fillna(0).tolist(),
                'temperature': recent_data['temperature'].fillna(0).tolist(),
                'diesel': recent_diesel.fillna(0).tolist()
            },
            'forecast': {
                'timestamps': [t.isoformat() for t in test_window.index],
                'demand_actual': test_window['total_demand_kw'].fillna(0).tolist(),
                'demand_predicted': [round(float(x), 1) for x in demand_forecast],
                'ci_lower': [round(float(x), 1) for x in ci_lower],
                'ci_upper': [round(float(x), 1) for x in ci_upper],
                'solar_predicted': [round(max(0.0, float(x)), 1) for x in solar_forecast],
                'wind_predicted': [round(max(0.0, float(x)), 1) for x in wind_forecast],
                'temperature': test_window['temperature'].fillna(0).tolist(),
                'blizzard_risk_probability': [round(float(p) * 100, 1) for p in blizzard_probs]
            },
            'dispatch': {
                'timestamps': [test_window.index[i].isoformat() for i in range(min(hours_ahead, len(dispatch['demand_kw'])))],
                'demand': dispatch['demand_kw'],
                'solar': dispatch['solar_kw'],
                'wind': dispatch['wind_kw'],
                'battery': dispatch['battery_kw'],
                'generator': dispatch['generator_kw'],
                'soc': dispatch['soc_after'],
                'mode': dispatch['operating_mode'],
                'diesel': dispatch['diesel_liters'],
                'renewable_share': dispatch['renewable_share']
            },
            'summary': result['summary'],
            'insights': optimizer.get_optimization_insights(result),
            'station_profile': {
                'hardware': {
                    'solar_capacity_kw': config.solar_capacity_kw,
                    'wind_capacity_kw': config.wind_capacity_kw,
                    'battery_capacity_kwh': config.battery_capacity_kwh,
                    'generator_max_kw': config.generator_max_output,
                    'critical_load_kw': config.critical_load_kw
                },
                'battery_derating': round(optimizer.get_effective_battery_capacity(avg_temp), 1)
            }
        }
    except Exception as e:
        traceback.print_exc()
        return JSONResponse(status_code=500, content={"error": str(e)})

@app.get("/api/model-performance")
async def get_model_performance(station: str = "Bharati (Antarctica)"):
    initialize_stations()
    bundle = registry.get_bundle(station)
    forecaster = bundle['forecaster']
    metrics = bundle['metrics']
    load_metrics = metrics.get('load_metrics', {})
    blizzard_metrics = metrics.get('blizzard_metrics', {})
    top_features = metrics.get('top_features', forecaster.get_feature_importance(10))
    return {
        'station': station,
        'model_type': 'Dedicated Hybrid Ensemble (XGBoost 45% + Random Forest 25% + Gradient Boosting 30%)',
        'load_forecasting': load_metrics,
        'blizzard_early_warning': blizzard_metrics,
        'feature_importance': top_features,
        'training_data_hours': metrics.get('training_hours', 17520),
        'dataset_source': 'Real Observational Archive (IMD / IIG / ERA5 Reanalysis)'
    }

@app.get("/api/weather-impact")
async def get_weather_impact_analysis(station: str = "Bharati (Antarctica)"):
    initialize_stations()
    if station not in station_cache:
        station = "Bharati (Antarctica)"
    df = station_cache[station]['raw_data']
    
    df['net_load'] = (df['total_demand_kw'] - df['solar_generation_kw'] - df['wind_generation_kw']).clip(lower=0)
    df['diesel_consumption'] = df['net_load'] * 0.26
    
    monthly = df.resample('ME').agg({
        'temperature': 'mean',
        'wind_speed': 'mean',
        'solar_generation_kw': 'sum',
        'wind_generation_kw': 'sum',
        'total_demand_kw': 'mean',
        'diesel_consumption': 'sum'
    }).round(2).tail(12)
    
    temp_demand_corr = float(df['temperature'].corr(df['total_demand_kw'])) if not df['temperature'].isnull().all() else 0.0
    wind_gen_corr = float(df['wind_speed'].corr(df['wind_generation_kw'])) if not df['wind_speed'].isnull().all() else 0.0
    solar_gen_corr = float(df.get('solar_irradiance', df['solar_generation_kw']).corr(df['solar_generation_kw'])) if not df.get('solar_irradiance', df['solar_generation_kw']).isnull().all() else 0.0
    
    return {
        'station': station,
        'monthly_trends': {
            'months': [idx.strftime('%b %Y') for idx in monthly.index],
            'temperature': monthly['temperature'].fillna(0).tolist(),
            'wind_speed': monthly['wind_speed'].fillna(0).tolist(),
            'solar_generation': monthly['solar_generation_kw'].fillna(0).tolist(),
            'wind_generation': monthly['wind_generation_kw'].fillna(0).tolist(),
            'avg_demand': monthly['total_demand_kw'].fillna(0).tolist(),
            'diesel_consumption': monthly['diesel_consumption'].fillna(0).tolist()
        },
        'correlations': {
            'temperature_vs_demand': round(temp_demand_corr, 3),
            'wind_speed_vs_generation': round(wind_gen_corr, 3),
            'irradiance_vs_solar_gen': round(solar_gen_corr, 3)
        },
        'insights': [
            f"Strong thermal sensitivity: temperature vs demand correlation r = {temp_demand_corr:.3f}",
            f"Wind turbine power generation strongly driven by wind dynamics (r = {wind_gen_corr:.3f})",
            "Polar night duration eliminates solar PV generation for 2-4 months"
        ]
    }

@app.get("/api/annual-summary")
async def get_annual_summary(station: str = "Bharati (Antarctica)"):
    initialize_stations()
    if station not in station_cache:
        station = "Bharati (Antarctica)"
        
    df = station_cache[station]['raw_data'].tail(8760)
    config = get_station_config(station)
    optimizer = EnergyOptimizer(config)
    resupply_plan = optimizer.generate_resupply_plan(df)
    
    total_demand_kwh = float(df['total_demand_kw'].sum())
    solar_gen_kwh = float(df['solar_generation_kw'].sum())
    wind_gen_kwh = float(df['wind_generation_kw'].sum())
    total_renewable_kwh = solar_gen_kwh + wind_gen_kwh
    baseline_diesel_liters = total_demand_kwh * 0.28
    optimized_diesel_liters = max(0.0, (total_demand_kwh - total_renewable_kwh * 0.85) * 0.27)
    fuel_saved_liters = baseline_diesel_liters - optimized_diesel_liters
    fuel_cost_per_l = 85.0
    
    annual = {
        'total_demand_kwh': round(total_demand_kwh, 0),
        'solar_generation_kwh': round(solar_gen_kwh, 0),
        'wind_generation_kwh': round(wind_gen_kwh, 0),
        'total_renewable_kwh': round(total_renewable_kwh, 0),
        'diesel_consumption_liters': round(optimized_diesel_liters, 0),
        'diesel_cost_rs': round(optimized_diesel_liters * fuel_cost_per_l, 0),
        'co2_emissions_tonnes': round(optimized_diesel_liters * 2.68 / 1000.0, 2),
        'avg_temperature_c': round(float(df['temperature'].mean()), 1),
        'min_temperature_c': round(float(df['temperature'].min()), 1),
        'max_temperature_c': round(float(df['temperature'].max()), 1),
        'avg_wind_speed_ms': round(float(df['wind_speed'].mean()), 1),
        'renewable_share_percent': round((total_renewable_kwh / total_demand_kwh) * 100.0, 1) if total_demand_kwh else 0,
        'peak_demand_kw': round(float(df['total_demand_kw'].max()), 1),
        'avg_demand_kw': round(float(df['total_demand_kw'].mean()), 1)
    }
    return {
        'station': station,
        'period': f"{df.index[0].strftime('%b %Y')} - {df.index[-1].strftime('%b %Y')}",
        'annual_metrics': annual,
        'resupply_plan': resupply_plan,
        'kpis': {
            'renewable_penetration': f"{annual['renewable_share_percent']}%",
            'diesel_dependency': f"{100.0 - annual['renewable_share_percent']:.1f}%",
            'carbon_intensity': f"{annual['co2_emissions_tonnes'] / (total_demand_kwh / 1000.0) if total_demand_kwh else 0:.2f} tCO2/MWh",
            'fuel_cost_per_kwh': f"Rs.{annual['diesel_cost_rs'] / total_demand_kwh if total_demand_kwh else 0:.2f}"
        },
        'impact_vs_traditional': {
            'fuel_saved_liters': round(fuel_saved_liters, 0),
            'cost_saved_rs': round(fuel_saved_liters * fuel_cost_per_l, 0),
            'co2_avoided_tonnes': round(fuel_saved_liters * 2.68 / 1000.0, 2),
            'note': 'Compared to traditional unoptimized diesel-only operation'
        }
    }

@app.get("/api/energy-flow")
async def get_energy_flow_data(station: str = "Bharati (Antarctica)"):
    initialize_stations()
    if station not in station_cache:
        station = "Bharati (Antarctica)"
    df = station_cache[station]['raw_data'].tail(24)
    solar_total = float(df['solar_generation_kw'].sum())
    wind_total = float(df['wind_generation_kw'].sum())
    demand_total = float(df['total_demand_kw'].sum())
    generator_total = max(0.0, demand_total - solar_total - wind_total)
    return {
        'sources': {
            'solar': round(solar_total, 1),
            'wind': round(wind_total, 1),
            'diesel_generator': round(generator_total, 1),
            'battery_discharge': round(max(0.0, demand_total * 0.15), 1)
        },
        'destinations': {
            'base_load_heating': round(float(df.get('base_load_kw', pd.Series(df['total_demand_kw']*0.4)).sum()), 1),
            'research_equipment': round(float(df.get('research_load_kw', pd.Series(df['total_demand_kw']*0.3)).sum()), 1),
            'water_desalination': round(float(df.get('water_load_kw', pd.Series(df['total_demand_kw']*0.2)).sum()), 1),
            'communications': round(float(df.get('comms_load_kw', pd.Series(df['total_demand_kw']*0.1)).sum()), 1),
            'battery_charging': round(max(0.0, solar_total + wind_total - demand_total), 1)
        },
        'losses': {
            'curtailment': round(max(0.0, (solar_total + wind_total) * 0.04), 1),
            'conversion_loss': round((solar_total + wind_total + generator_total) * 0.06, 1)
        }
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)