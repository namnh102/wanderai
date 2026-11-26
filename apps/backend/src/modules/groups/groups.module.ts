import { Module } from '@nestjs/common';
import { PrismaModule } from '../../prisma/prisma.module';
import { GroupExpensesService } from './group-expenses.service';
import { GroupItineraryService } from './group-itinerary.service';
import { GroupsController } from './groups.controller';
import { GroupsService } from './groups.service';

@Module({
  imports: [PrismaModule],
  controllers: [GroupsController],
  providers: [GroupsService, GroupItineraryService, GroupExpensesService],
  exports: [GroupsService, GroupItineraryService, GroupExpensesService],
})
export class GroupsModule {}
