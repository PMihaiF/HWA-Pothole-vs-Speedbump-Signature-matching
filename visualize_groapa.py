#!/usr/bin/env python3
import csv
import math
import os
import sys
import time

try:
    import numpy as np
    import matplotlib.pyplot as plt
    from matplotlib.patches import Rectangle, Circle
    from matplotlib.lines import Line2D
    from matplotlib.widgets import Button
    from PIL import Image
except ImportError:
    print("matplotlib, numpy, and pillow are required. Install them with: python3 -m pip install matplotlib numpy pillow")
    sys.exit(1)

CSV_FILE = "Raw Data.csv"
WINDOW_SIZE = 16          
PRAG_ACCELERATIE = 3.0   
CAR_IMAGE = "car.png"

def read_sensor_data(csv_path):
    times = []
    acc_x = []
    acc_y = []
    acc_z = []

    if not os.path.exists(csv_path):
        raise FileNotFoundError(f"Eroare: Fisierul {csv_path} nu a fost gasit!")

    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        header = next(reader, None)
        for row in reader:
            if not row or len(row) < 4:
                continue
            try:
                times.append(float(row[0]))
                acc_x.append(float(row[1]))
                acc_y.append(float(row[2]))
                acc_z.append(float(row[3]))
            except ValueError:
                continue

    # --- DOWNSAMPLING PENTRU PERFORMANȚĂ ---
    if len(times) > 10:
        dt = times[1] - times[0]
        if dt > 0:
            hz = 1.0 / dt
            target_hz = 20.0 
            if hz > target_hz * 1.5:
                step = int(hz / target_hz)
                times = times[::step]
                acc_x = acc_x[::step]
                acc_y = acc_y[::step]
                acc_z = acc_z[::step]
                print(f"[!] Info: Date reduse automat la ~{int(hz/step)}Hz pentru fluiditate.")

    return times, acc_x, acc_y, acc_z

def detect_anomalies(acc_z, window_size, threshold):
    window = [0.0] * window_size
    index = 0
    full = False
    anomaly_types = []

    for value in acc_z:
        window[index] = value
        index += 1
        if index >= window_size:
            index = 0
            full = True

        if not full:
            anomaly_types.append(0)
            continue

        mean = sum(window) / window_size
        diff = value - mean
        if abs(diff) > threshold:
            anomaly_types.append(1 if diff > 0 else -1)
        else:
            anomaly_types.append(0)

    return anomaly_types

def compute_moving_average(acc_z, window_size):
    moving_average = []
    window = []
    for value in acc_z:
        window.append(value)
        if len(window) > window_size:
            window.pop(0)
        if len(window) == window_size:
            moving_average.append(sum(window) / window_size)
        else:
            moving_average.append(None)
    return moving_average

def animate_data(times, acc_z, moving_average, anomalies):
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 6.5), gridspec_kw={"height_ratios": [3, 1]})

    x_padding = (times[-1] - times[0]) * 0.03
    orig_xlim = (times[0] - x_padding, times[-1] + x_padding)
    orig_ylim = (min(acc_z) - 0.75, max(acc_z) + 0.75)

    ax1.plot(times, acc_z, label="Acc Z", color="#1f77b4", linewidth=1.2)
    ax1.plot(times, moving_average, label=f"Mean({WINDOW_SIZE})", color="#ff7f0e", linestyle="--", linewidth=1.4)
    ax1.set_xlim(orig_xlim)
    ax1.set_ylim(orig_ylim)
    ax1.set_title("Vizualizare accelerație Z + Control Avansat Redare", y=1.05)
    ax1.set_xlabel("Timp (s)")
    ax1.set_ylabel("Accelerație Z (m/s^2)") 
    ax1.grid(True, alpha=0.3)
    
    ax1.legend(loc="lower left", bbox_to_anchor=(0.0, 1.02), borderaxespad=0.0, frameon=True)

    ax2.set_xlim(0, 1)
    ax2.set_ylim(-0.6, 0.8)
    ax2.axis("off")

    try:
        car_img = Image.open(CAR_IMAGE)
        car_img_array = np.array(car_img)
    except FileNotFoundError:
        car_img_array = np.zeros((50, 100, 4), dtype=np.uint8)
        car_img_array[:, :, 0] = 31; car_img_array[:, :, 1] = 119; car_img_array[:, :, 2] = 180; car_img_array[:, :, 3] = 255  
    
    car_width_data = (times[-1] - times[0]) * 0.05
    car_height_data = (max(acc_z) - min(acc_z)) * 0.15
    
    start_t = times[0]
    start_z = acc_z[0]
    initial_extent = [
        start_t - car_width_data / 2,
        start_t + car_width_data / 2,
        start_z - car_height_data / 2,
        start_z + car_height_data / 2
    ]
    
    car_image = ax1.imshow(car_img_array, extent=initial_extent, aspect='auto', zorder=20)

    status_text = ax2.text(0.02, 0.5, "", transform=ax2.transAxes, fontsize=12, weight="bold")
    event_text = ax1.text(0.02, 0.93, "", transform=ax1.transAxes, fontsize=11, bbox={"facecolor": "white", "alpha": 0.8, "edgecolor": "gray"})

    fig.subplots_adjust(bottom=0.18, top=0.88, hspace=0.3)
    timer = fig.canvas.new_timer(interval=40)

    state = {
        "playback_time": 0.0, "last_tick": None, "running": False, "panning": False,
        "mouse_start_x": 0.0, "mouse_start_y": 0.0, "xlim_start": orig_xlim, "ylim_start": orig_ylim,
        "rewind_pressed": False, "ff_pressed": False, "press_start_time": 0.0, "was_held": False
    }

    def zoom_on_scroll(event):
        if event.inaxes != ax1: return
        base_scale = 1.2
        scale_factor = 1 / base_scale if event.button == 'up' else base_scale
        cur_xlim = ax1.get_xlim(); cur_ylim = ax1.get_ylim()
        xdata, ydata = event.xdata, event.ydata
        if xdata is None or ydata is None: return
        new_width = (cur_xlim[1] - cur_xlim[0]) * scale_factor
        new_height = (cur_ylim[1] - cur_ylim[0]) * scale_factor
        relx = (cur_xlim[1] - xdata) / (cur_xlim[1] - cur_xlim[0])
        rely = (cur_ylim[1] - ydata) / (cur_ylim[1] - cur_ylim[0])
        new_width = min(new_width, orig_xlim[1] - orig_xlim[0])
        new_height = min(new_height, orig_ylim[1] - orig_ylim[0])
        new_x0 = xdata - new_width * (1 - relx); new_x1 = xdata + new_width * relx
        new_y0 = ydata - new_height * (1 - rely); new_y1 = ydata + new_height * rely
        if new_x0 < orig_xlim[0]: new_x0 = orig_xlim[0]; new_x1 = orig_xlim[0] + new_width
        if new_x1 > orig_xlim[1]: new_x1 = orig_xlim[1]; new_x0 = orig_xlim[1] - new_width
        if new_y0 < orig_ylim[0]: new_y0 = orig_ylim[0]; new_y1 = orig_ylim[0] + new_height
        if new_y1 > orig_ylim[1]: new_y1 = orig_ylim[1]; new_y0 = orig_ylim[1] - new_height
        ax1.set_xlim([new_x0, new_x1]); ax1.set_ylim([new_y0, new_y1])
        fig.canvas.draw_idle()

    def on_mouse_press(event):
        if event.button != 1: return
        
        if event.inaxes == ax1:
            state["panning"] = True; state["mouse_start_x"] = event.x; state["mouse_start_y"] = event.y
            state["xlim_start"] = ax1.get_xlim(); state["ylim_start"] = ax1.get_ylim()
        elif event.inaxes == rewind_ax:
            state["rewind_pressed"] = True
            state["press_start_time"] = time.time()
            state["was_held"] = False
            state["last_tick"] = time.time()
        elif event.inaxes == ff_ax:
            state["ff_pressed"] = True
            state["press_start_time"] = time.time()
            state["was_held"] = False
            state["last_tick"] = time.time()

    def on_mouse_move(event):
        if state["panning"]:
            if event.x is None or event.y is None: return
            dx_data = ((event.x - state["mouse_start_x"]) / ax1.get_window_extent().width) * (state["xlim_start"][1] - state["xlim_start"][0])
            dy_data = ((event.y - state["mouse_start_y"]) / ax1.get_window_extent().height) * (state["ylim_start"][1] - state["ylim_start"][0])
            new_x0 = state["xlim_start"][0] - dx_data; new_x1 = state["xlim_start"][1] - dx_data
            new_y0 = state["ylim_start"][0] - dy_data; new_y1 = state["ylim_start"][1] - dy_data
            ax1.set_xlim(new_x0, new_x1); ax1.set_ylim(new_y0, new_y1)
            fig.canvas.draw_idle()

    def on_mouse_release(event):
        if event.button != 1: return
        state["panning"] = False
        
        now = time.time()
        if state["rewind_pressed"]:
            state["rewind_pressed"] = False
            if not state["was_held"] or (now - state["press_start_time"] <= 0.3):
                state["playback_time"] -= 1.0  

        if state["ff_pressed"]:
            state["ff_pressed"] = False
            if not state["was_held"] or (now - state["press_start_time"] <= 0.3):
                state["playback_time"] += 1.0  

        if state["playback_time"] < times[0]: state["playback_time"] = times[0]
        if state["playback_time"] > times[-1]: state["playback_time"] = times[-1]

    fig.canvas.mpl_connect('scroll_event', zoom_on_scroll)
    fig.canvas.mpl_connect('button_press_event', on_mouse_press)
    fig.canvas.mpl_connect('motion_notify_event', on_mouse_move)
    fig.canvas.mpl_connect('button_release_event', on_mouse_release)

    baseline_y = acc_z[0]

    def timer_tick():
        now = time.time()
        dt = 0.04 if state["last_tick"] is None else now - state["last_tick"]
        state["last_tick"] = now

        if state["rewind_pressed"]:
            if now - state["press_start_time"] > 0.3:
                state["was_held"] = True
                state["playback_time"] -= dt * 6.0  
        elif state["ff_pressed"]:
            if now - state["press_start_time"] > 0.3:
                state["was_held"] = True
                state["playback_time"] += dt * 6.0  
        elif state["running"]:
            state["playback_time"] += dt

        if state["playback_time"] < times[0]:
            state["playback_time"] = times[0]
        if state["playback_time"] >= times[-1]:
            state["playback_time"] = times[-1]
            if state["running"]:
                state["running"] = False
                play_button.label.set_text("Play")

        t = state["playback_time"]
        idx = max(0, np.searchsorted(times, t) - 1)

        # --- RECONSTRUCȚIE LOGICĂ STATELESS (DETERMINISTĂ) ---
        active_event = 0
        offset = 0.0
        
        # Scanam in spate maxim 0.8 secunde din momentul curent 't' pentru a gasi ultima anomalie activa
        lookback_idx = idx
        while lookback_idx >= 0 and (t - times[lookback_idx]) <= 0.8:
            if anomalies[lookback_idx] != 0:
                t_anom = times[lookback_idx]
                direction = anomalies[lookback_idx]
                progress = (t - t_anom) / 0.8
                offset = direction * 0.5 * math.sin(math.pi * max(0.0, min(1.0, progress)))
                active_event = direction
                break  # Oprim scanarea la cel mai apropiat eveniment din trecut
            lookback_idx -= 1
        
        car_center_z = baseline_y + offset
        
        zoom_ratio_x = (ax1.get_xlim()[1] - ax1.get_xlim()[0]) / (orig_xlim[1] - orig_xlim[0])
        zoom_ratio_y = (ax1.get_ylim()[1] - ax1.get_ylim()[0]) / (orig_ylim[1] - orig_ylim[0])
        dyn_car_width = car_width_data * zoom_ratio_x
        dyn_car_height = car_height_data * zoom_ratio_y

        car_image.set_extent([t - dyn_car_width / 2, t + dyn_car_width / 2, car_center_z - dyn_car_height / 2, car_center_z + dyn_car_height / 2])
        
        status = "Normal"; event_color = "white"; event_edge = "gray"
        if active_event == 1: status = "Speedbump ↑"; event_color = "#fff3cd"; event_edge = "#ff9800"
        elif active_event == -1: status = "Pothole ↓"; event_color = "#ffcdd2"; event_edge = "#f44336"

        status_text.set_text(f"Timp: {t:.1f}s   Eveniment: {status}")
        event_text.set_bbox({"facecolor": event_color, "alpha": 0.9, "edgecolor": event_edge, "linewidth": 2})
        event_text.set_text(f"Detecție: {status}" if active_event != 0 else "Detecție: normal")
        fig.canvas.draw_idle()

    timer.add_callback(timer_tick)

    # --- ZONĂ BUTOANE (Simetrice) ---
    rewind_ax = fig.add_axes([0.31, 0.03, 0.10, 0.05], facecolor="#f0f0f0")
    button_ax = fig.add_axes([0.44, 0.03, 0.12, 0.05], facecolor="#f0f0f0")
    ff_ax     = fig.add_axes([0.59, 0.03, 0.10, 0.05], facecolor="#f0f0f0")

    rewind_button = Button(rewind_ax, "<<", color="#2196F3", hovercolor="#0b7dda")
    play_button   = Button(button_ax, "Play", color="#4CAF50", hovercolor="#45A049")
    ff_button     = Button(ff_ax, ">>", color="#2196F3", hovercolor="#0b7dda")

    rewind_button.label.set_color('white'); rewind_button.label.set_weight('bold')
    ff_button.label.set_color('white'); ff_button.label.set_weight('bold')

    def toggle_play(event):
        if state["running"]:
            state["running"] = False; play_button.label.set_text("Play")
        else:
            state["running"] = True; state["last_tick"] = time.time(); play_button.label.set_text("Pause")

    play_button.on_clicked(toggle_play)
    
    timer.start()
    plt.show()

def main():
    csv_path = CSV_FILE if len(sys.argv) == 1 else sys.argv[1]
    try: times, acc_x, acc_y, acc_z = read_sensor_data(csv_path)
    except FileNotFoundError as e: print(e); sys.exit(1)

    anomalies = detect_anomalies(acc_z, WINDOW_SIZE, PRAG_ACCELERATIE)
    moving_average = compute_moving_average(acc_z, WINDOW_SIZE)
    
    print("--- Pornire Interfață Media Player Reparată ---")
    animate_data(times, acc_z, moving_average, anomalies)

if __name__ == "__main__":
    main()