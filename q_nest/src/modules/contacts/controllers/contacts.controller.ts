import {
  BadRequestException,
  Body,
  Controller,
  Delete,
  Get,
  Headers,
  Param,
  Patch,
  Post,
  Query,
} from '@nestjs/common';
import { ContactsService } from '../services/contacts.service';
import { AddContactDto } from '../dto/add-contact.dto';
import { UpdateContactDto } from '../dto/update-contact.dto';

@Controller('contacts')
export class ContactsController {
  constructor(private readonly contactsService: ContactsService) {}

  /**
   * Add a new contact or get an invite link if not registered.
   * Resolves owner user ID from body.userId, query.userId, or header 'x-user-id'.
   */
  @Post('add')
  async addContact(
    @Body() dto: AddContactDto,
    @Query('userId') queryUserId?: string,
    @Headers('x-user-id') headerUserId?: string,
  ) {
    const ownerUserId = dto.userId || queryUserId || headerUserId;
    if (!ownerUserId) {
      throw new BadRequestException(
        'Owner user ID must be provided via request body (userId), query (?userId=...), or header (x-user-id).',
      );
    }

    return this.contactsService.addContact(ownerUserId, dto);
  }

  /**
   * Get all saved contacts for a given user.
   */
  @Get(':userId')
  async getContacts(@Param('userId') userId: string) {
    return this.contactsService.getContacts(userId);
  }

  /**
   * Update a contact's custom specific name.
   */
  @Patch(':id')
  async updateContact(
    @Param('id') contactId: string,
    @Body() dto: UpdateContactDto,
    @Query('userId') queryUserId?: string,
    @Headers('x-user-id') headerUserId?: string,
  ) {
    const ownerUserId = queryUserId || headerUserId;
    if (!ownerUserId) {
      throw new BadRequestException(
        'Owner user ID must be provided via query (?userId=...) or header (x-user-id).',
      );
    }

    return this.contactsService.updateContact(ownerUserId, contactId, dto);
  }

  /**
   * Delete a contact.
   */
  @Delete(':id')
  async deleteContact(
    @Param('id') contactId: string,
    @Query('userId') queryUserId?: string,
    @Headers('x-user-id') headerUserId?: string,
  ) {
    const ownerUserId = queryUserId || headerUserId;
    if (!ownerUserId) {
      throw new BadRequestException(
        'Owner user ID must be provided via query (?userId=...) or header (x-user-id).',
      );
    }

    return this.contactsService.deleteContact(ownerUserId, contactId);
  }
}
