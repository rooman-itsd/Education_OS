// Images of the admin screens, bundled by Vite from src/admin/assets/ so they ship only with
// admin.html. `asset("/campus.jpg")` returns the built URL of assets/campus.jpg.

const files = import.meta.glob<string>("../assets/*.{jpg,png}", { eager: true, query: "?url", import: "default" });

export function asset(path: string): string {
  const url = files[`../assets/${path.replace(/^\//, "")}`];
  if (!url) throw new Error(`missing admin asset: ${path}`);
  return url;
}
