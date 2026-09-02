import { Module } from '@nestjs/common';
import { AppConfigModule } from './config/config.module';
import { GatewaysModule } from './gateways/gateways.module';
import { UsersModule } from './modules/users/users.module';
import { ChatModule } from './modules/chat/chat.module';
import { AppController } from './app.controller';

// Upcoming modules (uncomment when implemented):
// import { AdminAuthModule } from './modules/admin-auth/admin-auth.module';
// import { DepartmentsModule } from './modules/departments/departments.module';
// import { GroupsModule } from './modules/groups/groups.module';
// import { MessagesModule } from './modules/messages/messages.module';
// import { CallsModule } from './modules/calls/calls.module';
// import { ChatPreferencesModule } from './modules/chat-preferences/chat-preferences.module';
// import { ReadStatusModule } from './modules/read-status/read-status.module';
// import { RagProxyModule } from './modules/rag-proxy/rag-proxy.module';

@Module({
  imports: [
    AppConfigModule,
    GatewaysModule,
    UsersModule,
    ChatModule,
    // Upcoming modules:
    // AdminAuthModule,
    // DepartmentsModule,
    // GroupsModule,
    // MessagesModule,
    // CallsModule,
    // ChatPreferencesModule,
    // ReadStatusModule,
    // RagProxyModule,
  ],
  controllers: [AppController],
})
export class AppModule {
  constructor() {
    console.log('[AppModule] Root Application Module Bootstrapped successfully.');
  }
}
