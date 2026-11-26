import { Module } from '@nestjs/common';
import { PrismaModule } from '../../prisma/prisma.module';
import { GroupItineraryService } from './group-itinerary.service';
import { GroupsController } from './groups.controller';
import { GroupsService } from './groups.service';

@Module({
  imports: [PrismaModule],
  controllers: [GroupsController],
  providers: [GroupsService, GroupItineraryService],
  exports: [GroupsService, GroupItineraryService],
})
export class GroupsModule {}
