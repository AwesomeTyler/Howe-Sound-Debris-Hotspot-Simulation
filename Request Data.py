import requests


#SQUAMISH AIRPORT 336

#PAM ROCKS  6817
#PORT MELLON 45267

#POINT ATKINSON  844


station_id = 336
start_year = 2017
end_year = 2020

for year in range(start_year, end_year + 1):
    for month in range(1, 13):
        url = f"https://climate.weather.gc.ca/climate_data/bulk_data_e.html?format=csv&stationID={station_id}&Year={year}&Month={month}&Day=1&timeframe=1&submit=Download+Data"
        response = requests.get(url)
        if response.status_code == 200:
            filename = f"C:/Users/zhangtyl.stu/OneDrive - UBC/Desktop/North/climate_data_{station_id}_{year}_{month:02d}.csv"
            with open(filename, 'wb') as f:
                f.write(response.content)
            print(f"Downloaded: {filename}")
        else:
            print(f"Failed to download data for {year}-{month:02d}")
print("Data Request Complete")