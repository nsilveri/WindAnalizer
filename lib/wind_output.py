# Wind scale factor indices
VOLT = 0
SPEED = 1

# Default wind scale [V, mt/s]
min_scale = [0.12, 2.5]
max_scale = [0.62, 10.3]

def voltage_to_wind_speed(voltage, min_s=min_scale, max_s=max_scale):
    if voltage is None:
        return None, True

    out_of_scale = not (min_s[VOLT] <= voltage <= max_s[VOLT])

    scale = (max_s[SPEED] - min_s[SPEED]) / (max_s[VOLT] - min_s[VOLT])
    wind_speed = min_s[SPEED] + scale * (voltage - min_s[VOLT])

    return wind_speed, out_of_scale


def print_wind_info(wind_speed, out_of_scale):
    if wind_speed is None:
        print("No voltage reading available")
        return

    if out_of_scale:
        print("Wind Speed: {:.2f} mt/s, WARNING: Wind Speed Out of Scale".format(wind_speed))
    else:
        print("Wind Speed: {:.2f} mt/s".format(wind_speed))


