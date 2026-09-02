import { Module } from '@nestjs/common';
import { MessagesGateway } from './messages.gateway';
import { CallsGateway } from './calls.gateway';
import { WsAuthService } from './ws-auth.service';

@Module({
  providers: [MessagesGateway, CallsGateway, WsAuthService],
  exports: [MessagesGateway, CallsGateway, WsAuthService],
})
export class GatewaysModule {
  constructor() {
    console.log('[GatewaysModule] Realtime Gateways Module Initialized.');
  }
}
