# Chat Module (`src/modules/chat`)

Is folder me CTD Backend ka Core Realtime Chat Module mojood hai.

Mukammal documentation, workflow diagrams, aur API/WebSocket endpoints reference k liye root file check karein:
👉 [CHAT_MODULE_README.md](../../../CHAT_MODULE_README.md)

---

## Quick Architecture Summary

- **WebSocket Gateway:** [`chat.gateway.ts`](./gateways/chat.gateway.ts) (`/chat` namespace)
  - Manages connections, online/offline presence, personal rooms, direct & group message broadcasting, typing indicators.
- **Service Layer:** [`chat.service.ts`](./services/chat.service.ts)
  - Handles message persistence via Prisma, direct & group message retrieval, member ID extraction.
- **REST Controller:** [`chat.controller.ts`](./controllers/chat.controller.ts)
  - `GET /chat/direct/:userId1/:userId2` -> History between two users.
  - `GET /chat/group/:groupId` -> History for a group.
- **DTOs:**
  - [`send-message.dto.ts`](./dto/send-message.dto.ts)
  - [`join-room.dto.ts`](./dto/join-room.dto.ts)
- **Placeholders for expansion:**
  - [`call.controller.ts`](./controllers/call.controller.ts)
  - [`group.controller.ts`](./controllers/group.controller.ts)
