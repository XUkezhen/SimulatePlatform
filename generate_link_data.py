# generate_link_data.py

def generate_link_data():
    # 初始数据
    data = [
        [1, -30, 1, 2, 0, 0, '169.0.0.1', '169.0.0.2'],
        [2, -30, 3, 4, 0, 0, '169.0.1.1', '169.0.0.4']
    ]

    # 每次增加的值
    increment = 30

    # 每一行的时间值（第二个数）最多增加到 600
    max_time = 600

    # 打开文件 linkslong.txt 进行写入（如果文件不存在则创建）
    with open('linkslong.txt', 'w') as file:
        # 循环打印每一组数据，直到时间达到最大值
        while True:

            for row in data:
                # 修改第二个数（time）
                row[1] += increment
                # 写入文件（使用 join 将行数据转换为字符串并以空格分隔）
                file.write(" ".join(map(str, row)) + "\n")

                # 检查是否达到了600，若达到则结束循环
                if row[1] >= max_time:
                    break
            if data[0][1] >= max_time:
                break
    data = [
        [1, 600, 3, 4, 0, 0, "169.0.1.1", "169.0.0.4"],
        [2, 600, 1, 3, 0, 1, "169.0.0.1", "169.0.0.3"]
    ]

    # 每次增加的值
    increment = 30

    # 每一行的时间值（第二个数）最多增加到 600
    max_time = 1800

    # 打开文件 linkslong.txt 进行写入（如果文件不存在则创建）
    with open('linkslong.txt', 'a') as file:
        # 循环打印每一组数据，直到时间达到最大值
        while True:
            for row in data:
                # 修改第二个数（time）
                row[1] += increment
                # 写入文件（使用 join 将行数据转换为字符串并以空格分隔）
                file.write(" ".join(map(str, row)) + "\n")

                # 检查是否达到了600，若达到则结束循环
                if row[1] >= max_time:
                    break
            if data[0][1] >= max_time:
                break

if __name__ == "__main__":
    generate_link_data()
