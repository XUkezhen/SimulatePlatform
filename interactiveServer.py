import socket
import threading

def start_server(host='127.0.0.1', port=12345):
    # 创建一个TCP/IP套接字
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        # 绑定套接字到地址和端口
        server_socket.bind((host, port))
        print(f"服务器启动，监听地址: {host}:{port}")

        # 监听连接
        server_socket.listen(5)  # 最大等待连接数为5
        print("等待客户端连接...")

        while True:
            # 接受客户端连接
            client_socket, client_address = server_socket.accept()
            print(f"客户端已连接：{client_address}")

            # 启动接收和发送的线程
            threading.Thread(target=handle_client_receive, args=(client_socket,)).start()
            threading.Thread(target=handle_client_send, args=(client_socket,)).start()

    except Exception as e:
        print(f"服务器出错：{e}")
    finally:
        server_socket.close()
        print("服务器已关闭")

def handle_client_receive(client_socket):
    try:
        while True:
            # 接收客户端消息
            data = client_socket.recv(10240)  # 每次接收最大1024字节
            if not data:
                print("客户端断开连接")
                break

            print(f"收到客户端的消息: {data.decode('utf-8')}")
    except Exception as e:
        print(f"接收数据时出错：{e}")
    finally:
        client_socket.close()

def handle_client_send(client_socket):
    try:
        while True:
            # 服务器输入命令或消息
            server_message = input("请输入发送给客户端的消息（输入 'exit' 结束会话，'cmd' 执行命令）：")

            # 判断输入是否为空或者为退出命令
            if server_message.lower() == 'exit':
                print("结束会话")
                break


            # 发送消息到客户端
            client_socket.sendall(server_message.encode('utf-8'))
            print(f"发送给客户端的消息：{server_message}")
    except Exception as e:
        print(f"发送数据时出错：{e}")
    finally:
        client_socket.close()



if __name__ == "__main__":
    start_server()
