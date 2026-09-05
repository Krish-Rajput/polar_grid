"""
Polar Station Energy Data Simulator
Generates realistic synthetic data for Antarctic research stations
Based on actual polar conditions: Maitri/Bharati station operational profiles
"""
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, Tuple


class PolarDataSimulator:
    """
    Simulates realistic polar station energy data
    Models: Maitri/Bharati (Antarctica) and Himadri (Arctic)
    """

    def __init__(self, station_type: str = "antarctica", seed: int = 42):
        self.station_type = station_type
        np.random.seed(seed)

        # Station-specific parameters
        if station_type == "antarctica":
            self.base_load = 150  # kW (heating, life support)
            self.research_load_max = 200  # kW (experiments, equipment)
            self.water_desal_load = 80  # kW
            self.communications_load = 30  # kW

            # Solar parameters (Antarctica)
            self.solar_panel_capacity = 120  # kW (like Bharati station)
            self.latitude = -70.77  # Maitri coordinates

            # Wind parameters
            self.wind_turbine_capacity = 50  # kW
            self.katabatic_wind_factor = 1.5  # Winter wind boost

        else:  # Arctic
            self.base_load = 120
            self.research_load_max = 150
            self.water_desal_load = 60
            self.communications_load = 25
            self.solar_panel_capacity = 100
            self.latitude = 78.92  # Ny-Ålesund
            self.wind_turbine_capacity = 60
            self.katabatic_wind_factor = 1.2

    def generate_hourly_data(self, days: int = 365, start_date: datetime = None) -> pd.DataFrame:
        """Generate comprehensive hourly energy data for polar station"""

        if start_date is None:
            start_date = datetime(2024, 1, 1)

        timestamps = []
        solar_irradiance = []
        temperature = []
        wind_speed = []
        base_load = []
        research_load = []
        water_load = []
        comms_load = []
        total_demand = []
        solar_generation = []
        wind_generation = []
        battery_soc = []
        generator_output = []
        diesel_consumption = []

        current_soc = 50.0  # Start with 50% battery
        hourly_battery_capacity = 400  # kWh

        for hour in range(days * 24):
            timestamp = start_date + timedelta(hours=hour)
            day_of_year = timestamp.timetuple().tm_yday
            hour_of_day = timestamp.hour

            # === SOLAR IRRADIANCE MODEL ===
            if self.station_type == "antarctica":
                if 120 <= day_of_year <= 244:
                    solar = 0.0
                elif 304 <= day_of_year or day_of_year <= 31:
                    solar = 0.85 + np.random.normal(0, 0.1)
                else:
                    angle = np.pi * (day_of_year - 31) / (120 - 31)
                    solar = 0.85 * (1 - np.cos(angle)) / 2
                    solar = max(0, solar)
            else:
                if 320 <= day_of_year or day_of_year <= 40:
                    solar = 0.0
                elif 130 <= day_of_year <= 214:
                    solar = 0.90 + np.random.normal(0, 0.08)
                else:
                    angle = np.pi * (day_of_year - 40) / (130 - 40)
                    solar = 0.90 * (1 - np.cos(angle)) / 2
                    solar = max(0, solar)

            cloud_factor = np.random.uniform(0.6, 0.8)
            solar *= cloud_factor

            # === TEMPERATURE MODEL ===
            if self.station_type == "antarctica":
                temp_base = -22 - 18 * np.cos(2 * np.pi * (day_of_year - 15) / 365)
                temp_noise = np.random.normal(0, 5)
                temp = temp_base + temp_noise
            else:
                temp_base = -10 - 15 * np.cos(2 * np.pi * (day_of_year - 15) / 365)
                temp_noise = np.random.normal(0, 4)
                temp = temp_base + temp_noise

            # === WIND SPEED MODEL ===
            if self.station_type == "antarctica":
                wind_base = 15 + 10 * np.cos(2 * np.pi * (day_of_year - 200) / 365)
                if 120 <= day_of_year <= 244:
                    wind_base *= self.katabatic_wind_factor
            else:
                wind_base = 12 + 8 * np.cos(2 * np.pi * (day_of_year - 200) / 365)

            wind = max(0, wind_base + np.random.normal(0, 3))

            # === LOAD MODELS ===
            heating_factor = max(0, (-temp - 10) / 30)
            base = self.base_load * (1 + 0.5 * heating_factor)
            base += np.random.normal(0, 5)

            if self.station_type == "antarctica":
                research_factor = 0.3 + 0.7 * max(0, np.sin(2 * np.pi * (day_of_year - 304) / 365))
            else:
                research_factor = 0.4 + 0.6 * max(0, np.sin(2 * np.pi * (day_of_year - 130) / 365))

            research = self.research_load_max * research_factor * (0.5 + 0.5 * np.sin(2 * np.pi * hour_of_day / 24))
            research *= np.random.uniform(0.8, 1.2)

            water = self.water_desal_load * (0.9 + 0.1 * np.random.random())
            comms = self.communications_load * np.random.uniform(0.95, 1.05)

            demand = max(50, base + research + water + comms)

            # === RENEWABLE GENERATION ===
            solar_gen = self.solar_panel_capacity * max(0, solar) * (0.9 + 0.1 * np.random.random())

            if wind < 3:
                wind_gen = 0
            elif wind < 12:
                wind_gen = self.wind_turbine_capacity * ((wind - 3) / 9) ** 3
            elif wind < 25:
                wind_gen = self.wind_turbine_capacity
            else:
                wind_gen = 0

            wind_gen *= np.random.uniform(0.9, 1.0)

            # === BATTERY & GENERATOR DISPATCH ===
            renewable = solar_gen + wind_gen

            if renewable >= demand:
                excess = renewable - demand
                current_soc += (excess / hourly_battery_capacity) * 100
                current_soc = min(95, current_soc)
                gen_output = 0
                diesel = 0
            else:
                deficit = demand - renewable
                if current_soc > 20:
                    battery_discharge = min(deficit * 0.6, (current_soc - 20) / 100 * hourly_battery_capacity)
                    current_soc -= (battery_discharge / hourly_battery_capacity) * 100
                    gen_output = deficit - battery_discharge
                else:
                    gen_output = deficit
                    current_soc = 20

                diesel = gen_output * 2.5 * np.random.uniform(0.95, 1.05)

            timestamps.append(timestamp)
            solar_irradiance.append(max(0, solar))
            temperature.append(round(temp, 1))
            wind_speed.append(round(wind, 1))
            base_load.append(round(base, 1))
            research_load.append(round(research, 1))
            water_load.append(round(water, 1))
            comms_load.append(round(comms, 1))
            total_demand.append(round(demand, 1))
            solar_generation.append(round(solar_gen, 1))
            wind_generation.append(round(wind_gen, 1))
            battery_soc.append(round(current_soc, 1))
            generator_output.append(round(gen_output, 1))
            diesel_consumption.append(round(diesel, 2))

        df = pd.DataFrame({
            'timestamp': timestamps,
            'solar_irradiance': solar_irradiance,
            'temperature': temperature,
            'wind_speed': wind_speed,
            'base_load_kw': base_load,
            'research_load_kw': research_load,
            'water_load_kw': water_load,
            'comms_load_kw': comms_load,
            'total_demand_kw': total_demand,
            'solar_generation_kw': solar_generation,
            'wind_generation_kw': wind_generation,
            'battery_soc_percent': battery_soc,
            'generator_output_kw': generator_output,
            'diesel_consumption_liters': diesel_consumption
        })

        df.set_index('timestamp', inplace=True)
        return df

    def generate_features_for_ml(self, df: pd.DataFrame) -> pd.DataFrame:
        """Create ML-ready features from raw data"""
        features = df.copy()

        features['hour'] = features.index.hour
        features['day_of_week'] = features.index.dayofweek
        features['day_of_year'] = features.index.dayofyear
        features['month'] = features.index.month
        features['is_weekend'] = (features['day_of_week'] >= 5).astype(int)

        features['hour_sin'] = np.sin(2 * np.pi * features['hour'] / 24)
        features['hour_cos'] = np.cos(2 * np.pi * features['hour'] / 24)
        features['doy_sin'] = np.sin(2 * np.pi * features['day_of_year'] / 365)
        features['doy_cos'] = np.cos(2 * np.pi * features['day_of_year'] / 365)

        features['heating_degree_hours'] = np.maximum(0, 10 - features['temperature'])
        features['cooling_degree_hours'] = np.maximum(0, features['temperature'] - (-5))
        features['wind_power_potential'] = np.where(
            (features['wind_speed'] >= 3) & (features['wind_speed'] < 25),
            0.5 * 1.225 * np.pi * 400 * features['wind_speed'] ** 3 / 1000,
            0
        )

        for lag in [1, 2, 3, 6, 12, 24]:
            features[f'load_lag_{lag}h'] = features['total_demand_kw'].shift(lag)

        features['load_rolling_mean_6h'] = features['total_demand_kw'].rolling(6, min_periods=1).mean()
        features['load_rolling_std_6h'] = features['total_demand_kw'].rolling(6, min_periods=1).std()
        features['load_rolling_mean_24h'] = features['total_demand_kw'].rolling(24, min_periods=1).mean()

        features['is_polar_night'] = (features['solar_irradiance'] == 0).astype(int)
        features['is_midnight_sun'] = (features['solar_irradiance'] > 0.7).astype(int)

        features.dropna(inplace=True)
        return features
