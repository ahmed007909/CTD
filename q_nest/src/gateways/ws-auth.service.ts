import { Injectable } from '@nestjs/common';
import { Socket } from 'socket.io';

@Injectable()
export class WsAuthService {
  constructor() {
    console.log('[WsAuthService] WebSocket Auth Service Initialized.');
  }

  async validateClient(client: Socket): Promise<boolean> {
    console.log(`[WsAuthService] Validating client handshake: ${client.id}`);
    return true;
  }
}
