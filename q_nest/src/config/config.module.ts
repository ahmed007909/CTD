import { Module } from '@nestjs/common';
import { ConfigModule as NestConfigModule } from '@nestjs/config';

@Module({
  imports: [
    NestConfigModule.forRoot({
      isGlobal: true,
      envFilePath: ['.env', '.env.example'],
    }),
  ],
  exports: [NestConfigModule],
})
export class AppConfigModule {
  constructor() {
    console.log('[AppConfigModule] Config Module Initialized.');
  }
}
