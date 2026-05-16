'use client';

import { useState } from 'react';
import { useAuth } from '@/context/AuthContext';

export default function AuthPage() {
  const { login, register, authMessage } = useAuth();
  const [mode, setMode] = useState('login');
  const [form, setForm] = useState({ username: '', email: '', password: '' });
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [success, setSuccess] = useState('');

  const handleChange = (e) => {
    setForm(prev => ({ ...prev, [e.target.name]: e.target.value }));
    setError('');
    setSuccess('');
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setSuccess('');
    setLoading(true);

    try {
      if (mode === 'login') {
        await login(form.username, form.password);
      } else {
        await register(form.username, form.email, form.password);
        setSuccess('Account created! Logging in...');
        setTimeout(async () => {
          try {
            await login(form.username, form.password);
          } catch (err) {
            setError(err.message);
            setLoading(false);
          }
        }, 800);
        return;
      }
    } catch (err) {
      setError(err.message || 'Something went wrong');
    }
    setLoading(false);
  };

  return (
    <div className="flex items-center justify-center min-h-screen p-5 relative overflow-hidden">
      {/* Decorative orbs */}
      <div className="absolute -top-30 -right-20 w-[400px] h-[400px] rounded-full bg-[radial-gradient(circle,rgba(99,102,241,0.15)_0%,transparent_70%)] blur-[60px] pointer-events-none" />
      <div className="absolute -bottom-25 -left-15 w-[350px] h-[350px] rounded-full bg-[radial-gradient(circle,rgba(139,92,246,0.12)_0%,transparent_70%)] blur-[60px] pointer-events-none" />

      <div className="w-full max-w-[440px] bg-bg-secondary/80 backdrop-blur-[30px] border border-border-subtle rounded-3xl p-10 shadow-[0_0_0_1px_rgba(255,255,255,0.05),0_20px_60px_rgba(0,0,0,0.5)] relative z-10 animate-fadeInScale">
        {/* Brand */}
        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center w-14 h-14 rounded-2xl bg-gradient-to-br from-accent to-accent-secondary text-white mb-4 shadow-[0_4px_20px_rgba(99,102,241,0.3)]">
            <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <circle cx="12" cy="12" r="10" />
              <path d="M12 2a14.5 14.5 0 0 0 0 20 14.5 14.5 0 0 0 0-20" />
              <path d="M2 12h20" />
            </svg>
          </div>
          <h1 className="text-[1.75rem] font-extrabold tracking-tight bg-gradient-to-br from-slate-200 to-slate-50 bg-clip-text text-transparent mb-1">
            Research Agent
          </h1>
          <p className="text-sm text-text-muted">AI-Powered Deep Research Assistant</p>
        </div>

        {/* Tab toggle */}
        <div className="flex gap-1 bg-bg-glass p-1 rounded-xl border border-border-subtle mb-7">
          <button
            type="button"
            onClick={() => { setMode('login'); setError(''); setSuccess(''); }}
            className={`flex-1 py-2 px-4 text-sm font-medium rounded-lg transition-all cursor-pointer ${
              mode === 'login'
                ? 'bg-accent text-white'
                : 'text-text-muted hover:text-text-secondary hover:bg-bg-glass-hover'
            }`}
          >
            Sign In
          </button>
          <button
            type="button"
            onClick={() => { setMode('register'); setError(''); setSuccess(''); }}
            className={`flex-1 py-2 px-4 text-sm font-medium rounded-lg transition-all cursor-pointer ${
              mode === 'register'
                ? 'bg-accent text-white'
                : 'text-text-muted hover:text-text-secondary hover:bg-bg-glass-hover'
            }`}
          >
            Create Account
          </button>
        </div>

        <form onSubmit={handleSubmit} className="flex flex-col">
          {/* Username */}
          <div className="mb-5">
            <label htmlFor="username" className="block text-[0.8125rem] font-medium text-text-secondary mb-1.5 tracking-wide">Username</label>
            <input
              id="username"
              name="username"
              type="text"
              className={`w-full py-3 px-4 text-[0.9375rem] text-text-primary bg-bg-input border rounded-xl outline-none transition-all placeholder:text-text-muted focus:bg-bg-input-focus focus:border-accent focus:shadow-[0_0_0_3px_var(--color-accent-glow)] ${error ? 'border-danger shadow-[0_0_0_3px_var(--color-danger-bg)]' : 'border-border-subtle'}`}
              placeholder="Enter your username"
              value={form.username}
              onChange={handleChange}
              autoComplete="username"
              required
            />
          </div>

          {/* Email (register only) */}
          {mode === 'register' && (
            <div className="mb-5 animate-fadeIn">
              <label htmlFor="email" className="block text-[0.8125rem] font-medium text-text-secondary mb-1.5 tracking-wide">Email</label>
              <input
                id="email"
                name="email"
                type="email"
                className="w-full py-3 px-4 text-[0.9375rem] text-text-primary bg-bg-input border border-border-subtle rounded-xl outline-none transition-all placeholder:text-text-muted focus:bg-bg-input-focus focus:border-accent focus:shadow-[0_0_0_3px_var(--color-accent-glow)]"
                placeholder="you@example.com"
                value={form.email}
                onChange={handleChange}
                autoComplete="email"
                required
              />
            </div>
          )}

          {/* Password */}
          <div className="mb-5">
            <label htmlFor="password" className="block text-[0.8125rem] font-medium text-text-secondary mb-1.5 tracking-wide">Password</label>
            <input
              id="password"
              name="password"
              type="password"
              className={`w-full py-3 px-4 text-[0.9375rem] text-text-primary bg-bg-input border rounded-xl outline-none transition-all placeholder:text-text-muted focus:bg-bg-input-focus focus:border-accent focus:shadow-[0_0_0_3px_var(--color-accent-glow)] ${error ? 'border-danger shadow-[0_0_0_3px_var(--color-danger-bg)]' : 'border-border-subtle'}`}
              placeholder={mode === 'register' ? 'Min 8 characters' : 'Enter your password'}
              value={form.password}
              onChange={handleChange}
              autoComplete={mode === 'login' ? 'current-password' : 'new-password'}
              required
              minLength={mode === 'register' ? 8 : undefined}
            />
          </div>

          {/* Error */}
          {error && (
            <div className="flex items-center gap-2 py-3 px-4 bg-danger-bg border border-danger/20 rounded-xl text-danger text-[0.8125rem] mb-4 animate-fadeIn">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="12" cy="12" r="10"/><line x1="15" y1="9" x2="9" y2="15"/><line x1="9" y1="9" x2="15" y2="15"/></svg>
              {error}
            </div>
          )}

          {/* authMessage (e.g. Session Expired) */}
          {authMessage && !error && !success && (
            <div className="flex items-center gap-2 py-3 px-4 bg-info-bg border border-info/20 rounded-xl text-info text-[0.8125rem] mb-4 animate-fadeIn">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/></svg>
              {authMessage}
            </div>
          )}

          {/* Success */}
          {success && (
            <div className="flex items-center gap-2 py-3 px-4 bg-success-bg border border-success/20 rounded-xl text-success text-[0.8125rem] mb-4 animate-fadeIn">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/></svg>
              {success}
            </div>
          )}

          {/* Submit */}
          <button
            type="submit"
            disabled={loading}
            className="w-full py-3.5 px-7 text-base font-semibold text-white bg-gradient-to-br from-accent to-accent-secondary rounded-2xl shadow-[0_2px_12px_var(--color-accent-glow)] hover:shadow-[0_4px_20px_var(--color-accent-glow),0_0_30px_var(--color-accent-glow)] transition-all active:scale-[0.97] disabled:opacity-50 disabled:cursor-not-allowed cursor-pointer"
          >
            {loading ? (
              <span className="flex items-center justify-center gap-1">
                <span className="w-1.5 h-1.5 rounded-full bg-white animate-[dotPulse_1.4s_ease-in-out_infinite]" />
                <span className="w-1.5 h-1.5 rounded-full bg-white animate-[dotPulse_1.4s_ease-in-out_infinite_0.16s]" />
                <span className="w-1.5 h-1.5 rounded-full bg-white animate-[dotPulse_1.4s_ease-in-out_infinite_0.32s]" />
              </span>
            ) : (
              mode === 'login' ? 'Sign In' : 'Create Account'
            )}
          </button>
        </form>

        <p className="text-center text-[0.8125rem] text-text-muted mt-5">
          {mode === 'login' ? "Don't have an account?" : 'Already have an account?'}{' '}
          <button
            type="button"
            onClick={() => { setMode(mode === 'login' ? 'register' : 'login'); setError(''); setSuccess(''); }}
            className="bg-transparent border-none text-accent font-semibold text-[0.8125rem] cursor-pointer hover:text-accent-hover hover:underline transition-colors"
          >
            {mode === 'login' ? 'Create one' : 'Sign in'}
          </button>
        </p>
      </div>
    </div>
  );
}
