import gradio as gr
import math

# --- Data and Functions from your takeoff_model.py ---
# I've copied all the calculation logic directly into this file
# to make it a self-contained application.

# Data Digitized from the PA-28-181 Chart
TAKEOFF_DATA = {
    0:    {8.283945422852682: 892.4445513013161, 29.982568972771546: 1283.66893069664},
    1000: {-3.8119853338943273: 888.693875097673, 30.775981246618983: 1507.1707639598485},
    2000: {-12.181282683176057: 892.3002945242533, 30.905812345975832: 1674.6528821301918},
    3000: {-22.421109575043573: 882.9236040151468, 31.045260563803566: 1854.5410831279678},
    4000: {-29.855142153032396: 893.021578409569, 30.908216625593553: 2077.7544028370503},
    5000: {-37.61856103864879: 878.2112159644166, 30.775981246618983: 2307.1707639598485},
}

TAKEOFF_DATA_50Ft = {
    1000 : {-5.699053711848606: 1500, 4.250299880047962: 1770.491803278689, 12.581634013061446: 2024.5901639344265, 21.543382646941225: 2319.6721311475417, 29.2123150739704: 2598.3606557377057},
    2000 : {-14.972007464676082:1494.6680885097298,
    -8.914956011730212:1681.9514796054377,
    -0.6291655558517704:1942.5486536923481,
    5.737136763529719:2154.3588376432945,
    12.092775259930704:2382.564649426819,
    28.936283657691277:2985.670487869901},
    3000 : {-23.417755265262592:1480.0053319114895,
    -18.011197014129564:1667.422020794454,
    -12.60463876299653:1854.8387096774186,
    -5.60917088776327:2099.306851506264,
    -0.21860837110104114:2311.3169821380957,
    10.26392961876833:2694.4148227139426,
    21.370301252999198:3118.368435083977,
    28.978938949613436:3420.087976539589},
    4000 : {-35.78245801119701:1490.735803785657,
    -27.155425219941343:1726.6728872300714,
    -21.73287123433751:1889.496134364169,
    -12.828579045587837:2199.1468941615562,
    -3.62036790189282:2541.5222607304713,
    2.0954412156758337:2753.4657424686748,
    10.64782724606772:3104.1722207411353,
    20.122633964276204:3536.6568914956006,
    28.63236470274593:3952.9458810983733},
    5000 : { -37.53132498000533:1679.6187683284456,
    -28.595041322314046:1940.0826446280985,
    -18.11783524393494:2331.378299120234,
    -8.621700879765399:2731.0717142095436,
    1.519594774726741:3138.829645427885,
    12.1940815782458:3726.806185017328,
    20.047987203412433:4151.426286323647,
    25.03332444681419:4486.470274593441},
}
REFERENCE_WEIGHT_LBS = 2850.0
MIN_CHART_WEIGHT_LBS = 2050.0

def _interpolate_1d(x, x_points, y_points):
    if not x_points or not y_points: return 0
    if x <= x_points[0]: return y_points[0]
    if x >= x_points[-1]: return y_points[-1]
    for i in range(len(x_points) - 1):
        if x_points[i] <= x <= x_points[i+1]:
            x1, x2 = x_points[i], x_points[i+1]
            y1, y2 = y_points[i], y_points[i+1]
            if (x2 - x1) == 0: return y1
            return y1 + (y2 - y1) * ((x - x1) / (x2 - x1))
    return y_points[0]

def _get_distance_at_temp_and_alt(temp, alt, data):
    alt_points = sorted(data.keys())
    if not alt_points: return 0
    alt_low, alt_high = -1, -1
    if alt <= alt_points[0]: alt_low = alt_high = alt_points[0]
    elif alt >= alt_points[-1]: alt_low = alt_high = alt_points[-1]
    else:
        for i in range(len(alt_points) - 1):
            if alt_points[i] <= alt <= alt_points[i+1]:
                alt_low, alt_high = alt_points[i], alt_points[i+1]
                break
    
    if alt_low not in data: return 0
    temp_points_low = sorted(data[alt_low].keys())
    dist_points_low = [data[alt_low][t] for t in temp_points_low]
    dist_at_alt_low = _interpolate_1d(temp, temp_points_low, dist_points_low)
    
    if alt_low == alt_high: return dist_at_alt_low
    
    if alt_high not in data: return dist_at_alt_low
    temp_points_high = sorted(data[alt_high].keys())
    dist_points_high = [data[alt_high][t] for t in temp_points_high]
    dist_at_alt_high = _interpolate_1d(temp, temp_points_high, dist_points_high)
    
    return _interpolate_1d(alt, [alt_low, alt_high], [dist_at_alt_low, dist_at_alt_high])

def _calculate_weight_correction(base_distance, weight_lbs):
    if weight_lbs >= REFERENCE_WEIGHT_LBS:
        return 0.0
    x_points = [1999.6411139821994, 2544.621494879893]
    y_points = [840.3100775193798, 1410.8527131782948]
    distance_at_actual_weight = _interpolate_1d(weight_lbs, x_points, y_points)
    distance_at_reference_weight = _interpolate_1d(REFERENCE_WEIGHT_LBS, x_points, y_points)
    weight_correction_delta = distance_at_actual_weight - distance_at_reference_weight
    return weight_correction_delta


def _calculate_weight_correction_50ft(base_distance, weight_lbs):
    if weight_lbs >= REFERENCE_WEIGHT_LBS:
        return 0.0
    x_points = [2074.7658688865768, 2545.629552549428]
    y_points = [1557.622268470344, 2718.652445369407]
    distance_at_actual_weight = _interpolate_1d(weight_lbs, x_points, y_points)
    distance_at_reference_weight = _interpolate_1d(REFERENCE_WEIGHT_LBS, x_points, y_points)
    weight_correction_delta = distance_at_actual_weight - distance_at_reference_weight
    return weight_correction_delta


def _calculate_headwind_correction(wind_knots):
    x_points = [0.16104294478526526, 15.04722311914756]
    y_points = [1139.2960929932183, 847.9173393606702]
    distance_at_actual_wind = _interpolate_1d(wind_knots, x_points, y_points)
    distance_at_zero_wind = _interpolate_1d(0, x_points, y_points)
    return distance_at_actual_wind - distance_at_zero_wind

def _calculate_headwind_correction_50ft(wind_knots):
    x_points = [-0.4118297401879545, 14.90049751243781]
    y_points = [2083.6557950985825, 1657.0849456421615]
    distance_at_actual_wind = _interpolate_1d(wind_knots, x_points, y_points)
    distance_at_zero_wind = _interpolate_1d(0, x_points, y_points)
    return distance_at_actual_wind - distance_at_zero_wind


def _calculate_tailwind_correction(wind_knots):
    x_points = [0.16104294478526526, 5.268404907975452]
    y_points = [1139.2960929932183, 1414.1427187600893]
    distance_at_actual_wind = _interpolate_1d(wind_knots, x_points, y_points)
    distance_at_zero_wind = _interpolate_1d(0, x_points, y_points)
    return distance_at_actual_wind - distance_at_zero_wind


def _calculate_tailwind_correction_50ft(wind_knots):
    x_points = [-0.10779436152570554, 4.483139856274192]
    y_points = [1681.684171733924, 2061.912658927585]
    distance_at_actual_wind = _interpolate_1d(wind_knots, x_points, y_points)
    distance_at_zero_wind = _interpolate_1d(0, x_points, y_points)
    return distance_at_actual_wind - distance_at_zero_wind

def calculate_density_altitude(pressure_altitude_ft, outside_air_temp_c):
    isa_temp_c = 15 - (2 * (pressure_altitude_ft / 1000))
    return pressure_altitude_ft + (120 * (outside_air_temp_c - isa_temp_c))

def calculate_takeoff_roll(indicated_altitude_ft, qnh_hpa, temperature_c, weight_kg, wind_type, wind_speed, safety_factor):
    # Common calculations
    weight_lbs = weight_kg * 2.20462
    pressure_altitude = indicated_altitude_ft + ((1013.2 - qnh_hpa) * 27)
    density_altitude = calculate_density_altitude(pressure_altitude, temperature_c)

    # --- 0ft (Ground Roll) Calculation Path ---
    base_distance_0ft = _get_distance_at_temp_and_alt(temperature_c, pressure_altitude, TAKEOFF_DATA)
    weight_delta_0ft = _calculate_weight_correction(base_distance_0ft, weight_lbs)
    distance_after_weight_0ft = base_distance_0ft + weight_delta_0ft
    wind_delta_0ft = 0.0
    if wind_type == "Headwind":
        wind_delta_0ft = _calculate_headwind_correction(wind_speed)
    elif wind_type == "Tailwind":
        wind_delta_0ft = _calculate_tailwind_correction(wind_speed)
    distance_after_wind_0ft = distance_after_weight_0ft + wind_delta_0ft
    final_distance_ft_0ft = distance_after_wind_0ft * safety_factor
    final_distance_m_0ft = final_distance_ft_0ft * 0.3048

    # --- 50ft Obstacle Calculation Path ---
    base_distance_50ft = _get_distance_at_temp_and_alt(temperature_c, pressure_altitude, TAKEOFF_DATA_50Ft)
    weight_delta_50ft = _calculate_weight_correction_50ft(base_distance_50ft, weight_lbs)
    distance_after_weight_50ft = base_distance_50ft + weight_delta_50ft
    wind_delta_50ft = 0.0
    if wind_type == "Headwind":
        wind_delta_50ft = _calculate_headwind_correction_50ft(wind_speed)
    elif wind_type == "Tailwind":
        wind_delta_50ft = _calculate_tailwind_correction_50ft(wind_speed)
    distance_after_wind_50ft = distance_after_weight_50ft + wind_delta_50ft
    final_distance_ft_50ft = distance_after_wind_50ft * safety_factor
    final_distance_m_50ft = final_distance_ft_50ft * 0.3048
    
    return (
        # Common outputs for environmental conditions
        f"{pressure_altitude:.0f} ft",
        f"{density_altitude:.0f} ft",
        # 0ft outputs for Column 2
        f"{base_distance_0ft:.1f} ft",
        f"{weight_delta_0ft:.1f} ft",
        f"{distance_after_weight_0ft:.1f} ft",
        f"{wind_delta_0ft:.1f} ft",
        # 50ft outputs for Column 3
        f"{base_distance_50ft:.1f} ft",
        f"{weight_delta_50ft:.1f} ft",
        f"{distance_after_weight_50ft:.1f} ft",
        f"{wind_delta_50ft:.1f} ft",
        # Final outputs for Column 4
        f"{final_distance_ft_0ft:.0f} ft\n{final_distance_m_0ft:.0f} m",
        f"{final_distance_ft_50ft:.0f} ft\n{final_distance_m_50ft:.0f} m"
    )

# --- Custom CSS for Styling the Columns ---
custom_css = """
.input-column .gradio-slider label > span, .input-column .gradio-radio label > span { color: #1E8449 !important; font-weight: bold !important; }
.comp-0ft-column .gradio-textbox { background-color: #FEF9E7 !important; border-color: #F39C12 !important; }
.comp-0ft-column .gradio-textbox > label > span { color: #B9770E !important; }
.comp-50ft-column .gradio-textbox { background-color: #FADBD8 !important; border-color: #E74C3C !important; }
.comp-50ft-column .gradio-textbox > label > span { color: #C0392B !important; }
.output-column .gradio-textbox { background-color: #EBF5FB !important; border-color: #3498DB !important; }
.output-column .gradio-textbox > label > span { color: #2980B9 !important; }
.output-column textarea { font-size: 1.2em !important; font-weight: bold !important; text-align: center !important; }
"""

# --- Gradio Interface Definition ---
with gr.Blocks(theme=gr.themes.Soft(), css=custom_css) as demo:
    gr.Markdown("# PA-28-181 Takeoff Performance Calculator")
    
    with gr.Row():
        # Column 1: Inputs
        with gr.Column(scale=2, elem_classes="input-column"):
            altitude = gr.Slider(minimum=0, maximum=8000, value=2000, step=50, label="Indicated Altitude (ft)")
            qnh = gr.Slider(minimum=950, maximum=1050, value=1013.25, step=0.1, label="QNH (hPa)")
            temp = gr.Slider(minimum=-40, maximum=40, value=21, step=1, label="Outside Air Temp (°C)")
            weight = gr.Slider(minimum=930, maximum=1160, value=1090, step=5, label="Aircraft Mass (kg)")
            wind_type = gr.Radio(["Headwind", "Tailwind"], label="Wind Type", value="Headwind")
            wind_speed = gr.Slider(minimum=0, maximum=20, value=8, step=1, label="Wind Speed (knots)")
            safety_factor = gr.Slider(minimum=1.0, maximum=2.0, value=1.0, step=0.05, label="Safety Factor")

        # Column 2: 0ft Computations
        with gr.Column(scale=2, elem_classes="comp-0ft-column"):
            gr.Markdown("### Ground Roll (0ft) Computations")
            pressure_alt_output = gr.Textbox(label="1. Pressure Altitude", interactive=False)
            density_alt_output = gr.Textbox(label="2. Density Altitude", interactive=False)
            base_dist_output = gr.Textbox(label="3. Base Distance", interactive=False)
            weight_delta_output = gr.Textbox(label="4. Weight Correction Delta", interactive=False)
            dist_after_weight_output = gr.Textbox(label="5. Dist. After Weight Adj.", interactive=False)
            wind_delta_output_0ft = gr.Textbox(label="6. Wind Correction Delta", interactive=False)

        # Column 3: 50ft Computations
        with gr.Column(scale=2, elem_classes="comp-50ft-column"):
            gr.Markdown("### 50ft Obstacle Computations")
            base_dist_50ft_output = gr.Textbox(label="3. Base Distance", interactive=False)
            weight_delta_50ft_output = gr.Textbox(label="4. Weight Correction Delta", interactive=False)
            dist_after_weight_50ft_output = gr.Textbox(label="5. Dist. After Weight Adj.", interactive=False)
            wind_delta_output_50ft = gr.Textbox(label="6. Wind Correction Delta", interactive=False)

        # Column 4: Final Output
        with gr.Column(scale=1, elem_classes="output-column"):
            gr.Markdown("### Final Distances")
            output_distance_0ft = gr.Textbox(label="Ground Roll", interactive=False, lines=2)
            output_distance_50ft = gr.Textbox(label="To Clear 50ft", interactive=False, lines=2)

    inputs = [altitude, qnh, temp, weight, wind_type, wind_speed, safety_factor]
    outputs = [
        pressure_alt_output, density_alt_output,
        base_dist_output, weight_delta_output, dist_after_weight_output, wind_delta_output_0ft,
        base_dist_50ft_output, weight_delta_50ft_output, dist_after_weight_50ft_output, wind_delta_output_50ft,
        output_distance_0ft, output_distance_50ft
    ]
    
    btn = gr.Button("Calculate", variant="primary")
    btn.click(fn=calculate_takeoff_roll, inputs=inputs, outputs=outputs)

demo.launch()
