import psutil


class BatteryMonitor:
    def percentage(self):
        battery = psutil.sensors_battery()

        if battery:
            return battery.percent

        return -1

    def charging(self):
        battery = psutil.sensors_battery()

        if battery:
            return battery.power_plugged

        return False