import os
from pathlib import Path

from services.environment_service import VENV_DIRNAME, CommandResult


def mock_command_runner(command: list[str], cwd: Path) -> CommandResult:
    if "-m" in command and "venv" in command:
        venv_path = cwd / VENV_DIRNAME
        venv_path.mkdir(parents=True, exist_ok=True)
        scripts_dir = "Scripts" if os.name == "nt" else "bin"
        pip_name = "pip.exe" if os.name == "nt" else "pip"
        python_name = "python.exe" if os.name == "nt" else "python"
        scripts_path = venv_path / scripts_dir
        scripts_path.mkdir(parents=True, exist_ok=True)
        (scripts_path / pip_name).write_text("", encoding="utf-8")
        (scripts_path / python_name).write_text("", encoding="utf-8")
        return CommandResult(0, "virtual environment created\n", "")

    if len(command) >= 4 and command[1:4] == ["-m", "pip", "install"]:
        return CommandResult(0, "requirements installed\n", "")

    if command and any(part.endswith("train.py") for part in command):
        return CommandResult(0, "Training complete.\n", "")

    return CommandResult(1, "", f"unexpected command: {command}\n")


def failing_train_command_runner(command: list[str], cwd: Path) -> CommandResult:
    if command and any(part.endswith("train.py") for part in command):
        return CommandResult(1, "", "training failed\n")
    return mock_command_runner(command, cwd)
