import os
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

folder_path = "C:/Users/zhangtyl.stu/OneDrive - UBC/Desktop/North"

months = {6,7,8} #summer
#months = {12,1,2}    #winter

wind_directions = []

for filename in os.listdir(folder_path):
    if filename.endswith(".csv"):
        parts = filename.split("_")
        month = int(parts[-1].split(".")[0])

        if month in months:
            file_path = os.path.join(folder_path, filename)
            df = pd.read_csv(file_path)


            #This section is for Seperating Day and Night
            df["Time (LST)"] = pd.to_datetime(df["Time (LST)"], format="%H:%M")
            df["Hour"] = df["Time (LST)"].dt.hour  # Extract the hour

            #df = df[(df["Hour"] < 7) | (df["Hour"] > 22)]     #night
            df = df[(df["Hour"] >= 9) & (df["Hour"] <= 19)]    #daytime



            wind_dir_col = "Wind Dir (10s deg)"
            valid_wind_data = df[wind_dir_col].dropna().tolist()  # Remove NaN values
            wind_directions.extend(valid_wind_data)


wind_directions = [x * 10 for x in wind_directions]


wind_directions_radians = np.radians(wind_directions)

num_bins = 36  # 36bins, 10 degrees per bin
bin_edges = np.linspace(0, 2 * np.pi, num_bins + 1)

hist, _ = np.histogram(wind_directions_radians, bins=bin_edges) # Count occurrences in each bin

# Find the top two highest frequency bins
top_two_indices = np.argsort(hist)[-2:][::-1]  # Get indices of two highest counts in descending order
max_bin_index, second_max_bin_index = top_two_indices
max_bin_center = (bin_edges[max_bin_index] + bin_edges[max_bin_index + 1]) / 2
second_max_bin_center = (bin_edges[second_max_bin_index] + bin_edges[second_max_bin_index + 1]) / 2

max_bin_degrees = np.degrees(max_bin_center)
second_max_bin_degrees = np.degrees(second_max_bin_center)
print(f"Most frequent wind direction: {max_bin_degrees:.1f}°")
print(f"Second most frequent wind direction: {second_max_bin_degrees:.1f}°")



hist = hist / hist.max()  #Normalize, Scale between 0 and 1

fig, ax = plt.subplots(subplot_kw={'projection': 'polar'}, figsize=(8, 8))

ax.bar(bin_edges[:-1], hist, width=np.pi / 18, color='b', edgecolor='blue', alpha=0.7)

#Labeling
ax.set_theta_zero_location("N")
ax.set_theta_direction(-1)
ax.set_title("Squamish Airport Station \n\n Summer Daytime 2017-2020", fontsize=10, pad=30)
plt.show()