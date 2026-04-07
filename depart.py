import binascii

# 定义消息前缀（假设这些前缀是固定的）
message_prefixes = ['16000000000000', '07000000000000']

# 用于存储拆分后的消息
SocketView_receive_queue = []

# 拆分消息的函数
def split_received_message(exata_response):
    while exata_response:
        for prefix in message_prefixes:
            if exata_response.startswith(prefix):
                # 提取长度字段，假设长度字段位于前缀之后的第16到19个字符（即，消息总长度包含前缀和内容）
                length_field = exata_response[14:16]  # 取长度字段
                message_length = int(length_field, 16)  # 将十六进制字符串转换为整数

                # 由于长度字段包含了前缀长度，实际内容长度应该是：message_length - 前缀长度
                # 每条消息都包含前缀，因此消息内容的长度是 message_length - len(prefix)
                content_length = message_length - len(prefix)

                # 提取完整消息：前缀 + 内容
                message = exata_response[:message_length*2]  # 这里将整个消息作为一条完整消息，包括前缀和内容

                # 将完整消息添加到消息队列
                SocketView_receive_queue.append(message)

                # 移除已经处理过的消息部分
                exata_response = exata_response[message_length*2:]
                break
        else:
            print("Error: Received data doesn't start with a valid prefix!")
            break

# 主函数
def main():
    # 模拟接收到的数据（假设我们接收到了一条合并的消息）
    response_data = '1600000000000013000931203320302030203407000000000000104014000000112e0c'


    # 调用拆分函数
    split_received_message(response_data)

    # 打印拆分后的消息
    print("消息拆分结果:")
    for msg in SocketView_receive_queue:
        print(f"Received message: {msg}")

if __name__ == "__main__":
    main()
