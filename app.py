from flask import Flask, render_template, jsonify, redirect, url_for, request, flash
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
import psutil
import mmap
import struct

app = Flask(__name__)
app.secret_key = "your_secret_key"

# Flask-Login setup
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"

# Dummy user for demonstration purposes
class User(UserMixin):
    def __init__(self, id):
        self.id = id

# Hardcoded username and password
users = {"admin": "password123"}

@login_manager.user_loader
def load_user(user_id):
    return User(user_id)

# Login route
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        if username in users and users[username] == password:
            user = User(username)
            login_user(user)
            flash("Login successful!", "success")
            return redirect(url_for("index"))
        else:
            flash("Invalid username or password.", "danger")
    return render_template("login.html")

# Logout route
@app.route("/logout")
@login_required
def logout():
    logout_user()
    flash("You have been logged out.", "info")
    return redirect(url_for("login"))

# Utility function to convert bytes to GB
def bytes_to_gigabytes(bytes_value):
    return round(bytes_value / (1024 ** 3), 2)

# Main Dashboard Route
@app.route("/")
@login_required
def index():
    """Render the main dashboard."""
    return render_template("index.html", user=current_user)

# Dynamic Section Route
@app.route("/<section>")
@login_required
def section_page(section):
    """Render the details page for a specific section."""
    # Fetch real-time data for each section
    data = fetch_section_data(section.lower())

    # If the section is invalid, return an error page
    if not data:
        return render_template("error.html", section=section), 404

    return render_template("details.html", section=section.capitalize(), data=data)

def fetch_section_data(section):
    """Fetch real-time data for the requested section."""
    if section == "cpu":
        # CPU data
        cpu_utilisation = psutil.cpu_percent(interval=1, percpu=True)
        average_utilisation = sum(cpu_utilisation) / len(cpu_utilisation)
        cpu_temp = get_cpu_temperature()
        return {
            "Average Utilisation": f"{average_utilisation:.2f}%",
            "Temperature": f"{cpu_temp}°C" if cpu_temp is not None else "Not Available"
        }

    elif section == "gpu":
        # GPU data
        try:
            from py3nvml.py3nvml import nvmlInit, nvmlDeviceGetHandleByIndex, nvmlDeviceGetTemperature, nvmlDeviceGetUtilizationRates
            nvmlInit()
            handle = nvmlDeviceGetHandleByIndex(0)
            gpu_temp = nvmlDeviceGetTemperature(handle, 0)
            gpu_utilisation = nvmlDeviceGetUtilizationRates(handle).gpu
            return {
                "Temperature": f"{gpu_temp}°C",
                "Utilisation": f"{gpu_utilisation}%"
            }
        except:
            return {
                "Temperature": "Not Available",
                "Utilisation": "Not Available"
            }

    elif section == "ram":
        # RAM data
        ram_utilisation = psutil.virtual_memory()
        return {
            "Used": f"{bytes_to_gigabytes(ram_utilisation.used)} GB",
            "Total": f"{bytes_to_gigabytes(ram_utilisation.total)} GB",
            "Utilisation": f"{ram_utilisation.percent}%"
        }

    elif section == "storage":
        # Storage data
        storage_utilisation = {}
        for partition in psutil.disk_partitions(all=False):
            try:
                usage = psutil.disk_usage(partition.mountpoint)
                storage_utilisation[partition.device] = {
                    "Used": f"{bytes_to_gigabytes(usage.used)} GB",
                    "Total": f"{bytes_to_gigabytes(usage.total)} GB",
                    "Utilisation": f"{usage.percent}%"
                }
            except PermissionError:
                storage_utilisation[partition.device] = "Permission Denied"
        return storage_utilisation

    elif section == "coolant":
        # Coolant (Water temperature) data
        water_temp = read_hwinfo_shared_memory()
        return {
            "Temperature": f"{water_temp:.2f}°C" if water_temp is not None else "Not Available"
        }

    return None

# Fetch CPU Temperature using OpenHardwareMonitor
def get_cpu_temperature():
    try:
        from OpenHardwareMonitor.Hardware import Computer
        computer = Computer()
        computer.CPUEnabled = True
        computer.Open()

        for hardware in computer.Hardware:
            if hardware.HardwareType == 'CPU':
                hardware.Update()
                for sensor in hardware.Sensors:
                    if sensor.SensorType == 'Temperature':
                        return sensor.Value
    except:
        return None

# Fetch coolant (T-Sensor) temperature from HWInfo Shared Memory
def read_hwinfo_shared_memory():
    try:
        mapping = mmap.mmap(0, 0, "Global\\HWiNFO_SENS_SM2", access=mmap.ACCESS_READ)
        num_sensors = struct.unpack("H", mapping[0:2])[0]
        for i in range(num_sensors):
            offset = 4 + (i * 128)
            sensor_name = mapping[offset:offset + 128].decode("utf-16", errors="ignore").strip("\x00")
            value = struct.unpack("f", mapping[offset + 68:offset + 72])[0]
            if "T-Sensor" in sensor_name:
                mapping.close()
                return value
        mapping.close()
    except:
        return None

@app.route('/api/<section>')
def api_section_data(section):
    """API endpoint to fetch real-time section data."""
    data = fetch_section_data(section.lower())
    if not data:
        return jsonify({"error": "Invalid section"}), 404
    return jsonify(data)

if __name__ == '__main__':
    app.run(debug=True)
