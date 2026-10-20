export const API_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

export type User = { id: string; email: string; created_at: string };
export type DailyPlan = { date: string; timezone: string; calorie_target: number; consumed_calories: number; remaining_calories: number; allocations: { meal_type: string; scheduled_time: string; allocated_calories: number }[] };
export type Meal = { id: string; meal_type: string; food_name: string | null; calories: number; occurred_at: string };
export type Recommendation = { recipe_id: string; name: string; description: string | null; cuisine: string; meal_type: string; calories: number; protein_g: string; carbs_g: string; fat_g: string; preparation_minutes: number; score: number; pantry_matches: string[]; missing_ingredients: string[]; explanations: string[] };
export type PantryItem = { id: string; ingredient_id: string; name: string; category: string; status: "available" | "low" | "unavailable" };
export type Ingredient = { id: string; name: string; category: string; matching_cuisines: string[] };
export type Notification = { id: string; title: string; body: string; read_at: string | null };

export class ApiError extends Error { constructor(public status: number, message: string) { super(message); } }

export async function api<T>(path: string, options: RequestInit = {}, token?: string): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, {
    ...options,
    headers: { "Content-Type": "application/json", ...(token ? { Authorization: `Bearer ${token}` } : {}), ...options.headers },
  });
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    const detail = typeof body.detail === "string" ? body.detail : "Something went wrong";
    throw new ApiError(response.status, detail);
  }
  return response.json() as Promise<T>;
}
