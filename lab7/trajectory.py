import requests
import pandas as pd
import folium
from folium.plugins import TimestampedGeoJson
import time

# access token
auth = requests.post(
    "http://3.134.109.104:8080/api/auth/login",
    json={"username": "tenant@thingsboard.org", "password": "tenant"}
)
token = auth.json()['token']
headers = {"X-Authorization": f"Bearer {token}"}

# all device ids
device_ids = [
    "ae0c6bc0-a4b9-11f0-bd90-73180dc3ced7",
    "8b9d0610-a4f2-11f0-9f61-39c42c8952cf",
    "4ee634a0-a4b9-11f0-bd90-73180dc3ced7"
]

# 10 hours ago
end_ts = int(time.time() * 1000)
start_ts = end_ts - 3600 * 10000  

# map
m = folium.Map(location=[37.7749, -122.4194], zoom_start=3)
colors = ['red', 'blue', 'green']

for i, device_id in enumerate(device_ids):
    url = f"http://3.134.109.104:8080/api/plugins/telemetry/DEVICE/{device_id}/values/timeseries"
    params = {"keys": "lat,lon", "startTs": start_ts, "endTs": end_ts}
    data = requests.get(url, headers=headers, params=params).json()

    if not data or 'lat' not in data or 'lon' not in data:
        print(f"❌ Device {device_id} has no telemetry data.")
        continue

    lats = data['lat']
    lons = data['lon']

    # build DataFrame
    df = pd.DataFrame({
        'lat': [float(v['value']) for v in lats],
        'lon': [float(v['value']) for v in lons],
        'ts': [float(v['ts']) for v in lats]
    })
    df['ts'] = pd.to_datetime(df['ts'], unit='ms').sort_values()

    if df.empty:
        print(f"Device {device_id} telemetry is empty after filtering.")
        continue

    color = colors[i % len(colors)]
    features = []

    for _, row in df.iterrows():
        features.append({
            'type': 'Feature',
            'geometry': {'type': 'Point', 'coordinates': [row['lon'], row['lat']]},
            'properties': {
                'time': row['ts'].isoformat(),
                'style': {'color': color},
                'icon': 'circle',
                'popup': f"Device {i+1} | {row['ts']}"
            }
        })

    TimestampedGeoJson(
        {'type': 'FeatureCollection', 'features': features},
        period='PT5S',          # every 5 seconds
        add_last_point=True,
        auto_play=True,
        loop=False
    ).add_to(m)

    print(f"Added device {device_id} with {len(df)} history points")

# save html
m.save("multi_device_history.html")
print("Map saved as multi_device_history.html")

