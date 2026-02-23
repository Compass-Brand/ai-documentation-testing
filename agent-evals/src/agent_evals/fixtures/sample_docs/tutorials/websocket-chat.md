# Tutorial: WebSocket Chat

Build a real-time chat application with WebSockets.

## Step 1: Server Setup

```python
from framework.websockets import WebSocketRouter

chat = WebSocketRouter(prefix="/ws/chat")

connected_users = {}

@chat.on_connect
async def handle_connect(ws, user):
    connected_users[user.id] = ws
    await ws.broadcast("user_joined", {"user": user.name})

@chat.on_disconnect
async def handle_disconnect(ws, user):
    del connected_users[user.id]
    await ws.broadcast("user_left", {"user": user.name})
```

## Step 2: Message Handling

```python
@chat.on("message")
async def handle_message(ws, data):
    await ws.broadcast("message", {
        "user": ws.user.name,
        "text": data["text"],
        "timestamp": datetime.utcnow().isoformat(),
    })
```

## Step 3: Client

```javascript
const ws = new WebSocket("wss://api.example.com/ws/chat");
ws.send(JSON.stringify({type: "message", text: "Hello!"}));
```

See [WebSockets](../sdks/websockets.md) for connection details.
