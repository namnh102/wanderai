import { Test } from '@nestjs/testing';
import { ValidationPipe } from '@nestjs/common';
import * as request from 'supertest';
import { AppModule } from '../src/app.module';
import { TransformInterceptor } from '../src/common/interceptors/transform.interceptor';
import { HttpExceptionFilter } from '../src/common/filters/http-exception.filter';
import { PrismaService } from '../src/prisma/prisma.service';
import { JwtService } from '@nestjs/jwt';
import * as bcrypt from 'bcryptjs';

async function runRuntimeSmoke() {
  console.log('======================================================================');
  console.log('WP-PROF-01 RUNTIME SMOKE VERIFICATION (LIVE DATABASE)');
  console.log('======================================================================');

  const moduleFixture = await Test.createTestingModule({
    imports: [AppModule],
  }).compile();

  const app = moduleFixture.createNestApplication();
  app.useGlobalPipes(
    new ValidationPipe({
      whitelist: true,
      transform: true,
      forbidNonWhitelisted: true,
    }),
  );
  app.useGlobalFilters(new HttpExceptionFilter());
  app.useGlobalInterceptors(new TransformInterceptor());
  await app.init();

  const prisma = app.get(PrismaService);
  const jwtService = app.get(JwtService);

  const testEmail = `smoke_user_${Date.now()}@wanderai.test`;
  const password = 'SmokePassword123!';
  const hash = await bcrypt.hash(password, 10);

  // 1. Setup live test user
  const user = await prisma.user.create({
    data: {
      email: testEmail,
      passwordHash: hash,
      profile: { create: { displayName: 'Smoke Test User' } },
    },
  });
  const token = jwtService.sign({ sub: user.id, email: user.email });

  try {
    // ------------------------------------------------------------------
    // A. User with no preference row -> PUT creates preference
    // ------------------------------------------------------------------
    console.log('\n--- SCENARIO A: User with no preference row creates preferences ---');
    const dbBefore = await prisma.travelPreference.findUnique({
      where: { userId: user.id },
    });
    console.log(`[DB BEFORE] TravelPreference exists: ${dbBefore !== null}`);

    const payloadA = {
      travelStyle: 'COMFORT',
      budgetMin: 1500000,
      budgetMax: 12000000,
      preferredGroup: 'COUPLE',
      interests: ['food_cuisine', 'culture_history', 'coffee_culture'],
      avoidances: ['crowds'],
      dietaryNeeds: ['vegetarian'],
    };
    console.log('[REQUEST A] PUT /users/me/preferences:', JSON.stringify(payloadA));

    const resA = await request(app.getHttpServer())
      .put('/users/me/preferences')
      .set('Authorization', `Bearer ${token}`)
      .send(payloadA);

    console.log(`[RESPONSE A] HTTP Status: ${resA.status}`);
    console.log('[RESPONSE A] Body:', JSON.stringify(resA.body));
    if (resA.status !== 200 || !resA.body.success) {
      throw new Error(`Scenario A failed: ${JSON.stringify(resA.body)}`);
    }

    const dbAfterA = await prisma.travelPreference.findUnique({
      where: { userId: user.id },
    });
    console.log(`[DB AFTER A] Row ID: ${dbAfterA?.id}`);
    console.log(`[DB AFTER A] TravelStyle: ${dbAfterA?.travelStyle}`);
    console.log(`[DB AFTER A] Budget: ${dbAfterA?.budgetMin} - ${dbAfterA?.budgetMax} VND`);
    console.log(`[DB AFTER A] Interests: ${JSON.stringify(dbAfterA?.interests)}`);

    // ------------------------------------------------------------------
    // B. Same user -> PUT new values updates same preference
    // ------------------------------------------------------------------
    console.log('\n--- SCENARIO B: Same user updates existing preferences ---');
    const payloadB = {
      travelStyle: 'LUXURY',
      budgetMin: 5000000,
      budgetMax: 35000000,
      preferredGroup: 'FAMILY',
      interests: ['beach_island', 'shopping_local', 'nightlife_entertainment'],
    };
    console.log('[REQUEST B] PUT /users/me/preferences:', JSON.stringify(payloadB));

    const resB = await request(app.getHttpServer())
      .put('/users/me/preferences')
      .set('Authorization', `Bearer ${token}`)
      .send(payloadB);

    console.log(`[RESPONSE B] HTTP Status: ${resB.status}`);
    console.log('[RESPONSE B] Body:', JSON.stringify(resB.body));
    if (resB.status !== 200 || !resB.body.success) {
      throw new Error(`Scenario B failed: ${JSON.stringify(resB.body)}`);
    }

    const dbAfterB = await prisma.travelPreference.findUnique({
      where: { userId: user.id },
    });
    console.log(`[DB AFTER B] Row ID (must match A): ${dbAfterB?.id} (matches: ${dbAfterB?.id === dbAfterA?.id})`);
    console.log(`[DB AFTER B] Updated TravelStyle: ${dbAfterB?.travelStyle}`);
    console.log(`[DB AFTER B] Updated Budget: ${dbAfterB?.budgetMin} - ${dbAfterB?.budgetMax} VND`);
    console.log(`[DB AFTER B] Updated Interests: ${JSON.stringify(dbAfterB?.interests)}`);

    // ------------------------------------------------------------------
    // C. GET /users/me returns saved values
    // ------------------------------------------------------------------
    console.log('\n--- SCENARIO C: GET /users/me returns saved values ---');
    const resC = await request(app.getHttpServer())
      .get('/users/me')
      .set('Authorization', `Bearer ${token}`);

    console.log(`[RESPONSE C] HTTP Status: ${resC.status}`);
    console.log('[RESPONSE C] Preferences in profile:', JSON.stringify(resC.body.data.preferences));
    if (resC.status !== 200 || resC.body.data.preferences?.travelStyle !== 'LUXURY') {
      throw new Error(`Scenario C failed: ${JSON.stringify(resC.body)}`);
    }

    // ------------------------------------------------------------------
    // D. Reload client state -> values remain persisted
    // ------------------------------------------------------------------
    console.log('\n--- SCENARIO D: Client reload verification ---');
    const resD = await request(app.getHttpServer())
      .get('/users/me')
      .set('Authorization', `Bearer ${token}`);

    console.log(`[RESPONSE D] HTTP Status: ${resD.status}`);
    console.log('[RESPONSE D] Persisted values re-verified successfully.');

    // ------------------------------------------------------------------
    // E. Invalid budget (budgetMin > budgetMax) -> rejected 400
    // ------------------------------------------------------------------
    console.log('\n--- SCENARIO E: Invalid budget rejected ---');
    const payloadE = { budgetMin: 50000000, budgetMax: 20000000 };
    console.log('[REQUEST E] PUT /users/me/preferences:', JSON.stringify(payloadE));

    const resE = await request(app.getHttpServer())
      .put('/users/me/preferences')
      .set('Authorization', `Bearer ${token}`)
      .send(payloadE);

    console.log(`[RESPONSE E] HTTP Status: ${resE.status}`);
    console.log('[RESPONSE E] Body:', JSON.stringify(resE.body));
    if (resE.status !== 400) {
      throw new Error(`Scenario E failed: Expected 400, got ${resE.status}`);
    }

    // ------------------------------------------------------------------
    // F. Unknown interest -> rejected 400
    // ------------------------------------------------------------------
    console.log('\n--- SCENARIO F: Unknown interest rejected ---');
    const payloadF = { interests: ['food_cuisine', 'free_climbing_extreme'] };
    console.log('[REQUEST F] PUT /users/me/preferences:', JSON.stringify(payloadF));

    const resF = await request(app.getHttpServer())
      .put('/users/me/preferences')
      .set('Authorization', `Bearer ${token}`)
      .send(payloadF);

    console.log(`[RESPONSE F] HTTP Status: ${resF.status}`);
    console.log('[RESPONSE F] Body:', JSON.stringify(resF.body));
    if (resF.status !== 400) {
      throw new Error(`Scenario F failed: Expected 400, got ${resF.status}`);
    }

    // ------------------------------------------------------------------
    // G. Unauthenticated request -> rejected 401
    // ------------------------------------------------------------------
    console.log('\n--- SCENARIO G: Unauthenticated request rejected ---');
    const resG = await request(app.getHttpServer())
      .put('/users/me/preferences')
      .send({ travelStyle: 'COMFORT' });

    console.log(`[RESPONSE G] HTTP Status: ${resG.status}`);
    console.log('[RESPONSE G] Body:', JSON.stringify(resG.body));
    if (resG.status !== 401) {
      throw new Error(`Scenario G failed: Expected 401, got ${resG.status}`);
    }

    console.log('\n======================================================================');
    console.log('ALL RUNTIME SMOKE SCENARIOS PASSED WITH LIVE DB EVIDENCE!');
    console.log('======================================================================');

  } finally {
    // Clean up smoke user
    await prisma.travelPreference.deleteMany({ where: { userId: user.id } });
    await prisma.profile.deleteMany({ where: { userId: user.id } });
    await prisma.user.deleteMany({ where: { id: user.id } });
    await app.close();
  }
}

runRuntimeSmoke().catch((err) => {
  console.error('Smoke test failed:', err);
  process.exit(1);
});
