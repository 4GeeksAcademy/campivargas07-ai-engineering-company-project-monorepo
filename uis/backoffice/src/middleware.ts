import { NextResponse } from 'next/server';
import type { NextRequest } from 'next/server';

// Rutas públicas que no requieren autenticación
const publicRoutes = ['/login', '/register'];

export function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;
  
  // Permitir rutas públicas
  const isPublicRoute = publicRoutes.some(route => pathname.startsWith(route));
  
  // Permitir archivos estáticos y API routes
  if (pathname.startsWith('/api') || pathname.startsWith('/_next') || pathname.includes('.')) {
    return NextResponse.next();
  }
  
  // Para rutas protegidas, verificaremos el token en el cliente
  // En Next.js App Router, el middleware se ejecuta en el servidor
  // y no tiene acceso a localStorage. La protección real se hace en el cliente.
  
  // Por ahora, permitimos todas las rutas y la protección se hará en el cliente
  // mediante el hook useAuth
  
  return NextResponse.next();
}

export const config = {
  matcher: [
    '/((?!api|_next/static|_next/image|favicon.ico).*)',
  ],
};
