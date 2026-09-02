import { Injectable, OnModuleInit } from '@nestjs/common';

@Injectable()
export class MatrixAdapter implements OnModuleInit {
  onModuleInit() {
    console.log('[MatrixAdapter] Matrix External Adapter Initialized.');
  }

  async sendDirectMessage(roomId: string, message: string) {
    console.log(`[MatrixAdapter] Sending message to room ${roomId}: ${message}`);
    return { success: true, roomId, message };
  }

  async createRoom(name: string, topic?: string) {
    console.log(`[MatrixAdapter] Creating Matrix room: ${name} (${topic})`);
    return { roomId: '!placeholder:matrix.org', name };
  }
}
