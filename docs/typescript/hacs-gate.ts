export interface HACSGateResponse {
  ok: boolean;
  can_proceed: boolean;
  checks: Record<string, boolean>;
  version?: string;
}
export async function checkHACSGate(baseUrl: string): Promise<HACSGateResponse> {
  const res = await fetch(`${baseUrl}/api/v1/hacs/gate`);
  return res.json();
}
