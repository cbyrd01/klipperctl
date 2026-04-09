"""Command menu screens — nested menus exposing all CLI functionality."""

from __future__ import annotations

from typing import Any, ClassVar

from textual.app import ComposeResult
from textual.containers import Vertical, VerticalScroll
from textual.screen import ModalScreen, Screen
from textual.widgets import (
    Button,
    Footer,
    Header,
    Input,
    Label,
    ListItem,
    ListView,
    Static,
)


class CommandMenuScreen(Screen):
    """Top-level command menu with all command groups."""

    BINDINGS: ClassVar[list[tuple[str, str, str]]] = [
        ("escape", "app.pop_screen", "Back"),
    ]

    DEFAULT_CSS = """
    CommandMenuScreen {
        layout: vertical;
    }
    CommandMenuScreen #menu-title {
        text-style: bold;
        text-align: center;
        padding: 1;
        background: $primary-background;
    }
    CommandMenuScreen ListView {
        height: 1fr;
    }
    CommandMenuScreen ListItem {
        padding: 1 2;
    }
    CommandMenuScreen ListItem Label {
        width: 100%;
    }
    """

    COMMAND_GROUPS: ClassVar[list[tuple[str, str, str]]] = [
        ("printer", "Printer Control", "Status, temps, GCode, restart, emergency stop"),
        ("print", "Print Jobs", "Start, pause, resume, cancel, progress"),
        ("files", "File Management", "List, upload, download, delete, move, copy"),
        ("history", "Print History", "Job history, totals, details"),
        ("queue", "Job Queue", "Queue status, add, start, pause, manage jobs"),
        ("server", "Server", "Server info, config, restart, logs, announcements"),
        ("system", "System", "System info, health, services, shutdown, reboot"),
        ("update", "Software Updates", "Update status, upgrade, rollback, recover"),
        ("power", "Power Devices", "List, status, on, off"),
        ("auth", "Authentication", "Login, logout, whoami, API key"),
        ("config", "Configuration", "Printer profiles, settings"),
    ]

    def compose(self) -> ComposeResult:
        yield Header()
        yield Static("Command Menu", id="menu-title")
        yield ListView(
            *[
                ListItem(
                    Label(f"[bold]{name}[/bold]  [dim]{desc}[/dim]"),
                    id=f"group-{key}",
                )
                for key, name, desc in self.COMMAND_GROUPS
            ],
            id="group-list",
        )
        yield Footer()

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        item_id = event.item.id or ""
        group_key = item_id.removeprefix("group-")
        screen_map: dict[str, type[Screen]] = {
            "printer": PrinterCommandScreen,
            "print": PrintCommandScreen,
            "files": FilesCommandScreen,
            "history": HistoryCommandScreen,
            "queue": QueueCommandScreen,
            "server": ServerCommandScreen,
            "system": SystemCommandScreen,
            "update": UpdateCommandScreen,
            "power": PowerCommandScreen,
            "auth": AuthCommandScreen,
            "config": ConfigCommandScreen,
        }
        screen_cls = screen_map.get(group_key)
        if screen_cls:
            self.app.push_screen(screen_cls())


# --- Confirmation Modal ---


class ConfirmModal(ModalScreen[bool]):
    """Modal confirmation dialog for destructive actions."""

    DEFAULT_CSS = """
    ConfirmModal {
        align: center middle;
    }
    #confirm-dialog {
        width: 50;
        height: auto;
        padding: 1 2;
        border: thick $error;
        background: $surface;
    }
    #confirm-dialog Label {
        margin-bottom: 1;
        width: 100%;
        text-align: center;
    }
    #confirm-buttons {
        height: auto;
        align: center middle;
    }
    #confirm-buttons Button {
        margin: 0 2;
    }
    """

    def __init__(self, message: str, **kwargs: object) -> None:
        super().__init__(**kwargs)
        self._message = message

    def compose(self) -> ComposeResult:
        from textual.containers import Horizontal

        with Vertical(id="confirm-dialog"):
            yield Label(self._message)
            with Horizontal(id="confirm-buttons"):
                yield Button("Confirm", variant="error", id="confirm-yes")
                yield Button("Cancel", variant="primary", id="confirm-no")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss(event.button.id == "confirm-yes")


# --- Result Display Modal ---


class ResultModal(ModalScreen):
    """Modal screen to display command results."""

    DEFAULT_CSS = """
    ResultModal {
        align: center middle;
    }
    #result-dialog {
        width: 70%;
        height: 70%;
        padding: 1 2;
        border: solid $primary;
        background: $surface;
    }
    #result-content {
        height: 1fr;
        overflow-y: auto;
    }
    #result-close {
        dock: bottom;
        width: 100%;
    }
    """

    def __init__(self, title: str, content: str, **kwargs: object) -> None:
        super().__init__(**kwargs)
        self._title = title
        self._content = content

    def compose(self) -> ComposeResult:
        with Vertical(id="result-dialog"):
            yield Static(f"[bold]{self._title}[/bold]")
            yield Static(self._content, id="result-content")
            yield Button("Close", variant="primary", id="result-close")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss()


# --- Base Command Screen ---


class _BaseCommandScreen(Screen):
    """Base class for command group screens."""

    BINDINGS: ClassVar[list[tuple[str, str, str]]] = [
        ("escape", "app.pop_screen", "Back"),
    ]

    DEFAULT_CSS = """
    _BaseCommandScreen, _BaseCommandScreen {
        layout: vertical;
    }
    .cmd-title {
        text-style: bold;
        text-align: center;
        padding: 1;
        background: $primary-background;
    }
    ListView {
        height: 1fr;
    }
    ListItem {
        padding: 1 2;
    }
    ListItem Label {
        width: 100%;
    }
    """

    group_name: ClassVar[str] = ""
    commands: ClassVar[list[tuple[str, str]]] = []

    def compose(self) -> ComposeResult:
        yield Header()
        yield Static(f"{self.group_name} Commands", classes="cmd-title")
        yield ListView(
            *[
                ListItem(Label(f"[bold]{name}[/bold]  [dim]{desc}[/dim]"), id=f"cmd-{name}")
                for name, desc in self.commands
            ],
        )
        yield Footer()

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        item_id = event.item.id or ""
        cmd_name = item_id.removeprefix("cmd-")
        self._run_command(cmd_name)

    def _run_command(self, cmd_name: str) -> None:
        """Override in subclasses to handle command execution."""

    def _execute_cli(self, args: list[str], title: str = "Result") -> None:
        """Execute a CLI command and show results in a modal."""
        from klipperctl.tui.app import KlipperApp

        app = self.app
        if isinstance(app, KlipperApp):
            app.run_cli_command(args, title)

    def _prompt_and_execute(
        self,
        title: str,
        fields: list[tuple[str, str, bool]],
        build_args: Any,
    ) -> None:
        """Push an input form screen for commands that need arguments."""
        self.app.push_screen(InputFormScreen(title=title, fields=fields, callback=build_args))


# --- Input Form Screen ---


class InputFormScreen(ModalScreen):
    """Modal form for collecting command arguments."""

    DEFAULT_CSS = """
    InputFormScreen {
        align: center middle;
    }
    #form-dialog {
        width: 60;
        height: auto;
        max-height: 80%;
        padding: 1 2;
        border: solid $primary;
        background: $surface;
    }
    #form-dialog Static {
        margin-bottom: 1;
    }
    .form-field {
        margin-bottom: 1;
    }
    .form-field Label {
        margin-bottom: 0;
    }
    #form-buttons {
        height: auto;
        align: center middle;
        margin-top: 1;
    }
    #form-buttons Button {
        margin: 0 2;
    }
    """

    def __init__(
        self,
        title: str,
        fields: list[tuple[str, str, bool]],
        callback: Any,
        **kwargs: object,
    ) -> None:
        super().__init__(**kwargs)
        self._title = title
        self._fields = fields  # (name, placeholder, required)
        self._callback = callback

    def compose(self) -> ComposeResult:
        from textual.containers import Horizontal

        with VerticalScroll(id="form-dialog"):
            yield Static(f"[bold]{self._title}[/bold]")
            for name, placeholder, _required in self._fields:
                with Vertical(classes="form-field"):
                    yield Label(name)
                    yield Input(placeholder=placeholder, id=f"field-{name}")
            with Horizontal(id="form-buttons"):
                yield Button("Execute", variant="success", id="form-submit")
                yield Button("Cancel", variant="primary", id="form-cancel")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "form-cancel":
            self.dismiss()
            return
        if event.button.id == "form-submit":
            values: dict[str, str] = {}
            for name, _placeholder, required in self._fields:
                inp = self.query_one(f"#field-{name}", Input)
                val = inp.value.strip()
                if required and not val:
                    self.notify(f"{name} is required", severity="error")
                    return
                values[name] = val
            args = self._callback(values)
            if args is not None:
                self.dismiss()
                from klipperctl.tui.app import KlipperApp

                app = self.app
                if isinstance(app, KlipperApp):
                    app.run_cli_command(args, self._title)


# --- Individual Command Group Screens ---


class PrinterCommandScreen(_BaseCommandScreen):
    group_name = "Printer"
    commands = [
        ("status", "Show printer status dashboard"),
        ("info", "Show raw Klipper host information"),
        ("temps", "Show all temperatures"),
        ("set-temp", "Set heater temperatures"),
        ("gcode", "Send GCode command"),
        ("gcode-help", "List available GCode commands"),
        ("objects", "List printer objects"),
        ("query", "Query printer object attributes"),
        ("endstops", "Query endstop states"),
        ("restart", "Soft restart Klipper"),
        ("firmware-restart", "Full firmware restart"),
        ("emergency-stop", "Emergency stop (destructive)"),
    ]

    def _run_command(self, cmd_name: str) -> None:
        simple = {
            "status": ["printer", "status"],
            "info": ["printer", "info"],
            "temps": ["printer", "temps", "--all"],
            "gcode-help": ["printer", "gcode-help"],
            "objects": ["printer", "objects"],
            "endstops": ["printer", "endstops"],
            "restart": ["printer", "restart"],
        }
        if cmd_name in simple:
            self._execute_cli(simple[cmd_name], cmd_name)
        elif cmd_name == "set-temp":
            self._prompt_and_execute(
                "Set Temperature",
                [("Hotend", "e.g. 210", False), ("Bed", "e.g. 60", False)],
                lambda v: _build_set_temp_args(v),
            )
        elif cmd_name == "gcode":
            self._prompt_and_execute(
                "Send GCode",
                [("Command", "e.g. G28", True)],
                lambda v: ["printer", "gcode", v["Command"]],
            )
        elif cmd_name == "query":
            self._prompt_and_execute(
                "Query Object",
                [("Object", "e.g. toolhead", True), ("Attrs", "e.g. position (optional)", False)],
                lambda v: (
                    ["printer", "query", v["Object"]]
                    + (["--attrs", v["Attrs"]] if v["Attrs"] else [])
                ),
            )
        elif cmd_name == "firmware-restart":
            self._execute_cli(["printer", "firmware-restart"], "Firmware Restart")
        elif cmd_name == "emergency-stop":

            def _on_confirm(confirmed: bool) -> None:
                if confirmed:
                    self._execute_cli(["printer", "emergency-stop", "--yes"], "Emergency Stop")

            self.app.push_screen(
                ConfirmModal("Are you sure you want to EMERGENCY STOP?"), _on_confirm
            )


def _build_set_temp_args(values: dict[str, str]) -> list[str] | None:
    args = ["printer", "set-temp"]
    if values.get("Hotend"):
        args.extend(["--hotend", values["Hotend"]])
    if values.get("Bed"):
        args.extend(["--bed", values["Bed"]])
    if len(args) == 2:
        return None
    return args


class PrintCommandScreen(_BaseCommandScreen):
    group_name = "Print"
    commands = [
        ("start", "Start a print"),
        ("pause", "Pause current print"),
        ("resume", "Resume paused print"),
        ("cancel", "Cancel current print (destructive)"),
        ("progress", "Show print progress"),
    ]

    def _run_command(self, cmd_name: str) -> None:
        if cmd_name == "start":
            self._prompt_and_execute(
                "Start Print",
                [("Filename", "e.g. benchy.gcode", True)],
                lambda v: ["print", "start", v["Filename"]],
            )
        elif cmd_name == "pause":
            self._execute_cli(["print", "pause"], "Pause Print")
        elif cmd_name == "resume":
            self._execute_cli(["print", "resume"], "Resume Print")
        elif cmd_name == "cancel":

            def _on_confirm(confirmed: bool) -> None:
                if confirmed:
                    self._execute_cli(["print", "cancel", "--yes"], "Cancel Print")

            self.app.push_screen(
                ConfirmModal("Are you sure you want to cancel the print?"), _on_confirm
            )
        elif cmd_name == "progress":
            self._execute_cli(["print", "progress"], "Print Progress")


class FilesCommandScreen(_BaseCommandScreen):
    group_name = "Files"
    commands = [
        ("list", "List files"),
        ("info", "File metadata"),
        ("upload", "Upload a file"),
        ("download", "Download a file"),
        ("delete", "Delete a file (destructive)"),
        ("move", "Move/rename a file"),
        ("copy", "Copy a file"),
        ("mkdir", "Create directory"),
        ("rmdir", "Remove directory (destructive)"),
        ("thumbnails", "Show file thumbnails"),
        ("scan", "Rescan file metadata"),
    ]

    def _run_command(self, cmd_name: str) -> None:
        if cmd_name == "list":
            self._execute_cli(["files", "list"], "File List")
        elif cmd_name == "info":
            self._prompt_and_execute(
                "File Info",
                [("Filename", "e.g. benchy.gcode", True)],
                lambda v: ["files", "info", v["Filename"]],
            )
        elif cmd_name == "upload":
            self._prompt_and_execute(
                "Upload File",
                [
                    ("File", "Local file path", True),
                    ("Path", "Remote subdirectory (optional)", False),
                ],
                lambda v: (
                    ["files", "upload", v["File"]] + (["--path", v["Path"]] if v["Path"] else [])
                ),
            )
        elif cmd_name == "download":
            self._prompt_and_execute(
                "Download File",
                [
                    ("Filename", "Remote filename", True),
                    ("Output", "Local output path (optional)", False),
                ],
                lambda v: (
                    ["files", "download", v["Filename"]]
                    + (["--output", v["Output"]] if v["Output"] else [])
                ),
            )
        elif cmd_name == "delete":

            def _prompt_delete() -> None:
                self._prompt_and_execute(
                    "Delete File",
                    [("Filename", "File to delete", True)],
                    lambda v: ["files", "delete", v["Filename"], "--yes"],
                )

            def _on_confirm(confirmed: bool) -> None:
                if confirmed:
                    _prompt_delete()

            self.app.push_screen(
                ConfirmModal("Are you sure you want to delete a file?"), _on_confirm
            )
        elif cmd_name == "move":
            self._prompt_and_execute(
                "Move File",
                [("Source", "Source path", True), ("Dest", "Destination path", True)],
                lambda v: ["files", "move", v["Source"], v["Dest"]],
            )
        elif cmd_name == "copy":
            self._prompt_and_execute(
                "Copy File",
                [("Source", "Source path", True), ("Dest", "Destination path", True)],
                lambda v: ["files", "copy", v["Source"], v["Dest"]],
            )
        elif cmd_name == "mkdir":
            self._prompt_and_execute(
                "Create Directory",
                [("Path", "Directory path", True)],
                lambda v: ["files", "mkdir", v["Path"]],
            )
        elif cmd_name == "rmdir":

            def _prompt_rmdir() -> None:
                self._prompt_and_execute(
                    "Remove Directory",
                    [("Path", "Directory path", True)],
                    lambda v: ["files", "rmdir", v["Path"], "--force", "--yes"],
                )

            def _on_confirm_rmdir(confirmed: bool) -> None:
                if confirmed:
                    _prompt_rmdir()

            self.app.push_screen(
                ConfirmModal("Are you sure you want to remove a directory?"),
                _on_confirm_rmdir,
            )
        elif cmd_name == "thumbnails":
            self._prompt_and_execute(
                "Thumbnails",
                [("Filename", "GCode file", True)],
                lambda v: ["files", "thumbnails", v["Filename"]],
            )
        elif cmd_name == "scan":
            self._prompt_and_execute(
                "Scan Metadata",
                [("Filename", "File to rescan", True)],
                lambda v: ["files", "scan", v["Filename"]],
            )


class HistoryCommandScreen(_BaseCommandScreen):
    group_name = "History"
    commands = [
        ("list", "Recent print jobs"),
        ("show", "Job details"),
        ("totals", "Aggregate print statistics"),
        ("reset-totals", "Reset print totals (destructive)"),
    ]

    def _run_command(self, cmd_name: str) -> None:
        if cmd_name == "list":
            self._execute_cli(["history", "list"], "Print History")
        elif cmd_name == "show":
            self._prompt_and_execute(
                "Job Details",
                [("Job ID", "Job ID to show", True)],
                lambda v: ["history", "show", v["Job ID"]],
            )
        elif cmd_name == "totals":
            self._execute_cli(["history", "totals"], "Print Totals")
        elif cmd_name == "reset-totals":

            def _on_confirm(confirmed: bool) -> None:
                if confirmed:
                    self._execute_cli(["history", "reset-totals", "--yes"], "Reset Totals")

            self.app.push_screen(
                ConfirmModal("Are you sure you want to reset print totals?"),
                _on_confirm,
            )


class QueueCommandScreen(_BaseCommandScreen):
    group_name = "Queue"
    commands = [
        ("status", "Queue state and pending jobs"),
        ("add", "Add files to queue"),
        ("start", "Start processing queue"),
        ("pause", "Pause queue"),
        ("jump", "Move job to front"),
        ("remove", "Remove job from queue"),
    ]

    def _run_command(self, cmd_name: str) -> None:
        if cmd_name == "status":
            self._execute_cli(["queue", "status"], "Queue Status")
        elif cmd_name == "add":
            self._prompt_and_execute(
                "Add to Queue",
                [("Files", "Space-separated filenames", True)],
                lambda v: ["queue", "add", *v["Files"].split()],
            )
        elif cmd_name == "start":
            self._execute_cli(["queue", "start"], "Start Queue")
        elif cmd_name == "pause":
            self._execute_cli(["queue", "pause"], "Pause Queue")
        elif cmd_name == "jump":
            self._prompt_and_execute(
                "Jump Job",
                [("Job ID", "Job ID to move to front", True)],
                lambda v: ["queue", "jump", v["Job ID"]],
            )
        elif cmd_name == "remove":
            self._prompt_and_execute(
                "Remove Job",
                [("Job IDs", "Space-separated job IDs", True)],
                lambda v: ["queue", "remove", *v["Job IDs"].split()],
            )


class ServerCommandScreen(_BaseCommandScreen):
    group_name = "Server"
    commands = [
        ("info", "Server info (version, components)"),
        ("config", "Moonraker configuration"),
        ("restart", "Restart Moonraker"),
        ("logs", "Server log entries"),
        ("logs-rollover", "Trigger log rollover"),
        ("announcements", "Server announcements"),
        ("dismiss", "Dismiss an announcement"),
    ]

    def _run_command(self, cmd_name: str) -> None:
        simple = {
            "info": ["server", "info"],
            "config": ["server", "config"],
            "restart": ["server", "restart"],
            "logs": ["server", "logs"],
            "logs-rollover": ["server", "logs-rollover"],
            "announcements": ["server", "announcements"],
        }
        if cmd_name in simple:
            self._execute_cli(simple[cmd_name], cmd_name.replace("-", " ").title())
        elif cmd_name == "dismiss":
            self._prompt_and_execute(
                "Dismiss Announcement",
                [("Entry ID", "Announcement entry ID", True)],
                lambda v: ["server", "dismiss", v["Entry ID"]],
            )


class SystemCommandScreen(_BaseCommandScreen):
    group_name = "System"
    commands = [
        ("info", "System info (OS, CPU, memory)"),
        ("health", "CPU temp, uptime, memory usage"),
        ("services", "System services status"),
        ("service-restart", "Restart a service"),
        ("service-stop", "Stop a service"),
        ("service-start", "Start a service"),
        ("peripherals", "USB, serial, video, CAN devices"),
        ("shutdown", "Shutdown system (destructive)"),
        ("reboot", "Reboot system (destructive)"),
    ]

    def _run_command(self, cmd_name: str) -> None:
        simple = {
            "info": ["system", "info"],
            "health": ["system", "health"],
            "services": ["system", "services"],
            "peripherals": ["system", "peripherals"],
        }
        if cmd_name in simple:
            self._execute_cli(simple[cmd_name], cmd_name.title())
        elif cmd_name.startswith("service-"):
            action = cmd_name.split("-", 1)[1]
            self._prompt_and_execute(
                f"Service {action.title()}",
                [("Service", "Service name", True)],
                lambda v, a=action: ["system", "service", a, v["Service"]],
            )
        elif cmd_name in ("shutdown", "reboot"):

            def _on_confirm(confirmed: bool, action: str = cmd_name) -> None:
                if confirmed:
                    self._execute_cli(["system", action, "--yes"], action.title())

            self.app.push_screen(
                ConfirmModal(f"Are you sure you want to {cmd_name} the system?"),
                _on_confirm,
            )


class UpdateCommandScreen(_BaseCommandScreen):
    group_name = "Update"
    commands = [
        ("status", "Update status for all components"),
        ("upgrade", "Upgrade components"),
        ("rollback", "Rollback a component"),
        ("recover", "Recover a component"),
    ]

    def _run_command(self, cmd_name: str) -> None:
        if cmd_name == "status":
            self._execute_cli(["update", "status"], "Update Status")
        elif cmd_name == "upgrade":
            self._prompt_and_execute(
                "Upgrade",
                [("Name", "Component name (blank for all)", False)],
                lambda v: ["update", "upgrade"] + (["--name", v["Name"]] if v["Name"] else []),
            )
        elif cmd_name == "rollback":
            self._prompt_and_execute(
                "Rollback",
                [("Name", "Component name", True)],
                lambda v: ["update", "rollback", v["Name"]],
            )
        elif cmd_name == "recover":
            self._prompt_and_execute(
                "Recover",
                [("Name", "Component name", True)],
                lambda v: ["update", "recover", v["Name"]],
            )


class PowerCommandScreen(_BaseCommandScreen):
    group_name = "Power"
    commands = [
        ("list", "List configured power devices"),
        ("status", "Power device status"),
        ("on", "Turn on device (destructive)"),
        ("off", "Turn off device (destructive)"),
    ]

    def _run_command(self, cmd_name: str) -> None:
        if cmd_name == "list":
            self._execute_cli(["power", "list"], "Power Devices")
        elif cmd_name == "status":
            self._execute_cli(["power", "status", "--all"], "Power Status")
        elif cmd_name in ("on", "off"):

            def _prompt_power(action: str = cmd_name) -> None:
                self._prompt_and_execute(
                    f"Power {action.upper()}",
                    [("Device", "Device name", True)],
                    lambda v, a=action: ["power", a, v["Device"], "--yes"],
                )

            def _on_confirm(confirmed: bool) -> None:
                if confirmed:
                    _prompt_power()

            self.app.push_screen(
                ConfirmModal(f"Are you sure you want to turn {cmd_name} a power device?"),
                _on_confirm,
            )


class AuthCommandScreen(_BaseCommandScreen):
    group_name = "Auth"
    commands = [
        ("login", "Login to Moonraker"),
        ("logout", "Logout"),
        ("whoami", "Show current user"),
        ("info", "Authorization module info"),
        ("api-key", "Show API key"),
    ]

    def _run_command(self, cmd_name: str) -> None:
        simple = {
            "logout": ["auth", "logout"],
            "whoami": ["auth", "whoami"],
            "info": ["auth", "info"],
            "api-key": ["auth", "api-key"],
        }
        if cmd_name in simple:
            self._execute_cli(simple[cmd_name], cmd_name.title())
        elif cmd_name == "login":
            self._prompt_and_execute(
                "Login",
                [("Username", "Username", True), ("Password", "Password", True)],
                lambda v: [
                    "auth",
                    "login",
                    "--username",
                    v["Username"],
                    "--password",
                    v["Password"],
                ],
            )


class ConfigCommandScreen(_BaseCommandScreen):
    group_name = "Config"
    commands = [
        ("show", "Show current configuration"),
        ("printers", "List configured printers"),
        ("set", "Set a configuration value"),
        ("add-printer", "Add a printer profile"),
        ("remove-printer", "Remove a printer profile"),
        ("use", "Switch active printer"),
    ]

    def _run_command(self, cmd_name: str) -> None:
        simple = {
            "show": ["config", "show"],
            "printers": ["config", "printers"],
        }
        if cmd_name in simple:
            self._execute_cli(simple[cmd_name], cmd_name.title())
        elif cmd_name == "set":
            self._prompt_and_execute(
                "Set Config",
                [("Key", "Configuration key", True), ("Value", "Value", True)],
                lambda v: ["config", "set", v["Key"], v["Value"]],
            )
        elif cmd_name == "add-printer":
            self._prompt_and_execute(
                "Add Printer",
                [
                    ("Name", "Printer profile name", True),
                    ("URL", "Printer URL", True),
                    ("API Key", "API key (optional)", False),
                ],
                lambda v: (
                    ["config", "add-printer", v["Name"], v["URL"]]
                    + (["--api-key", v["API Key"]] if v["API Key"] else [])
                ),
            )
        elif cmd_name == "remove-printer":
            self._prompt_and_execute(
                "Remove Printer",
                [("Name", "Printer name to remove", True)],
                lambda v: ["config", "remove-printer", v["Name"]],
            )
        elif cmd_name == "use":
            self._prompt_and_execute(
                "Switch Printer",
                [("Name", "Printer name to activate", True)],
                lambda v: ["config", "use", v["Name"]],
            )
