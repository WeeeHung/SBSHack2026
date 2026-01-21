## Coasting Recommendation Logic

if the current + next link is fast:
	- maintain speed

if the current link is fast, next link start to slow down:
	- if bus can pass next link before down:
	- speed up

if the current link if fast, next link is slow:
	- start coasting early
	- earlier if raining

if both links are slow
	- crawl

predict next link using past data & current conditions & AI

traffic speedband, weather, trafficincidents, inbound, outbound link data

## Progress Status

1. ✅ data collection: traffic speedband, weather, trafficincidents - COMPLETED
2. ✅ training model - COMPLETED
3. ✅ interface to output suggestion to driver - COMPLETED
4. ✅ write tests to showcase - COMPLETED

## Completed Components

- ✅ Data collection and integration (LTA Speed Bands, Bus Routes, Incidents, Rainfall)
- ✅ Route mapping and link identification
- ✅ ML model training (XGBoost) and prediction service
- ✅ Backend API with `/realtime_stats` and `/coasting_recommendation` endpoints
- ✅ Recommendation service implementing coasting logic
- ✅ Frontend web interface with color-coded display
- ✅ Voice guidance using Web Speech API
- ✅ GPS location support
- ✅ Unit tests for recommendation service
- ✅ Demo script for showcasing scenarios

## Next Steps (Future Enhancements)

- [ ] Real-time GPS tracking integration
- [ ] Historical performance analytics
- [ ] Fuel savings estimation
- [ ] Mobile app version
- [ ] Integration with bus fleet management systems 
