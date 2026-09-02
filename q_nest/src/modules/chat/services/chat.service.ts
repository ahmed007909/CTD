import { Injectable } from '@nestjs/common';
import { PrismaService } from '../../../prisma/prisma.service';
import { MessageType } from '@prisma/client';
import { randomUUID } from 'crypto';

@Injectable()
export class ChatService {
  constructor(private prisma: PrismaService) {}

  async saveMessage(data: {
    senderId: string;
    receiverId?: string;
    groupId?: string;
    messageType: MessageType;
    content?: string;
    mediaUrl?: string;
    mediaDuration?: number;
    mediaSize?: number;
    replyToId?: string;
  }) {
    return this.prisma.message.create({
      data: {
        matrixEventId: randomUUID(), // required unique field
        senderId: data.senderId,
        receiverId: data.receiverId,
        groupId: data.groupId,
        messageType: data.messageType,
        content: data.content,
        mediaUrl: data.mediaUrl,
        mediaDuration: data.mediaDuration,
        mediaSize: data.mediaSize,
        replyToId: data.replyToId,
      },
      include: {
        sender: { select: { id: true, fullName: true, username: true } },
      },
    });
  }

  async getDirectMessages(userId1: string, userId2: string) {
    return this.prisma.message.findMany({
      where: {
        OR: [
          { senderId: userId1, receiverId: userId2 },
          { senderId: userId2, receiverId: userId1 },
        ],
        isDeleted: false,
      },
      orderBy: { sentAt: 'asc' },
    });
  }

  async getGroupMessages(groupId: string) {
    return this.prisma.message.findMany({
      where: { groupId, isDeleted: false },
      orderBy: { sentAt: 'asc' },
    });
  }

  async getGroupMemberIds(groupId: string) {
    const members = await this.prisma.groupMember.findMany({
      where: { groupId },
      select: { userId: true },
    });
    return members.map((m) => m.userId);
  }
}