import { Controller, Get } from '@nestjs/common';

@Controller()
export class AppController {
  @Get()
  getHealth() {
    return {
      status: 'ok',
      service: 'CTD NestJS Backend API',
      timestamp: new Date().toISOString(),
    };
  }
}
