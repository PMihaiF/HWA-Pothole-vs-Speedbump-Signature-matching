# Road Anomaly Detector

A small project that uses raw accelerometer data to detect when a car hits a pothole or a speedbump. 

It includes a Python visualizer that works like a media player. You can play, pause, rewind, and fast-forward through the sensor data, while a little car animation shows you exactly when and what type of anomaly was detected on the road.

## What's inside
- `visualize_groapa.py`: The main Python script for the interactive UI and visualization.
- `detectie_groapa.cpp`: The core detection algorithm written in C++ (if you just want to look at or compile the raw logic).
- `Raw Data.csv`: A sample dataset included so you can run the app right out of the box.
- `car.png`: A small image asset for the UI.

## How to run it

First, make sure you have the required Python libraries installed (```bashpip install matplotlib numpy pillow)
Then run the visualizer (python visualize_groapa.py)

## Controls 

Play/Pause, <<, >>: Navigate through the timeline just like a video player.
Scroll: Zoom in and out on the graph.
Click & Drag: Pan around the timeline manually.
The UI will flash red for potholes (↓) and orange for speedbumps (↑).
