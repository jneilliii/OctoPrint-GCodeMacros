import octoprint.plugin

from octoprint_gcode_macro import _version

__version__ = _version.get_versions()["version"]
del _version


# These macros will be ignored, because they are known to be already taken
FORBIDDEN_MACROS = [
    "cancel",
    "abort",
    "pause",
    "resume",
]


class GcodeMacroPlugin(
    octoprint.plugin.SettingsPlugin,
    octoprint.plugin.AssetPlugin,
    octoprint.plugin.TemplatePlugin,
):
    def __init__(self):
        super().__init__()
        self.macros = {}

    # SettingsPlugin mixin
    def get_settings_defaults(self):
        return {
            "macros": [
                {
                    "command": "example",
                    "content": "M117 Hello!",
                    "description": "An example macro you can customize",
                }
            ]
        }

    def initialize(self):
        self.reload_macros()

    def on_settings_save(self, data):
        octoprint.plugin.SettingsPlugin.on_settings_save(self, data)
        self.reload_macros()

    def reload_macros(self):
        self.macros = {}
        macros = self._settings.get(["macros"], merged=True)
        for macro in macros:
            self.macros[macro["command"]] = macro["content"]

    # AssetPlugin mixin
    def get_assets(self):
        return {
            "js": ["dist/gcode_macro.js"],
            "css": ["dist/gcode_macro.css"],
        }

    def gcode_queueing(
        self,
        c,
        p,
        command,
        ct,
        g,
        subcode=None,
        tags=None,
        *args,
        **kwargs,
    ):
        if command.startswith("@"):
            return self.render_macro(command)

    def render_macro(self, command, level=0):
        """
        Render a macro from a command
        :param command: string, macro to lookup
        :param level: int, number of sub-macros that have been rendered
        :return: list, list of commands to send to the printer
        """
        command = command.strip("@")

        if command in FORBIDDEN_MACROS or command not in self.macros.keys():
            # Forbidden, illegal, not a command, ignore, no command
            return []

        self._logger.debug(f"Rendering macro for @ command @{command}")

        try:
            content = self.macros[command]
        except KeyError as e:
            # In theory this shouldn't happen with the check above, but if it does I want to know
            self._logger.exception(e)
            return []

        if content and isinstance(content, str):
            # Split long string into list of commands for OctoPrint to digest
            commands = content.split("\n")
            # Strip gcode comments & whitespace
            commands = list(map(lambda x: x.split(";")[0].strip(), commands))

            if level <= 4:
                # Only render up to 5 levels (0 start)
                # Seems like a sane limit, don't want crashes from circular macros
                for cmd in commands:
                    if cmd.startswith("@"):
                        # Recursively render for each @ command in macro
                        commands = commands + self.render_macro(cmd, level=level + 1)

            return commands

        return []

    # Software update hook
    def get_update_information(self):
        return {
            "gcode_macro": {
                "displayName": "Gcode Macros",
                "displayVersion": self._plugin_version,
                # version check: github repository
                "type": "github_release",
                "user": "cp2004",
                "repo": "OctoPrint-GcodeMacros",
                "current": self._plugin_version,
                "stable_branch": {
                    "name": "Stable",
                    "branch": "master",
                    "comittish": ["master"],
                },
                "prerelease_branches": [
                    {
                        "name": "Release Candidate",
                        "branch": "pre-release",
                        "comittish": ["pre-release", "master"],
                    }
                ],
                # update method: pip
                "pip": "https://github.com/cp2004/OctoPrint-GcodeMacros/releases/download/{target_version}/release.zip",
            }
        }


__plugin_name__ = "Gcode Macros"
__plugin_pythoncompat__ = ">=3.6,<4"
__plugin_version__ = __version__


def __plugin_load__():
    global __plugin_implementation__
    __plugin_implementation__ = GcodeMacroPlugin()

    global __plugin_hooks__
    __plugin_hooks__ = {
        "octoprint.plugin.softwareupdate.check_config": __plugin_implementation__.get_update_information,
        "octoprint.comm.protocol.gcode.queuing": __plugin_implementation__.gcode_queueing,
    }
