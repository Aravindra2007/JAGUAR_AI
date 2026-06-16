import psutil


class NetworkMonitor:
    def stats(self):
        net = psutil.net_io_counters()

        return {
            "sent": round(
                net.bytes_sent / (1024 ** 2),
                2
            ),
            "received": round(
                net.bytes_recv / (1024 ** 2),
                2
            )
        }