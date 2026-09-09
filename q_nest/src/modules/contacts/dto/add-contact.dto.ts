import { IsNotEmpty, IsOptional, IsString } from 'class-validator';

export class AddContactDto {
  @IsOptional()
  @IsString()
  userId?: string;

  @IsNotEmpty({ message: 'Phone number is required' })
  @IsString()
  phone: string;

  @IsNotEmpty({ message: 'Specific / Custom name is required' })
  @IsString()
  customName: string;
}
