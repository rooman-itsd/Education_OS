import { asset } from '../lib/assets';
import React, { useState } from 'react';
import { useNavigate } from '../lib/router';
import { Shield, Lock, User, ArrowRight, ShieldCheck, Building2, Layers, Wallet, KeyRound } from '../lib/icons';
import { signInError, useAuth } from '../lib/auth';
import { EduMark, Wordmark } from '../components/ui/Wordmark';
import { PLATFORM_SERVICES, SUITES } from '../data/architecture';
import { PROFILES } from '../data/repo';

/** What Education OS is, from the architecture and README; counts are read from the repo. */
const FEATURES = [
  { icon: Building2, title: 'Multi-tenant', text: 'One deployment, many organisations. Each signs in to its own data.' },
  { icon: Layers, title: 'Academy profiles', text: `${Object.keys(PROFILES).length} academy types, each with its own suites, roles and dashboards.` },
  { icon: Wallet, title: 'Plans & entitlements', text: 'Trial, standard and premium plans decide which modules are on.' },
  { icon: KeyRound, title: 'Permission keys', text: 'Every module checks keys, never roles, and records changes to audit.' }
];

const STATS = [
  { value: Object.keys(PROFILES).length, label: 'Academy types' },
  { value: SUITES.reduce((n, s) => n + s.modules.length, 0), label: 'Feature modules' },
  { value: PLATFORM_SERVICES.length, label: 'Platform services' }
];

export const LoginPage: React.FC = () => {
  const navigate = useNavigate();
  const { preview, signIn } = useAuth();
  // Preview (no API) keeps demo values; a real sign-in starts empty.
  const [universityId, setUniversityId] = useState(preview ? 'admin@example.org' : '');
  const [password, setPassword] = useState(preview ? '••••••••••••' : '');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);
    try {
      await signIn(universityId.trim(), password);
      navigate('/dashboard', { replace: true });
    } catch (err) {
      setError(signInError(err));
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-[#F6F8FB] grid grid-cols-1 lg:grid-cols-2">
      {/* Brand panel: campus photo under the hero gradient */}
      <aside className="relative hidden lg:flex flex-col justify-between overflow-hidden text-white" style={{ padding: 40 }} aria-label="About Education OS">
        <div
          className="absolute inset-0 bg-cover"
          style={{ backgroundImage: `url('${asset('/campus.jpg')}')`, backgroundPosition: '62% 72%' }}
          aria-hidden
        />
        <div className="absolute inset-0" style={{ backgroundImage: 'var(--hero-gradient)', opacity: 0.9 }} aria-hidden />
        <div
          className="absolute inset-0 pointer-events-none"
          style={{ backgroundImage: 'radial-gradient(rgba(255,255,255,0.18) 1px, transparent 1px)', backgroundSize: '22px 22px' }}
          aria-hidden
        />
        <div
          className="absolute rounded-full pointer-events-none"
          style={{ width: 420, height: 420, right: -140, top: -120, background: 'radial-gradient(circle, rgba(246,91,102,0.45), transparent 70%)' }}
          aria-hidden
        />

        <div className="relative z-10 flex items-center gap-3">
          <span className="rounded-xl bg-white flex items-center justify-center shadow-lg" style={{ width: 48, height: 48 }}>
            <EduMark size={36} />
          </span>
          <Wordmark inverse className="text-2xl" />
        </div>

        <div className="relative z-10 max-w-md space-y-6 eos-nav-in">
          <div>
            <h1 className="text-[32px] leading-tight font-bold tracking-[-0.02em]">One platform for every institution</h1>
            <p className="eos-hero-sub text-[14px] mt-2">
              Configured for the way each institution teaches, trains, manages and supports its students.
            </p>
          </div>
          <ul className="space-y-3 stagger">
            {FEATURES.map(({ icon: Icon, title, text }) => (
              <li key={title} className="flex items-start gap-3">
                <span className="w-9 h-9 rounded-lg flex items-center justify-center flex-shrink-0" style={{ background: 'rgba(255,255,255,0.16)' }}>
                  <Icon className="w-4 h-4" />
                </span>
                <div>
                  <p className="text-sm font-semibold">{title}</p>
                  <p className="eos-hero-sub text-xs">{text}</p>
                </div>
              </li>
            ))}
          </ul>
        </div>

        <div className="relative z-10 space-y-4">
          <div className="grid grid-cols-3 gap-3">
            {STATS.map((s) => (
              <div key={s.label} className="rounded-xl p-3" style={{ background: 'rgba(255,255,255,0.12)', boxShadow: 'inset 0 0 0 1px rgba(255,255,255,0.22)' }}>
                <div className="text-2xl font-bold tabular-nums">{s.value}</div>
                <div className="eos-hero-sub text-[11px]">{s.label}</div>
              </div>
            ))}
          </div>
          <p className="eos-hero-sub text-[11px]">© 2026 Education OS · Multi-tenant platform for higher-education institutions</p>
        </div>
      </aside>

      {/* Sign-in panel */}
      <main className="relative flex flex-col justify-center py-12 px-4 sm:px-8 overflow-hidden">
        <div
          className="absolute inset-0 opacity-[0.03] pointer-events-none"
          style={{ backgroundImage: 'radial-gradient(#7E22CE 1px, transparent 1px)', backgroundSize: '24px 24px' }}
          aria-hidden
        />
        <div
          className="absolute rounded-full pointer-events-none"
          style={{ width: 360, height: 360, left: -160, bottom: -160, background: 'radial-gradient(circle, rgba(124,58,237,0.12), transparent 70%)' }}
          aria-hidden
        />

        <div className="relative z-10 w-full max-w-md mx-auto page-enter">
          <div className="text-center">
            <img src={asset('/eos-logo.png')} alt="Education OS — University Operating System" className="mx-auto w-full h-auto" style={{ maxWidth: 260 }} />
            <p className="mt-3 text-xs text-[#475569] font-medium uppercase tracking-wider">One configurable higher-education platform</p>
          </div>

          <div className="mt-6 bg-[#FFFFFF] py-8 px-6 sm:px-10 shadow-lg rounded-xl border border-[#E2E8F0]">
            <div className="flex items-center justify-between pb-4 border-b border-[#E2E8F0] mb-6">
              <div>
                <span className="text-sm font-semibold text-[#12233F]">Sign In to Portal</span>
                <p className="text-xs text-[#475569]">Super admins and organisation admins</p>
              </div>
              {preview ? (
                <span className="inline-flex items-center gap-1 text-[11px] font-semibold px-2 py-0.5 rounded-full bg-[#F39A1926] text-[#8A4F00]">
                  <Shield className="w-3.5 h-3.5" />
                  Preview mode
                </span>
              ) : (
                <span className="inline-flex items-center gap-1 text-[11px] font-semibold px-2 py-0.5 rounded-full bg-[#16834B26] text-[#126B3D]">
                  <ShieldCheck className="w-3.5 h-3.5" />
                  Connected to API
                </span>
              )}
            </div>

            <form className="space-y-4" onSubmit={handleSubmit}>
              <div>
                <label className="block text-xs font-semibold text-[#12233F] mb-1.5">Institutional Email</label>
                <div className="relative rounded-lg shadow-2xs">
                  <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-[#475569]">
                    <User className="h-4 w-4" />
                  </div>
                  <input
                    type="email"
                    required
                    value={universityId}
                    onChange={(e) => setUniversityId(e.target.value)}
                    placeholder="e.g. name@your-institution.edu"
                    className="block w-full pl-9 pr-3 py-2 text-xs rounded-lg border border-[#E2E8F0] text-[#12233F] placeholder-[#64748B] focus:outline-none focus:ring-2 focus:ring-[#9333EA] focus:border-transparent bg-[#F6F8FB]"
                  />
                </div>
              </div>

              <div>
                <div className="flex items-center justify-between mb-1.5">
                  <label className="block text-xs font-semibold text-[#12233F]">Password</label>
                  <a
                    href="#forgot"
                    onClick={(e) => {
                      e.preventDefault();
                      alert('Password reset is not available yet. Ask your organisation admin.');
                    }}
                    className="text-xs font-medium text-[#7E22CE] hover:underline"
                  >
                    Forgot Password?
                  </a>
                </div>
                <div className="relative rounded-lg shadow-2xs">
                  <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-[#475569]">
                    <Lock className="h-4 w-4" />
                  </div>
                  <input
                    type="password"
                    required
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    placeholder="••••••••••••"
                    className="block w-full pl-9 pr-3 py-2 text-xs rounded-lg border border-[#E2E8F0] text-[#12233F] placeholder-[#64748B] focus:outline-none focus:ring-2 focus:ring-[#9333EA] focus:border-transparent bg-[#F6F8FB]"
                  />
                </div>
              </div>

              {error && (
                <p role="alert" className="rounded-lg border border-[#FECACA] bg-[#FEF2F2] px-3 py-2 text-xs text-[#B91C1C]">
                  {error}
                </p>
              )}

              <div className="pt-1">
                <button
                  type="submit"
                  disabled={loading}
                  className="w-full flex items-center justify-center gap-2 py-2.5 px-4 rounded-lg text-xs font-semibold text-white bg-[#F65B66] hover:bg-[#E9505C] focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-[#7E22CE] transition-all shadow-md active:scale-[0.99] disabled:opacity-70"
                >
                  {loading ? (
                    <span className="inline-flex items-center gap-2">
                      <span className="w-3.5 h-3.5 border-2 border-white border-t-transparent rounded-full animate-spin" />
                      Signing in...
                    </span>
                  ) : (
                    <>
                      <span>Sign In to Education OS</span>
                      <ArrowRight className="w-4 h-4" />
                    </>
                  )}
                </button>
              </div>
            </form>

            {/* Preview only: no API, so any credentials open the sample dashboard */}
            {preview && (
              <div className="mt-6 pt-5 border-t border-[#E2E8F0]">
                <p className="text-[11px] font-semibold text-[#475569] uppercase tracking-wider mb-2 text-center">Quick Prototype Demo Logins</p>
                <button
                  type="button"
                  onClick={() => {
                    setUniversityId('admin@example.org');
                    setPassword('demo');
                  }}
                  className="w-full px-2 py-1.5 text-[11px] font-medium rounded-md bg-[#7E22CE26] text-[#7E22CE] hover:bg-[#7E22CE40] transition-colors text-center border border-[#9333EA]/20"
                >
                  Preview as organisation admin (sample data)
                </button>
              </div>
            )}

            <div className="mt-6 flex items-center justify-center gap-2 text-[11px] text-[#475569]">
              <Shield className="w-3.5 h-3.5 text-[#126B3D]" />
              <span>Each organisation sees only its own data (row-level security)</span>
            </div>
          </div>

          <div className="mt-6 text-center text-xs text-[#475569] space-y-1 lg:hidden">
            <p>Education OS</p>
            <p className="text-[11px] text-[#64748B]">Multi-tenant platform for higher-education institutions</p>
          </div>
        </div>
      </main>
    </div>
  );
};
