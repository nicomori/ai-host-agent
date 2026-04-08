import { useState, useEffect, useRef } from "react";
import { AlertCircle } from "lucide-react";

import { setAuthToken } from "../lib/api";

function CutleryIcon({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 32 32" fill="none" xmlns="http://www.w3.org/2000/svg">
      <g transform="translate(16,16)" stroke="#e8d5a3" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
        <line x1="-4" y1="-11" x2="-4" y2="11"/>
        <line x1="-6" y1="-11" x2="-6" y2="-5"/>
        <line x1="-2" y1="-11" x2="-2" y2="-5"/>
        <path d="M-6 -5 Q-4 -2 -2 -5"/>
        <line x1="4" y1="-11" x2="4" y2="11"/>
        <path d="M4 -11 Q7 -8 4 -4"/>
      </g>
    </svg>
  );
}

const BG_VIDEOS = ["/login-bg.mp4", "/login-bg-2.mp4", "/login-bg-3.mp4"];

export default function Login() {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError]       = useState("");
  const [loading, setLoading]   = useState(false);
  const [videoIdx, setVideoIdx] = useState(0);
  const videoRef = useRef<HTMLVideoElement>(null);

  useEffect(() => {
    const el = videoRef.current;
    if (!el) return;
    const onEnded = () => setVideoIdx((i) => (i + 1) % BG_VIDEOS.length);
    el.addEventListener("ended", onEnded);
    return () => el.removeEventListener("ended", onEnded);
  }, []);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    if (!username.trim() || !password.trim()) {
      setError("Username and password are required");
      return;
    }
    setLoading(true);
    try {
      const body = new URLSearchParams({ username: username.trim(), password });
      const resp = await fetch("/api/v1/auth/token", {
        method: "POST",
        headers: { "Content-Type": "application/x-www-form-urlencoded" },
        body: body.toString(),
      });
      if (!resp.ok) {
        const data = await resp.json();
        setError(data.detail || "Invalid credentials");
        return;
      }
      const data = await resp.json();
      localStorage.setItem("ha_token",    data.access_token);
      localStorage.setItem("ha_username", data.username);
      localStorage.setItem("ha_role",     data.role);
      setAuthToken(data.access_token);
      window.location.href = "/dashboard";
    } catch {
      setError("Network error — please retry");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex bg-white">

      {/* ─── Left panel: cinematic video background ──────────────────────── */}
      <div className="hidden lg:flex lg:w-[58%] relative overflow-hidden bg-stone-900">
        {/* Videos — cycle through BG_VIDEOS on each end */}
        <video
          ref={videoRef}
          key={BG_VIDEOS[videoIdx]}
          className="absolute inset-0 w-full h-full object-cover"
          autoPlay
          muted
          playsInline
          src={BG_VIDEOS[videoIdx]}
        />

        {/* Cinematic gradient overlay */}
        <div className="absolute inset-0 bg-gradient-to-br from-black/70 via-black/40 to-orange-950/50" />

        {/* Grain texture overlay */}
        <div className="absolute inset-0 opacity-[0.03] bg-noise" />

        {/* Content */}
        <div className="relative z-10 flex flex-col justify-between p-14 w-full">
          {/* Logo */}
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-2xl flex items-center justify-center" style={{background:"#1a1208", border:"1px solid rgba(232,213,163,0.2)"}}>
              <CutleryIcon className="w-5 h-5" />
            </div>
            <span className="text-white font-semibold text-base tracking-tight">AI Host Agent</span>
          </div>

          {/* Bottom headline */}
          <div>
            <p className="text-white/40 text-xs uppercase tracking-[0.2em] mb-4 font-medium">
              Restaurant Intelligence
            </p>
            <h2 className="text-white text-[2.6rem] font-bold leading-[1.15] mb-5">
              Every reservation,<br />perfectly handled.
            </h2>
            <p className="text-white/55 text-base leading-relaxed max-w-sm">
              Manage bookings, coordinate your team, and delight every guest — all from one intelligent platform.
            </p>

            {/* Subtle stat pills */}
            <div className="flex gap-3 mt-8">
              {["Real-time updates", "Voice reservations", "AI-powered"].map((t) => (
                <span key={t} className="px-3 py-1.5 rounded-full bg-white/10 backdrop-blur-sm border border-white/10 text-white/70 text-xs font-medium">
                  {t}
                </span>
              ))}
            </div>
          </div>
        </div>
      </div>

      {/* ─── Right panel: login form ─────────────────────────────────────── */}
      <div className="flex-1 flex items-center justify-center px-8 py-12">
        <div className="w-full max-w-[360px]">

          {/* Mobile logo */}
          <div className="lg:hidden flex items-center gap-2.5 mb-10">
            <div className="w-9 h-9 rounded-xl flex items-center justify-center" style={{background:"#1a1208", border:"1px solid rgba(232,213,163,0.2)"}}>
              <CutleryIcon className="w-4 h-4" />
            </div>
            <span className="font-semibold text-slate-800">AI Host Agent</span>
          </div>

          <h1 className="text-[2rem] font-bold text-slate-900 leading-tight mb-1">
            Welcome back
          </h1>
          <p className="text-slate-400 text-sm mb-9">
            Sign in to your workspace
          </p>

          <form onSubmit={handleSubmit} className="space-y-4">

            {/* Username — floating label */}
            <div className="float-label-group">
              <input
                id="fl-username"
                type="text"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                placeholder=" "
                autoComplete="username"
                required
                className="float-label-input"
              />
              <label htmlFor="fl-username" className="float-label">Username</label>
            </div>

            {/* Password — floating label */}
            <div className="float-label-group">
              <input
                id="fl-password"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder=" "
                autoComplete="current-password"
                required
                className="float-label-input"
              />
              <label htmlFor="fl-password" className="float-label">Password</label>
            </div>

            {error && (
              <div className="flex items-center gap-2.5 text-destructive text-sm bg-destructive/8 px-4 py-3 rounded-xl border border-destructive/15">
                <AlertCircle className="w-4 h-4 flex-shrink-0" />
                {error}
              </div>
            )}

            <button
              type="submit"
              disabled={loading}
              className="w-full mt-2 py-3.5 bg-primary text-white rounded-xl font-semibold text-sm
                         hover:bg-primary/90 active:scale-[0.98] transition-all
                         disabled:opacity-55 shadow-md shadow-primary/20"
            >
              {loading ? "Signing in…" : "Sign in"}
            </button>
          </form>

          <p className="mt-10 text-xs text-center text-slate-400">
            Roles: <span className="text-primary font-semibold">admin</span> · writer · reader
          </p>
        </div>
      </div>
    </div>
  );
}
