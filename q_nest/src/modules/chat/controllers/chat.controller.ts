import { Controller, Get, Param } from '@nestjs/common';
import { ChatService } from '../services/chat.service';

@Controller('chat')
export class ChatController {
  constructor(private readonly chatService: ChatService) {}

  @Get('direct/:userId1/:userId2')
  getDirectMessages(
    @Param('userId1') userId1: string,
    @Param('userId2') userId2: string,
  ) {
    return this.chatService.getDirectMessages(userId1, userId2);
  }

  @Get('group/:groupId')
  getGroupMessages(@Param('groupId') groupId: string) {
    return this.chatService.getGroupMessages(groupId);
  }
}