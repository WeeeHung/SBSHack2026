# LTA DataMall API - Traffic Speed Band Test

This project tests the LTA DataMall Traffic Speed Band API.

## Setup

1. **Install dependencies:**

   ```bash
   pip install -r requirements.txt
   ```

2. **Create a `.env` file** in the project root with your LTA DataMall credentials:

   ```
   LTA_ACCOUNT_KEY=your_account_key_here
   ```

   Replace `your_account_key_here` with your actual AccountKey from LTA DataMall.

3. **Run the test script:**
   ```bash
   python test_traffic_speed_band.py
   ```

## Scripts

### 1. Test Script (`test_traffic_speed_band.py`)

Quick test to verify API connectivity and view sample data.

### 2. Data Collection (`collect_traffic_data.py`)

Collects traffic speed band data every 2 minutes for 2 hours and saves to `traffic_speed_data.json`.

```bash
python collect_traffic_data.py
```

The script will:

- Call the API every 2 minutes for 2 hours (60 total calls)
- Save data incrementally to `traffic_speed_data.json`
- Display progress and statistics

### 3. Visualization (`visualize_traffic_data.py`)

Creates visualizations showing speed changes over time for the first 10 LinkIDs.

```bash
python visualize_traffic_data.py
```

This will generate:

- `traffic_speed_individual.png`: Separate subplot for each LinkID showing speed over time with min/max ranges
- `traffic_speed_combined.png`: Single plot with all LinkIDs overlaid
- Summary statistics printed to console

## Environment Variables

The `.env` file should contain:

- `LTA_ACCOUNT_KEY`: Your LTA DataMall AccountKey (required for API authentication)

## API Information

- **API Endpoint**: `https://datamall2.mytransport.sg/ltaodataservice/v4/TrafficSpeedBands`
- **Update Frequency**: 5 minutes
- **Documentation**: [LTA DataMall API User Guide](https://datamall.lta.gov.sg/content/dam/datamall/datasets/LTA_DataMall_API_User_Guide.pdf)

## Response Attributes

The API returns traffic speed band data with the following attributes:

- `LinkID`: Unique ID for the road stretch
- `RoadName`: Name of the road
- `RoadCategory`: Road category (1=Expressways, 2=Major Arterial, 3=Arterial, 4=Minor Arterial, 5=Small Roads, 6=Slip Roads, 8=Short Tunnels)
- `SpeedBand`: Speed band (1-8, representing speed ranges from 0-9 km/h to 70+ km/h)
- `MinimumSpeed`: Minimum speed in km/h
- `MaximumSpeed`: Maximum speed in km/h
- `StartLon`, `StartLat`: Longitude and latitude for start point
- `EndLon`, `EndLat`: Longitude and latitude for end point
