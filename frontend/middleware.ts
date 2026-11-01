import { NextResponse, type NextRequest } from "next/server";

// Send anyone without a session cookie to /login. The backend still verifies the JWT on every
// API call; this only avoids rendering empty screens for logged-out users.
export function middleware(req: NextRequest) {
  if (!req.cookies.has("kk_session")) {
    const url = req.nextUrl.clone();
    url.pathname = "/login";
    url.search = "";
    return NextResponse.redirect(url);
  }
  return NextResponse.next();
}

export const config = {
  // Everything except the login page, API proxy, Next internals and PWA files.
  matcher: ["/((?!login|api|_next|icons|sw\.js|offline\.html|manifest\.webmanifest|icon\.svg|favicon\.ico).*)"],
};
