import psutil


class CPUMonitor:
    def usage(self):
        return psutil.cpu_percent()

    def cores(self):
        return psutil.cpu_count()

    def frequency(self):
        freq = psutil.cpu_freq()

        if freq:
            return freq.current

        return 0