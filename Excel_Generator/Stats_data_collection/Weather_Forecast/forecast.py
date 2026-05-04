import requests
import pandas as pd

# List of your specific cities with accurate coordinates
CITIES = {
    "Bahawalpur":     {"lat": 29.3956, "lon": 71.6836},
    "Multan":         {"lat": 30.1575, "lon": 71.5249},
    "Rahim Yar Khan": {"lat": 28.4212, "lon": 70.2989},
    "Khanewal":       {"lat": 30.3017, "lon": 71.9321},
    "Sanghar":        {"lat": 26.0466, "lon": 68.9485},
    "Hyderabad":      {"lat": 25.3960, "lon": 68.3578},
    "Ghotki":         {"lat": 28.0060, "lon": 69.3161},
    "Khairpur":       {"lat": 27.5295, "lon": 68.7592},
    "Bahawalnagar":   {"lat": 29.9987, "lon": 73.2536},
    "Lodhran":        {"lat": 29.5405, "lon": 71.6336}
}

def get_detailed_rain_forecast(city_name, lat, lon):
    url = "https://api.open-meteo.com/v1/forecast"
    
    # requesting detailed rain metrics
    params = {
        "latitude": lat,
        "longitude": lon,
        "daily": [
            "temperature_2m_max", 
            "temperature_2m_min", 
            "precipitation_sum",        # Total amount (mm)
            "precipitation_probability_max", # Chance of rain (%)
            "precipitation_hours"       # Duration of rain (hours)
        ],
        "timezone": "Asia/Karachi",
        "forecast_days": 16
    }
    
    try:
        response = requests.get(url, params=params)
        response.raise_for_status()
        data = response.json()
        
        daily = data.get("daily", {})
        dates = daily.get("time", [])
        
        # Weather Variables
        max_temps = daily.get("temperature_2m_max", [])
        min_temps = daily.get("temperature_2m_min", [])
        precip_sum = daily.get("precipitation_sum", [])
        precip_prob = daily.get("precipitation_probability_max", [])
        precip_hours = daily.get("precipitation_hours", [])
        
        forecast_list = []
        
        for i in range(len(dates)):
            forecast_list.append({
                "City": city_name,
                "Date": dates[i],
                "Max Temp (°C)": max_temps[i],
                "Min Temp (°C)": min_temps[i],
                "Rain Amount (mm)": precip_sum[i],
                "Rain Chance (%)": precip_prob[i],   # Probability
                "Rain Duration (Hrs)": precip_hours[i] # How long it lasts
            })

        return forecast_list

    except Exception as e:
        print(f"Error for {city_name}: {e}")
        return []

# --- MAIN EXECUTION ---
all_data = []

print("Fetching detailed 16-day rain forecast...")
for city, coords in CITIES.items():
    print(f"Processing {city}...")
    city_data = get_detailed_rain_forecast(city, coords["lat"], coords["lon"])
    all_data.extend(city_data)

# Convert to DataFrame
df = pd.DataFrame(all_data)

# Save to CSV
import os
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
csv_filename = os.path.join(BASE_DIR, 'pakistan_16day_detailed_rain.csv')
df.to_csv(csv_filename, index=False)

print(f"\nSuccess! Detailed rain data saved to '{csv_filename}'")
print("\n--- Sample Data (First 5 Rows) ---")
print(df.head())