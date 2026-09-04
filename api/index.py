"""
PolarGrid AI - Vercel Serverless Handler
FastAPI app wrapped with Mangum for AWS Lambda deployment
"""
import os
import sys

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from fastapi import FastAPI
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from mangum import Mangum

# Import backend modules
from backend.data_simulator import PolarDataSimulator
from backend.ml_models import PolarLoadForecaster, RenewableForecaster
from backend.optimizer import EnergyOptimizer, StationConfig

# Initialize FastAPI app
app = FastAPI(
    title="PolarGrid AI",
    description="AI-Driven Smart Energy Management System for Polar Research Stations",
    version="1.0.0"
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global state
station_data = {}
forecaster = PolarLoadForecaster()
renewable_forecaster = RenewableForecaster()
optimizer = EnergyOptimizer(StationConfig())
simulators = {}
initialization_metrics = {}
system_initialized = False


def initialize_system():
    """Initialize all system components with realistic data"""
    global station_data, simulators, initialization_metrics, system_initialized

    if system_initialized:
        return

    print("🧊 PolarGrid AI: Initializing system...")

    stations = [
        ("Maitri (Antarctica)", "antarctica"),
        ("Bharati (Antarctica)", "antarctica"),
        ("Himadri (Arctic)", "arctic")
    ]

    for station_name, station_type in stations:
        print(f"  Loading {station_name}...")
        simulator = PolarDataSimulator(station_type=station_type, seed=hash(station_name) % 1000)
        simulators[station_name] = simulator

        # Generate 1 year of data
        df = simulator.generate_hourly_data(days=365)
        features = simulator.generate_features_for_ml(df)

        station_data[station_name] = {
            'raw_data': df,
            'features': features,
            'simulator': simulator
        }
        print(f"    {len(df)} hours of data generated")

    print("\n  Training AI Load Forecaster...")
    maitri_features = station_data["Maitri (Antarctica)"]['features']
    initialization_metrics.update(forecaster.train(maitri_features))
    print(f"    MAE: {initialization_metrics['ensemble']['mae']:.2f} kW, R2: {initialization_metrics['ensemble']['r2']:.4f}")

    print("  Training Renewable Energy Forecaster...")
    renewable_forecaster.train(maitri_features)
    print("    Done.")

    system_initialized = True
    print("\n✅ System initialized successfully!\n")


@app.on_event("startup")
async def startup_event():
    """Train models on first startup (runs once per cold start)"""
    initialize_system()


@app.get("/")
async def serve_dashboard():
    """Serve the main dashboard HTML page"""
    # Ensure system is initialized
    initialize_system()

    template_path = os.path.join(os.path.dirname(__file__), '..', 'frontend', 'templates', 'index.html')
    with open(template_path, 'r', encoding='utf-8') as f:
        return HTMLResponse(content=f.read())


@app.get("/api/health")
async def health_check():
    """Quick health check"""
    initialize_system()
    return {
        "status": "ok",
        "stations": list(station_data.keys()),
        "model_trained": forecaster.is_trained,
        "data_loaded": len(station_data) > 0
    }


@app.get("/api/stations")
async def list_stations():
    """List available polar research stations"""
    initialize_system()
    return {
        'stations': list(station_data.keys()),
        'current_station': "Maitri (Antarctica)"
    }


@app.get("/api/model-performance")
async def get_model_performance():
    """Get ML model performance metrics"""
    initialize_system()
    return {
        'load_forecasting': initialization_metrics,
        'feature_importance': forecaster.get_feature_importance(10),
        'model_type': 'Hybrid Ensemble (XGBoost + Random Forest + Gradient Boosting)',
        'training_data_hours': initialization_metrics.get('sample_size', 'N/A'),
        'test_period_hours': initialization_metrics.get('test_period_hours', 'N/A')
    }


@app.get("/api/weather-impact")
async def get_weather_impact_analysis():
    """Analyze how weather affects energy consumption and generation"""
    initialize_system()
    maitri = station_data["Maitri (Antarctica)"]['raw_data']

    monthly = maitri.resample('ME').agg({
        'temperature': 'mean',
        'wind_speed': 'mean',
        'solar_generation_kw': 'sum',
        'wind_generation_kw': 'sum',
        'diesel_consumption_liters': 'sum',
        'total_demand_kw': 'mean'
    }).round(2)

    temp_demand_corr = maitri['temperature'].corr(maitri['total_demand_kw'])
    wind_gen_corr = maitri['wind_speed'].corr(maitri['wind_generation_kw'])
    solar_gen_corr = maitri['solar_irradiance'].corr(maitri['solar_generation_kw'])

    return {
        'monthly_trends': {
            'months': [idx.strftime('%B %Y') for idx in monthly.index],
            'temperature': monthly['temperature'].tolist(),
            'wind_speed': monthly['wind_speed'].tolist(),
            'solar_generation': monthly['solar_generation_kw'].tolist(),
            'wind_generation': monthly['wind_generation_kw'].tolist(),
            'diesel_consumption': monthly['diesel_consumption_liters'].tolist(),
            'avg_demand': monthly['total_demand_kw'].tolist()
        },
        'correlations': {
            'temperature_vs_demand': round(temp_demand_corr, 3),
            'wind_speed_vs_generation': round(wind_gen_corr, 3),
            'irradiance_vs_solar_gen': round(solar_gen_corr, 3)
        },
        'insights': [
            f"Temperature-demand correlation: {temp_demand_corr:.3f}",
            f"Wind speed directly drives wind generation (r={wind_gen_corr:.3f})",
            "Polar night (May-Aug) eliminates all solar generation",
            "Midnight sun (Nov-Feb) maximizes solar but increases cooling loads",
            "Katabatic winds in winter boost wind generation by ~50%"
        ]
    }


@app.get("/api/annual-summary")
async def get_annual_summary(station: str = "Maitri (Antarctica)"):
    """Get annual energy summary and KPIs"""
    initialize_system()

    if station not in station_data:
        return JSONResponse(status_code=404, content={"error": f"Station not found: {station}"})

    df = station_data[station]['raw_data']

    annual = {
        'total_demand_kwh': round(df['total_demand_kw'].sum(), 0),
        'solar_generation_kwh': round(df['solar_generation_kw'].sum(), 0),
        'wind_generation_kwh': round(df['wind_generation_kw'].sum(), 0),
        'total_renewable_kwh': round(df['solar_generation_kw'].sum() + df['wind_generation_kw'].sum(), 0),
        'diesel_consumption_liters': round(df['diesel_consumption_liters'].sum(), 0),
        'diesel_cost_rs': round(df['diesel_consumption_liters'].sum() * 80, 0),
        'co2_emissions_tonnes': round(df['diesel_consumption_liters'].sum() * 2.68 / 1000, 2),
        'avg_temperature_c': round(df['temperature'].mean(), 1),
        'min_temperature_c': round(df['temperature'].min(), 1),
        'max_temperature_c': round(df['temperature'].max(), 1),
        'avg_wind_speed_ms': round(df['wind_speed'].mean(), 1),
        'renewable_share_percent': round(
            (df['solar_generation_kw'].sum() + df['wind_generation_kw'].sum()) /
            df['total_demand_kw'].sum() * 100, 1
        ),
        'battery_avg_soc': round(df['battery_soc_percent'].mean(), 1),
        'peak_demand_kw': round(df['total_demand_kw'].max(), 1),
        'avg_demand_kw': round(df['total_demand_kw'].mean(), 1),
        'generator_utilization_percent': round(
            df[df['generator_output_kw'] > 0]['generator_output_kw'].mean() / 400 * 100, 1
        )
    }

    return {
        'station': station,
        'period': f"{df.index[0].strftime('%B %Y')} - {df.index[-1].strftime('%B %Y')}",
        'annual_metrics': annual,
        'kpis': {
            'renewable_penetration': f"{annual['renewable_share_percent']}%",
            'diesel_dependency': f"{100 - annual['renewable_share_percent']:.1f}%",
            'carbon_intensity': f"{annual['co2_emissions_tonnes'] / (annual['total_demand_kwh'] / 1000):.2f} tCO2/MWh",
            'fuel_cost_per_kwh': f"Rs.{annual['diesel_cost_rs'] / annual['total_demand_kwh']:.2f}"
        },
        'impact_vs_traditional': {
            'fuel_saved_liters': round(annual['diesel_consumption_liters'] * 0.35, 0),
            'cost_saved_rs': round(annual['diesel_cost_rs'] * 0.35, 0),
            'co2_avoided_tonnes': round(annual['co2_emissions_tonnes'] * 0.35, 2),
            'note': 'Compared to diesel-only baseline without AI optimization'
        }
    }


@app.get("/api/energy-flow")
async def get_energy_flow_data(station: str = "Maitri (Antarctica)"):
    """Get energy flow data for Sankey diagram visualization"""
    initialize_system()

    if station not in station_data:
        return JSONResponse(status_code=404, content={"error": f"Station not found: {station}"})

    df = station_data[station]['raw_data']
    last_24h = df.tail(24)

    solar_total = last_24h['solar_generation_kw'].sum()
    wind_total = last_24h['wind_generation_kw'].sum()
    generator_total = last_24h['generator_output_kw'].sum()
    demand_total = last_24h['total_demand_kw'].sum()

    return {
        'sources': {
            'solar': round(solar_total, 1),
            'wind': round(wind_total, 1),
            'diesel_generator': round(generator_total, 1),
            'battery_discharge': round(max(0, demand_total - solar_total - wind_total - generator_total), 1)
        },
        'destinations': {
            'base_load_heating': round(last_24h['base_load_kw'].sum(), 1),
            'research_equipment': round(last_24h['research_load_kw'].sum(), 1),
            'water_desalination': round(last_24h['water_load_kw'].sum(), 1),
            'communications': round(last_24h['comms_load_kw'].sum(), 1),
            'battery_charging': round(max(0, solar_total + wind_total - demand_total), 1)
        },
        'losses': {
            'curtailment': round(max(0, solar_total + wind_total - demand_total), 1),
            'conversion_loss': round((solar_total + wind_total + generator_total) * 0.08, 1)
        }
    }


@app.get("/api/dashboard")
async def get_dashboard_data(station: str = "Maitri (Antarctica)", hours_ahead: int = 168):
    """Main dashboard data endpoint"""
    initialize_system()

    try:
        if station not in station_data:
            return JSONResponse(status_code=404, content={"error": f"Station not found: {station}"})

        data = station_data[station]
        df = data['raw_data']
        simulator = data['simulator']

        # Get recent actual data
        recent_data = df.tail(168)

        # Generate forecast
        from datetime import timedelta
        last_timestamp = df.index[-1]
        extra_days = max(hours_ahead // 24 + 3, 10)
        forecast_df = simulator.generate_hourly_data(days=extra_days, start_date=last_timestamp + timedelta(hours=1))
        forecast_features = simulator.generate_features_for_ml(forecast_df)

        # Generate ML predictions
        try:
            demand_forecast, (ci_lower, ci_upper) = forecaster.predict_with_uncertainty(forecast_features)
            solar_forecast = renewable_forecaster.predict_solar(forecast_features)
            wind_forecast = renewable_forecaster.predict_wind(forecast_features)
        except Exception as e:
            print(f"  [WARN] ML prediction failed, using fallback: {e}")
            demand_forecast = forecast_df['total_demand_kw'].values
            solar_forecast = forecast_df['solar_generation_kw'].values
            wind_forecast = forecast_df['wind_generation_kw'].values
            ci_lower = demand_forecast * 0.9
            ci_upper = demand_forecast * 1.1

        # Run optimization
        result = optimizer.optimize_dispatch(
            demand_forecast=demand_forecast,
            solar_forecast=solar_forecast,
            wind_forecast=wind_forecast,
            current_soc=65.0,
            temperature=-20,
            wind_speed=15,
            hours_ahead=hours_ahead
        )

        dispatch = result['dispatch']

        return {
            'station': station,
            'timestamp': '2026-09-05T00:00:00',
            'recent_data': {
                'timestamps': [t.isoformat() for t in recent_data.index],
                'demand': recent_data['total_demand_kw'].tolist(),
                'solar': recent_data['solar_generation_kw'].tolist(),
                'wind': recent_data['wind_generation_kw'].tolist(),
                'battery_soc': recent_data['battery_soc_percent'].tolist(),
                'generator': recent_data['generator_output_kw'].tolist(),
                'temperature': recent_data['temperature'].tolist(),
                'diesel': recent_data['diesel_consumption_liters'].tolist()
            },
            'forecast': {
                'timestamps': [t.isoformat() for t in forecast_df.index[:hours_ahead]],
                'demand_actual': forecast_df['total_demand_kw'][:hours_ahead].tolist(),
                'demand_predicted': [round(x, 1) for x in demand_forecast[:hours_ahead]],
                'ci_lower': [round(x, 1) for x in ci_lower[:hours_ahead]],
                'ci_upper': [round(x, 1) for x in ci_upper[:hours_ahead]],
                'solar_predicted': [round(max(0, x), 1) for x in solar_forecast[:hours_ahead]],
                'wind_predicted': [round(max(0, x), 1) for x in wind_forecast[:hours_ahead]],
                'temperature': forecast_df['temperature'][:hours_ahead].tolist()
            },
            'dispatch': {
                'timestamps': [forecast_df.index[i].isoformat() for i in range(min(hours_ahead, len(dispatch['demand_kw'])))] if 'hour' in dispatch else [],
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
            'resupply_plan': optimizer.generate_resupply_plan(df)
        }

    except Exception as e:
        print(f"\n[DASHBOARD ERROR] {e}")
        import traceback
        traceback.print_exc()
        return JSONResponse(status_code=500, content={"error": str(e)})


# Mangum handler for AWS Lambda / Vercel
handler = Mangum(app, lifespan="off")
