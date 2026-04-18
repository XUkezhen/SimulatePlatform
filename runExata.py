import os
import signal
import subprocess
from pathlib import Path

import psutil


class ExataSimulator:
    def __init__(self, working_directory, executable_path, config_file):
        """
        初始化模拟器路径和配置。
        :param working_directory: 工作目录路径
        :param executable_path: Exata 可执行文件路径
        :param config_file: 配置文件名称
        """
        self.working_directory = working_directory
        self.executable_path = executable_path
        self.config_file = config_file
        self.process = None

    def run_simulation(self):
        """
        切换目录并运行 Exata 模拟命令。
        """
        command = [self.executable_path, self.config_file, "-animate", "-simulation"]
        try:
            original_directory = os.getcwd()
            print(f"Original working directory: {original_directory}")
            print(f"Switching to: {self.working_directory}")
            print(f"commandcommandcommand to: {command}")
            subprocess.Popen(
                command,
                cwd=self.working_directory,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
        except FileNotFoundError:
            print(f"Executable not found: {self.executable_path}")
        except Exception as e:
            print(f"An error occurred: {e}")

    def stop_simulation(self):
        """
        强制终止正在运行的模拟进程。
        """
        pid = None
        for proc in psutil.process_iter(["pid", "name"]):
            if "exata" in proc.info["name"]:
                pid = proc.info["pid"]
                break

        if pid:
            try:
                os.kill(pid, signal.SIGTERM)
                print(f"Exata 进程 {pid} 已被终止")
            except Exception as e:
                print(f"关闭 Exata 进程时发生错误: {e}")


if __name__ == "__main__":
    default_working_directory = Path(__file__).resolve().parent / "scene_files" / "8plane"
    default_executable_path = Path(__file__).resolve().parent.parent / "exata.exe"

    working_directory = os.getenv("EXATA_WORKING_DIRECTORY", str(default_working_directory))
    executable_path = os.getenv("EXATA_EXECUTABLE_PATH", str(default_executable_path))
    config_file = os.getenv("EXATA_CONFIG_FILE", "8plane.config")

    simulator = ExataSimulator(working_directory, executable_path, config_file)
    simulator.run_simulation()
