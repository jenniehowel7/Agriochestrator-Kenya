# Real Data Sources

These datasets are downloaded directly from public APIs:

1. NASA POWER Daily Agroclimatology (Kenya coordinates around Nairobi)
- URL:
  https://power.larc.nasa.gov/api/temporal/daily/point?parameters=T2M,PRECTOTCORR,RH2M&community=AG&longitude=36.8219&latitude=-1.2921&start=20180101&end=20251231&format=JSON
- Local file: `kenya_nasa_weather_daily.json`

2. World Bank Indicator: Cereal yield (kg per hectare)
- Indicator: `AG.YLD.CREL.KG`
- URL:
  https://api.worldbank.org/v2/country/KEN/indicator/AG.YLD.CREL.KG?format=json&per_page=20000
- Local file: `worldbank_kenya_cereal_yield.json`

3. World Bank Indicator: Agricultural land equipped for irrigation (%)
- Indicator: `AG.LND.IRIG.AG.ZS`
- URL:
  https://api.worldbank.org/v2/country/KEN/indicator/AG.LND.IRIG.AG.ZS?format=json&per_page=20000
- Local file: `worldbank_kenya_irrigated_land.json`

4. World Bank Indicator: Fertilizer consumption (% of fertilizer production)
- Indicator: `AG.CON.FERT.PT.ZS`
- URL:
  https://api.worldbank.org/v2/country/KEN/indicator/AG.CON.FERT.PT.ZS?format=json&per_page=20000
- Local file: `worldbank_kenya_fertilizer.json`
