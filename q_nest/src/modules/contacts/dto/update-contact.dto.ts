import { IsNotEmpty, IsString } from 'class-validator';

export class UpdateContactDto {
  @IsNotEmpty({ message: 'Custom name cannot be empty' })
  @IsString()
  customName: string;
}
