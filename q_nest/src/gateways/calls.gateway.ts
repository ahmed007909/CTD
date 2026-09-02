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
  namespace: '/calls',
})
export class CallsGateway implements OnGatewayConnection, OnGatewayDisconnect {
  @WebSocketServer()
  server: Server;

  constructor(private readonly wsAuthService: WsAuthService) {}

  async handleConnection(client: Socket) {
    console.log(`[CallsGateway] Client connected for calls: ${client.id}`);
    await this.wsAuthService.validateClient(client);
  }

  handleDisconnect(client: Socket) {
    console.log(`[CallsGateway] Client disconnected: ${client.id}`);
  }

  @SubscribeMessage('callOffer')
  handleCallOffer(
    @ConnectedSocket() client: Socket,
    @MessageBody() payload: any,
  ) {
    console.log(`[CallsGateway] Call offer from ${client.id}:`, payload);
    return { event: 'callOfferAck', data: payload };
  }

  @SubscribeMessage('callAnswer')
  handleCallAnswer(
    @ConnectedSocket() client: Socket,
    @MessageBody() payload: any,
  ) {
    console.log(`[CallsGateway] Call answer from ${client.id}:`, payload);
    return { event: 'callAnswerAck', data: payload };
  }
}
