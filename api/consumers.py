import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from django.http import JsonResponse

async def send_to_frontend():
    channel_layer = get_channel_layer()
    await channel_layer.group_send(
        "test_group",  # 指定组名
        {
            "type": "chat.message",  # 消息类型
            "message": "Hello, this is a push from the backend!"
        }
    )

def trigger_push(request):
    channel_layer = get_channel_layer()
    async_to_sync(channel_layer.group_send)(
        "test_group",
        {
            "type": "chat.message",
            "message": "Triggered message from Django view!"
        }
    )
    return JsonResponse({"status": "Message sent!"})

class MyWebSocketConsumer(AsyncWebsocketConsumer):

    async def connect(self):
        await self.accept()
        # 将用户加入组
        print("有链接进入")
        await self.channel_layer.group_add("test_group", self.channel_name)

    async def disconnect(self, close_code):
        # 将用户移出组
        await self.channel_layer.group_discard("test_group", self.channel_name)

    async def chat_message(self, event):
        # 发送消息给 WebSocket
        # print("chat_message")
        await self.send(text_data=json.dumps({
            "message": event["message"]
        }))

    async def send_message(self, event):
        # 发送消息给 WebSocket
        print("send_message")
        await self.send(json.dumps(event['message']))

    async def receive(self, text_data):
        # 接收到消息时处理逻辑
        data = json.loads(text_data)
        print(f"Received message: {data}")


        # 回复前端消息
        await self.send(text_data=json.dumps({
            "message": "Hello from Django!"
        }))

