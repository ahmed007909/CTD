import { SetMetadata } from '@nestjs/common';
import { Role } from '../constants/roles.enum';

export const ROLES_KEY = 'roles';
export const Roles = (...roles: Role[]) => {
  console.log('[RolesDecorator] Setting required roles:', roles);
  return SetMetadata(ROLES_KEY, roles);
};
