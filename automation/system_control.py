import os


class SystemControl:
    def shutdown(self):
        os.system(
            "shutdown /s /t 1"
        )

    def restart(self):
        os.system(
            "shutdown /r /t 1"
        )

    def sleep(self):
        os.system(
            "rundll32.exe "
            "powrprof.dll,"
            "SetSuspendState 0,1,0"
        )