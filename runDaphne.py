import os
import subprocess
import signal

# 定义 Daphne 启动命令
DAPHNE_COMMAND = ["daphne", "-b", "0.0.0.0", "-p", "8000", "mytest.asgi:application"]

def get_daphne_pid_windows():
    """
    获取正在运行的 Daphne 进程的 PID (Windows)。
    """
    try:
        # 使用 tasklist 查找 Daphne 进程
        result = subprocess.check_output("tasklist | findstr daphne", shell=True)
        lines = result.decode('utf-8').strip().split("\n")
        for line in lines:
            parts = line.split()
            # PID 是 tasklist 输出的第二列
            return int(parts[1])
    except subprocess.CalledProcessError:
        # 如果没有找到进程，返回 None
        return None

def stop_daphne_windows(pid):
    """
    停止运行中的 Daphne 进程 (Windows)。
    """
    try:
        print(f"正在停止 Daphne 进程 (PID: {pid})...")
        os.kill(pid, signal.SIGTERM)  # Windows 上推荐使用 SIGTERM
        print(f"Daphne 进程 (PID: {pid}) 已停止。")
    except Exception as e:
        print(f"停止 Daphne 进程时发生错误: {e}")

def start_daphne():
    """
    启动 Daphne 服务并实时显示输出。
    """
    try:
        print("正在启动 Daphne 服务...")
        # 使用 Popen 启动并捕获实时输出
        process = subprocess.Popen(
            DAPHNE_COMMAND,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            shell=True
        )

        # 实时打印输出
        while True:
            output = process.stdout.readline()
            if output == "" and process.poll() is not None:
                break
            if output:
                print(output.strip())

        # 打印结束状态
        return_code = process.poll()
        print(f"Daphne 服务已退出，返回码：{return_code}")

    except Exception as e:
        print(f"启动 Daphne 服务时发生错误: {e}")

if __name__ == "__main__":
    # 查找是否有运行中的 Daphne 进程
    pid = get_daphne_pid_windows()

    if pid:
        # 如果有运行中的进程，先停止
        stop_daphne_windows(pid)

    # 启动 Daphne 服务
    start_daphne()
