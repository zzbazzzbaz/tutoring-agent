import type { Role } from '@/stores/auth'

/**
 * Mock 登录。未来替换为 POST /auth/login 拿 JWT。
 * 当前：直接返回成功，不做任何验证。
 */
export async function mockLogin(
  _username: string,
  _password: string,
  _role: Role,
): Promise<{ ok: true }> {
  await new Promise(r => setTimeout(r, 300))
  return { ok: true }
}
