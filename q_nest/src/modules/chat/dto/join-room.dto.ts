import { IsNotEmpty, IsString, IsIn } from 'class-validator';

export class JoinRoomDto {
  @IsNotEmpty()
  @IsIn(['direct', 'group'])
  chatType: 'direct' | 'group';

  @IsNotEmpty()
  @IsString()
  targetId: string;
}
