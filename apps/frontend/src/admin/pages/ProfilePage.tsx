import React, { useRef, useState } from 'react';
import { Link, useNavigate } from '../lib/router';
import {
  Shield,
  KeyRound,
  Building2,
  Lock,
  Camera,
  Upload,
  Trash2,
  Pencil,
  Save,
  X,
  CheckCircle2,
  AlertTriangle,
  Mail,
  Smartphone,
  Bell,
  Languages,
  Clock,
  Palette,
  LogOut
} from '../lib/icons';
import { PANEL, PanelHeader, BTN_PRIMARY, BTN_SECONDARY } from '../components/ui/dashboard';
import { useAuth } from '../lib/auth';
import { useEntitlementView } from '../data/entitlement';
import { academyLabel, permissionsFor } from '../data/repo';
import { roleTitle } from '../data/roles';
import { PHOTO_MAX_BYTES, initialsOf, preparePhoto, useLocalProfile, type LocalProfile } from '../lib/profileStore';

const INPUT =
  'w-full px-3 py-2 text-xs rounded-lg border border-[#E2E8F0] text-[#12233F] placeholder-[#64748B] focus:outline-none focus:ring-2 focus:ring-[#9333EA] focus:border-transparent bg-[#F6F8FB]';

const Row: React.FC<{ label: string; children: React.ReactNode; muted?: boolean }> = ({ label, children, muted }) => (
  <div className="px-5 py-3 flex items-start justify-between gap-4 text-xs">
    <span className="text-[#64748B] flex-shrink-0">{label}</span>
    <span className={`text-right min-w-0 ${muted ? 'text-[#64748B]' : 'text-[#12233F] font-semibold'}`} style={{ overflowWrap: 'anywhere' }}>
      {children}
    </span>
  </div>
);

const Soon: React.FC<{ children?: React.ReactNode }> = ({ children = 'Not available yet' }) => (
  <span className="inline-flex items-center text-[10px] font-semibold px-2 py-0.5 rounded-full bg-[#F1F5F9] text-[#475569] whitespace-nowrap">{children}</span>
);

const Field: React.FC<{ label: string; error?: string; hint?: string; children: React.ReactNode }> = ({ label, error, hint, children }) => (
  <label className="block">
    <span className="block text-xs font-semibold text-[#12233F] mb-1.5">{label}</span>
    {children}
    {error ? (
      <span role="alert" className="block mt-1 text-[11px] text-[#B91C1C]">
        {error}
      </span>
    ) : (
      hint && <span className="block mt-1 text-[11px] text-[#64748B]">{hint}</span>
    )}
  </label>
);

type Draft = Pick<LocalProfile, 'firstName' | 'lastName' | 'displayName' | 'phone' | 'jobTitle' | 'bio'>;

function validate(d: Draft): Partial<Record<keyof Draft, string>> {
  const e: Partial<Record<keyof Draft, string>> = {};
  if (!d.firstName.trim()) e.firstName = 'First name is required.';
  if (!d.lastName.trim()) e.lastName = 'Last name is required.';
  if (d.displayName.trim().length > 60) e.displayName = 'Keep the display name under 60 characters.';
  if (d.phone && !/^\+?[0-9 ()-]{7,20}$/.test(d.phone.trim())) e.phone = 'Enter a valid phone number, e.g. +91 98765 43210.';
  if (d.jobTitle.trim().length > 80) e.jobTitle = 'Keep the job title under 80 characters.';
  if (d.bio.length > 300) e.bio = `${d.bio.length}/300 characters: please shorten.`;
  return e;
}

/**
 * The signed-in admin's own profile. Account name, email and role come from GET /identity/auth/me;
 * the organisation from GET /tenancy/organisation. Personal details and the photo are saved on this
 * device (lib/profileStore): platform/identity has no profile-update or photo endpoint yet.
 */
export const ProfilePage: React.FC = () => {
  const { session, preview, signOut } = useAuth();
  const navigate = useNavigate();
  const view = useEntitlementView();

  const sample = !session;
  const me = session?.me ?? {
    id: 'preview',
    organisation_id: 'preview',
    email: 'admin@example.org',
    name: 'Administrator',
    roles: ['org-admin'],
    is_super_admin: false,
    permissions: permissionsFor(['org-admin']),
    impersonated_by: null
  };
  const org = session?.organisation ?? null;
  const orgCountry = (org as { country?: string | null } | null)?.country ?? null;
  const roleId = me.is_super_admin ? 'super-admin' : me.roles[0] ?? 'org-admin';
  const academy = view.profile ? academyLabel(view.profile) : '–';
  const orgName = org?.name ?? (sample ? 'Demo organisation' : me.is_super_admin ? 'Education OS platform' : '–');

  const [profile, saveProfile] = useLocalProfile(me.id);
  const [nameFirst, ...nameRest] = me.name.split(/\s+/).filter(Boolean);
  const current: Draft = {
    firstName: profile.firstName || nameFirst || '',
    lastName: profile.lastName || nameRest.join(' '),
    displayName: profile.displayName,
    phone: profile.phone,
    jobTitle: profile.jobTitle,
    bio: profile.bio
  };
  const shownName = current.displayName || [current.firstName, current.lastName].filter(Boolean).join(' ') || me.name || me.email;

  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState<Draft>(current);
  const [errors, setErrors] = useState<Partial<Record<keyof Draft, string>>>({});
  const [toast, setToast] = useState<{ ok: boolean; text: string } | null>(null);

  // Photo: a pending preview until saved.
  const fileRef = useRef<HTMLInputElement>(null);
  const [pending, setPending] = useState<string | null>(null);
  const [processing, setProcessing] = useState(false);
  const [photoError, setPhotoError] = useState<string | null>(null);
  const photo = pending ?? profile.photo;

  const flash = (ok: boolean, text: string) => {
    setToast({ ok, text });
    window.setTimeout(() => setToast(null), 3500);
  };

  const persist = (next: Partial<LocalProfile>, message: string) => {
    try {
      saveProfile({ ...profile, ...next });
      flash(true, message);
      return true;
    } catch {
      flash(false, 'Could not save: this browser is blocking storage (private window or storage full).');
      return false;
    }
  };

  const startEdit = () => {
    setDraft(current);
    setErrors({});
    setEditing(true);
  };
  const saveDetails = (e: React.FormEvent) => {
    e.preventDefault();
    const found = validate(draft);
    setErrors(found);
    if (Object.keys(found).length) return;
    const clean = Object.fromEntries(Object.entries(draft).map(([k, v]) => [k, v.trim()])) as Draft;
    if (persist(clean, 'Profile details saved on this device')) setEditing(false);
  };

  const choosePhoto = async (file: File | undefined) => {
    if (!file) return;
    setPhotoError(null);
    setProcessing(true);
    try {
      setPending(await preparePhoto(file));
    } catch (err) {
      setPhotoError(err instanceof Error ? err.message : 'This image could not be used.');
    } finally {
      setProcessing(false);
      if (fileRef.current) fileRef.current.value = '';
    }
  };
  const savePhoto = () => {
    if (pending && persist({ photo: pending }, 'Profile photo saved on this device')) setPending(null);
  };
  const removePhoto = () => {
    setPending(null);
    if (profile.photo && window.confirm('Remove your profile photo?')) persist({ photo: null }, 'Profile photo removed');
  };

  const timeZone = Intl.DateTimeFormat().resolvedOptions().timeZone;
  const language = typeof navigator !== 'undefined' ? navigator.language : 'en';

  return (
    <div className="space-y-6">
      {toast && (
        <div role="status" className="fixed bottom-6 right-6 z-50 flex items-center gap-2 bg-[#12233F] text-white px-4 py-3 rounded-lg shadow-lg text-xs">
          {toast.ok ? <CheckCircle2 className="w-4 h-4 text-[#6FCF97]" /> : <AlertTriangle className="w-4 h-4" style={{ color: '#F39A19' }} />}
          <span>{toast.text}</span>
        </div>
      )}

      {/* 1. Profile header */}
      <header className="eos-hero relative rounded-xl px-6 py-7 sm:px-8 text-white overflow-hidden">
        <div className="relative z-10 flex flex-col md:flex-row md:items-center gap-5">
          <div className="relative flex-shrink-0 self-start">
            <div
              className="rounded-full overflow-hidden flex items-center justify-center text-2xl font-bold shadow-lg"
              style={{ width: 96, height: 96, background: photo ? '#FFFFFF' : '#D03F1B', boxShadow: '0 0 0 4px rgba(255,255,255,0.35)' }}
            >
              {photo ? <img src={photo} alt="Profile photo" className="w-full h-full" style={{ objectFit: 'cover' }} /> : initialsOf(shownName)}
            </div>
            <button
              type="button"
              onClick={() => fileRef.current?.click()}
              aria-label="Change profile photo"
              title="Change profile photo"
              className="absolute bottom-0 right-0 w-8 h-8 rounded-full bg-white text-[#7E22CE] flex items-center justify-center shadow-lg"
            >
              <Camera className="w-4 h-4" />
            </button>
          </div>
          <div className="min-w-0 flex-1">
            <div className="eos-hero-sub text-[12px] font-medium mb-1 inline-flex items-center gap-1.5">
              <span className="w-1.5 h-1.5 rounded-full bg-white" />
              {roleTitle(roleId)}
            </div>
            <h1 className="text-[32px] leading-tight font-bold tracking-[-0.02em] text-white truncate">{shownName}</h1>
            <p className="eos-hero-sub text-[14px] mt-1 truncate">
              {current.jobTitle ? `${current.jobTitle} · ` : ''}
              {orgName}
            </p>
            <div className="mt-3 flex flex-wrap items-center gap-2">
              <span className="inline-flex items-center gap-1.5 text-[11px] font-semibold px-2 py-0.5 rounded-full bg-white text-[#126B3D]">
                <span className="w-1.5 h-1.5 rounded-full bg-[#16834B]" />
                {sample ? 'Preview' : 'Active'}
              </span>
              <span className="text-[11px] font-semibold px-2 py-0.5 rounded-full" style={{ background: 'rgba(255,255,255,0.16)' }}>
                {academy}
              </span>
            </div>
          </div>
          <div className="flex flex-wrap gap-2.5">
            <button type="button" onClick={startEdit} className={BTN_PRIMARY}>
              <Pencil className="w-3.5 h-3.5" />
              Edit Profile
            </button>
          </div>
        </div>
      </header>

      <input
        ref={fileRef}
        type="file"
        accept="image/jpeg,image/png,image/webp"
        className="hidden"
        aria-label="Profile photo file"
        onChange={(e) => choosePhoto(e.target.files?.[0])}
      />

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* 2. Profile photo */}
        <section className={`${PANEL} eos-lift`}>
          <PanelHeader title="Profile Photo" subtitle={`JPG, PNG or WebP · up to ${PHOTO_MAX_BYTES / 1048576} MB`} />
          <div className="px-5 pb-5 flex flex-col items-center gap-4">
            <div
              className="rounded-full overflow-hidden flex items-center justify-center font-bold text-white"
              style={{ fontSize: 30, width: 120, height: 120, background: photo ? '#F6F8FB' : '#D03F1B', boxShadow: pending ? '0 0 0 3px #9333EA' : '0 0 0 1px #E2E8F0' }}
            >
              {processing ? (
                <span className="w-6 h-6 border-2 border-white border-t-transparent rounded-full animate-spin" aria-label="Processing image" />
              ) : photo ? (
                <img src={photo} alt={pending ? 'New photo preview' : 'Profile photo'} className="w-full h-full" style={{ objectFit: 'cover' }} />
              ) : (
                initialsOf(shownName)
              )}
            </div>
            {pending && <p className="text-[11px] font-semibold text-[#7E22CE]">Preview: not saved yet</p>}
            {photoError && (
              <p role="alert" className="w-full rounded-lg border border-[#FECACA] bg-[#FEF2F2] px-3 py-2 text-xs text-[#B91C1C]">
                {photoError}
              </p>
            )}
            <div className="flex flex-wrap justify-center gap-2">
              {pending ? (
                <>
                  <button type="button" onClick={savePhoto} className={BTN_PRIMARY}>
                    <Save className="w-3.5 h-3.5" />
                    Save Photo
                  </button>
                  <button type="button" onClick={() => setPending(null)} className={BTN_SECONDARY}>
                    <X className="w-3.5 h-3.5" />
                    Cancel
                  </button>
                </>
              ) : (
                <>
                  <button type="button" onClick={() => fileRef.current?.click()} disabled={processing} className={BTN_SECONDARY}>
                    <Upload className="w-3.5 h-3.5 text-[#7E22CE]" />
                    {profile.photo ? 'Replace' : 'Upload'}
                  </button>
                  {profile.photo && (
                    <button type="button" onClick={removePhoto} className={BTN_SECONDARY}>
                      <Trash2 className="w-3.5 h-3.5 text-[#B91C1C]" />
                      Remove
                    </button>
                  )}
                </>
              )}
            </div>
            <p className="text-[11px] text-[#64748B] text-center">Saved on this device. Photo storage needs platform/documents, which is not built yet.</p>
          </div>
        </section>

        {/* 3. Personal information */}
        <section className={`${PANEL} lg:col-span-2 eos-lift`}>
          <PanelHeader
            title="Personal Information"
            subtitle={editing ? 'Edit your details, then save' : 'Your details as people in your organisation see them'}
            action={
              !editing && (
                <button type="button" onClick={startEdit} className="inline-flex items-center gap-1 text-xs font-medium text-[var(--accent)] hover:opacity-80 pt-0.5">
                  <Pencil className="w-3.5 h-3.5" />
                  Edit
                </button>
              )
            }
          />
          {editing ? (
            <form onSubmit={saveDetails} noValidate className="px-5 pb-5 space-y-4 page-enter">
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <Field label="First Name *" error={errors.firstName}>
                  <input className={INPUT} value={draft.firstName} onChange={(e) => setDraft({ ...draft, firstName: e.target.value })} autoFocus />
                </Field>
                <Field label="Last Name *" error={errors.lastName}>
                  <input className={INPUT} value={draft.lastName} onChange={(e) => setDraft({ ...draft, lastName: e.target.value })} />
                </Field>
                <Field label="Display Name" error={errors.displayName} hint="Leave empty to use your full name.">
                  <input className={INPUT} value={draft.displayName} onChange={(e) => setDraft({ ...draft, displayName: e.target.value })} />
                </Field>
                <Field label="Email" hint="Your sign-in email. Changing it is not in the identity API yet.">
                  <input className={INPUT} style={{ opacity: 0.7, cursor: 'not-allowed' }} value={me.email} readOnly aria-readonly />
                </Field>
                <Field label="Phone Number" error={errors.phone}>
                  <input className={INPUT} type="tel" value={draft.phone} onChange={(e) => setDraft({ ...draft, phone: e.target.value })} placeholder="+91 98765 43210" />
                </Field>
                <Field label="Job Title / Designation" error={errors.jobTitle}>
                  <input className={INPUT} value={draft.jobTitle} onChange={(e) => setDraft({ ...draft, jobTitle: e.target.value })} placeholder="e.g. Registrar" />
                </Field>
              </div>
              <Field label="Bio" error={errors.bio} hint={`${draft.bio.length}/300`}>
                <textarea className={INPUT} rows={3} value={draft.bio} onChange={(e) => setDraft({ ...draft, bio: e.target.value })} />
              </Field>
              <div className="flex flex-wrap items-center justify-between gap-3 pt-1">
                <p className="text-[11px] text-[#64748B]">Saved on this device until profile editing is added to platform/identity.</p>
                <div className="flex gap-2">
                  <button type="button" onClick={() => setEditing(false)} className={BTN_SECONDARY}>
                    <X className="w-3.5 h-3.5" />
                    Cancel
                  </button>
                  <button type="submit" className={BTN_PRIMARY}>
                    <Save className="w-3.5 h-3.5" />
                    Save Changes
                  </button>
                </div>
              </div>
            </form>
          ) : (
            <div className="grid grid-cols-1 sm:grid-cols-2 border-t border-[#F1F5F9]">
              <div className="divide-y divide-[#F1F5F9]">
                <Row label="First Name">{current.firstName || '–'}</Row>
                <Row label="Last Name">{current.lastName || '–'}</Row>
                <Row label="Display Name" muted={!current.displayName}>
                  {current.displayName || 'Not set'}
                </Row>
                <Row label="Email">{me.email}</Row>
              </div>
              <div className="divide-y divide-[#F1F5F9]">
                <Row label="Phone Number" muted={!current.phone}>
                  {current.phone || 'Not set'}
                </Row>
                <Row label="Job Title" muted={!current.jobTitle}>
                  {current.jobTitle || 'Not set'}
                </Row>
                <Row label="Bio" muted={!current.bio}>
                  {current.bio || 'Not set'}
                </Row>
                <Row label="Last updated" muted>
                  {profile.updatedAt ? new Date(profile.updatedAt).toLocaleString('en-IN') : 'Never'}
                </Row>
              </div>
            </div>
          )}
        </section>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* 4. Organisation information (read-only) */}
        <section className={`${PANEL} eos-lift`}>
          <PanelHeader title="Organisation Information" subtitle="platform/tenancy · read-only" />
          <div className="px-5 pb-3 flex items-center gap-3">
            <span className="rounded-xl flex items-center justify-center text-sm font-bold text-white flex-shrink-0" style={{ width: 44, height: 44, background: 'var(--hero-gradient)' }}>
              {initialsOf(orgName)}
            </span>
            <div className="min-w-0">
              <p className="text-[13px] font-semibold text-[#12233F] truncate">{orgName}</p>
              <p className="text-[11px] text-[#64748B]">Logo upload needs platform/documents (not built)</p>
            </div>
          </div>
          <div className="divide-y divide-[#F1F5F9] border-t border-[#F1F5F9]">
            <Row label="Organisation Name">{orgName}</Row>
            <Row label="Organisation Type">{academy}</Row>
            <Row label="Short Name">
              <span className="font-mono text-[11px] font-normal">{org?.slug ?? '–'}</span>
            </Row>
            <Row label="Country" muted={!orgCountry}>
              {orgCountry ?? 'Not recorded'}
            </Row>
            <Row label="Organisation Email" muted>Not recorded</Row>
            <Row label="Organisation Phone" muted>Not recorded</Row>
            <Row label="Website" muted>Not recorded</Row>
            <Row label="Address · City · State" muted>Not recorded</Row>
          </div>
          <p className="px-5 py-3 text-[11px] text-[#64748B] border-t border-[#F1F5F9]">
            Read-only: editing (<code>PATCH /tenancy/organisation</code>) is in the tenancy contract but not built yet, and the organisation record has no
            contact or address fields.
          </p>
        </section>

        <div className="space-y-6">
          {/* 7. Role (read-only) */}
          <section className={`${PANEL} eos-lift`}>
            <PanelHeader
              title="Role & Access"
              subtitle="Assigned by your organisation; you cannot change your own role"
              action={
                <Link to="/access" className="text-xs font-medium text-[var(--accent)] hover:underline pt-0.5">
                  Details
                </Link>
              }
            />
            <div className="divide-y divide-[#F1F5F9] border-t border-[#F1F5F9]">
              <Row label="Role">
                <span className="inline-flex items-center gap-1.5">
                  <Shield className="w-3.5 h-3.5 text-[#7E22CE]" />
                  {roleTitle(roleId)}
                </span>
              </Row>
              <Row label="Scope">{me.is_super_admin ? 'All organisations' : `${orgName} only`}</Row>
              <Row label="Permission keys">
                <span className="inline-flex items-center gap-1.5">
                  <KeyRound className="w-3.5 h-3.5 text-[#475569]" />
                  {me.permissions.length}
                </span>
              </Row>
            </div>
          </section>

          {/* 5. Security */}
          <section className={`${PANEL} eos-lift`}>
            <PanelHeader title="Security" subtitle="Sign-in is email and password (platform/identity)" />
            <div className="divide-y divide-[#F1F5F9] border-t border-[#F1F5F9]">
              <div className="px-5 py-3 flex items-center justify-between gap-3 text-xs">
                <span className="inline-flex items-center gap-2 text-[#12233F] font-semibold">
                  <Lock className="w-3.5 h-3.5 text-[#475569]" />
                  Change Password
                </span>
                <Soon />
              </div>
              <div className="px-5 py-3 flex items-center justify-between gap-3 text-xs">
                <span className="inline-flex items-center gap-2 text-[#12233F] font-semibold">
                  <Smartphone className="w-3.5 h-3.5 text-[#475569]" />
                  Two-Factor Authentication
                </span>
                <Soon />
              </div>
              <div className="px-5 py-3 flex items-center justify-between gap-3 text-xs">
                <span className="inline-flex items-center gap-2 text-[#12233F] font-semibold">
                  <Building2 className="w-3.5 h-3.5 text-[#475569]" />
                  This device
                </span>
                <button
                  type="button"
                  onClick={() => {
                    signOut();
                    navigate('/login', { replace: true });
                  }}
                  className="inline-flex items-center gap-1 text-xs font-semibold text-[#B91C1C] hover:opacity-80"
                >
                  <LogOut className="w-3.5 h-3.5" />
                  Sign out
                </button>
              </div>
              <div className="px-5 py-3 flex items-center justify-between gap-3 text-xs">
                <span className="text-[#475569]">Sign out other devices</span>
                <Soon />
              </div>
            </div>
          </section>
        </div>
      </div>

      {/* 6. Preferences */}
      <section className={`${PANEL} eos-lift`}>
        <PanelHeader title="Notifications & Preferences" subtitle="Notification settings need platform/notification, which is not built yet" />
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 border-t border-[#F1F5F9]">
          {[
            { icon: Mail, label: 'Email notifications', value: <Soon /> },
            { icon: Bell, label: 'Important system notices', value: <Soon /> },
            { icon: Languages, label: 'Language', value: <span className="text-[#12233F] font-semibold">{language} (browser)</span> },
            {
              icon: Clock,
              label: 'Time zone',
              value: (
                <span className="text-[#12233F] font-semibold text-right" style={{ overflowWrap: 'anywhere' }}>
                  {timeZone} (browser)
                </span>
              )
            },
            { icon: Palette, label: 'Theme', value: <span className="text-[#12233F] font-semibold">Light</span> }
          ].map(({ icon: Icon, label, value }) => (
            <div key={label} className="px-5 py-3 flex items-center justify-between gap-3 text-xs border-b border-[#F1F5F9]">
              <span className="inline-flex items-center gap-2 text-[#475569] flex-shrink-0">
                <Icon className="w-3.5 h-3.5" />
                {label}
              </span>
              {value}
            </div>
          ))}
        </div>
      </section>

      {preview && <p className="text-[11px] text-[#64748B] text-center">Preview mode: sample account, no API connected.</p>}
    </div>
  );
};
