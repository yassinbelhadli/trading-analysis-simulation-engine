const clientPortal = process.env.NEXT_PUBLIC_CLIENT_PORTAL_URL ?? "http://localhost:3000";
const adminPortal = process.env.NEXT_PUBLIC_ADMIN_PORTAL_URL ?? "http://localhost:3001";

export const portalUrls = {
  clientLogin: `${clientPortal}/login`,
  clientRegister: `${clientPortal}/register`,
  clientForgotPassword: `${clientPortal}/forgot-password`,
  adminLogin: `${adminPortal}/login`,
};
