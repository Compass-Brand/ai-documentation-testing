# WebSocket API

Real-time communication via WebSockets.

## Connection

```javascript
const ws = new WebSocket("wss://api.example.com/ws");

ws.onopen = () => {
  ws.send(JSON.stringify({
    type: "auth",
    token: "<access_token>",
  }));
};
```

## Events

```javascript
ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  switch (data.type) {
    case "notification":
      handleNotification(data.payload);
      break;
    case "order_update":
      handleOrderUpdate(data.payload);
      break;
  }
};
```

## Server-Side

```python
from framework.websockets import WebSocketRouter

ws_router = WebSocketRouter()

@ws_router.on("chat_message")
async def handle_chat(ws, data):
    await ws.broadcast("chat_message", data)
```

See [Authentication](../api/auth.md) for WebSocket auth flow.
