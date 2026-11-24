import { ExceptionFilter, Catch, ArgumentsHost, HttpException, HttpStatus } from '@nestjs/common';
import { Request, Response } from 'express';

@Catch()
export class HttpExceptionFilter implements ExceptionFilter {
  catch(exception: unknown, host: ArgumentsHost) {
    const ctx = host.switchToHttp();
    const response = ctx.getResponse<Response>();
    const request = ctx.getRequest<Request>();

    let status = HttpStatus.INTERNAL_SERVER_ERROR;
    let message: unknown = 'Internal server error';
    let errorCode: string | undefined;

    if (exception instanceof HttpException) {
      status = exception.getStatus();
      const res = exception.getResponse();

      if (typeof res === 'object' && res !== null) {
        const body = res as Record<string, unknown>;
        if (typeof body.errorCode === 'string' && body.errorCode.trim().length > 0) {
          errorCode = body.errorCode.trim();
        }
        message = body.message !== undefined ? body.message : res;
      } else {
        message = res;
      }
    }

    response.status(status).json({
      success: false,
      statusCode: status,
      ...(errorCode ? { errorCode } : {}),
      message: Array.isArray(message) ? message[0] : message,
      timestamp: new Date().toISOString(),
      path: request.url,
    });
  }
}
