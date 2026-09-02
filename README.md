# CTD Backend Architecture

This repository contains the backend services for the CTD platform.

## Architecture

- **`q_nest/`**: Core NestJS API backend service handling authentication, users, departments, groups, messaging, calls, chat preferences, read status, and gateways.
- **`q_python/`** *(Upcoming)*: RAG + OSINT FastAPI service.
- **`docker/`** *(Upcoming)*: Docker compose orchestration.

## Getting Started with NestJS (`q_nest`)

```bash
cd q_nest
npm install
npm run start:dev
```
