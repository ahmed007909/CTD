import {
  WebSocketGateway,
  WebSocketServer,
  SubscribeMessage,
  OnGatewayConnection,
  OnGatewayDisconnect,
  MessageBody,
  ConnectedSocket,
} from '@nestjs/websockets';
import { Server, Socket } from 'socket.io';
import { WsAuthService } from './ws-auth.service';

@WebSocketGateway({
  cors: { origin: '*' },
  namespace: '/messages',
})
export class MessagesGateway implements OnGatewayConnection, OnGatewayDisconnect {
  @WebSocketServer()
  server: Server;

  constructor(private readonly wsAuthService: WsAuthService) {}

  async handleConnection(client: Socket) {
    console.log(`[MessagesGateway] Client connected: ${client.id}`);
    await this.wsAuthService.validateClient(client);
  }

  handleDisconnect(client: Socket) {
    console.log(`[MessagesGateway] Client disconnected: ${client.id}`);
  }

  @SubscribeMessage('sendMessage')
  handleSendMessage(
    @ConnectedSocket() client: Socket,
    @MessageBody() payload: any,
  ) {
    console.log(`[MessagesGateway] Received message from ${client.id}:`, payload);
    return { event: 'messageSent', data: payload };
  }
}
