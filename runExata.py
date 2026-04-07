import os
import subprocess
import signal

import psutil


class ExataSimulator:
    def __init__(self, working_directory, executable_path, config_file):
        """
        初始化模拟器路径和配置
        :param working_directory: 工作目录路径
        :param executable_path: Exata 可执行文件路径
        :param config_file: 配置文件名称
        """
        self.working_directory = working_directory
        self.executable_path = executable_path
        self.config_file = config_file
        self.process = None  # 用于存储运行的进程对象

    def run_simulation(self):
        """
        切换目录并运行 Exata 模拟命令（实时输出日志）
        """
        command = [self.executable_path, self.config_file, '-animate', '-simulation']
        try:
            original_directory = os.getcwd()
            print(f"Original working directory: {original_directory}")
            print(f"Switching to: {self.working_directory}")
            print(f"commandcommandcommand to: {command}")
            # 使用 Popen 实现实时输出
            subprocess.Popen(
                    command, cwd=self.working_directory, text=True,
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE
            )
            #as process:
            #     for line in process.stdout:
            #         print(line, end='')  # 实时输出 stdout
            #     for line in process.stderr:
            #         print(f"ERROR: {line}", end='')  # 实时输出 stderr
            #
            # process.wait()  # 等待子进程完成
            # print(f"Simulation finished with exit code: {process.returncode}")

        except FileNotFoundError:
            print(f"Executable not found: {self.executable_path}")
        except Exception as e:
            print(f"An error occurred: {e}")

    def stop_simulation(self):
        """
        强制终止运行的模拟进程
        """
        pid = None
        for proc in psutil.process_iter(['pid', 'name']):
            if 'exata' in proc.info['name']:  # 查找 daphne 进程
                pid = proc.info['pid']
                break

        # 如果找到了 daphne 进程，尝试结束它
        if pid:
            try:
                os.kill(pid, signal.SIGTERM)  # 发送终止信号

                print(f"Exata 进程 {pid} 已被终止")

            except Exception as e:
                print(f"关闭 Exata 进程时发生错误: {e}")


if __name__ == "__main__":
    # 示例使用
    working_directory = r"C:\Users\lyk\Desktop\mytestdjango_five\scene_files\8plane"
    executable_path = r"D:\Scalable\exata7.3.0.0\exata\7.3.0.0\bin\exata.exe"
    config_file = "8plane.config"

    # 创建模拟器对象
    simulator = ExataSimulator(working_directory, executable_path, config_file)

    # 运行模拟
    simulator.run_simulation()

    # 示例：等待几秒后终止模拟
    # import time
    # time.sleep(5)  # 模拟运行时间
    # simulator.stop_simulation()
