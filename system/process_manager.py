import psutil


class ProcessManager:
    def top_processes(self):
        processes = []

        for p in psutil.process_iter(
            ["pid", "name", "memory_percent"]
        ):
            try:
                processes.append(
                    p.info
                )
            except:
                pass

        return sorted(
            processes,
            key=lambda x:
            x["memory_percent"],
            reverse=True
        )[:10]