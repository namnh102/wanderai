import { NestFactory } from '@nestjs/core';
import { AppModule } from './app.module';
import { ValidationPipe } from '@nestjs/common';
import { DocumentBuilder, SwaggerModule } from '@nestjs/swagger';
import { HttpExceptionFilter } from './common/filters/http-exception.filter';
import { TransformInterceptor } from './common/interceptors/transform.interceptor';
import {
  buildNestCorsOptions,
  resolveNetworkConfig,
} from './config/network.config';

async function bootstrap() {
  const networkConfig = resolveNetworkConfig(process.env);
  const app = await NestFactory.create(AppModule);

  // Explicit CORS allowlist with fail-closed wildcard rejection when credentials are enabled
  app.enableCors(buildNestCorsOptions(networkConfig.corsOrigins));

  // Global pipes, filters, interceptors
  app.useGlobalPipes(
    new ValidationPipe({
      whitelist: true,
      transform: true,
      forbidNonWhitelisted: true,
    }),
  );
  app.useGlobalFilters(new HttpExceptionFilter());
  app.useGlobalInterceptors(new TransformInterceptor());

  // Swagger setup
  const config = new DocumentBuilder()
    .setTitle('WanderAI API')
    .setDescription('The WanderAI travel app API description')
    .setVersion('1.0')
    .addBearerAuth()
    .build();
  const document = SwaggerModule.createDocument(app, config);
  SwaggerModule.setup('api', app, document);

  if (networkConfig.host) {
    await app.listen(networkConfig.port, networkConfig.host);
  } else {
    await app.listen(networkConfig.port);
  }
}
bootstrap();
