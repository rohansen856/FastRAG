/**
 * Public, build-time site settings from the environment. Both are optional: without a repo
 * URL the site hides every GitHub link and star button, and without a developer it hides the
 * developer section and its footer and navigation entries.
 *
 * They use NEXT_PUBLIC_ because client components render them; neither is a secret. Next
 * inlines them at build time, so changing them needs a rebuild.
 */

export interface Developer {
  name: string;
  role?: string;
  bio?: string;
  /** A path under public/ (e.g. "/developers/rohan.png") or an https URL. */
  photo?: string;
  github?: string;
  linkedin?: string;
  website?: string;
  email?: string;
}

function httpsUrl(value: unknown): string | null {
  if (typeof value !== "string" || !value.trim()) return null;
  try {
    const url = new URL(value.trim());
    return url.protocol === "https:" || url.protocol === "http:" ? url.toString().replace(/\/+$/, "") : null;
  } catch {
    return null;
  }
}

function text(value: unknown): string | undefined {
  return typeof value === "string" && value.trim() ? value.trim() : undefined;
}

function parseDeveloper(raw: string | undefined): Developer | null {
  if (!raw?.trim()) return null;
  try {
    const value = JSON.parse(raw) as Record<string, unknown>;
    const name = text(value.name);
    if (!name) return null;
    const photo = text(value.photo);
    const email = text(value.email);
    return {
      name,
      role: text(value.role),
      bio: text(value.bio),
      photo: photo && (photo.startsWith("/") ? photo : (httpsUrl(photo) ?? undefined)),
      github: httpsUrl(value.github) ?? undefined,
      linkedin: httpsUrl(value.linkedin) ?? undefined,
      website: httpsUrl(value.website) ?? undefined,
      email: email && /^[^\s@]+@[^\s@]+$/.test(email) ? email : undefined,
    };
  } catch {
    return null;
  }
}

/** The repository's web URL, without a trailing slash, or null when it is not configured. */
export const GITHUB_REPO_URL = httpsUrl(process.env.NEXT_PUBLIC_GITHUB_REPO_URL);

/** Branch that file links point at. */
export const GITHUB_REPO_BRANCH = text(process.env.NEXT_PUBLIC_GITHUB_REPO_BRANCH) ?? "master";

/** The repo URL without its scheme, for display ("github.com/owner/repo"). */
export const GITHUB_REPO_LABEL = GITHUB_REPO_URL?.replace(/^https?:\/\//, "") ?? null;

/** A link to a file in the repository, or null when no repository is configured. */
export function repoFileUrl(path: string): string | null {
  return GITHUB_REPO_URL ? `${GITHUB_REPO_URL}/blob/${GITHUB_REPO_BRANCH}/${path.replace(/^\/+/, "")}` : null;
}

/** The developer credited on the site, or null when NEXT_PUBLIC_DEVELOPER is unset or invalid. */
export const DEVELOPER = parseDeveloper(process.env.NEXT_PUBLIC_DEVELOPER);
