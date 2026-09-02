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
import { ChatService } from '../services/chat.service';
import { SendMessageDto } from '../dto/send-message.dto';
import { JoinRoomDto } from '../dto/join-room.dto';

@WebSocketGateway({
  cors: { origin: '*' }, // production me apna frontend url daalna
  namespace: '/chat',
})
export class ChatGateway implements OnGatewayConnection, OnGatewayDisconnect {
  @WebSocketServer()
  server: Server;

  // userId -> socketId (reference k liye; personal room already delivery guarantee deta hai)
  private onlineUsers = new Map<string, string>();

  constructor(private readonly chatService: ChatService) {}

  handleConnection(client: Socket) {
    const userId = client.handshake.query.userId as string;

    if (!userId) {
      client.disconnect();
      return;
    }

    // har user apne khud k userId wale personal room me auto-join
    client.join(userId);
    this.onlineUsers.set(userId, client.id);

    this.server.emit('user_online', { userId });
  }

  handleDisconnect(client: Socket) {
    for (const [userId, socketId] of this.onlineUsers.entries()) {
      if (socketId === client.id) {
        this.onlineUsers.delete(userId);
        this.server.emit('user_offline', { userId });
        break;
      }
    }
  }

  // direct chat k liye consistent room naam (dono users k liye same rahega)
  private getDirectRoomId(userId1: string, userId2: string) {
    return [userId1, userId2].sort().join('_');
  }

  @SubscribeMessage('join_room')
  handleJoinRoom(
    @MessageBody() data: JoinRoomDto,
    @ConnectedSocket() client: Socket,
  ) {
    const myUserId = client.handshake.query.userId as string;

    const roomName =
      data.chatType === 'group'
        ? data.targetId // group k liye room naam = groupId
        : this.getDirectRoomId(myUserId, data.targetId);

    client.join(roomName);
    client.emit('joined_room', { roomName });
  }

  @SubscribeMessage('send_message')
  async handleMessage(
    @MessageBody() data: SendMessageDto,
    @ConnectedSocket() client: Socket,
  ) {
    try {
      // 1. DB me save
      const savedMessage = await this.chatService.saveMessage({
        senderId: data.senderId,
        receiverId: data.receiverId,
        groupId: data.groupId,
        messageType: data.messageType,
        content: data.content,
        mediaUrl: data.mediaUrl,
        mediaDuration: data.mediaDuration,
        mediaSize: data.mediaSize,
        replyToId: data.replyToId,
      });

      if (data.groupId) {
        // GROUP MESSAGE
        this.server.to(data.groupId).emit('new_message', savedMessage);

        // guaranteed delivery: har member k personal room pe bhi bhej do
        const memberIds = await this.chatService.getGroupMemberIds(data.groupId);
        memberIds.forEach((id) => this.server.to(id).emit('new_message', savedMessage));
      } else if (data.receiverId) {
        // DIRECT MESSAGE
        const roomName = this.getDirectRoomId(data.senderId, data.receiverId);
        this.server.to(roomName).emit('new_message', savedMessage);

        // guaranteed delivery receiver k personal room pe (chahe room join kiya ho ya nahi)
        this.server.to(data.receiverId).emit('new_message', savedMessage);
      }
    } catch (error: any) {
      console.error('[ChatGateway] Error saving message:', error.message);
      let errorMessage = 'Failed to send message.';
      if (error.code === 'P2003') {
        errorMessage = `Foreign key violation: senderId "${data.senderId}", receiverId "${data.receiverId}", or groupId "${data.groupId}" does not exist in the database. Please verify user/group exists.`;
      }
      client.emit('chat_error', { message: errorMessage, code: error.code });
    }
  }

  @SubscribeMessage('typing')
  handleTyping(@MessageBody() data: { roomName: string; userId: string }) {
    this.server.to(data.roomName).emit('user_typing', { userId: data.userId });
  }
}