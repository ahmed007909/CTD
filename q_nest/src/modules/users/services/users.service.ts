import { Injectable } from '@nestjs/common';
import { CreateUserDto } from '../dto/create-user.dto';

@Injectable()
export class UsersService {
  constructor() {
    console.log('[UsersService] UsersService Initialized.');
  }

  async findAll() {
    console.log('[UsersService] Fetching all users...');
    return [];
  }

  async findOne(id: string) {
    console.log(`[UsersService] Fetching user with id: ${id}`);
    return { id, name: 'Sample User' };
  }

  async create(createUserDto: CreateUserDto) {
    console.log('[UsersService] Creating user:', createUserDto);
    return { id: 'sample-user-id', ...createUserDto };
  }
}
