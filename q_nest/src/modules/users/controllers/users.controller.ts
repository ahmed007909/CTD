import { Controller, Get, Post, Body, Param, UseGuards } from '@nestjs/common';
import { UsersService } from '../services/users.service';
import { CreateUserDto } from '../dto/create-user.dto';
// import { JwtAuthGuard } from '../../admin-auth/guards/jwt-auth.guard';

@UseGuards()
@Controller('users')
export class UsersController {
  constructor(private readonly usersService: UsersService) {
    console.log('[UsersController] UsersController Initialized.');
  }

  @Get()
  async findAll() {
    console.log('[UsersController] GET /users called');
    return this.usersService.findAll();
  }

  @Get(':id')
  async findOne(@Param('id') id: string) {
    console.log(`[UsersController] GET /users/${id} called`);
    return this.usersService.findOne(id);
  }

  @Post()
  async create(@Body() createUserDto: CreateUserDto) {
    console.log('[UsersController] POST /users called with:', createUserDto);
    return this.usersService.create(createUserDto);
  }
}
