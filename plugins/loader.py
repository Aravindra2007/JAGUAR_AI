import importlib
import os


class PluginLoader:
    def load_plugins(self):
        plugins = {}

        folder = "plugins/installed"

        for name in os.listdir(folder):
            path = (
                f"plugins.installed."
                f"{name}.plugin"
            )

            try:
                module = importlib.import_module(
                    path
                )

                plugins[name] = module.Plugin()

            except Exception as e:
                print(
                    f"Plugin {name} failed:",
                    e
                )

        return plugins