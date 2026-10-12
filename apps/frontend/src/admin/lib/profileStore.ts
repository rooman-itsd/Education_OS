// The signed-in admin's own profile details and photo, kept in this browser per user.
// platform/identity stores only name, email, roles and status and has no endpoint to update a
// profile or store a photo (platform/documents is not built), so these edits are saved on this
// device until identity gains profile editing. The account name and email from the API stay
// the source of truth and are never overwritten here.

import { useCallback, useSyncExternalStore } from 'react';

export interface LocalProfile {
  firstName: string;
  lastName: string;
  displayName: string;
  phone: string;
  jobTitle: string;
  bio: string;
  /** Square JPEG data URL, at most 256×256, or null. */
  photo: string | null;
  updatedAt: string | null;
}

const EMPTY: LocalProfile = { firstName: '', lastName: '', displayName: '', phone: '', jobTitle: '', bio: '', photo: null, updatedAt: null };
const EVENT = 'eos-profile-change';
const key = (userKey: string) => `eos.admin.profile.${userKey}`;

const cache = new Map<string, { raw: string | null; value: LocalProfile }>();

function read(userKey: string): LocalProfile {
  let raw: string | null = null;
  try {
    raw = localStorage.getItem(key(userKey));
  } catch {
    raw = null;
  }
  const hit = cache.get(userKey);
  if (hit && hit.raw === raw) return hit.value;
  let value = EMPTY;
  try {
    value = raw ? { ...EMPTY, ...(JSON.parse(raw) as Partial<LocalProfile>) } : EMPTY;
  } catch {
    value = EMPTY;
  }
  cache.set(userKey, { raw, value });
  return value;
}

/** Saves the profile; throws when the browser refuses storage (private mode or full). */
export function saveProfile(userKey: string, next: LocalProfile): void {
  localStorage.setItem(key(userKey), JSON.stringify({ ...next, updatedAt: new Date().toISOString() }));
  window.dispatchEvent(new Event(EVENT));
}

function subscribe(onChange: () => void) {
  window.addEventListener(EVENT, onChange);
  window.addEventListener('storage', onChange);
  return () => {
    window.removeEventListener(EVENT, onChange);
    window.removeEventListener('storage', onChange);
  };
}

export function useLocalProfile(userKey: string): [LocalProfile, (next: LocalProfile) => void] {
  const value = useSyncExternalStore(subscribe, () => read(userKey));
  const save = useCallback((next: LocalProfile) => saveProfile(userKey, next), [userKey]);
  return [value, save];
}

export const PHOTO_TYPES = ['image/jpeg', 'image/png', 'image/webp'];
export const PHOTO_MAX_BYTES = 2 * 1024 * 1024;

/** Checks type and size, then centre-crops and scales the image to a 256×256 JPEG data URL. */
export async function preparePhoto(file: File): Promise<string> {
  if (!PHOTO_TYPES.includes(file.type)) throw new Error('Choose a JPG, PNG or WebP image.');
  if (file.size > PHOTO_MAX_BYTES) throw new Error(`The image is ${(file.size / 1048576).toFixed(1)} MB; the limit is 2 MB.`);
  const url = URL.createObjectURL(file);
  try {
    const img = await new Promise<HTMLImageElement>((resolve, reject) => {
      const i = new Image();
      i.onload = () => resolve(i);
      i.onerror = () => reject(new Error('This file could not be read as an image.'));
      i.src = url;
    });
    const side = Math.min(img.naturalWidth, img.naturalHeight);
    const canvas = document.createElement('canvas');
    canvas.width = canvas.height = 256;
    const ctx = canvas.getContext('2d');
    if (!ctx) throw new Error('This browser cannot process images.');
    ctx.drawImage(img, (img.naturalWidth - side) / 2, (img.naturalHeight - side) / 2, side, side, 0, 0, 256, 256);
    return canvas.toDataURL('image/jpeg', 0.88);
  } finally {
    URL.revokeObjectURL(url);
  }
}

export const initialsOf = (name: string) =>
  name
    .split(/[\s@.]+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((w) => w[0]!.toUpperCase())
    .join('') || 'AD';
