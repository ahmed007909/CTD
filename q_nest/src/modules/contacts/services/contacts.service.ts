import {
  BadRequestException,
  Injectable,
  NotFoundException,
} from '@nestjs/common';
import { PrismaService } from '../../../prisma/prisma.service';
import { AddContactDto } from '../dto/add-contact.dto';
import { UpdateContactDto } from '../dto/update-contact.dto';

@Injectable()
export class ContactsService {
  constructor(private readonly prisma: PrismaService) {}

  /**
   * Add a new contact or return an invite link if the user doesn't exist in DB.
   */
  async addContact(ownerUserId: string, dto: AddContactDto) {
    const cleanPhone = dto.phone.trim();
    const cleanCustomName = dto.customName.trim();

    // 1. Verify that the owner user exists
    const owner = await this.prisma.user.findUnique({
      where: { id: ownerUserId },
    });

    if (!owner) {
      throw new NotFoundException(`User with ID '${ownerUserId}' does not exist.`);
    }

    // 2. Prevent adding self
    if (owner.phone === cleanPhone) {
      throw new BadRequestException('You cannot add your own phone number as a contact.');
    }

    // 3. Check if the target phone number exists in the database
    const registeredUser = await this.prisma.user.findUnique({
      where: { phone: cleanPhone },
      select: {
        id: true,
        username: true,
        fullName: true,
        phone: true,
        role: true,
        designation: true,
        isActive: true,
      },
    });

    // 4. Branch YES: User exists in DB -> Save to contacts table
    if (registeredUser) {
      const contact = await this.prisma.contact.upsert({
        where: {
          userId_phone: {
            userId: ownerUserId,
            phone: cleanPhone,
          },
        },
        update: {
          contactId: registeredUser.id,
          customName: cleanCustomName,
        },
        create: {
          userId: ownerUserId,
          contactId: registeredUser.id,
          customName: cleanCustomName,
          phone: cleanPhone,
        },
        include: {
          contactUser: {
            select: {
              id: true,
              username: true,
              fullName: true,
              phone: true,
              role: true,
              designation: true,
              isActive: true,
            },
          },
        },
      });

      return {
        isRegistered: true,
        message: 'Contact saved successfully.',
        contact,
      };
    }

    // 5. Branch NO: User does not exist in DB -> Return invite link
    const inviteLink = `https://ctd.gov.pk/invite?ref=${ownerUserId}&phone=${encodeURIComponent(cleanPhone)}`;

    return {
      isRegistered: false,
      message: 'User is not registered on the CTD network. Invite link generated.',
      inviteLink,
      phone: cleanPhone,
      customName: cleanCustomName,
    };
  }

  /**
   * Get all saved contacts for a user.
   */
  async getContacts(ownerUserId: string) {
    return this.prisma.contact.findMany({
      where: { userId: ownerUserId },
      include: {
        contactUser: {
          select: {
            id: true,
            username: true,
            fullName: true,
            phone: true,
            role: true,
            designation: true,
            isActive: true,
          },
        },
      },
      orderBy: { customName: 'asc' },
    });
  }

  /**
   * Update a contact's custom specific name.
   */
  async updateContact(ownerUserId: string, contactId: string, dto: UpdateContactDto) {
    const existing = await this.prisma.contact.findFirst({
      where: { id: contactId, userId: ownerUserId },
    });

    if (!existing) {
      throw new NotFoundException('Contact not found or does not belong to you.');
    }

    return this.prisma.contact.update({
      where: { id: contactId },
      data: { customName: dto.customName.trim() },
      include: {
        contactUser: {
          select: {
            id: true,
            username: true,
            fullName: true,
            phone: true,
            role: true,
            designation: true,
            isActive: true,
          },
        },
      },
    });
  }

  /**
   * Delete a contact from the user's contact book.
   */
  async deleteContact(ownerUserId: string, contactId: string) {
    const existing = await this.prisma.contact.findFirst({
      where: { id: contactId, userId: ownerUserId },
    });

    if (!existing) {
      throw new NotFoundException('Contact not found or does not belong to you.');
    }

    await this.prisma.contact.delete({
      where: { id: contactId },
    });

    return { success: true, message: 'Contact deleted successfully.' };
  }
}
