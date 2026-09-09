# CTD Backend Architecture

This repository contains the backend services for the CTD platform.

## Architecture

- **`q_nest/`**: Core NestJS API backend service handling authentication, users, departments, groups, messaging, calls, chat preferences, read status, and gateways.
- **`q_python/`** *(Upcoming)*: RAG + OSINT FastAPI service.
- **`docker/`** *(Upcoming)*: Docker compose orchestration.

## Documentation

- 📘 **[Chat Module Complete Workflow & Endpoints Documentation](CHAT_MODULE_README.md)**: Detailed architecture diagrams, sequence flows, REST endpoints, and WebSocket events.
- 📇 **[Contact Management Architecture & Workflow](CHAT_MODULE_README.md#9-contact-management-architecture--workflow-add-contact-flow)**: Complete flow for adding contacts, number verification in DB, custom nicknames, invite link fallback, and ER diagram.

## Getting Started with NestJS (`q_nest`)

```bash
cd q_nest
npm install
npm run seed     # Seeds test users (Officer Ahmed & Investigator Ali) and test group
npm run start:dev
```

Open `index.html` in your browser to test live real-time chat.

