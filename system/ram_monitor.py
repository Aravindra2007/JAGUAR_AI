import psutil


class RAMMonitor:
    def usage(self):
        return psutil.virtual_memory().percent

    def total(self):
        return round(
            psutil.virtual_memory().total
            / (1024 ** 3),
            2
        )

    def available(self):
        return round(
            psutil.virtual_memory().available
            / (1024 ** 3),
            2
        )