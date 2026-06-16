from plugins.loader import PluginLoader


class PluginManager:
    def __init__(self):
        self.loader = PluginLoader()
        self.plugins = (
            self.loader.load_plugins()
        )

    def execute(
        self,
        name,
        assistant,
        command
    ):
        plugin = self.plugins.get(
            name
        )

        if plugin:
            return plugin.execute(
                assistant,
                command
            )

        return False